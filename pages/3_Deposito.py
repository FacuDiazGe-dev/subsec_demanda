from datetime import date
from html import escape

import pandas as pd
import streamlit as st

from services.deposito_service import (
    listar_ordenes_por_estados,
    listar_pedidos_deposito,
    listar_programados_deposito,
    marcar_a_deposito_desde_programados,
    marcar_entregado_desde_programados,
    marcar_no_realizado,
    programar_ordenes_deposito,
)
from services.materiales_orden_service import listar_materiales_por_orden
from utils.auth import require_login
from utils.operational_card_component import operational_card
from utils.operational_list_editor_component import operational_list_editor


ESTILOS_ESTADO = {
    "Pendiente de entrega": "Programada",
    "Pendiente de retiro": "Programada",
    "Pedido entrega": "Pedido",
    "Pedido retiro": "Pedido",
    "Pedido": "Pedido",
    "En deposito": "En deposito",
    "Entregado parcial": "Parcial",
    "En deposito parcial": "Parcial",
    "Entrega parcial": "Parcial",
}

TIPOS_STOCK = {
    "gestion de stock",
    "compra para emergencias",
    "reposicion de deposito",
    "insumos internos",
    "herramientas / equipamiento",
}


def cargar_estilos_deposito():
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] main .block-container {
            max-width: 1380px;
        }
        .dep-header {
            margin-bottom: 6px;
        }
        .dep-title {
            color: #0f2742;
            font-size: 24px;
            line-height: 1.1;
            font-weight: 850;
            margin: 0;
        }
        .dep-subtitle {
            color: #64748b;
            font-size: 13px;
            font-weight: 600;
            margin-top: 2px;
        }
        .dep-section-title {
            color: #0f2742;
            font-size: 16px;
            font-weight: 850;
            margin: 0 0 2px;
        }
        .dep-section-caption {
            color: #64748b;
            font-size: 12px;
            font-weight: 650;
            margin-bottom: 5px;
        }
        .dep-kpi-card {
            background: #ffffff;
            border: 1px solid #dbe7ee;
            border-radius: 10px;
            border-left: 3px solid #006b68;
            padding: 4px 6px;
            min-height: 38px;
            box-shadow: 0 1px 6px rgba(15, 23, 42, 0.035);
            text-align: center;
        }
        .dep-kpi-label {
            color: #64748b;
            font-size: 9px;
            font-weight: 850;
            letter-spacing: 0.02em;
            text-transform: uppercase;
            line-height: 1.15;
        }
        .dep-kpi-value {
            color: #0f2742;
            font-size: 17px;
            font-weight: 850;
            line-height: 1;
            margin-top: 3px;
        }
        .dep-kpi-muted { border-left-color: #94a3b8; }
        .dep-kpi-blue { border-left-color: #1d4ed8; }
        .dep-kpi-amber { border-left-color: #f59e0b; }
        .dep-kpi-green { border-left-color: #006b68; }
        div[data-testid="stExpander"] {
            border-color: #dbe7ee !important;
            border-radius: 12px !important;
        }
        div[data-testid="stDateInput"] input {
            background: #ffffff !important;
            border-color: #cbd5e1 !important;
            border-radius: 10px !important;
            min-height: 30px !important;
            height: 30px !important;
            font-size: 12.5px !important;
        }
        div[class*="st-key-dep_filtros"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff !important;
            border-color: #dbe7ee !important;
            padding: 5px 8px !important;
            box-shadow: 0 1px 7px rgba(15, 23, 42, 0.04) !important;
        }
        div[class*="st-key-dep_filtros"] label {
            color: #475569 !important;
            font-size: 11px !important;
            font-weight: 650 !important;
            margin-bottom: 1px !important;
        }
        div[class*="st-key-dep_filtros"] input,
        div[class*="st-key-dep_filtros"] [data-baseweb="select"] > div {
            background: #ffffff !important;
            min-height: 30px !important;
            height: 30px !important;
            font-size: 12.5px !important;
        }
        div[class*="st-key-dep_btn_buscar"] button {
            background: #006b68 !important;
            border-color: #006b68 !important;
            color: #ffffff !important;
            box-shadow: none !important;
            min-height: 30px !important;
            height: 30px !important;
            padding-top: 3px !important;
            padding-bottom: 3px !important;
            font-size: 12.5px !important;
        }
        div[class*="st-key-dep_btn_buscar"] button:hover {
            background: #004f4c !important;
            border-color: #004f4c !important;
        }
        div[class*="st-key-dep_fecha_programacion"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff !important;
            border-color: #dbe7ee !important;
            padding: 6px 8px !important;
            box-shadow: 0 1px 6px rgba(15, 23, 42, 0.035) !important;
        }
        .dep-date-label {
            color: #475569;
            font-size: 11px;
            font-weight: 850;
            letter-spacing: 0.02em;
            text-transform: uppercase;
            margin-bottom: 2px;
        }
        .dep-order-group {
            margin-top: 14px;
            margin-bottom: 8px;
        }
        .dep-order-group-title {
            color: #0f2742;
            font-size: 14px;
            font-weight: 850;
            line-height: 1.2;
            margin: 0;
        }
        .dep-order-group-rule {
            height: 1px;
            background: #dbe7ee;
            margin-top: 6px;
        }
        div[class*="st-key-dep_parcial_bloque"] {
            margin-top: -18px !important;
            position: relative;
            z-index: 1;
        }
        div[class*="st-key-dep_parcial_bloque"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff !important;
            border-color: #dbe7ee !important;
            border-left: 4px solid #1d4ed8 !important;
            border-top-color: #cbd5e1 !important;
            border-radius: 0 0 14px 14px !important;
            box-shadow: 0 4px 10px rgba(15, 23, 42, 0.035) !important;
            padding: 6px 10px 10px !important;
        }
        div[class*="st-key-dep_parcial_bloque"] [data-testid="stMarkdownContainer"] p {
            margin-bottom: 4px !important;
        }
        div[class*="st-key-dep_detalle_bloque"] {
            margin-top: -26px !important;
            position: relative;
            z-index: 1;
        }
        div[class*="st-key-dep_detalle_bloque"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff !important;
            border-color: #dbe7ee !important;
            border-left: 4px solid #f59e0b !important;
            border-top-color: #e2e8f0 !important;
            border-radius: 0 0 14px 14px !important;
            box-shadow: 0 5px 10px rgba(15, 23, 42, 0.032) !important;
            padding: 4px 10px 10px !important;
        }
        div[class*="st-key-dep_detalle_bloque"] [data-testid="stVerticalBlock"] {
            gap: 0.35rem !important;
        }
        div[class*="st-key-dep_detalle_bloque"] [data-testid="stMarkdownContainer"] p {
            margin-bottom: 2px !important;
        }
        .dep-detail-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin: 2px 0 8px;
        }
        .dep-detail-chip {
            border: 1px solid #dbe7ee;
            background: #f8fafc;
            border-radius: 999px;
            padding: 4px 8px;
            color: #334155;
            font-size: 12px;
            font-weight: 650;
            line-height: 1.2;
        }
        .dep-detail-label {
            color: #475569;
            font-size: 11px;
            font-weight: 850;
            letter-spacing: 0.02em;
            text-transform: uppercase;
            margin: 6px 0 2px;
        }
        .dep-detail-text {
            border: 1px solid #e2e8f0;
            background: #f8fafc;
            border-radius: 10px;
            padding: 7px 9px;
            color: #1e293b;
            font-size: 13px;
            font-weight: 600;
            line-height: 1.35;
            margin-bottom: 8px;
        }
        .dep-history-card {
            background: #ffffff;
            border: 1px solid #dbe7ee;
            border-radius: 12px;
            border-left: 4px solid var(--dep-history-accent, #006b68);
            padding: 9px 10px;
            margin-bottom: 4px;
            box-shadow: 0 1px 6px rgba(15, 23, 42, 0.035);
        }
        .dep-history-head {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 8px;
        }
        .dep-history-title {
            color: #0f2742;
            font-size: 14px;
            font-weight: 850;
            line-height: 1.2;
            margin: 0;
        }
        .dep-history-subtitle {
            color: #475569;
            font-size: 12.5px;
            font-weight: 650;
            line-height: 1.25;
            margin-top: 2px;
        }
        .dep-history-badge {
            border: 1px solid var(--dep-history-accent, #006b68);
            color: var(--dep-history-accent, #006b68);
            background: #f8fafc;
            border-radius: 999px;
            padding: 3px 8px;
            font-size: 12px;
            font-weight: 850;
            white-space: nowrap;
        }
        .dep-history-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin: 7px 0 6px;
        }
        .dep-history-chip {
            border: 1px solid #dbe7ee;
            background: #f8fafc;
            border-radius: 999px;
            padding: 3px 7px;
            color: #475569;
            font-size: 12px;
            font-weight: 650;
            line-height: 1.2;
        }
        .dep-history-task {
            border-top: 1px solid #e2e8f0;
            color: #1e293b;
            font-size: 12.5px;
            font-weight: 650;
            line-height: 1.35;
            margin-top: 6px;
            padding-top: 6px;
        }
        div[class*="st-key-dep_hist_block"] {
            margin-bottom: 12px !important;
        }
        div[class*="st-key-dep_hist_block"] [data-testid="stVerticalBlock"] {
            gap: 0.05rem !important;
        }
        div[class*="st-key-dep_hist_block"] [data-testid="stElementContainer"] {
            margin-top: 0 !important;
            margin-bottom: 0 !important;
        }
        div[class*="st-key-dep_hist_block"] div[data-testid="stExpander"] {
            margin-top: -34px !important;
        }
        div[class*="st-key-dep_hist_block"] div[data-testid="stExpander"] details > summary {
            min-height: 34px !important;
            padding-top: 6px !important;
            padding-bottom: 6px !important;
        }
        div[class*="st-key-dep_hist_block"] div[data-testid="stExpander"] details {
            border-radius: 10px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header_deposito():
    st.subheader("Deposito")
    st.caption("Programacion, entrega y retiro de ordenes de materiales.")


def texto(valor):
    return "" if valor is None else str(valor)


def consumir_evento_card(evento, scope):
    if not evento:
        return None
    event_id = evento.get("event_id") or f"{evento.get('card_key')}:{evento.get('action')}:{evento.get('selected')}"
    clave = f"{scope}_ultimo_evento_card"
    if st.session_state.get(clave) == event_id:
        return None
    st.session_state[clave] = event_id
    return evento


def limpiar(valor):
    return texto(valor).strip()


def fecha_visible(valor):
    valor = limpiar(valor)
    if not valor:
        return "-"
    partes = valor[:10].split("-")
    if len(partes) == 3 and all(partes):
        return f"{partes[2]}/{partes[1]}/{partes[0]}"
    return valor


def nombre_persona(orden):
    return f"{texto(orden.get('apellido'))}, {texto(orden.get('nombre'))}".strip(", ")


def domicilio_barrio(orden):
    domicilio = limpiar(orden.get("domicilio"))
    barrio = limpiar(orden.get("barrio"))
    if domicilio and barrio:
        return f"{domicilio} - {barrio}"
    return domicilio or barrio or "-"


def tipo_materiales_desde_obs_orden(orden):
    demanda = orden.get("demanda") or {}
    obs = limpiar(demanda.get("observaciones"))
    prefijo = "tipo materiales:"
    if obs.lower().startswith(prefijo):
        resto = obs[len(prefijo):].strip()
        return resto.split(".")[0].strip()
    return ""


def es_orden_stock(orden):
    accion = limpiar(orden.get("accion")).lower()
    if accion not in {"materiales", "entregar materiales"}:
        return False
    tipo = tipo_materiales_desde_obs_orden(orden).lower()
    return tipo in TIPOS_STOCK


def resumen_texto(valor, max_len=110):
    valor = limpiar(valor)
    if len(valor) <= max_len:
        return valor
    return f"{valor[:max_len].rstrip()}..."


def badge_estado(estado):
    estado = limpiar(estado)
    return f"{ESTILOS_ESTADO.get(estado, 'Estado')} - {estado}"


def color_estado_deposito(estado):
    estado = limpiar(estado).lower()
    if estado in {"entregado", "cerrado"} or "completo" in estado:
        return "#006b68"
    if "parcial" in estado:
        return "#7c3aed"
    if "pendiente de entrega" in estado or "pendiente de retiro" in estado:
        return "#1d4ed8"
    if "pedido" in estado:
        return "#f59e0b"
    if "deposito" in estado or "depÃ³sito" in estado:
        return "#64748b"
    if "cancelado" in estado:
        return "#dc2626"
    return "#94a3b8"


def variante_estado_deposito(estado):
    estado = limpiar(estado).lower()
    if estado in {"entregado", "cerrado"}:
        return "success"
    if "cancelado" in estado:
        return "danger"
    if "pendiente" in estado:
        return "highlight"
    if "pedido" in estado:
        return "warning"
    if "deposito" in estado or "depÃ³sito" in estado:
        return "muted"
    return "default"


def render_kpi_deposito(label, value, tone="green"):
    st.markdown(
        f"""
        <div class="dep-kpi-card dep-kpi-{tone}">
            <div class="dep-kpi-label">{label}</div>
            <div class="dep-kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def aplicar_filtros_pedidos(ordenes):
    if not ordenes:
        return []

    df = pd.DataFrame(ordenes)
    with st.container(border=True, key="dep_filtros"):
        col0, col1, col2, col3, col4, col5 = st.columns([2.0, 1.15, 1.15, 1.15, 1.15, 0.75])
        with col0:
            busqueda = st.text_input("Busqueda libre", placeholder="N orden, expediente, apellido, nombre...", key="dep_busqueda")
        with col1:
            estados = sorted({limpiar(x) for x in df["estado"].dropna().tolist() if limpiar(x)})
            filtro_estado = st.multiselect("Estado", estados, key="dep_f_estado")
        with col2:
            barrios = sorted({limpiar(x) for x in df["barrio"].dropna().tolist() if limpiar(x)})
            filtro_barrio = st.multiselect("Barrio", barrios, key="dep_f_barrio")
        with col3:
            origenes = sorted({limpiar(x) for x in df["origen"].dropna().tolist() if limpiar(x)})
            filtro_origen = st.multiselect("Origen", origenes, key="dep_f_origen")
        with col4:
            prioridades = sorted({limpiar(x) for x in df["prioridad"].dropna().tolist() if limpiar(x)})
            filtro_prioridad = st.multiselect("Prioridad", prioridades, key="dep_f_prioridad")
        with col5:
            st.write("")
            st.button("Buscar", type="primary", use_container_width=True, key="dep_btn_buscar")

    filtrado = ordenes[:]
    if filtro_estado:
        filtrado = [o for o in filtrado if limpiar(o.get("estado")) in set(filtro_estado)]
    if filtro_barrio:
        filtrado = [o for o in filtrado if limpiar(o.get("barrio")) in set(filtro_barrio)]
    if filtro_origen:
        filtrado = [o for o in filtrado if limpiar(o.get("origen")) in set(filtro_origen)]
    if filtro_prioridad:
        filtrado = [o for o in filtrado if limpiar(o.get("prioridad")) in set(filtro_prioridad)]

    busqueda = limpiar(busqueda).lower()
    if busqueda:
        def coincide(orden):
            base = " ".join(
                [
                    texto(orden.get("n_orden")),
                    texto(orden.get("expediente")),
                    texto(orden.get("apellido")),
                    texto(orden.get("nombre")),
                    texto(orden.get("estado")),
                ]
            ).lower()
            return busqueda in base

        filtrado = [o for o in filtrado if coincide(o)]

    return filtrado


def mostrar_detalle_orden(orden):
    with st.container(border=True, key=f"dep_detalle_bloque_{orden.get('n_orden')}"):
        st.caption("Detalle de orden")
        st.markdown(
            f"""
            <div class="dep-detail-meta">
                <div class="dep-detail-chip">ID demanda: {texto(orden.get('id_demanda')) or '-'}</div>
                <div class="dep-detail-chip">DNI: {texto(orden.get('dni')) or '-'}</div>
                <div class="dep-detail-chip">Contacto: {texto(orden.get('contacto')) or '-'}</div>
            </div>
            <div class="dep-detail-label">Instruccion completa</div>
            <div class="dep-detail-text">{texto(orden.get('instrucciones_tarea')) or '-'}</div>
            """,
            unsafe_allow_html=True,
        )
        try:
            materiales = listar_materiales_por_orden(orden.get("n_orden"))
        except Exception as error:
            st.error(f"No se pudieron cargar materiales: {error}")
            materiales = []

        if materiales:
            operational_list_editor(
                title="Materiales asociados",
                rows=filas_materiales_operativas(materiales),
                mode="read",
                show_unit=False,
                allow_delete=False,
                item_label="Material",
                embedded=True,
                key=f"dep_detalle_materiales_{orden.get('n_orden')}",
            )
        else:
            st.info("Esta orden no tiene materiales asociados.")

        historial = limpiar(orden.get("historial"))
        if historial:
            with st.expander("Historial", expanded=False):
                for entrada in historial.split("||"):
                    valor = limpiar(entrada)
                    if valor:
                        st.caption(valor)


def card_pedido(orden):
    n_orden = orden.get("n_orden")
    clave_check = f"dep_pedido_sel_{n_orden}"
    clave_detalle = f"dep_pedido_det_{n_orden}"

    with st.container(border=True):
        col_sel, col_info, col_lupa = st.columns([0.7, 5, 0.6])
        with col_sel:
            st.checkbox("Sel", key=clave_check, label_visibility="collapsed")
        with col_info:
            st.markdown(f"**Orden N\u00b0 {texto(n_orden)}**")
            st.caption(
                f"{badge_estado(orden.get('estado'))} | Emision: {fecha_visible(orden.get('fecha_emision'))} | "
                f"Prioridad: {texto(orden.get('prioridad'))}"
            )
            st.write(f"Expte: {texto(orden.get('expediente'))}")
            if es_orden_stock(orden):
                st.write("Destino: Deposito / Stock")
                st.write(f"Tipo: {tipo_materiales_desde_obs_orden(orden) or 'Gestion de stock'}")
            else:
                st.write(f"Beneficiario: {nombre_persona(orden)}")
                st.write(f"Domicilio: {domicilio_barrio(orden)}")
            st.caption(f"Origen: {texto(orden.get('origen'))}")
            st.caption(f"Tarea: {resumen_texto(orden.get('instrucciones_tarea'))}")
        with col_lupa:
            if st.button("Ã°Å¸â€Â", key=f"dep_btn_lupa_{n_orden}", help="Ver detalle"):
                st.session_state[clave_detalle] = not st.session_state.get(clave_detalle, False)
        if st.session_state.get(clave_detalle, False):
            mostrar_detalle_orden(orden)


def card_resumen_estado_legacy(orden):
    with st.container(border=True):
        st.markdown(f"**Orden N\u00b0 {texto(orden.get('n_orden'))}**")
        st.caption(
            f"{badge_estado(orden.get('estado'))} | Emision: {fecha_visible(orden.get('fecha_emision'))} | "
            f"Entrega: {fecha_visible(orden.get('fecha_entrega'))}"
        )
        st.write(f"Expte: {texto(orden.get('expediente'))}")
        if es_orden_stock(orden):
            st.write("Destino: Deposito / Stock")
            st.write(f"Tipo: {tipo_materiales_desde_obs_orden(orden) or 'Gestion de stock'}")
        else:
            st.write(f"Beneficiario: {nombre_persona(orden)}")
            st.write(f"Domicilio: {domicilio_barrio(orden)}")
        st.caption(f"Tarea: {resumen_texto(orden.get('instrucciones_tarea'))}")


def card_resumen_estado(orden):
    n_orden = orden.get("n_orden")
    estado = texto(orden.get("estado")) or "-"
    accent = color_estado_deposito(estado)
    titulo = f"Orden N\u00b0 {texto(n_orden)} · Expte. {texto(orden.get('expediente')) or '-'}"
    if es_orden_stock(orden):
        subtitulo = f"Deposito / Stock · {tipo_materiales_desde_obs_orden(orden) or 'Gestion de stock'}"
    else:
        subtitulo = f"{nombre_persona(orden) or 'Sin beneficiario'} · {domicilio_barrio(orden)}"
    tarea = resumen_texto(orden.get("instrucciones_tarea"), 150)

    with st.container(border=False, key=f"dep_hist_block_{n_orden}"):
        st.markdown(
            f"""
            <div class="dep-history-card" style="--dep-history-accent: {accent};">
                <div class="dep-history-head">
                    <div>
                        <div class="dep-history-title">{escape(titulo)}</div>
                        <div class="dep-history-subtitle">{escape(subtitulo)}</div>
                    </div>
                    <div class="dep-history-badge">{escape(estado)}</div>
                </div>
                <div class="dep-history-meta">
                    <div class="dep-history-chip">Emision: {escape(fecha_visible(orden.get('fecha_emision')))}</div>
                    <div class="dep-history-chip">Entrega: {escape(fecha_visible(orden.get('fecha_entrega')))}</div>
                </div>
                <div class="dep-history-task">{escape(tarea or '-')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        try:
            materiales = listar_materiales_por_orden(n_orden)
        except Exception as error:
            st.caption(f"No se pudieron cargar materiales: {error}")
            materiales = []

        if materiales:
            operational_list_editor(
                title="Materiales asociados",
                rows=filas_materiales_operativas(materiales),
                mode="read",
                show_unit=False,
                allow_delete=False,
                item_label="Material",
                embedded=True,
                key=f"dep_hist_materiales_{n_orden}",
            )
        else:
            st.caption("Sin materiales asociados.")

        historial = limpiar(orden.get("historial"))
        if historial:
            with st.expander("Historial", expanded=False):
                for entrada in historial.split("||"):
                    valor = limpiar(entrada)
                    if valor:
                        st.caption(valor)


def card_pedido_ui(orden, fecha_estimada):
    n_orden = orden.get("n_orden")
    clave_detalle = f"dep_pedido_det_{n_orden}"

    meta = [
        f"Emision: {fecha_visible(orden.get('fecha_emision'))}",
        f"Origen: {texto(orden.get('origen')) or '-'}",
        f"Demanda ID: {texto(orden.get('id_demanda')) or '-'}",
    ]
    if es_orden_stock(orden):
        subtitle = f"Deposito / Stock - {tipo_materiales_desde_obs_orden(orden) or 'Gestion de stock'}"
    else:
        subtitle = f"{nombre_persona(orden) or 'Sin beneficiario'} - {domicilio_barrio(orden)}"

    accion = operational_card(
        title=f"Orden N\u00b0 {texto(n_orden)} - Expte. {texto(orden.get('expediente')) or '-'}",
        subtitle=subtitle,
        status=texto(orden.get("estado")) or None,
        priority=texto(orden.get("prioridad")) or None,
        meta=meta,
        description=None,
        footer=None,
        variant=variante_estado_deposito(orden.get("estado")),
        accent_color=color_estado_deposito(orden.get("estado")),
        actions=[
            {"label": "Ver detalle", "key": "ver_detalle", "kind": "secondary"},
            {"label": "Programar", "key": "programar", "kind": "primary"},
        ],
        actions_layout="corner",
        card_key=f"dep_pedido_{n_orden}",
        key=f"dep_pedido_{n_orden}",
    )
    accion = consumir_evento_card(accion, f"dep_pedido_{n_orden}")

    if accion and accion.get("action") == "ver_detalle":
        st.session_state[clave_detalle] = not st.session_state.get(clave_detalle, False)

    if accion and accion.get("action") == "programar":
        try:
            programar_ordenes_deposito([n_orden], fecha_estimada.isoformat())
        except Exception as error:
            st.error(f"No se pudo programar la orden {n_orden}: {error}")
        else:
            st.success(f"Orden {n_orden} programada correctamente.")
            st.rerun()

    if st.session_state.get(clave_detalle, False):
        mostrar_detalle_orden(orden)
def tab_pedidos():
    contexto = preparar_pedidos_programables()
    render_pedidos_programables_lista(contexto)
    consultas_rapidas_deposito()


def kpis_pedidos_deposito(ordenes):
    ordenes = ordenes or []
    sin_validar = sum(1 for orden in ordenes if limpiar(orden.get("estado")) == "Pedido")
    pedido_entrega_retiro = sum(
        1
        for orden in ordenes
        if limpiar(orden.get("estado")) in {"Pedido entrega", "Pedido retiro"}
    )
    en_deposito = sum(
        1
        for orden in ordenes
        if limpiar(orden.get("estado")) in {"En deposito", "En depÃ³sito"}
    )
    try:
        entregados = len(listar_ordenes_por_estados({"Entregado", "Cerrado"}))
    except Exception:
        entregados = 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_deposito("Sin validar", sin_validar, "amber")
    with c2:
        render_kpi_deposito("Entrega / retiro", pedido_entrega_retiro, "blue")
    with c3:
        render_kpi_deposito("En deposito", en_deposito, "muted")
    with c4:
        render_kpi_deposito("Total entregados", entregados, "green")


def preparar_pedidos_programables():
    ordenes = listar_pedidos_deposito()
    kpis_pedidos_deposito(ordenes)
    ordenes_filtradas = aplicar_filtros_pedidos(ordenes) if ordenes else []

    agrupadas = {}
    for orden in ordenes_filtradas:
        estado = limpiar(orden.get("estado")) or "Sin estado"
        agrupadas.setdefault(estado, []).append(orden)

    orden_estado = [
        "Pedido entrega",
        "Pedido retiro",
        "En deposito",
        "Pedido",
    ]
    estados_restantes = [e for e in agrupadas.keys() if e not in orden_estado]
    estados_a_mostrar = orden_estado + sorted(estados_restantes)

    return {
        "ordenes": ordenes,
        "ordenes_filtradas": ordenes_filtradas,
        "agrupadas": agrupadas,
        "estados_a_mostrar": estados_a_mostrar,
    }


def render_pedidos_programables_lista(contexto):
    ordenes = contexto.get("ordenes") or []
    ordenes_filtradas = contexto.get("ordenes_filtradas") or []
    agrupadas = contexto.get("agrupadas") or {}
    estados_a_mostrar = contexto.get("estados_a_mostrar") or []

    st.markdown('<div class="dep-section-title">Ordenes pendientes programables</div>', unsafe_allow_html=True)
    with st.container(border=True, key="dep_fecha_programacion"):
        st.markdown('<div class="dep-date-label">Fecha estimada para programar</div>', unsafe_allow_html=True)
        fecha_estimada = st.date_input(
            "Fecha estimada para programar",
            value=date.today(),
            format="DD/MM/YYYY",
            key="dep_fecha_estimada_programacion",
            label_visibility="collapsed",
        )

    if not ordenes:
        st.info("No hay pedidos para programar.")
    elif not ordenes_filtradas:
        st.info("No hay pedidos que coincidan con los filtros.")

    for estado in estados_a_mostrar:
        items = agrupadas.get(estado, [])
        if not items:
            continue
        st.markdown(
            f"""
            <div class="dep-order-group">
                <div class="dep-order-group-title">{estado} ({len(items)})</div>
                <div class="dep-order-group-rule"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for orden in items:
            card_pedido_ui(orden, fecha_estimada)


def consultas_rapidas_deposito():
    st.divider()
    st.markdown("#### Consultas rapidas")

    with st.expander("Entregadas o canceladas", expanded=False):
        cerradas = listar_ordenes_por_estados({"Entregado", "Cancelado", "Cerrado"})
        if not cerradas:
            st.info("No hay ordenes entregadas o canceladas.")
        else:
            for orden in cerradas:
                card_resumen_estado(orden)

    with st.expander("Entregas parciales", expanded=False):
        parciales = listar_ordenes_por_estados(
            {"Entregado parcial", "En deposito parcial", "En depÃƒÂ³sito parcial", "Entrega parcial"}
        )
        if not parciales:
            st.info("No hay ordenes en entrega parcial.")
        else:
            for orden in parciales:
                card_resumen_estado(orden)


def resumen_materiales(orden):
    materiales = orden.get("materiales") or []
    if not materiales:
        return "Sin materiales asociados."
    partes = []
    for item in materiales[:4]:
        mat = limpiar(item.get("Material"))
        cant = limpiar(item.get("cantidad"))
        partes.append(f"{mat} ({cant})" if cant else mat)
    if len(materiales) > 4:
        partes.append("...")
    return " | ".join(partes)


def numero_cantidad(valor):
    texto_valor = limpiar(valor).replace(",", ".")
    if not texto_valor:
        return None
    try:
        return float(texto_valor)
    except ValueError:
        return None


def cantidad_visible_numero(valor):
    if valor is None:
        return ""
    if float(valor).is_integer():
        return str(int(valor))
    return f"{valor:g}"


def filas_materiales_operativas(materiales, n_orden=None):
    filas = []
    for idx, material in enumerate(materiales or []):
        nombre = limpiar(material.get("Material") or material.get("item_label"))
        cantidad = limpiar(material.get("cantidad") or material.get("quantity"))
        if not nombre and not cantidad:
            continue
        entregado = ""
        if n_orden is not None:
            entregado = st.session_state.get(f"dep_mat_entregado_{n_orden}_{idx}", 0)
        filas.append(
            {
                "id": f"{n_orden or 'mat'}_{idx}",
                "item_label": nombre,
                "quantity": cantidad,
                "delivered": entregado,
            }
        )
    return filas


def guardar_resultado_parcialidad(n_orden, resultado):
    if not resultado:
        return
    filas = resultado.get("rows") or []
    for idx, fila in enumerate(filas):
        st.session_state[f"dep_mat_entregado_{n_orden}_{idx}"] = fila.get("delivered", 0)
    st.session_state[f"dep_parcial_rows_{n_orden}"] = filas


def materiales_pendientes_desde_editor(orden):
    materiales = orden.get("materiales") or []
    pendientes = []
    sin_detalle = False
    for idx, material in enumerate(materiales):
        nombre = limpiar(material.get("Material"))
        cantidad_original = numero_cantidad(material.get("cantidad"))
        entregada = st.session_state.get(f"dep_mat_entregado_{orden.get('n_orden')}_{idx}", 0)
        try:
            entregada = float(entregada or 0)
        except (TypeError, ValueError):
            entregada = 0

        if not nombre:
            continue
        if cantidad_original is None:
            sin_detalle = True
            continue

        entregada = max(0, min(entregada, cantidad_original))
        pendiente = max(cantidad_original - entregada, 0)
        if pendiente > 0:
            pendientes.append({"Material": nombre, "cantidad": cantidad_visible_numero(pendiente)})
    return pendientes, sin_detalle


def materiales_parcialidad_ui(orden, prefijo):
    materiales = orden.get("materiales") or []
    st.caption("Materiales efectivamente entregados/retirados")
    st.caption(
        "Seleccione los materiales que efectivamente se entregaron o retiraron. "
        "Los no seleccionados pasaran automaticamente a una nueva orden. "
        "Si no selecciona ninguno, la nueva orden quedara sin materiales para revision manual."
    )
    if not materiales:
        st.info(
            "Esta orden no tiene materiales asociados. Si confirma parcialidad, "
            "se generara una nueva orden sin materiales para revision manual."
        )
        return []

    seleccionados = []
    with st.expander("Ver materiales asociados", expanded=False):
        for idx, material in enumerate(materiales):
            nombre = limpiar(material.get("Material"))
            cantidad = limpiar(material.get("cantidad"))
            etiqueta = f"{nombre} | {cantidad}" if cantidad else nombre
            clave = f"dep_mat_sel_{prefijo}_{orden.get('n_orden')}_{idx}"
            if st.checkbox(etiqueta, key=clave):
                seleccionados.append(idx)
    return seleccionados


def acciones_programado(orden):
    n_orden = orden.get("n_orden")
    estado = limpiar(orden.get("estado"))
    st.caption("Acciones")

    if estado == "Pendiente de entrega":
        parcial = st.checkbox("Entrega parcial", key=f"dep_chk_parcial_ent_{n_orden}")
        materiales_idx = materiales_parcialidad_ui(orden, "ent") if parcial else []
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Ã¢Å“â€œ", key=f"dep_ok_{n_orden}", help="Completado", use_container_width=True):
                marcar_entregado_desde_programados(
                    n_orden,
                    parcial=parcial,
                    materiales_seleccionados_idx=materiales_idx,
                )
                if parcial:
                    st.success("Entrega parcial registrada y nueva orden creada.")
                else:
                    st.success("Orden marcada como entregada.")
                st.rerun()
        with c2:
            if st.button("X", key=f"dep_no_{n_orden}", help="No entregado", use_container_width=True):
                if parcial:
                    st.warning(
                        "Si no se realizo la entrega, no corresponde registrar parcialidad. "
                        "La orden volvera a En deposito."
                    )
                marcar_no_realizado(n_orden)
                st.warning("Orden devuelta a En deposito.")
                st.rerun()
        return

    if estado == "Pendiente de retiro":
        parcial = st.checkbox("Retiro parcial", key=f"dep_chk_parcial_ret_{n_orden}")
        materiales_idx = materiales_parcialidad_ui(orden, "ret") if parcial else []
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Ã¢Å“â€œ", key=f"dep_okr_{n_orden}", help="Completado", use_container_width=True):
                marcar_entregado_desde_programados(
                    n_orden,
                    parcial=parcial,
                    materiales_seleccionados_idx=materiales_idx,
                )
                if parcial:
                    st.success("Retiro parcial registrado y nueva orden creada.")
                else:
                    st.success("Retiro completado y orden entregada.")
                st.rerun()
        with c2:
            if st.button("Ã°Å¸ÂÂ ", key=f"dep_home_{n_orden}", help="A deposito", use_container_width=True):
                marcar_a_deposito_desde_programados(
                    n_orden,
                    parcial=parcial,
                    materiales_seleccionados_idx=materiales_idx,
                )
                if parcial:
                    st.success("Retiro parcial a deposito registrado y nueva orden creada.")
                else:
                    st.success("Retiro completado. Materiales en deposito.")
                st.rerun()
        with c3:
            if st.button("X", key=f"dep_nor_{n_orden}", help="No retirado", use_container_width=True):
                if parcial:
                    st.warning(
                        "Si no se realizo el retiro, no corresponde registrar parcialidad. "
                        "La orden volvera a Pedido retiro."
                    )
                marcar_no_realizado(n_orden)
                st.warning("Orden devuelta a Pedido retiro.")
                st.rerun()


def bloque_parcialidad_programado(orden, tipo_parcialidad):
    n_orden = orden.get("n_orden")
    materiales = orden.get("materiales") or []
    with st.container(border=True, key=f"dep_parcial_bloque_{n_orden}"):
        st.caption(f"{tipo_parcialidad} activada")
        if not materiales:
            st.info("Esta orden no tiene materiales cargados. La nueva orden quedara sin materiales para revision manual.")
        else:
            resultado_materiales = operational_list_editor(
                title="Materiales de parcialidad",
                rows=filas_materiales_operativas(materiales, n_orden),
                mode="partial",
                show_unit=False,
                allow_delete=False,
                item_label="Material",
                help_text="Cargue la cantidad efectivamente entregada o retirada. El pendiente se copiara a la nueva orden.",
                save_label="Aplicar cantidades",
                embedded=True,
                key=f"dep_parcial_materiales_{n_orden}",
            )
            guardar_resultado_parcialidad(n_orden, resultado_materiales)

    return materiales_pendientes_desde_editor(orden)


def card_programado(orden):
    n_orden = orden.get("n_orden")
    estado = limpiar(orden.get("estado"))
    parcial_key = f"dep_prog_parcial_{n_orden}"
    parcial_actual = bool(st.session_state.get(parcial_key, False))

    if es_orden_stock(orden):
        title = f"Orden N\u00b0 {texto(n_orden)}"
        subtitle = "Destino: Deposito / Stock"
        descripcion = resumen_texto(orden.get("instrucciones_tarea"), 65)
        meta_extra = f"Tipo: {tipo_materiales_desde_obs_orden(orden) or '-'}"
    else:
        title = nombre_persona(orden) or f"Orden N\u00b0 {texto(n_orden)}"
        subtitle = f"Orden N\u00b0 {texto(n_orden)} - Expte. {texto(orden.get('expediente')) or '-'}"
        descripcion = resumen_texto(orden.get("instrucciones_tarea"), 65)
        meta_extra = domicilio_barrio(orden)

    variant = variante_estado_deposito(estado)

    if estado == "Pendiente de entrega":
        acciones = [
            {"label": "Completo", "key": "entregado", "kind": "success"},
            {"label": "No entregado", "key": "no_realizado", "kind": "danger"},
        ]
        parcial_label = "Entrega parcial"
    else:
        acciones = [
            {"label": "Entregado", "key": "entregado", "kind": "success"},
            {"label": "A deposito", "key": "a_deposito", "kind": "primary"},
            {"label": "No retirado", "key": "no_realizado", "kind": "danger"},
        ]
        parcial_label = "Retiro parcial"

    accion = operational_card(
        title=title,
        subtitle=subtitle,
        status=estado or None,
        priority=texto(orden.get("prioridad")) or None,
        meta=[
            f"Fecha: {fecha_visible(orden.get('fecha_entrega'))}",
            f"Origen: {texto(orden.get('origen')) or '-'}",
            meta_extra,
        ],
        description=descripcion,
        footer=None,
        variant=variant,
        accent_color=color_estado_deposito(estado),
        selectable=True,
        selected=parcial_actual,
        selectable_label=parcial_label,
        actions=acciones,
        actions_layout="corner",
        card_key=f"dep_programado_{n_orden}",
        key=f"dep_programado_{n_orden}",
    )
    accion = consumir_evento_card(accion, f"dep_programado_{n_orden}")

    if accion and accion.get("action") == "toggle_select":
        st.session_state[parcial_key] = bool(accion.get("selected"))
        parcial_actual = bool(accion.get("selected"))
        accion = None

    parcial = bool(st.session_state.get(parcial_key, parcial_actual))
    materiales_faltantes = []
    materiales_sin_detalle = False
    if parcial:
        materiales_faltantes, materiales_sin_detalle = bloque_parcialidad_programado(orden, parcial_label)

    if not accion:
        return

    accion_key = accion.get("action")
    accion_positiva = accion_key in {"entregado", "a_deposito"}
    if parcial and accion_positiva and (orden.get("materiales") or []) and not materiales_faltantes and not materiales_sin_detalle:
        st.warning(
            "La parcialidad no tiene materiales pendientes. "
            "Revise las cantidades o desmarque parcialidad para completar la orden."
        )
        return

    if accion_key == "entregado":
        marcar_entregado_desde_programados(
            n_orden,
            parcial=parcial,
            materiales_seleccionados_idx=[],
            materiales_faltantes=materiales_faltantes,
        )
        if parcial:
            st.success("Parcialidad registrada y nueva orden creada para revision manual.")
        else:
            st.success("Orden marcada como entregada.")
        st.rerun()

    if accion_key == "a_deposito":
        marcar_a_deposito_desde_programados(
            n_orden,
            parcial=parcial,
            materiales_seleccionados_idx=[],
            materiales_faltantes=materiales_faltantes,
        )
        if parcial:
            st.success("Retiro parcial a deposito registrado y nueva orden creada para revision manual.")
        else:
            st.success("Retiro completado. Materiales en deposito.")
        st.rerun()

    if accion_key == "no_realizado":
        if parcial:
            st.warning("Si no se realizo la operacion, no corresponde registrar parcialidad.")
        marcar_no_realizado(n_orden)
        st.warning("Orden devuelta al estado operativo anterior.")
        st.rerun()


def tab_programados():
    ordenes = listar_programados_deposito()
    if not ordenes:
        st.info("No hay ordenes programadas.")
        return

    agrupadas = {}
    for orden in ordenes:
        clave = limpiar(orden.get("fecha_entrega")) or "sin_fecha"
        agrupadas.setdefault(clave, []).append(orden)

    for fecha in sorted(agrupadas.keys()):
        titulo = "Sin fecha" if fecha == "sin_fecha" else fecha_visible(fecha)
        st.markdown(f"### {titulo}")
        for orden in agrupadas[fecha]:
            card_programado(orden)


def bloque_programados_compacto():
    ordenes = listar_programados_deposito()
    st.markdown('<div class="dep-section-title">Programadas</div>', unsafe_allow_html=True)
    st.markdown('<div class="dep-section-caption">Ordenes con fecha estimada para entrega o retiro</div>', unsafe_allow_html=True)

    if not ordenes:
        st.info("No hay ordenes programadas.")
        return

    agrupadas = {}
    for orden in ordenes:
        clave = limpiar(orden.get("fecha_entrega")) or "sin_fecha"
        agrupadas.setdefault(clave, []).append(orden)

    for fecha in sorted(agrupadas.keys()):
        titulo = "Sin fecha" if fecha == "sin_fecha" else fecha_visible(fecha)
        with st.expander(f"{titulo} ({len(agrupadas[fecha])})", expanded=True):
            for orden in agrupadas[fecha]:
                card_programado(orden)


def vista_programacion_ordenes():
    contexto_pedidos = preparar_pedidos_programables()

    col_pedidos, col_programadas = st.columns([0.55, 0.45], gap="medium")
    with col_pedidos:
        render_pedidos_programables_lista(contexto_pedidos)
    with col_programadas:
        bloque_programados_compacto()

    consultas_rapidas_deposito()


require_login(["deposito"])
cargar_estilos_deposito()
render_header_deposito()

vista_programacion_ordenes()
