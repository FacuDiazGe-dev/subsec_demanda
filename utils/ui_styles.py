import streamlit as st


def aplicar_estilos_globales():
    st.markdown(
        """
        <style>
        :root {
            --primary: #006B68;
            --primary-dark: #004F4C;
            --primary-soft: #E4F4F2;

            --accent-blue: #12AEEA;
            --accent-coral: #EF4E3F;
            --accent-yellow: #FFD51E;

            --app-bg: #F3F7F6;
            --card-bg: #FFFFFF;
            --card-soft: #F8FAFA;
            --border: #D9E6E4;

            --text-main: #1F2D2F;
            --text-muted: #667879;
            --text-disabled: #A0ADAD;

            --danger: #B42318;
            --success: #067647;
            --warning: #9A6700;
        }

        .stApp {
            background-image: linear-gradient(rgba(243, 247, 246, 0.95 ), rgba(243, 247, 246, 0.80)), url("https://iwrjlwjyokkjzgnyzclj.supabase.co/storage/v1/object/public/SIGAH/ChatGPT%20Image%201%20jun%202026,%2011_37_20%20p.m..png");
            background-attachment: fixed;
            background-size: cover;
            color: var(--text-main);
        }

        .block-container {
            padding-top: 1.8rem;
            padding-bottom: 3rem;
            max-width: 1400px;
        }

        h1, h2, h3 {
            color: var(--text-main);
            letter-spacing: -0.02em;
        }

        .page-hero {
            background: linear-gradient(
                135deg,
                #FFFFFF 0%,
                #F3F7F6 55%,
                #E4F4F2 100%
            );
            border: 1px solid var(--border);
            border-radius: 22px;
            padding: 24px 28px;
            margin-bottom: 18px;
            box-shadow: 0 10px 28px rgba(0, 79, 76, 0.06);
        }

        .page-eyebrow {
            color: var(--primary);
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 4px;
        }

        .page-title {
            font-size: 34px;
            font-weight: 800;
            color: var(--primary-dark);
            margin: 0;
            line-height: 1.1;
        }

        .page-subtitle {
            color: var(--text-muted);
            font-size: 15px;
            margin-top: 8px;
            max-width: 760px;
        }

        .section-title {
            color: var(--primary-dark);
            font-size: 20px;
            font-weight: 750;
            margin-bottom: 4px;
        }

        .section-caption {
            color: var(--text-muted);
            font-size: 13px;
            margin-bottom: 14px;
        }

        .soft-divider {
            height: 1px;
            background: var(--border);
            margin: 12px 0 18px 0;
        }

        .info-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 18px 20px;
            margin-bottom: 16px;
            box-shadow: 0 8px 22px rgba(0, 79, 76, 0.05);
        }

        .detail-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 18px 20px;
            margin-top: 16px;
            box-shadow: 0 8px 22px rgba(0, 79, 76, 0.05);
        }

        .mini-label {
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 2px;
        }

        .mini-value {
            color: var(--text-main);
            font-size: 14px;
            font-weight: 650;
            margin-bottom: 10px;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 5px 10px;
            font-size: 12px;
            font-weight: 700;
            line-height: 1;
            white-space: nowrap;
        }

        .badge-primary {
            background: var(--primary-soft);
            color: var(--primary-dark);
        }

        .badge-urgent {
            background: #FDECEC;
            color: #B42318;
        }

        .badge-warning {
            background: #FFF4D8;
            color: #9A6700;
        }

        .badge-info {
            background: #E6F4FB;
            color: #05668D;
        }

        .badge-success {
            background: #E7F6EC;
            color: #067647;
        }

        .badge-neutral {
            background: #EEF2F6;
            color: #475467;
        }

        .historial-box {
            background: #F8FAFA;
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 14px 16px;
            max-height: 220px;
            overflow-y: auto;
            color: #344054;
            font-size: 13px;
            line-height: 1.5;
            white-space: pre-wrap;
        }

        div.stButton > button[kind="primary"],
        div.stFormSubmitButton > button[kind="primary"] {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
            border-radius: 12px;
            font-weight: 700;
            min-height: 42px;
        }

        div.stButton > button[kind="primary"]:hover,
        div.stFormSubmitButton > button[kind="primary"]:hover {
            background: var(--primary-dark);
            border-color: var(--primary-dark);
            color: white;
        }

        div.stButton > button,
        div.stFormSubmitButton > button {
            border-radius: 12px;
            min-height: 42px;
            font-weight: 650;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 6px 18px rgba(0, 79, 76, 0.04);
        }

        div[data-testid="stExpander"] {
            border: 1px solid var(--border);
            border-radius: 16px;
            background: #FFFFFF;
            box-shadow: 0 6px 18px rgba(0, 79, 76, 0.04);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background: transparent;
        }

        .stTabs [data-baseweb="tab"] {
            background: #FFFFFF;
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 8px 18px;
            color: var(--text-muted);
            font-weight: 700;
        }

        .stTabs [aria-selected="true"] {
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }

        input, textarea {
            border-radius: 12px !important;
        }

        /* =====================================================
        CHECKBOX PERSONALIZADO
        ===================================================== */

        /* Contenedor general del checkbox */
        div[data-testid="stCheckbox"] {
            margin-bottom: 6px;
        }

        /* Texto del checkbox */
        div[data-testid="stCheckbox"] label {
            color: var(--text-main);
            font-weight: 600;
            font-size: 14px;
        }

        /* Cuadrado del checkbox */
        div[data-testid="stCheckbox"] input[type="checkbox"] {
            accent-color: var(--primary);
        }

        /* Caja visual del checkbox - versiones recientes de Streamlit */
        div[data-testid="stCheckbox"] div[data-testid="stWidgetLabel"] {
            color: var(--text-main);
        }

        /* Refuerzo visual sobre el checkbox */
        div[data-testid="stCheckbox"] label span {
            color: var(--text-main);
        }

        /* Borde del checkbox sin marcar */
        div[data-testid="stCheckbox"] input[type="checkbox"] {
            width: 18px;
            height: 18px;
            border: 2px solid var(--primary);
            border-radius: 5px;
            cursor: pointer;
        }

        /* Hover */
        div[data-testid="stCheckbox"]:hover input[type="checkbox"] {
            border-color: var(--primary-dark);
        }

        /* Checkbox marcado */
        div[data-testid="stCheckbox"] input[type="checkbox"]:checked {
            background-color: var(--primary);
            border-color: var(--primary);
        }

        </style>
        """,
        unsafe_allow_html=True,

        
    )


