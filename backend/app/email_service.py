import io
import string
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import UPLOAD_DIR
from app.models import ImagenPago, Pago

_CHL_TZ = ZoneInfo("America/Santiago")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

_PDF_COLORS = {
    "navy_dark":  "#036b89",
    "navy":       "#0487a8",
    "navy_light": "#d1eff6",
    "gold":       "#FFB236",
    "gold_light": "#fff8ed",
    "cream":      "#f0fafc",
    "charcoal":   "#2c2c2c",
    "border":     "#b0d9e4",
}

DEFAULT_ASUNTO = "Solicitud de $tipo - $concepto ($proveedor)"

DEFAULT_CUERPO = """\
<html>
<body style="font-family: Arial, sans-serif; color: #2c2c2c; max-width: 620px; margin: 0 auto;">
  <div style="background: #036b89; padding: 24px 20px; border-radius: 4px 4px 0 0;">
    <h2 style="color: white; margin: 0; font-size: 20px;">Solicitud de $tipo</h2>
    <p style="color: #FFB236; margin: 6px 0 0; font-size: 14px;">Andy Jara M. &mdash; Consultor</p>
  </div>
  <div style="border: 1px solid #b0d9e4; border-top: none; padding: 20px; border-radius: 0 0 4px 4px;">
    <p style="margin: 0 0 16px; font-size: 14px;">Estimado/a <strong>$nombre_destinatario</strong>,</p>
    <p style="margin: 0 0 16px; font-size: 14px;">Le envío adjunto la solicitud de $tipo correspondiente al siguiente gasto:</p>
    <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
      <tr style="background: #fff8ed;">
        <td style="padding: 9px 14px; font-weight: bold; color: #036b89; width: 38%;">Concepto</td>
        <td style="padding: 9px 14px;">$concepto</td>
      </tr>
      <tr>
        <td style="padding: 9px 14px; font-weight: bold; color: #036b89;">Proveedor</td>
        <td style="padding: 9px 14px;">$proveedor</td>
      </tr>
      <tr style="background: #fff8ed;">
        <td style="padding: 9px 14px; font-weight: bold; color: #036b89;">Monto</td>
        <td style="padding: 9px 14px;">$monto $moneda</td>
      </tr>
      <tr>
        <td style="padding: 9px 14px; font-weight: bold; color: #036b89;">Equivalente CLP</td>
        <td style="padding: 9px 14px;">$monto_clp</td>
      </tr>
      <tr style="background: #fff8ed;">
        <td style="padding: 9px 14px; font-weight: bold; color: #036b89;">Fecha de pago</td>
        <td style="padding: 9px 14px;">$fecha_pago</td>
      </tr>
      <tr>
        <td style="padding: 9px 14px; font-weight: bold; color: #036b89;">Comprobante</td>
        <td style="padding: 9px 14px;">$comprobante</td>
      </tr>
      <tr style="background: #fff8ed;">
        <td style="padding: 9px 14px; font-weight: bold; color: #036b89;">Notas</td>
        <td style="padding: 9px 14px;">$notas</td>
      </tr>
    </table>
    <p style="margin-top: 18px; font-size: 12px; color: #888;">
      Se adjunta el PDF con el detalle completo de la solicitud.
    </p>
  </div>
</body>
</html>
"""


