from datetime import date, datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def texto(valor):
    if valor is None or valor == "":
        return "-"
    return str(valor)


def fecha_simple(valor):
    if not valor:
        return "-"
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")

    valor = str(valor)
    for formato in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(valor, formato).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return valor[:10]


def parrafo(texto_valor, estilo):
    return Paragraph(texto(texto_valor).replace("\n", "<br/>"), estilo)


def linea():
    tabla = Table([[""]], colWidths=[17 * cm])
    tabla.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 0.75, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return tabla


def generar_pdf_orden(orden, demanda, materiales):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
    )

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontName = "Helvetica"
    normal.fontSize = 10
    normal.leading = 13

    encabezado = ParagraphStyle(
        "Encabezado",
        parent=normal,
        alignment=TA_CENTER,
        fontSize=11,
        leading=15,
    )
    titulo = ParagraphStyle(
        "Titulo",
        parent=normal,
        alignment=TA_CENTER,
        fontSize=14,
        leading=18,
        spaceAfter=8,
        fontName="Helvetica-Bold",
    )
    seccion = ParagraphStyle(
        "Seccion",
        parent=normal,
        fontSize=10,
        leading=13,
        fontName="Helvetica-Bold",
    )

    elementos = [
        Paragraph("Municipalidad de Tafí Viejo<br/>Subsecretaría de Vivienda y Hábitat", encabezado),
        Spacer(1, 0.25 * cm),
        Paragraph("ORDEN DE ENTREGA / RETIRO DE MATERIALES", titulo),
        linea(),
        Spacer(1, 0.35 * cm),
    ]

    datos_orden = Table(
        [
            [
                parrafo(f"<b>N° Orden:</b> {texto(orden.get('n_orden'))}", normal),
                parrafo(f"<b>Fecha:</b> {fecha_simple(orden.get('fecha_emision'))}", normal),
            ]
        ],
        colWidths=[8.5 * cm, 8.5 * cm],
    )
    elementos.extend([datos_orden, Spacer(1, 0.35 * cm)])

    beneficiario = f"{texto(demanda.get('apellido'))}, {texto(demanda.get('nombre'))}"
    direccion = f"{texto(demanda.get('domicilio'))} - {texto(demanda.get('barrio'))}"
    datos_expte = [
        [parrafo(f"<b>Expediente:</b> {texto(demanda.get('expediente'))}", normal)],
        [parrafo(f"<b>Beneficiario:</b> {beneficiario}", normal)],
        [parrafo(f"<b>Dirección:</b> {direccion}", normal)],
    ]
    elementos.extend([Table(datos_expte, colWidths=[17 * cm]), Spacer(1, 0.25 * cm), linea()])

    elementos.extend(
        [
            Spacer(1, 0.3 * cm),
            Paragraph("INSTRUCCIÓN / TAREA", seccion),
            Spacer(1, 0.15 * cm),
            parrafo(orden.get("instrucciones_tarea"), normal),
            Spacer(1, 0.35 * cm),
            linea(),
            Spacer(1, 0.3 * cm),
            Paragraph("MATERIALES ASOCIADOS", seccion),
            Spacer(1, 0.15 * cm),
        ]
    )

    if materiales:
        filas = [[Paragraph("<b>Material</b>", normal), Paragraph("<b>Cantidad</b>", normal)]]
        for material in materiales:
            filas.append(
                [
                    parrafo(material.get("Material"), normal),
                    parrafo(material.get("cantidad"), normal),
                ]
            )
        tabla_materiales = Table(filas, colWidths=[11 * cm, 6 * cm], repeatRows=1)
        tabla_materiales.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elementos.append(tabla_materiales)
    else:
        elementos.append(Paragraph("No se registran materiales asociados a esta orden.", normal))

    observaciones = Table(
        [
            [Paragraph("<b>Observaciones:</b>", normal)],
            [Paragraph("&nbsp;", normal)],
            [Paragraph("&nbsp;", normal)],
        ],
        colWidths=[17 * cm],
        rowHeights=[0.65 * cm, 0.75 * cm, 0.75 * cm],
    )
    observaciones.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, colors.grey),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    elementos.extend(
        [
            Spacer(1, 0.35 * cm),
            observaciones,
            Spacer(1, 0.35 * cm),
            linea(),
            Spacer(1, 0.3 * cm),
            Paragraph("Autorizado / solicitado por:", seccion),
            Spacer(1, 0.1 * cm),
            Paragraph(texto(orden.get("origen")), normal),
            Spacer(1, 1.9 * cm),
        ]
    )

    firmas = Table(
        [
            ["_____________________________", "_____________________________"],
            ["Equipo de depósito", "Beneficiario"],
        ],
        colWidths=[8.5 * cm, 8.5 * cm],
    )
    firmas.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elementos.append(firmas)

    doc.build(elementos)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
