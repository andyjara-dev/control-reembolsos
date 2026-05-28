import io
import os
import uuid
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import UPLOAD_DIR
from app.database import get_db
from app.email_service import (
    generar_pdf_bytes, enviar_solicitud, renderizar_solicitud,
    generar_pdf_reporte_bytes, enviar_reporte, renderizar_reporte,
)
from app.models import Configuracion, Pago, ImagenPago, User
from app.schemas import (
    PagoCreate, PagoUpdate, PagoResponse, ImagenPagoResponse, ResumenResponse,
    PagosListResponse, SolicitarRequest, PreviewSolicitarResponse,
    PreviewReporteRequest, PreviewReporteResponse, EnviarReporteRequest,
)

_CHL_TZ = ZoneInfo("America/Santiago")

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
VALID_TIPO_IMAGEN = {"cobro", "reembolso"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

router = APIRouter(prefix="/api/pagos", tags=["pagos"], dependencies=[Depends(get_current_user)])


@router.get("/resumen", response_model=ResumenResponse)
def get_resumen(db: Session = Depends(get_db)):
    def sum_by(tipo: str, estado: str) -> Decimal:
        result = db.query(func.coalesce(func.sum(Pago.monto_clp), 0)).filter(
            Pago.tipo == tipo, Pago.estado == estado
        ).scalar()
        return Decimal(str(result))

    hoy = datetime.now(tz=_CHL_TZ).date()
    primer_dia_mes = hoy.replace(day=1)
    total_pagado_mes = db.query(func.coalesce(func.sum(Pago.monto_clp), 0)).filter(
        Pago.estado == "PAGADO",
        Pago.fecha_reembolso >= primer_dia_mes,
    ).scalar()

    cantidad_pendientes = db.query(func.count(Pago.id)).filter(Pago.estado == "PENDIENTE").scalar()
    cantidad_no_pagados = db.query(func.count(Pago.id)).filter(Pago.estado.in_(["PENDIENTE", "SOLICITADO"])).scalar()

    return ResumenResponse(
        total_pendiente_reembolso=sum_by("REEMBOLSO", "PENDIENTE"),
        total_pendiente_provision=sum_by("PROVISION", "PENDIENTE"),
        total_solicitado_reembolso=sum_by("REEMBOLSO", "SOLICITADO"),
        total_solicitado_provision=sum_by("PROVISION", "SOLICITADO"),
        total_pagado_mes=Decimal(str(total_pagado_mes)),
        cantidad_pendientes=cantidad_pendientes,
        cantidad_no_pagados=cantidad_no_pagados,
    )


@router.get("", response_model=PagosListResponse)
def list_pagos(
    estado: str | None = Query(None),
    tipo: str | None = Query(None),
    proveedor: str | None = Query(None),
    desde: date | None = Query(None),
    hasta: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Pago)
    if estado:
        q = q.filter(Pago.estado == estado)
    if tipo:
        q = q.filter(Pago.tipo == tipo)
    if proveedor:
        q = q.filter(Pago.proveedor.ilike(f"%{proveedor}%"))
    if desde:
        q = q.filter(Pago.fecha_pago >= desde)
    if hasta:
        q = q.filter(Pago.fecha_pago <= hasta)

    total = q.with_entities(func.count(Pago.id)).scalar()
    total_monto_clp = q.with_entities(func.coalesce(func.sum(Pago.monto_clp), 0)).scalar()
    total_monto_usd = q.with_entities(
        func.coalesce(func.sum(Pago.monto), 0)
    ).filter(Pago.moneda == "USD").scalar()

    pagos = q.order_by(Pago.fecha_pago.desc()).offset(skip).limit(limit).all()
    return PagosListResponse(
        items=[PagoResponse.from_pago(p) for p in pagos],
        total=total,
        total_monto_clp=float(total_monto_clp),
        total_monto_usd=float(total_monto_usd),
    )


@router.get("/reporte")
def generar_reporte(
    estado: str | None = Query(None),
    tipo: str | None = Query(None),
    proveedor: str | None = Query(None),
    desde: date | None = Query(None),
    hasta: date | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Pago)
    if estado:
        q = q.filter(Pago.estado == estado)
    if tipo:
        q = q.filter(Pago.tipo == tipo)
    if proveedor:
        q = q.filter(Pago.proveedor.ilike(f"%{proveedor}%"))
    if desde:
        q = q.filter(Pago.fecha_pago >= desde)
    if hasta:
        q = q.filter(Pago.fecha_pago <= hasta)
    pagos = q.order_by(Pago.fecha_pago.desc()).all()
    pdf_bytes = generar_pdf_reporte_bytes(pagos)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=reporte_pagos.pdf"},
    )


