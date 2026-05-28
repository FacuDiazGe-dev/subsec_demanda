import pandas as pd
import streamlit as st

from services.demandas_service import listar_demandas_abiertas
from services.materiales_orden_service import (
    crear_materiales_orden,
    eliminar_materiales_por_orden,
    listar_materiales_por_orden,
)
from services.ordenes_service import (
    ESTADOS_CIERRE,
    actualizar_orden_material,
    crear_orden_material,
    eliminar_orden_material,
    listar_ordenes_con_demanda,
    obtener_datos_pdf_orden,
)
from services.pdf_orden_service import generar_pdf_orden


ESTADOS_ORDEN = [
    "Pedido",
    "Pendiente de retiro",
    "Pendiente de entrega",
    "En depósito",
    "Entregado",
    "Cancelado",
]


def texto(valor):
    return "" if valor is None else str(valor)


def limpiar(valor):
    return texto(valor).strip()


def mostrar_error_supabase(error):
    mensaje = str(error)
    if "row-level security" in mensaje:
        st.error(
            "Supabase no permite esta operacion con la anon key. "
            "Revisar las politicas RLS de la tabla correspondiente."
        )
        return
    st.error(f"No se pudo completar la operacion en Supabase: {mensaje}")


def limpiar_materiales_df(materiales_df):
    if materiales_df is None or materiales_df.empty:
        return []

    materiales = []
    for material in materiales_df.to_dict("records"):
        nombre = limpiar(material.get("Material"))
        cantidad = limpiar(material.get("cantidad"))
        if nombre:
            materiales.append({"Material": nombre, "cantidad": cantidad})
    return materiales


def editor_materiales(key):
    return st.data_editor(
        pd.DataFrame([{"Material": "", "cantidad": ""}]),
        key=key,
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Material": st.column_config.TextColumn("Material", required=False),
            "cantidad": st.column_config.TextColumn("Cantidad", required=False),
        },
    )


def mostrar_materiales_orden(n_orden):
    try:
        materiales = listar_materiales_por_orden(n_orden)
    except Exception as error:
        mostrar_error_supabase(error)
        return

    if not materiales:
        st.info("Esta orden no tiene materiales asociados.")
        return

    st.dataframe(
        pd.DataFrame(materiales)[["Material", "cantidad"]],
        use_container_width=True,
        hide_index=True,
    )


def nombre_archivo_pdf(orden, demanda):
    expediente = limpiar(demanda.get("expediente")).replace("/", "-").replace("\\", "-")
    if not expediente:
        expediente = "sin-expediente"
    return f"orden_N{orden.get('n_orden')}_expte_{expediente}.pdf"


def etiqueta_demanda(demanda):
    return (
        f"ID {demanda.get('id_demanda')} | "
        f"Expte {texto(demanda.get('expediente'))} | "
        f"{texto(demanda.get('apellido'))}, {texto(demanda.get('nombre'))} | "
        f"{texto(demanda.get('barrio'))} | "
        f"{texto(demanda.get('accion'))} | "
        f"{texto(demanda.get('estado'))}"
    )


def mostrar_ficha_demanda(demanda):
    if not demanda:
        st.warning("No se encontraron datos de la demanda vinculada.")
        return

    col_1, col_2, col_3, col_4 = st.columns(4)
    with col_1:
        st.metric("ID demanda", texto(demanda.get("id_demanda")))
        st.caption(f"Expte: {texto(demanda.get('expediente'))}")
    with col_2:
        st.write(f"**Persona:** {texto(demanda.get('apellido'))}, {texto(demanda.get('nombre'))}")
        st.caption(f"DNI: {texto(demanda.get('dni'))}")
    with col_3:
        st.write(f"**Domicilio:** {texto(demanda.get('domicilio'))}")
        st.caption(f"Barrio: {texto(demanda.get('barrio'))}")
    with col_4:
        st.write(f"**Contacto:** {texto(demanda.get('contacto'))}")
        st.caption(f"Responsable: {texto(demanda.get('responsable'))}")

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.caption(f"Origen: {texto(demanda.get('origen'))}")
    with col_b:
        st.caption(f"Prioridad: {texto(demanda.get('prioridad'))}")
    with col_c:
        st.caption(f"Accion: {texto(demanda.get('accion'))}")
    with col_d:
        st.caption(f"Estado: {texto(demanda.get('estado'))}")
    st.caption(f"Tipo intervencion: {texto(demanda.get('tipo_intervencion'))}")


