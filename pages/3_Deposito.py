from datetime import date

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


ESTILOS_ESTADO = {
    "Pendiente de entrega": "🟧",
    "Pendiente de retiro": "🟨",
    "Pedido entrega": "⬜",
    "Pedido retiro": "⬜",
    "Pedido": "⬜",
    "En deposito": "🟦",
    "Entregado parcial": "🟪",
    "En deposito parcial": "🟪",
    "Entrega parcial": "🟪",
}

TIPOS_STOCK = {
    "gestion de stock",
    "compra para emergencias",
    "reposicion de deposito",
    "insumos internos",
    "herramientas / equipamiento",
}


def texto(valor):
    return "" if valor is None else str(valor)


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
    return f"{ESTILOS_ESTADO.get(estado, '⬛')} {estado}"


def aplicar_filtros_pedidos(ordenes):
    if not ordenes:
        return []

    df = pd.DataFrame(ordenes)
    with st.expander("Filtros", expanded=False):
        busqueda = st.text_input("Buscar", placeholder="N orden, expediente, apellido, nombre...")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            estados = sorted({limpiar(x) for x in df["estado"].dropna().tolist() if limpiar(x)})
            filtro_estado = st.multiselect("Estado", estados)
        with col2:
            barrios = sorted({limpiar(x) for x in df["barrio"].dropna().tolist() if limpiar(x)})
            filtro_barrio = st.multiselect("Barrio", barrios)
        with col3:
            origenes = sorted({limpiar(x) for x in df["origen"].dropna().tolist() if limpiar(x)})
            filtro_origen = st.multiselect("Origen", origenes)
        with col4:
            prioridades = sorted({limpiar(x) for x in df["prioridad"].dropna().tolist() if limpiar(x)})
            filtro_prioridad = st.multiselect("Prioridad", prioridades)

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
    with st.container(border=True):
        st.caption("Detalle de orden")
        st.write(f"ID demanda: {texto(orden.get('id_demanda'))}")
        st.write(f"DNI: {texto(orden.get('dni'))}")
        st.write(f"Contacto: {texto(orden.get('contacto'))}")
        st.write(f"Instruccion completa: {texto(orden.get('instrucciones_tarea'))}")
        try:
            materiales = listar_materiales_por_orden(orden.get("n_orden"))
        except Exception as error:
            st.error(f"No se pudieron cargar materiales: {error}")
            materiales = []

        st.caption("Materiales asociados")
        if materiales:
            st.dataframe(
                pd.DataFrame(materiales)[["Material", "cantidad"]],
                hide_index=True,
                use_container_width=True,
                height=180,
            )
        else:
            st.info("Esta orden no tiene materiales asociados.")

        historial = limpiar(orden.get("historial"))
        if historial:
            st.write("Historial:")
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
            st.markdown(f"**Orden N° {texto(n_orden)}**")
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
            if st.button("🔍", key=f"dep_btn_lupa_{n_orden}", help="Ver detalle"):
                st.session_state[clave_detalle] = not st.session_state.get(clave_detalle, False)
        if st.session_state.get(clave_detalle, False):
            mostrar_detalle_orden(orden)


def card_resumen_estado(orden):
    with st.container(border=True):
        st.markdown(f"**Orden N° {texto(orden.get('n_orden'))}**")
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


def tab_pedidos():
    ordenes = listar_pedidos_deposito()
    st.markdown("#### Ordenes pendientes programables")
    ordenes_filtradas = aplicar_filtros_pedidos(ordenes) if ordenes else []
    if not ordenes:
        st.info("No hay pedidos para programar.")
    elif not ordenes_filtradas:
        st.info("No hay pedidos que coincidan con los filtros.")
    else:
        st.caption("Seleccion multiple y programacion rapida")
        for orden in ordenes_filtradas:
            card_pedido(orden)

        st.divider()
        col_fecha, col_btn = st.columns([2, 1])
        with col_fecha:
            fecha_estimada = st.date_input("Fecha estimada", value=date.today(), format="DD/MM/YYYY")
        with col_btn:
            st.write("")
            programar = st.button("Programar seleccionadas", type="primary", use_container_width=True)

        if programar:
            ids = [
                orden.get("n_orden")
                for orden in ordenes_filtradas
                if st.session_state.get(f"dep_pedido_sel_{orden.get('n_orden')}", False)
            ]
            if not ids:
                st.warning("Selecciona al menos una orden.")
            else:
                try:
                    programar_ordenes_deposito(ids, fecha_estimada.isoformat())
                except Exception as error:
                    st.error(f"No se pudieron programar las ordenes: {error}")
                else:
                    st.success("Ordenes programadas correctamente.")
                    st.rerun()

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
            {"Entregado parcial", "En deposito parcial", "En depósito parcial", "Entrega parcial"}
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
            if st.button("✓", key=f"dep_ok_{n_orden}", help="Completado", use_container_width=True):
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
            if st.button("✓", key=f"dep_okr_{n_orden}", help="Completado", use_container_width=True):
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
            if st.button("🏠", key=f"dep_home_{n_orden}", help="A deposito", use_container_width=True):
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


def card_programado(orden):
    n_orden = orden.get("n_orden")
    with st.container(border=True):
        st.markdown(f"**Orden N° {texto(n_orden)}**")
        st.caption(
            f"{badge_estado(orden.get('estado'))} | Fecha: {fecha_visible(orden.get('fecha_entrega'))} | "
            f"Prioridad: {texto(orden.get('prioridad'))}"
        )
        st.write(f"Expte: {texto(orden.get('expediente'))}")
        if es_orden_stock(orden):
            st.write("Destino: Deposito / Stock")
            st.write(f"Tipo: {tipo_materiales_desde_obs_orden(orden) or 'Gestion de stock'}")
        else:
            st.write(f"Beneficiario: {nombre_persona(orden)}")
            st.write(f"Domicilio: {domicilio_barrio(orden)}")
            st.caption(f"Contacto: {texto(orden.get('contacto'))}")
        st.caption(f"Origen: {texto(orden.get('origen'))}")
        st.caption(f"Tarea: {texto(orden.get('instrucciones_tarea'))}")
        st.caption(f"Materiales: {resumen_materiales(orden)}")
        acciones_programado(orden)


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


st.set_page_config(page_title="Deposito", layout="wide")
st.title("Deposito")

tab_ped, tab_prog = st.tabs(["Pedidos", "Programados"])
with tab_ped:
    tab_pedidos()
with tab_prog:
    tab_programados()
