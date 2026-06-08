from datetime import date
from html import escape

import streamlit as st

from utils.auth import require_login
from services.notas_rapidas_obra_service import actualizar_nota_rapida, crear_nota_rapida, listar_notas_rapidas
from services.obras_service import listar_obras_con_demanda

RESPONSABLES_TECNICOS = ["Facundo", "Pedro", "Bea", "Iris", "Guillo"]


def txt(v):
    return "" if v is None else str(v)


def clean(v):
    return txt(v).strip()


def fecha_corta(v):
    v = clean(v)
    if not v:
        return "-"
    p = v[:10].split("-")
    return f"{p[2]}/{p[1]}/{p[0][2:]}" if len(p) == 3 else v


def fecha_larga(v):
    v = clean(v)
    if not v:
        return "-"
    p = v[:10].split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else v


def sin_dato(v):
    v = clean(v)
    return v if v and v.lower() not in {"nan", "none", "null", "-"} else "Sin dato"


def show_error(error):
    st.error(f"No se pudo completar la operacion en Supabase: {error}")


def selector_obra(obras):
    opciones = {
        f"Obra {txt(o.get('id_obra'))} | {clean(o.get('apellido'))}, {clean(o.get('nombre'))} | Expte {txt(o.get('expediente')) or '-'}": o
        for o in obras
    }
    if not opciones:
        return None
    return st.selectbox("Obra seleccionada", list(opciones.keys()), key="nr_sel_obra")