@router.post("/pendientes/reporte/preview", response_model=PreviewReporteResponse)
def preview_reporte_pendientes(data: PreviewReporteRequest, db: Session = Depends(get_db)):
    pagos = (
        db.query(Pago)
        .filter(Pago.id.in_(data.pago_ids), Pago.estado == "PENDIENTE")
        .order_by(Pago.fecha_pago.desc())
        .all()
    )
    config = {c.clave: c.valor for c in db.query(Configuracion).all()}
    rendered = renderizar_reporte(pagos, config, data.nombre_destinatario or "")
    return PreviewReporteResponse(**rendered, cantidad_pendientes=len(pagos))


@router.post("/pendientes/reporte")
def enviar_reporte_pendientes(data: EnviarReporteRequest, db: Session = Depends(get_db)):
    pagos = (
        db.query(Pago)
        .filter(Pago.id.in_(data.pago_ids), Pago.estado == "PENDIENTE")
        .order_by(Pago.fecha_pago.desc())
        .all()
    )
    if not pagos:
        raise HTTPException(status_code=400, detail="No hay pagos pendientes seleccionados")
    config = {c.clave: c.valor for c in db.query(Configuracion).all()}
    try:
        pdf_bytes = generar_pdf_reporte_bytes(pagos, config)
        enviar_reporte(
            pagos,
            data.email_destinatario,
            pdf_bytes,
            config,
            nombre_destinatario=data.nombre_destinatario,
            asunto=data.asunto,
            cuerpo_html=data.cuerpo_html,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al enviar reporte: {exc}")
    return {"ok": True, "cantidad": len(pagos)}


@router.get("/{pago_id}/pdf")
def generar_pdf_individual(pago_id: int, db: Session = Depends(get_db)):
    pago = db.query(Pago).filter(Pago.id == pago_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    config = {c.clave: c.valor for c in db.query(Configuracion).all()}
    pdf_bytes = generar_pdf_bytes(pago, db, config)
    filename = f"solicitud_{pago.tipo.lower()}_{pago_id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{pago_id}/solicitar/preview", response_model=PreviewSolicitarResponse)
def preview_solicitar(pago_id: int, nombre: str = Query(""), db: Session = Depends(get_db)):
    pago = db.query(Pago).filter(Pago.id == pago_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    config = {c.clave: c.valor for c in db.query(Configuracion).all()}
    return renderizar_solicitud(pago, config, nombre)


@router.post("/{pago_id}/solicitar")
def solicitar_pago(pago_id: int, data: SolicitarRequest, db: Session = Depends(get_db)):
    pago = db.query(Pago).filter(Pago.id == pago_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    if pago.estado != "PENDIENTE":
        raise HTTPException(status_code=400, detail="Solo se pueden solicitar pagos en estado PENDIENTE")

    config = {c.clave: c.valor for c in db.query(Configuracion).all()}

    try:
        pdf_bytes = generar_pdf_bytes(pago, db, config)
        enviar_solicitud(
            pago,
            data.email_destinatario,
            pdf_bytes,
            config,
            nombre_destinatario=data.nombre_destinatario,
            asunto=data.asunto,
            cuerpo_html=data.cuerpo_html,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al enviar email: {exc}")

    pago.estado = "SOLICITADO"
    pago.fecha_solicitud = datetime.now(tz=_CHL_TZ).date()
    pago.email_destinatario = data.email_destinatario
    pago.nombre_destinatario = data.nombre_destinatario
    pago.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(pago)
    return PagoResponse.from_pago(pago)


@router.post("", status_code=201)
def create_pago(data: PagoCreate, db: Session = Depends(get_db)):
    pago = Pago(**data.model_dump())
    db.add(pago)
    db.commit()
    db.refresh(pago)
    return PagoResponse.from_pago(pago)


@router.put("/{pago_id}")
def update_pago(pago_id: int, data: PagoUpdate, db: Session = Depends(get_db)):
    pago = db.query(Pago).filter(Pago.id == pago_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(pago, key, value)
    pago.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(pago)
    return PagoResponse.from_pago(pago)


@router.delete("/{pago_id}", status_code=204)
def delete_pago(pago_id: int, db: Session = Depends(get_db)):
    pago = db.query(Pago).filter(Pago.id == pago_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    # Borrar archivo comprobante
    if pago.archivo_comprobante:
        filepath = Path(UPLOAD_DIR) / pago.archivo_comprobante
        if filepath.exists():
            filepath.unlink()
    # Borrar archivos de imágenes (tabla imagenes_pago, cascade eliminará registros)
    for img in pago.imagenes:
        filepath = Path(UPLOAD_DIR) / img.filename
        if filepath.exists():
            filepath.unlink()
    db.delete(pago)
    db.commit()


@router.post("/{pago_id}/archivo")
def upload_archivo(pago_id: int, archivo: UploadFile = File(...), db: Session = Depends(get_db)):
    pago = db.query(Pago).filter(Pago.id == pago_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    ext = Path(archivo.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Extensión no permitida. Permitidas: {', '.join(ALLOWED_EXTENSIONS)}")

    content = archivo.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Archivo excede 10 MB")

    upload_dir = Path(UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Eliminar archivo anterior si existe
    if pago.archivo_comprobante:
        old_path = upload_dir / pago.archivo_comprobante
        if old_path.exists():
            old_path.unlink()

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = upload_dir / filename
    filepath.write_bytes(content)

    pago.archivo_comprobante = filename
    pago.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(pago)
    return {"archivo_comprobante": filename}


@router.get("/{pago_id}/archivo")
def download_archivo(pago_id: int, db: Session = Depends(get_db)):
    pago = db.query(Pago).filter(Pago.id == pago_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    if not pago.archivo_comprobante:
        raise HTTPException(status_code=404, detail="No hay archivo adjunto")

    filepath = Path(UPLOAD_DIR) / pago.archivo_comprobante
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")

    return FileResponse(str(filepath), filename=pago.archivo_comprobante)


@router.post("/{pago_id}/imagen/{tipo_imagen}", response_model=ImagenPagoResponse, status_code=201)
def upload_imagen(pago_id: int, tipo_imagen: str, archivo: UploadFile = File(...), db: Session = Depends(get_db)):
    if tipo_imagen not in VALID_TIPO_IMAGEN:
        raise HTTPException(status_code=400, detail="tipo_imagen debe ser 'cobro' o 'reembolso'")
    pago = db.query(Pago).filter(Pago.id == pago_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    ext = Path(archivo.filename).suffix.lower()
    if ext not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Solo imágenes permitidas: {', '.join(IMAGE_EXTENSIONS)}")

    content = archivo.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Archivo excede 10 MB")

    upload_dir = Path(UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    (upload_dir / filename).write_bytes(content)

    imagen = ImagenPago(pago_id=pago_id, tipo_imagen=tipo_imagen, filename=filename)
    db.add(imagen)
    pago.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(imagen)
    return imagen


@router.get("/{pago_id}/imagenes/{tipo_imagen}", response_model=list[ImagenPagoResponse])
def list_imagenes(pago_id: int, tipo_imagen: str, db: Session = Depends(get_db)):
    if tipo_imagen not in VALID_TIPO_IMAGEN:
        raise HTTPException(status_code=400, detail="tipo_imagen debe ser 'cobro' o 'reembolso'")
    pago = db.query(Pago).filter(Pago.id == pago_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    return db.query(ImagenPago).filter(
        ImagenPago.pago_id == pago_id, ImagenPago.tipo_imagen == tipo_imagen
    ).all()


@router.get("/{pago_id}/imagen/{imagen_id}/file")
def download_imagen_by_id(pago_id: int, imagen_id: int, db: Session = Depends(get_db)):
    imagen = db.query(ImagenPago).filter(
        ImagenPago.id == imagen_id, ImagenPago.pago_id == pago_id
    ).first()
    if not imagen:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    filepath = Path(UPLOAD_DIR) / imagen.filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Imagen no encontrada en disco")

    return FileResponse(str(filepath), filename=imagen.filename)


@router.get("/{pago_id}/imagen/{tipo_imagen}")
def download_imagen_legacy(pago_id: int, tipo_imagen: str, db: Session = Depends(get_db)):
    """Compatibilidad: retorna la primera imagen del tipo dado."""
    if tipo_imagen not in VALID_TIPO_IMAGEN:
        raise HTTPException(status_code=400, detail="tipo_imagen debe ser 'cobro' o 'reembolso'")
    imagen = db.query(ImagenPago).filter(
        ImagenPago.pago_id == pago_id, ImagenPago.tipo_imagen == tipo_imagen
    ).first()
    if not imagen:
        raise HTTPException(status_code=404, detail="No hay imagen adjunta")

    filepath = Path(UPLOAD_DIR) / imagen.filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Imagen no encontrada en disco")

    return FileResponse(str(filepath), filename=imagen.filename)


@router.delete("/{pago_id}/imagen/{imagen_id}", status_code=204)
def delete_imagen(pago_id: int, imagen_id: int, db: Session = Depends(get_db)):
    imagen = db.query(ImagenPago).filter(
        ImagenPago.id == imagen_id, ImagenPago.pago_id == pago_id
    ).first()
    if not imagen:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    filepath = Path(UPLOAD_DIR) / imagen.filename
    if filepath.exists():
        filepath.unlink()
    db.delete(imagen)
    db.commit()
