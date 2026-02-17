import io
import os
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import UPLOAD_DIR
from app.database import get_db
from app.models import Pago, ImagenPago, User
from app.schemas import PagoCreate, PagoUpdate, PagoResponse, ImagenPagoResponse, ResumenResponse

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
VALID_TIPO_IMAGEN = {"cobro", "reembolso"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

router = APIRouter(prefix="/api/pagos", tags=["pagos"], dependencies=[Depends(get_current_user)])


@router.get("/resumen", response_model=ResumenResponse)
def get_resumen(db: Session = Depends(get_db)):
    def sum_by(tipo: str, estado: str) -> Decimal:
        result = db.query(func.coalesce(func.sum(Pago.monto), 0)).filter(
            Pago.tipo == tipo, Pago.estado == estado
        ).scalar()
        return Decimal(str(result))

    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1)
    total_pagado_mes = db.query(func.coalesce(func.sum(Pago.monto), 0)).filter(
        Pago.estado == "PAGADO",
        Pago.fecha_reembolso >= primer_dia_mes,
    ).scalar()

    cantidad_pendientes = db.query(func.count(Pago.id)).filter(Pago.estado == "PENDIENTE").scalar()

    return ResumenResponse(
        total_pendiente_reembolso=sum_by("REEMBOLSO", "PENDIENTE"),
        total_pendiente_provision=sum_by("PROVISION", "PENDIENTE"),
        total_solicitado_reembolso=sum_by("REEMBOLSO", "SOLICITADO"),
        total_solicitado_provision=sum_by("PROVISION", "SOLICITADO"),
        total_pagado_mes=Decimal(str(total_pagado_mes)),
        cantidad_pendientes=cantidad_pendientes,
    )


@router.get("")
def list_pagos(
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
    return [PagoResponse.from_pago(p) for p in pagos]


@router.get("/reporte")
def generar_reporte(
    estado: str | None = Query(None),
    tipo: str | None = Query(None),
    proveedor: str | None = Query(None),
    desde: date | None = Query(None),
    hasta: date | None = Query(None),
    db: Session = Depends(get_db),
):
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table as RLTable, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm

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

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), topMargin=1 * cm, bottomMargin=1 * cm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Reporte de Pagos", styles["Title"]))
    elements.append(Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    header = ["Fecha", "Concepto", "Proveedor", "Monto", "Moneda", "Monto CLP", "Tipo", "Estado"]
    data = [header]
    total_monto = Decimal("0")
    total_clp = Decimal("0")
    for p in pagos:
        data.append([
            str(p.fecha_pago),
            p.concepto[:40],
            p.proveedor[:30],
            f"{p.monto:,.2f}",
            p.moneda,
            f"{p.monto_clp:,.0f}" if p.monto_clp else "-",
            p.tipo,
            p.estado,
        ])
        total_monto += p.monto or Decimal("0")
        total_clp += p.monto_clp or Decimal("0")

    data.append(["", "", "TOTALES", f"{total_monto:,.2f}", "", f"{total_clp:,.0f}" if total_clp else "-", "", ""])

    table = RLTable(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1976d2")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.whitesmoke, colors.white]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e3f2fd")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("ALIGN", (5, 0), (5, -1), "RIGHT"),
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=reporte_pagos.pdf"},
    )


@router.get("/{pago_id}/pdf")
def generar_pdf_individual(pago_id: int, db: Session = Depends(get_db)):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table as RLTable, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak,
    )

    pago = db.query(Pago).filter(Pago.id == pago_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=2 * cm, bottomMargin=2 * cm,
                            leftMargin=2.5 * cm, rightMargin=2.5 * cm)
    styles = getSampleStyleSheet()
    elements = []

    # Estilos personalizados
    header_style = ParagraphStyle("Header", parent=styles["Title"], fontSize=16,
                                  textColor=colors.HexColor("#1a237e"), spaceAfter=4)
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Heading2"], fontSize=13,
                                    textColor=colors.HexColor("#333333"), spaceAfter=20)

    # Cabecera
    elements.append(Paragraph("Del escritorio de Andy Jara M.", header_style))
    if pago.tipo == "REEMBOLSO":
        subtitulo = "Solicitud de reembolso de gasto"
    else:
        subtitulo = "Solicitud de provisión de fondos"
    elements.append(Paragraph(subtitulo, subtitle_style))
    elements.append(Spacer(1, 12))

    # Tabla de datos
    def fmt_date(d):
        return d.strftime("%d/%m/%Y") if d else "-"

    def fmt_money(val, moneda=""):
        if val is None:
            return "-"
        formatted = f"{val:,.2f}"
        return f"{formatted} {moneda}".strip() if moneda else formatted

    datos = [
        ["Fecha de pago", fmt_date(pago.fecha_pago)],
        ["Concepto", pago.concepto or "-"],
        ["Proveedor", pago.proveedor or "-"],
        ["Monto", fmt_money(pago.monto, pago.moneda)],
        ["Equivalente CLP", f"{pago.monto_clp:,.0f} CLP" if pago.monto_clp else "-"],
        ["Estado", pago.estado],
        ["Fecha solicitud", fmt_date(pago.fecha_solicitud)],
        ["Fecha reembolso/pago", fmt_date(pago.fecha_reembolso)],
        ["Comprobante", pago.comprobante or "-"],
        ["Notas", pago.notas or "-"],
    ]

    table = RLTable(datos, colWidths=[5.5 * cm, 10 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8eaf6")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)

    # Página 2: comprobantes adjuntos (imágenes)
    imagenes = db.query(ImagenPago).filter(ImagenPago.pago_id == pago_id).all()
    if imagenes:
        elements.append(PageBreak())
        elements.append(Paragraph("Comprobantes adjuntos", styles["Heading2"]))
        elements.append(Spacer(1, 12))

        max_width = 15 * cm
        max_height = 10 * cm

        for img_record in imagenes:
            filepath = Path(UPLOAD_DIR) / img_record.filename
            if not filepath.exists():
                continue
            ext = filepath.suffix.lower()
            if ext not in IMAGE_EXTENSIONS:
                continue
            try:
                label = "Cobro" if img_record.tipo_imagen == "cobro" else "Reembolso"
                elements.append(Paragraph(f"<b>{label}</b>", styles["Normal"]))
                elements.append(Spacer(1, 4))
                rl_img = RLImage(str(filepath))
                # Escalar manteniendo proporción
                iw, ih = rl_img.imageWidth, rl_img.imageHeight
                if iw > 0 and ih > 0:
                    ratio = min(max_width / iw, max_height / ih, 1.0)
                    rl_img.drawWidth = iw * ratio
                    rl_img.drawHeight = ih * ratio
                elements.append(rl_img)
                elements.append(Spacer(1, 16))
            except Exception:
                continue

    doc.build(elements)
    buffer.seek(0)

    filename = f"solicitud_{pago.tipo.lower()}_{pago_id}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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