def nueva_orden_tab():
    demandas = listar_demandas_abiertas()
    if not demandas:
        st.info("No hay demandas abiertas disponibles para vincular una orden.")
        return

    opciones = {etiqueta_demanda(demanda): demanda for demanda in demandas}
    seleccion = st.selectbox("Demanda vinculada", list(opciones.keys()))
    demanda = opciones[seleccion]

    st.markdown("#### Referencia de demanda")
    mostrar_ficha_demanda(demanda)

    instrucciones_tarea = st.text_area(
        "Instrucciones de tarea",
        height=120,
        placeholder="Retirar de Corralon Brito y llevar a deposito.",
    )
    estado = st.selectbox("Estado inicial", ESTADOS_ORDEN, index=ESTADOS_ORDEN.index("Pedido"))

    agregar_materiales = st.checkbox("Agregar materiales asociados")
    materiales_df = None
    if agregar_materiales:
        st.markdown("#### Materiales asociados a la orden")
        materiales_df = editor_materiales("materiales_nueva_orden")

    crear = st.button("Crear orden", type="primary", use_container_width=True)

    if crear:
        if not limpiar(instrucciones_tarea):
            st.error("Completa las instrucciones de tarea antes de crear la orden.")
            return

        try:
            orden = crear_orden_material(
                {
                    "id_demanda": demanda.get("id_demanda"),
                    "origen": demanda.get("origen"),
                    "estado": estado,
                    "instrucciones_tarea": instrucciones_tarea,
                }
            )
            materiales = limpiar_materiales_df(materiales_df)
            if orden and materiales:
                crear_materiales_orden(orden["n_orden"], materiales)
        except Exception as error:
            mostrar_error_supabase(error)
            return

        st.success(f"Orden creada correctamente. N orden: {orden.get('n_orden') if orden else ''}")


def opciones_filtro(df, columna):
    if columna not in df.columns:
        return []
    valores = [limpiar(valor) for valor in df[columna].dropna().tolist()]
    return sorted({valor for valor in valores if valor})


def aplicar_filtros_ordenes(df):
    with st.expander("Filtros", expanded=True):
        busqueda = st.text_input("Buscar", placeholder="N orden, ID demanda, expediente, apellido, nombre...")
        col_1, col_2, col_3 = st.columns(3)
        with col_1:
            filtro_estado = st.multiselect("Estado", opciones_filtro(df, "estado"))
        with col_2:
            filtro_origen = st.multiselect("Origen", opciones_filtro(df, "origen"))
        with col_3:
            filtro_barrio = st.multiselect("Barrio", opciones_filtro(df, "barrio"))

    filtrado = df.copy()
    filtros = {
        "estado": filtro_estado,
        "origen": filtro_origen,
        "barrio": filtro_barrio,
    }
    for columna, valores in filtros.items():
        if valores and columna in filtrado.columns:
            filtrado = filtrado[filtrado[columna].fillna("").astype(str).isin(valores)]

    busqueda = limpiar(busqueda).lower()
    if busqueda:
        columnas_busqueda = [
            "n_orden",
            "id_demanda",
            "expediente",
            "apellido",
            "nombre",
            "barrio",
            "estado",
            "origen",
            "instrucciones_tarea",
        ]
        columnas_busqueda = [col for col in columnas_busqueda if col in filtrado.columns]
        mascara = (
            filtrado[columnas_busqueda]
            .fillna("")
            .astype(str)
            .agg(" ".join, axis=1)
            .str.lower()
            .str.contains(busqueda, regex=False)
        )
        filtrado = filtrado[mascara]

    return filtrado


