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
from app.models import Pago, ImagenPago, User
from app.schemas import PagoCreate, PagoUpdate, PagoResponse, ImagenPagoResponse, ResumenResponse

_CHL_TZ = ZoneInfo("America/Santiago")

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
VALID_TIPO_IMAGEN = {"cobro", "reembolso"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# ── Paleta de colores para PDFs (desarrollador.cl) ───────────────────────────
_PDF_COLORS = {
    "navy_dark":  "#036b89",  # teal oscuro (cabecera)
    "navy":       "#0487a8",  # teal primario
    "navy_light": "#d1eff6",  # teal claro (relleno alternado)
    "gold":       "#FFB236",  # naranja acento
    "gold_light": "#fff8ed",  # naranja muy claro (fondo etiquetas)
    "cream":      "#f0fafc",  # teal crema (filas alternas)
    "charcoal":   "#2c2c2c",  # texto oscuro
    "border":     "#b0d9e4",  # borde teal suave
}


def _get_pdf_fonts() -> dict:
    """Registra y retorna fuentes TrueType si están disponibles; hace fallback a fuentes PDF estándar."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        font_dir = Path("/usr/share/fonts/truetype/freefont")
        mapping = {
            "PdfHeader":       "FreeSansBold.ttf",          # cabecera: sans-serif bold
            "PdfHeaderItalic": "FreeSansBoldOblique.ttf",
            "PdfNormal":       "FreeSerif.ttf",             # cuerpo: serif elegante
            "PdfBold":         "FreeSerifBold.ttf",
            "PdfItalic":       "FreeSerifItalic.ttf",
            "PdfBoldItalic":   "FreeSerifBoldItalic.ttf",
        }
        for name, fname in mapping.items():
            fp = font_dir / fname
            if not fp.exists():
                raise FileNotFoundError(fp)
            try:
                pdfmetrics.getFont(name)
            except KeyError:
                pdfmetrics.registerFont(TTFont(name, str(fp)))
        return {
            "header":      "PdfHeader",
            "header_it":   "PdfHeaderItalic",
            "normal":      "PdfNormal",
            "bold":        "PdfBold",
            "italic":      "PdfItalic",
            "bold_italic": "PdfBoldItalic",
        }
    except Exception:
        return {
            "header":      "Helvetica-Bold",
            "header_it":   "Helvetica-BoldOblique",
            "normal":      "Times-Roman",
            "bold":        "Times-Bold",
            "italic":      "Times-Italic",
            "bold_italic": "Times-BoldItalic",
        }

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
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable, Paragraph, SimpleDocTemplate, Spacer,
        Table as RLTable, TableStyle,
    )

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

    fonts = _get_pdf_fonts()
    C = {k: colors.HexColor(v) for k, v in _PDF_COLORS.items()}
    C["white"] = colors.white

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    elements = []

    # ── Banda de cabecera ────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "RTitle",
        fontName=fonts["header"],
        fontSize=22,
        textColor=C["white"],
        alignment=TA_CENTER,
        spaceAfter=0,
        spaceBefore=0,
    )
    date_style = ParagraphStyle(
        "RDate",
        fontName=fonts["italic"],
        fontSize=9,
        textColor=C["gold"],
        alignment=TA_CENTER,
    )
    header_band = RLTable(
        [
            [Paragraph("Reporte de Pagos", title_style)],
            [Paragraph(f"Generado: {datetime.now(tz=_CHL_TZ).strftime('%d/%m/%Y %H:%M')}", date_style)],
        ],
        colWidths=[doc.width],
    )
    header_band.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C["navy_dark"]),
        ("TOPPADDING",    (0, 0), (-1, 0),  16),
        ("BOTTOMPADDING", (0, 0), (-1, 0),  4),
        ("TOPPADDING",    (0, 1), (-1, 1),  2),
        ("BOTTOMPADDING", (0, 1), (-1, 1),  14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_band)
    elements.append(HRFlowable(width="100%", thickness=3, color=C["gold"], spaceBefore=0, spaceAfter=10))

    # ── Tabla de datos ───────────────────────────────────────────────────────
    header_row = ["Fecha", "Concepto", "Proveedor", "Monto", "Moneda", "Monto CLP", "Tipo", "Estado"]
    data = [header_row]
    total_monto = Decimal("0")
    total_clp = Decimal("0")
    for p in pagos:
        data.append([
            p.fecha_pago.strftime("%d/%m/%Y") if p.fecha_pago else "-",
            (p.concepto or "-")[:42],
            (p.proveedor or "-")[:30],
            f"{p.monto:,.2f}" if p.monto else "-",
            p.moneda or "-",
            f"{p.monto_clp:,.0f}" if p.monto_clp else "-",
            p.tipo or "-",
            p.estado or "-",
        ])
        total_monto += p.monto or Decimal("0")
        total_clp += p.monto_clp or Decimal("0")
    data.append(["", "", "TOTALES", f"{total_monto:,.2f}", "", f"{total_clp:,.0f}" if total_clp else "-", "", ""])

    w = doc.width
    col_widths = [w * 0.08, w * 0.22, w * 0.18, w * 0.11, w * 0.07, w * 0.13, w * 0.11, w * 0.10]

    n = len(data)
    alternating = [("BACKGROUND", (0, i), (-1, i), C["cream"] if i % 2 == 0 else C["white"])
                   for i in range(1, n - 1)]

    table = RLTable(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        # Encabezado
        ("BACKGROUND",    (0, 0),  (-1, 0),  C["navy"]),
        ("TEXTCOLOR",     (0, 0),  (-1, 0),  C["white"]),
        ("FONTNAME",      (0, 0),  (-1, 0),  fonts["header"]),
        ("FONTSIZE",      (0, 0),  (-1, 0),  9),
        ("ALIGN",         (0, 0),  (-1, 0),  "CENTER"),
        ("TOPPADDING",    (0, 0),  (-1, 0),  8),
        ("BOTTOMPADDING", (0, 0),  (-1, 0),  8),
        # Cuerpo
        ("FONTNAME",      (0, 1),  (-1, -2), fonts["normal"]),
        ("FONTSIZE",      (0, 1),  (-1, -2), 8),
        ("TEXTCOLOR",     (0, 1),  (-1, -2), C["charcoal"]),
        ("TOPPADDING",    (0, 1),  (-1, -2), 5),
        ("BOTTOMPADDING", (0, 1),  (-1, -2), 5),
        # Fila de totales
        ("BACKGROUND",    (0, -1), (-1, -1), C["gold_light"]),
        ("FONTNAME",      (0, -1), (-1, -1), fonts["bold"]),
        ("FONTSIZE",      (0, -1), (-1, -1), 9),
        ("TEXTCOLOR",     (0, -1), (-1, -1), C["navy_dark"]),
        ("TOPPADDING",    (0, -1), (-1, -1), 7),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
        # Alineación de montos
        ("ALIGN",         (3, 1),  (3, -1),  "RIGHT"),
        ("ALIGN",         (5, 1),  (5, -1),  "RIGHT"),
        # Bordes
        ("GRID",          (0, 0),  (-1, -1), 0.5, C["border"]),
        ("LINEBELOW",     (0, 0),  (-1, 0),  1.5, C["gold"]),
        ("LINEABOVE",     (0, -1), (-1, -1), 1.0, C["gold"]),
        # Paddings laterales
        ("LEFTPADDING",   (0, 0),  (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 6),
        *alternating,
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
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable, Image as RLImage, PageBreak, Paragraph,
        SimpleDocTemplate, Spacer, Table as RLTable, TableStyle,
    )

    pago = db.query(Pago).filter(Pago.id == pago_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    fonts = _get_pdf_fonts()
    C = {k: colors.HexColor(v) for k, v in _PDF_COLORS.items()}
    C["white"] = colors.white

    # ── Clase con marca de agua ──────────────────────────────────────────────
    class _DocWatermark(SimpleDocTemplate):
        _wm_text: str | None = None
        _wm_font: str = "Helvetica-Bold"

        def afterPage(self):
            if self._wm_text:
                c = self.canv
                c.saveState()
                c.setFont(self._wm_font, 90)
                c.setFillColor(colors.Color(0.15, 0.60, 0.25, alpha=0.22))
                pw, ph = self.pagesize
                c.translate(pw / 2, ph / 2)
                c.rotate(45)
                c.drawCentredString(0, 0, self._wm_text)
                c.restoreState()

    buffer = io.BytesIO()
    doc = _DocWatermark(
        buffer, pagesize=letter,
        topMargin=1.5 * cm, bottomMargin=2 * cm,
        leftMargin=2.5 * cm, rightMargin=2.5 * cm,
    )
    if pago.estado == "PAGADO":
        doc._wm_text = "PAGADO"
        doc._wm_font = fonts.get("header", "Helvetica-Bold")

    elements = []

    # ── Banda de cabecera principal ─────────────────────────────────────────
    titulo_txt = (
        "Solicitud de reembolso de gasto"
        if pago.tipo == "REEMBOLSO"
        else "Solicitud de provisión de fondos"
    )
    header_band = RLTable(
        [
            [Paragraph(titulo_txt, ParagraphStyle(
                "MainH",
                fontName=fonts["header"],
                fontSize=18,
                textColor=C["white"],
                alignment=TA_CENTER,
            ))],
            [Paragraph("Andy Jara M.", ParagraphStyle(
                "SubH",
                fontName=fonts["header_it"],
                fontSize=13,
                textColor=C["gold"],
                alignment=TA_CENTER,
            ))],
        ],
        colWidths=[doc.width],
    )
    header_band.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C["navy_dark"]),
        ("TOPPADDING",    (0, 0), (-1, 0),  18),
        ("BOTTOMPADDING", (0, 0), (-1, 0),  4),
        ("TOPPADDING",    (0, 1), (-1, 1),  2),
        ("BOTTOMPADDING", (0, 1), (-1, 1),  14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
    ]))
    elements.append(header_band)
    elements.append(HRFlowable(width="100%", thickness=3, color=C["gold"], spaceBefore=0, spaceAfter=10))

    # ── Tabla de datos ───────────────────────────────────────────────────────
    def fmt_date(d):
        return d.strftime("%d/%m/%Y") if d else "-"

    def fmt_money(val, moneda=""):
        if val is None:
            return "-"
        formatted = f"{val:,.2f}"
        return f"{formatted} {moneda}".strip() if moneda else formatted

    label_st = ParagraphStyle("Lbl", fontName=fonts["bold"],   fontSize=10, textColor=C["navy_dark"], leading=14)
    value_st = ParagraphStyle("Val", fontName=fonts["normal"], fontSize=10, textColor=C["charcoal"],  leading=14)

    estado_color = {
        "PENDIENTE":  colors.HexColor("#fff3e0"),
        "SOLICITADO": C["navy_light"],
        "PAGADO":     colors.HexColor("#d1eff6"),
    }.get(pago.estado or "", C["white"])

    datos = [
        [Paragraph("Fecha de pago",         label_st), Paragraph(fmt_date(pago.fecha_pago),                           value_st)],
        [Paragraph("Concepto",              label_st), Paragraph(pago.concepto or "-",                                value_st)],
        [Paragraph("Proveedor",             label_st), Paragraph(pago.proveedor or "-",                               value_st)],
        [Paragraph("Monto",                 label_st), Paragraph(fmt_money(pago.monto, pago.moneda),                  value_st)],
        [Paragraph("Equivalente CLP",       label_st), Paragraph(f"{pago.monto_clp:,.0f} CLP" if pago.monto_clp else "-", value_st)],
        [Paragraph("Estado",                label_st), Paragraph(pago.estado or "-",                                  value_st)],
        [Paragraph("Fecha solicitud",       label_st), Paragraph(fmt_date(pago.fecha_solicitud),                      value_st)],
        [Paragraph("Fecha reembolso/pago",  label_st), Paragraph(fmt_date(pago.fecha_reembolso),                      value_st)],
        [Paragraph("Comprobante",           label_st), Paragraph(pago.comprobante or "-",                             value_st)],
        [Paragraph("Notas",                 label_st), Paragraph(pago.notas or "-",                                   value_st)],
    ]

    table = RLTable(datos, colWidths=[5 * cm, 11 * cm])
    table.setStyle(TableStyle([
        # Columna de etiquetas
        ("BACKGROUND",    (0, 0),  (0, -1),  C["gold_light"]),
        # Columna de valores (alternando)
        ("BACKGROUND",    (1, 0),  (1, -1),  C["white"]),
        ("BACKGROUND",    (1, 1),  (1, 1),   C["cream"]),
        ("BACKGROUND",    (1, 3),  (1, 3),   C["cream"]),
        ("BACKGROUND",    (1, 7),  (1, 7),   C["cream"]),
        ("BACKGROUND",    (1, 9),  (1, 9),   C["cream"]),
        # Fila de estado con color dinámico
        ("BACKGROUND",    (1, 5),  (1, 5),   estado_color),
        # Separador vertical dorado entre etiqueta y valor
        ("LINEAFTER",     (0, 0),  (0, -1),  1.5, C["gold"]),
        # Bordes
        ("GRID",          (0, 0),  (-1, -1), 0.5, C["border"]),
        ("LINEABOVE",     (0, 0),  (-1, 0),  1.5, C["navy_dark"]),
        ("LINEBELOW",     (0, -1), (-1, -1), 1.5, C["gold"]),
        # Tipografía y layout
        ("VALIGN",        (0, 0),  (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0),  (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 8),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 10),
    ]))
    elements.append(table)

    # ── Pie de página ────────────────────────────────────────────────────────
    elements.append(Spacer(1, 18))
    elements.append(HRFlowable(width="100%", thickness=1, color=C["gold"], spaceBefore=0, spaceAfter=6))
    elements.append(Paragraph(
        f"Documento generado el {datetime.now(tz=_CHL_TZ).strftime('%d/%m/%Y a las %H:%M')} (hora Chile)",
        ParagraphStyle("Footer", fontName=fonts["italic"], fontSize=8,
                       textColor=colors.HexColor("#888888"), alignment=TA_CENTER),
    ))

    # ── Página 2: comprobantes adjuntos ──────────────────────────────────────
    imagenes = db.query(ImagenPago).filter(ImagenPago.pago_id == pago_id).all()
    if imagenes:
        elements.append(PageBreak())
        img_band = RLTable(
            [[Paragraph("Comprobantes adjuntos", ParagraphStyle(
                "ImgH",
                fontName=fonts["header"],
                fontSize=16,
                textColor=C["white"],
                alignment=TA_CENTER,
            ))]],
            colWidths=[doc.width],
        )
        img_band.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C["navy_dark"]),
            ("TOPPADDING",    (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ]))
        elements.append(img_band)
        elements.append(HRFlowable(width="100%", thickness=3, color=C["gold"], spaceBefore=0, spaceAfter=16))

        max_width = 15 * cm
        max_height = 10 * cm
        img_label_st = ParagraphStyle("ImgLbl", fontName=fonts["bold"], fontSize=10, textColor=C["navy"])

        for img_record in imagenes:
            filepath = Path(UPLOAD_DIR) / img_record.filename
            if not filepath.exists():
                continue
            if filepath.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            try:
                label = "Cobro" if img_record.tipo_imagen == "cobro" else "Reembolso"
                elements.append(Paragraph(label, img_label_st))
                elements.append(Spacer(1, 4))
                rl_img = RLImage(str(filepath))
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