def cargar_nota_tab(obras):
    sel = selector_obra(obras)
    if not sel:
        st.info("No hay obras disponibles.")
        return
    obra = {
        f"Obra {txt(o.get('id_obra'))} | {clean(o.get('apellido'))}, {clean(o.get('nombre'))} | Expte {txt(o.get('expediente')) or '-'}": o
        for o in obras
    }[sel]

    st.markdown(
        f"""
        <div class="nr-obra-summary">
            <div><strong>Obra #{sin_dato(obra.get('id_obra'))}</strong> · Expte. {sin_dato(obra.get('expediente'))}</div>
            <div>Domicilio: {sin_dato(obra.get('domicilio'))} · {sin_dato(obra.get('barrio'))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("nr_form_carga"):
        fecha_nota = date.today()
        st.markdown(f'<div class="nr-date-pill">Fecha: {fecha_larga(fecha_nota.isoformat())}</div>', unsafe_allow_html=True)
        responsable = st.selectbox("Responsable técnico", RESPONSABLES_TECNICOS, index=0)
        nota = st.text_area("Nota de visita", height=150, placeholder="Escribí lo observado en obra...")
        st.markdown('<div class="nr-pending-text">Estado inicial: Pendiente</div>', unsafe_allow_html=True)
        guardar = st.form_submit_button("Guardar nota", type="primary", use_container_width=True)

    if guardar:
        if not clean(nota):
            st.warning("Escribe la nota antes de guardar.")
            return
        try:
            crear_nota_rapida(
                {
                    "id_obra": obra.get("id_obra"),
                    "fecha_nota": fecha_nota.isoformat(),
                    "responsable_tecnico": responsable,
                    "nota": clean(nota),
                    "estado_nota": "Pendiente",
                }
            )
        except Exception as e:
            show_error(e)
            return
        st.success("Nota rápida guardada.")
        st.rerun()


def editar_notas_tab(obras):
    st.markdown('<div class="nr-section-title">Notas emitidas</div>', unsafe_allow_html=True)
    try:
        notas = listar_notas_rapidas()
    except Exception as e:
        show_error(e)
        return

    if not notas:
        st.markdown('<div class="nr-empty">No hay notas emitidas.</div>', unsafe_allow_html=True)
        return

    obras_por_id = {o.get("id_obra"): o for o in obras}

    if "nr_filtros" not in st.session_state:
        st.session_state["nr_filtros"] = {"estado": "Todos", "responsable": "Todos", "obra": "Todas"}

    estado_opts = ["Todos", "Pendiente", "Aplicada", "Descartada"]
    resp_opts = ["Todos"] + RESPONSABLES_TECNICOS
    obra_opts = ["Todas"] + [str(k) for k in sorted({n.get("id_obra") for n in notas if n.get("id_obra") is not None})]

    with st.expander("Filtros", expanded=False):
        with st.form("nr_filtros_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                e_idx = estado_opts.index(st.session_state["nr_filtros"]["estado"]) if st.session_state["nr_filtros"]["estado"] in estado_opts else 0
                estado_in = st.selectbox("Estado", estado_opts, index=e_idx)
            with c2:
                r_idx = resp_opts.index(st.session_state["nr_filtros"]["responsable"]) if st.session_state["nr_filtros"]["responsable"] in resp_opts else 0
                resp_in = st.selectbox("Responsable", resp_opts, index=r_idx)
            with c3:
                o_idx = obra_opts.index(st.session_state["nr_filtros"]["obra"]) if st.session_state["nr_filtros"]["obra"] in obra_opts else 0
                obra_in = st.selectbox("Obra", obra_opts, index=o_idx)
            aplicar = st.form_submit_button("Aplicar filtros", type="primary", use_container_width=True)

    if aplicar:
        st.session_state["nr_filtros"] = {"estado": estado_in, "responsable": resp_in, "obra": obra_in}

    estado_f = st.session_state["nr_filtros"]["estado"]
    resp_f = st.session_state["nr_filtros"]["responsable"]
    obra_f = st.session_state["nr_filtros"]["obra"]

    filtradas = []
    for n in notas:
        if estado_f != "Todos" and clean(n.get("estado_nota")) != estado_f:
            continue
        if resp_f != "Todos" and clean(n.get("responsable_tecnico")) != resp_f:
            continue
        if obra_f != "Todas" and str(n.get("id_obra")) != obra_f:
            continue
        filtradas.append(n)

    if not filtradas:
        st.markdown('<div class="nr-empty">No hay notas emitidas.</div>', unsafe_allow_html=True)
        return

    st.caption(f"Notas encontradas: {len(filtradas)}")

    for n in filtradas:
        obra = obras_por_id.get(n.get("id_obra"), {})
        estado = sin_dato(n.get("estado_nota"))
        st.markdown(
            f"""
            <div class="nr-note-card">
                <div class="nr-note-top">
                    <div>
                        <div class="nr-note-title">{fecha_corta(n.get('fecha_nota'))} · {escape(sin_dato(n.get('responsable_tecnico')))}</div>
                        <div class="nr-note-sub">Obra #{sin_dato(n.get('id_obra'))} · Expte. {sin_dato(obra.get('expediente'))}</div>
                    </div>
                    <span class="nr-status">{escape(estado)}</span>
                </div>
                <div class="nr-note-work">{escape(sin_dato(obra.get('apellido')))}, {escape(sin_dato(obra.get('nombre')))}</div>
                <div class="nr-note-text">{escape(sin_dato(n.get('nota')))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("Editar nota", expanded=False):
            with st.form(f"edit_nota_{n.get('id_nota')}"):
                fecha_ed = st.date_input("Fecha", value=date.fromisoformat(clean(n.get("fecha_nota"))[:10]) if clean(n.get("fecha_nota")) else date.today(), key=f"f_{n.get('id_nota')}")
                resp_ed = st.selectbox(
                    "Responsable técnico",
                    RESPONSABLES_TECNICOS,
                    index=RESPONSABLES_TECNICOS.index(n.get("responsable_tecnico")) if n.get("responsable_tecnico") in RESPONSABLES_TECNICOS else 0,
                    key=f"r_{n.get('id_nota')}",
                )
                nota_ed = st.text_area("Nota", value=txt(n.get("nota")), height=110, key=f"t_{n.get('id_nota')}")
                estado_ed = st.selectbox("Estado", ["Pendiente", "Aplicada", "Descartada"], index=["Pendiente", "Aplicada", "Descartada"].index(clean(n.get("estado_nota"))) if clean(n.get("estado_nota")) in {"Pendiente", "Aplicada", "Descartada"} else 0, key=f"e_{n.get('id_nota')}")
                guardar = st.form_submit_button("Guardar cambios", type="primary", use_container_width=True)
            if guardar:
                if not clean(nota_ed):
                    st.warning("La nota no puede quedar vacía.")
                    continue
                try:
                    actualizar_nota_rapida(
                        n.get("id_nota"),
                        {
                            "fecha_nota": fecha_ed.isoformat(),
                            "responsable_tecnico": resp_ed,
                            "nota": clean(nota_ed),
                            "estado_nota": estado_ed,
                        },
                    )
                except Exception as e:
                    show_error(e)
                    continue
                st.success("Nota actualizada.")
                st.rerun()


def main():
    require_login(["admin", "tecnico"])
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 720px;
            padding-top: 1.1rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        .nr-header-title {
            color: #0f2742;
            font-size: 24px;
            font-weight: 850;
            line-height: 1.15;
            margin: 0 0 2px;
        }
        .nr-header-subtitle {
            color: #64748b;
            font-size: 13px;
            font-weight: 650;
            margin: 0 0 12px;
        }
        div[class*="st-key-nr_card_carga"] [data-testid="stVerticalBlockBorderWrapper"],
        div[class*="st-key-nr_notas_emitidas"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff !important;
            border-color: #dbe7ee !important;
            border-radius: 14px !important;
            padding: 13px 14px !important;
            box-shadow: 0 1px 8px rgba(15, 23, 42, 0.04) !important;
        }
        div[class*="st-key-nr_card_carga"] [data-testid="stVerticalBlock"],
        div[class*="st-key-nr_notas_emitidas"] [data-testid="stVerticalBlock"] {
            gap: 0.56rem !important;
        }
        div[class*="st-key-nr_card_carga"] label,
        div[class*="st-key-nr_notas_emitidas"] label {
            color: #475569 !important;
            font-size: 12px !important;
            font-weight: 700 !important;
            margin-bottom: 2px !important;
        }
        div[class*="st-key-nr_card_carga"] input,
        div[class*="st-key-nr_card_carga"] textarea,
        div[class*="st-key-nr_card_carga"] [data-baseweb="select"] > div,
        div[class*="st-key-nr_notas_emitidas"] input,
        div[class*="st-key-nr_notas_emitidas"] textarea,
        div[class*="st-key-nr_notas_emitidas"] [data-baseweb="select"] > div {
            background: #f8fafc !important;
            border-color: #dbe7ee !important;
            font-size: 14px !important;
        }
        div[class*="st-key-nr_card_carga"] [data-testid="stFormSubmitButton"] button,
        div[class*="st-key-nr_notas_emitidas"] [data-testid="stFormSubmitButton"] button,
        div[class*="st-key-nr_notas_emitidas"] [data-testid="stFormSubmitButton"] button[kind="primary"],
        div[class*="st-key-nr_notas_emitidas"] button[kind="primary"] {
            background: #006b68 !important;
            border-color: #006b68 !important;
            color: #ffffff !important;
            min-height: 38px !important;
            box-shadow: none !important;
        }
        div[class*="st-key-nr_card_carga"] [data-testid="stFormSubmitButton"] button:hover,
        div[class*="st-key-nr_notas_emitidas"] [data-testid="stFormSubmitButton"] button:hover,
        div[class*="st-key-nr_notas_emitidas"] [data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
        div[class*="st-key-nr_notas_emitidas"] button[kind="primary"]:hover {
            background: #004f4c !important;
            border-color: #004f4c !important;
        }
        div[class*="st-key-nr_notas_emitidas"] [data-testid="stExpander"] {
            background: #ffffff !important;
            border: 1px solid #dbe7ee !important;
            border-radius: 11px !important;
            box-shadow: none !important;
            margin-top: 3px !important;
            margin-bottom: 10px !important;
        }
        div[class*="st-key-nr_notas_emitidas"] [data-testid="stExpander"] summary {
            color: #0f2742 !important;
            font-size: 13px !important;
            font-weight: 750 !important;
        }
        div[class*="st-key-nr_notas_emitidas"] [data-testid="stForm"] {
            border: 0 !important;
            background: transparent !important;
            padding: 4px 0 0 !important;
        }
        div[class*="st-key-nr_notas_emitidas"] [data-testid="stFormSubmitButton"] button {
            min-height: 36px !important;
            height: 36px !important;
            border-radius: 10px !important;
            font-size: 13px !important;
            font-weight: 750 !important;
            box-shadow: none !important;
        }
        .nr-card-title {
            color: #0f2742;
            font-size: 17px;
            font-weight: 850;
            margin: 0 0 2px;
        }
        .nr-card-caption {
            color: #64748b;
            font-size: 12px;
            font-weight: 650;
            margin: 0 0 8px;
        }
        .nr-obra-summary {
            background: #f8fafc;
            border: 1px solid #dbe7ee;
            border-left: 4px solid #006b68;
            border-radius: 11px;
            color: #1e293b;
            font-size: 13px;
            line-height: 1.35;
            padding: 9px 10px;
        }
        .nr-date-pill,
        .nr-pending-text {
            display: inline-flex;
            border: 1px solid #dbe7ee;
            border-radius: 999px;
            background: #f8fafc;
            color: #475569;
            font-size: 12px;
            font-weight: 750;
            padding: 5px 9px;
        }
        .nr-date-pill {
            margin-bottom: 8px;
        }
        .nr-pending-text {
            background: #ecfdf5;
            border-color: #99f6e4;
            color: #0f766e;
            margin-bottom: 12px;
        }
        .nr-section-title {
            color: #0f2742;
            font-size: 17px;
            font-weight: 850;
            margin: 0 0 7px;
        }
        .nr-empty {
            background: #f8fafc;
            border: 1px dashed #cbd5e1;
            border-radius: 11px;
            color: #64748b;
            font-size: 13px;
            font-weight: 700;
            padding: 10px 11px;
        }
        .nr-note-card {
            background: #ffffff;
            border: 1px solid #dbe7ee;
            border-left: 4px solid #006b68;
            border-radius: 12px;
            padding: 10px 11px;
            margin: 8px 0 5px;
        }
        .nr-note-top {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            align-items: flex-start;
        }
        .nr-note-title {
            color: #0f2742;
            font-size: 13px;
            font-weight: 850;
        }
        .nr-note-sub,
        .nr-note-work {
            color: #64748b;
            font-size: 12px;
            font-weight: 650;
            margin-top: 2px;
        }
        .nr-note-text {
            color: #1e293b;
            font-size: 13px;
            line-height: 1.35;
            margin-top: 8px;
            overflow-wrap: anywhere;
        }
        .nr-status {
            border: 1px solid #99f6e4;
            border-radius: 999px;
            background: #ecfdf5;
            color: #0f766e;
            font-size: 11px;
            font-weight: 800;
            padding: 4px 8px;
            white-space: nowrap;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="nr-header-title">Notas rápidas</div>', unsafe_allow_html=True)
    st.markdown('<div class="nr-header-subtitle">Registro rápido de observaciones de campo.</div>', unsafe_allow_html=True)

    try:
        obras = listar_obras_con_demanda()
    except Exception as e:
        show_error(e)
        return

    with st.container(border=True, key="nr_card_carga"):
        st.markdown('<div class="nr-card-title">Nueva nota</div>', unsafe_allow_html=True)
        st.markdown('<div class="nr-card-caption">Carga rápida desde obra.</div>', unsafe_allow_html=True)
        cargar_nota_tab(obras)
    with st.container(border=True, key="nr_notas_emitidas"):
        editar_notas_tab(obras)


main()