def seguimiento_ordenes_tab():
    ordenes = listar_ordenes_con_demanda()
    if not ordenes:
        st.info("No hay ordenes pendientes.")
        return

    df = pd.DataFrame(ordenes)
    df_filtrado = aplicar_filtros_ordenes(df)
    if df_filtrado.empty:
        st.info("No hay ordenes que coincidan con los filtros.")
        return

    columnas = [
        "n_orden",
        "fecha_emision",
        "id_demanda",
        "expediente",
        "apellido",
        "nombre",
        "barrio",
        "origen",
        "estado",
        "instrucciones_tarea",
    ]
    columnas_visibles = [col for col in columnas if col in df_filtrado.columns]
    seleccion_tabla = st.dataframe(
        df_filtrado[columnas_visibles],
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="tabla_ordenes_pendientes",
    )

    filas = seleccion_tabla.selection.rows
    if not filas:
        st.info("Selecciona una orden desde la tabla para editarla.")
        return

    orden = df_filtrado.iloc[filas[0]].to_dict()
    demanda = orden.get("demanda") or {}

    st.markdown("#### Detalle de orden")
    col_1, col_2, col_3 = st.columns(3)
    with col_1:
        st.metric("N orden", texto(orden.get("n_orden")))
    with col_2:
        st.metric("Estado", texto(orden.get("estado")))
    with col_3:
        st.metric("Fecha emision", texto(orden.get("fecha_emision")))

    st.write(f"**Instrucciones:** {texto(orden.get('instrucciones_tarea'))}")
    st.text_area("Historial", value=texto(orden.get("historial")), height=130, disabled=True)

    st.markdown("#### Materiales asociados")
    mostrar_materiales_orden(orden.get("n_orden"))

    try:
        datos_pdf = obtener_datos_pdf_orden(orden.get("n_orden"))
        if datos_pdf:
            pdf_bytes = generar_pdf_orden(
                datos_pdf["orden"],
                datos_pdf["demanda"],
                datos_pdf["materiales"],
            )
            st.download_button(
                label="Descargar orden PDF",
                data=pdf_bytes,
                file_name=nombre_archivo_pdf(datos_pdf["orden"], datos_pdf["demanda"]),
                mime="application/pdf",
                use_container_width=True,
            )
    except Exception as error:
        mostrar_error_supabase(error)

    st.markdown("#### Demanda vinculada")
    mostrar_ficha_demanda(demanda)

    if orden.get("fecha_cierre") or orden.get("estado") in ESTADOS_CIERRE:
        st.warning("Esta orden esta cerrada y no se puede editar.")
        return

    agregar_materiales = st.checkbox("Agregar nuevos materiales")
    materiales_nuevos_df = None
    if agregar_materiales:
        materiales_nuevos_df = editor_materiales("materiales_orden_existente")

    with st.form("actualizar_orden_material_form"):
        estado_actual = orden.get("estado") if orden.get("estado") in ESTADOS_ORDEN else "Pedido"
        nuevo_estado = st.selectbox("Estado", ESTADOS_ORDEN, index=ESTADOS_ORDEN.index(estado_actual))
        comentario = st.text_area(
            "Comentario para historial",
            height=100,
            placeholder="Se coordina retiro con deposito.",
        )
        actualizar = st.form_submit_button("Actualizar orden", type="primary", use_container_width=True)

    st.markdown("#### Eliminar orden")
    confirmar_eliminacion = st.checkbox(
        f"Confirmo que quiero eliminar la orden {orden.get('n_orden')}",
        key=f"confirmar_eliminar_orden_{orden.get('n_orden')}",
    )
    eliminar = st.button(
        "Eliminar orden seleccionada",
        disabled=not confirmar_eliminacion,
        type="secondary",
        use_container_width=True,
    )

    if actualizar:
        materiales_nuevos = limpiar_materiales_df(materiales_nuevos_df)
        if nuevo_estado == estado_actual and not limpiar(comentario) and not materiales_nuevos:
            st.warning("No hay cambios para actualizar.")
            return
        try:
            if nuevo_estado != estado_actual or limpiar(comentario):
                actualizar_orden_material(orden["n_orden"], nuevo_estado, comentario)
            if materiales_nuevos:
                crear_materiales_orden(orden["n_orden"], materiales_nuevos)
        except Exception as error:
            mostrar_error_supabase(error)
            return
        st.success("Orden actualizada correctamente.")
        st.rerun()

    if eliminar:
        try:
            eliminar_materiales_por_orden(orden["n_orden"])
            eliminar_orden_material(orden["n_orden"])
        except Exception as error:
            mostrar_error_supabase(error)
            return
        st.success("Orden eliminada correctamente.")
        st.rerun()


def ordenes_section():
    tab_nueva, tab_seguimiento = st.tabs(["Nueva orden", "Seguimiento de órdenes"])
    with tab_nueva:
        nueva_orden_tab()
    with tab_seguimiento:
        seguimiento_ordenes_tab()


st.set_page_config(page_title="Obras", layout="wide")
st.title("Obras")

seccion = st.tabs(["Órdenes"])
with seccion[0]:
    ordenes_section()