def page_header(titulo, subtitulo, eyebrow="Sistema de Gestión Municipal"):
    st.markdown(
        f"""
        <div class="page-hero">
            <div class="page-eyebrow">{eyebrow}</div>
            <h1 class="page-title">{titulo}</h1>
            <div class="page-subtitle">{subtitulo}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(titulo, subtitulo=None):
    subtitulo_html = f'<div class="section-caption">{subtitulo}</div>' if subtitulo else ""
    st.markdown(
        f"""
        <div class="section-title">{titulo}</div>
        {subtitulo_html}
        """,
        unsafe_allow_html=True,
    )


def badge(texto, tipo="neutral"):
    clases = {
        "primary": "badge-primary",
        "urgent": "badge-urgent",
        "warning": "badge-warning",
        "info": "badge-info",
        "success": "badge-success",
        "neutral": "badge-neutral",
    }
    clase = clases.get(tipo, "badge-neutral")
    return f'<span class="badge {clase}">{texto}</span>'


def prioridad_badge(prioridad):
    prioridad = str(prioridad or "")
    if prioridad.startswith("1"):
        return badge(prioridad, "urgent")
    if prioridad.startswith("2"):
        return badge(prioridad, "warning")
    if prioridad.startswith("3"):
        return badge(prioridad, "info")
    return badge(prioridad or "Sin prioridad", "neutral")


def estado_badge(estado):
    estado = str(estado or "Sin estado")
    estado_lower = estado.lower()

    if "cerrado" in estado_lower:
        return badge(estado, "neutral")
    if "ejecut" in estado_lower or "presentada" in estado_lower or "resuelta" in estado_lower:
        return badge(estado, "success")
    if "gestion" in estado_lower or "ejecucion" in estado_lower or "elaboracion" in estado_lower:
        return badge(estado, "info")
    if "pendiente" in estado_lower or "programada" in estado_lower:
        return badge(estado, "warning")
    if "suspendida" in estado_lower or "urgente" in estado_lower:
        return badge(estado, "urgent")

    return badge(estado, "primary")