def _get_pdf_fonts() -> dict:
    """Registra y retorna fuentes TrueType si están disponibles; hace fallback a fuentes PDF estándar."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        font_dir = Path("/usr/share/fonts/truetype/freefont")
        mapping = {
            "PdfHeader":       "FreeSansBold.ttf",
            "PdfHeaderItalic": "FreeSansBoldOblique.ttf",
            "PdfNormal":       "FreeSerif.ttf",
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


def generar_pdf_bytes(pago: Pago, db) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable, Image as RLImage, PageBreak, Paragraph,
        SimpleDocTemplate, Spacer, Table as RLTable, TableStyle,
    )

    fonts = _get_pdf_fonts()
    C = {k: colors.HexColor(v) for k, v in _PDF_COLORS.items()}
    C["white"] = colors.white

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

    titulo_txt = (
        "Solicitud de reembolso de gasto"
        if pago.tipo == "REEMBOLSO"
        else "Solicitud de provisión de fondos"
    )
    header_band = RLTable(
        [
            [Paragraph(titulo_txt, ParagraphStyle(
                "MainH", fontName=fonts["header"], fontSize=18,
                textColor=C["white"], alignment=TA_CENTER,
            ))],
            [Paragraph("Andy Jara M.", ParagraphStyle(
                "SubH", fontName=fonts["header_it"], fontSize=13,
                textColor=C["gold"], alignment=TA_CENTER,
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
        [Paragraph("Fecha de pago",         label_st), Paragraph(fmt_date(pago.fecha_pago),                               value_st)],
        [Paragraph("Concepto",              label_st), Paragraph(pago.concepto or "-",                                    value_st)],
        [Paragraph("Proveedor",             label_st), Paragraph(pago.proveedor or "-",                                   value_st)],
        [Paragraph("Monto",                 label_st), Paragraph(fmt_money(pago.monto, pago.moneda),                      value_st)],
        [Paragraph("Equivalente CLP",       label_st), Paragraph(f"{pago.monto_clp:,.0f} CLP" if pago.monto_clp else "-", value_st)],
        [Paragraph("Estado",                label_st), Paragraph(pago.estado or "-",                                      value_st)],
        [Paragraph("Fecha solicitud",       label_st), Paragraph(fmt_date(pago.fecha_solicitud),                          value_st)],
        [Paragraph("Fecha reembolso/pago",  label_st), Paragraph(fmt_date(pago.fecha_reembolso),                          value_st)],
        [Paragraph("Comprobante",           label_st), Paragraph(pago.comprobante or "-",                                 value_st)],
        [Paragraph("Notas",                 label_st), Paragraph(pago.notas or "-",                                       value_st)],
    ]

    table = RLTable(datos, colWidths=[5 * cm, 11 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (0, -1),  C["gold_light"]),
        ("BACKGROUND",    (1, 0),  (1, -1),  C["white"]),
        ("BACKGROUND",    (1, 1),  (1, 1),   C["cream"]),
        ("BACKGROUND",    (1, 3),  (1, 3),   C["cream"]),
        ("BACKGROUND",    (1, 7),  (1, 7),   C["cream"]),
        ("BACKGROUND",    (1, 9),  (1, 9),   C["cream"]),
        ("BACKGROUND",    (1, 5),  (1, 5),   estado_color),
        ("LINEAFTER",     (0, 0),  (0, -1),  1.5, C["gold"]),
        ("GRID",          (0, 0),  (-1, -1), 0.5, C["border"]),
        ("LINEABOVE",     (0, 0),  (-1, 0),  1.5, C["navy_dark"]),
        ("LINEBELOW",     (0, -1), (-1, -1), 1.5, C["gold"]),
        ("VALIGN",        (0, 0),  (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0),  (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 8),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 10),
    ]))
    elements.append(table)

    elements.append(Spacer(1, 18))
    elements.append(HRFlowable(width="100%", thickness=1, color=C["gold"], spaceBefore=0, spaceAfter=6))
    elements.append(Paragraph(
        f"Documento generado el {datetime.now(tz=_CHL_TZ).strftime('%d/%m/%Y a las %H:%M')} (hora Chile)",
        ParagraphStyle("Footer", fontName=fonts["italic"], fontSize=8,
                       textColor=colors.HexColor("#888888"), alignment=TA_CENTER),
    ))

    imagenes = db.query(ImagenPago).filter(ImagenPago.pago_id == pago.id).all()
    if imagenes:
        elements.append(PageBreak())
        img_band = RLTable(
            [[Paragraph("Comprobantes adjuntos", ParagraphStyle(
                "ImgH", fontName=fonts["header"], fontSize=16,
                textColor=C["white"], alignment=TA_CENTER,
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
    return buffer.read()


def _build_variables(pago: Pago, nombre_destinatario: str = "") -> dict:
    return {
        "tipo":                 pago.tipo or "",
        "concepto":             pago.concepto or "",
        "proveedor":            pago.proveedor or "",
        "monto":                f"{pago.monto:,.2f}" if pago.monto else "-",
        "moneda":               pago.moneda or "",
        "monto_clp":            f"{pago.monto_clp:,.0f} CLP" if pago.monto_clp else "-",
        "fecha_pago":           pago.fecha_pago.strftime("%d/%m/%Y") if pago.fecha_pago else "-",
        "comprobante":          pago.comprobante or "-",
        "notas":                pago.notas or "-",
        "nombre_destinatario":  nombre_destinatario or "",
    }


def renderizar_solicitud(pago: Pago, config: dict, nombre_destinatario: str = "") -> dict:
    """Renderiza el asunto y cuerpo HTML con las variables del pago. Retorna {asunto, cuerpo_html}."""
    asunto_tmpl = config.get("email_asunto_template") or DEFAULT_ASUNTO
    cuerpo_tmpl = config.get("email_cuerpo_template") or DEFAULT_CUERPO
    variables = _build_variables(pago, nombre_destinatario)
    return {
        "asunto":     string.Template(asunto_tmpl).safe_substitute(variables),
        "cuerpo_html": string.Template(cuerpo_tmpl).safe_substitute(variables),
    }


def enviar_solicitud(
    pago: Pago,
    email_destinatario: str,
    pdf_bytes: bytes,
    config: dict,
    nombre_destinatario: str | None = None,
    asunto: str | None = None,
    cuerpo_html: str | None = None,
) -> None:
    import resend

    api_key = config.get("resend_api_key") or ""
    if not api_key:
        raise ValueError("Resend API Key no configurada. Ve a Ajustes para configurarla.")

    email_from = config.get("email_from") or "Control Reembolsos <noreply@resend.dev>"
    email_copia = config.get("email_copia") or ""

    # Usar contenido pre-renderizado si el usuario lo editó; si no, renderizar desde plantilla
    if not asunto or not cuerpo_html:
        rendered = renderizar_solicitud(pago, config, nombre_destinatario or "")
        asunto = asunto or rendered["asunto"]
        cuerpo_html = cuerpo_html or rendered["cuerpo_html"]

    # Formatear el To con nombre si está disponible
    to_field = f"{nombre_destinatario} <{email_destinatario}>" if nombre_destinatario else email_destinatario

    resend.api_key = api_key

    params: resend.Emails.SendParams = {
        "from": email_from,
        "to": [to_field],
        "subject": asunto,
        "html": cuerpo_html,
        "attachments": [
            {
                "filename": f"solicitud_{pago.tipo.lower()}_{pago.id}.pdf",
                "content": list(pdf_bytes),
            }
        ],
    }
    if email_copia:
        params["cc"] = [email_copia]

    resend.Emails.send(params)
