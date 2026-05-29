import pandas as pd
import streamlit as st
from datetime import datetime

from services.demandas_service import listar_demandas_abiertas
from services.materiales_base_service import listar_materiales_base_activos
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
    "Pedido entrega",
    "Pedido retiro",
    "Pendiente de retiro",
    "Pendiente de entrega",
    "En deposito",
    "Entrega parcial",
    "Entregado",
    "Cancelado",
]

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


def fecha_corta_visible(valor):
    valor = limpiar(valor)
    if not valor:
        return ""
    partes = valor[:10].split("-")
    if len(partes) == 3 and all(partes):
        return f"{partes[2]}/{partes[1]}/{partes[0][2:]}"
    return valor


def parsear_fecha_corta_ddmmaa(valor):
    valor = limpiar(valor)
    if not valor:
        return None
    try:
        fecha = datetime.strptime(valor, "%d/%m/%y").date()
    except ValueError:
        return None
    return fecha.isoformat()


def leyenda_fecha_entrega(estado):
    estado_limpio = limpiar(estado).lower()
    if estado_limpio == "pendiente de retiro":
        return "Fecha estimada de retiro:"
    if estado_limpio == "pendiente de entrega":
        return "Fecha estimada de entrega:"
    if estado_limpio == "en deposito":
        return "Retirado el dia:"
    if estado_limpio == "entregado":
        return "Fecha de entrega:"
    return ""


def mostrar_error_supabase(error):
    mensaje = str(error)
    if "row-level security" in mensaje:
        st.error(
            "Supabase no permite esta operacion con la anon key. "
            "Revisar las politicas RLS de la tabla correspondiente."
        )
        return
    st.error(f"No se pudo completar la operacion en Supabase: {mensaje}")


def formatear_cantidad(valor):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return ""
    if numero.is_integer():
        return str(int(numero))
    return f"{numero:.2f}".rstrip("0").rstrip(".")


@st.cache_data(ttl=300)
def cargar_opciones_materiales_base():
    materiales = listar_materiales_base_activos()
    opciones = []
    etiqueta_a_material = {}
    for item in materiales:
        material = limpiar(item.get("material"))
        if not material:
            continue
        tipo = limpiar(item.get("tipo"))
        unidad = limpiar(item.get("unidad"))
        partes = [material]
        if tipo:
            partes.append(tipo)
        if unidad:
            partes.append(unidad)
        etiqueta = " - ".join(partes)
        opciones.append(etiqueta)
        etiqueta_a_material[etiqueta] = material
    return opciones, etiqueta_a_material


def _key_materiales_tmp(prefijo):
    return f"{prefijo}_materiales_tmp"


def _key_material_select(prefijo):
    return f"{prefijo}_material_select"


def _key_cantidad_input(prefijo):
    return f"{prefijo}_cantidad_input"


def inicializar_materiales_tmp(prefijo):
    clave_lista = _key_materiales_tmp(prefijo)
    if clave_lista not in st.session_state:
        st.session_state[clave_lista] = []


def seleccionar_sugerencia_material(prefijo, material):
    st.session_state[_key_material_select(prefijo)] = material


def agregar_material_tmp(prefijo):
    opciones, etiqueta_a_material = cargar_opciones_materiales_base()
    seleccion = st.session_state.get(_key_material_select(prefijo))
    material = limpiar(etiqueta_a_material.get(seleccion, seleccion))
    cantidad = formatear_cantidad(st.session_state.get(_key_cantidad_input(prefijo)))
    if not material:
        return

    st.session_state[_key_materiales_tmp(prefijo)].append(
        {"Material": material, "cantidad": cantidad}
    )
    st.session_state[_key_material_select(prefijo)] = ""
    st.session_state[_key_cantidad_input(prefijo)] = 1.0


def quitar_material_tmp(prefijo, idx):
    materiales = st.session_state.get(_key_materiales_tmp(prefijo), [])
    if 0 <= idx < len(materiales):
        materiales.pop(idx)
        st.session_state[_key_materiales_tmp(prefijo)] = materiales


def limpiar_materiales_tmp(prefijo):
    st.session_state[_key_materiales_tmp(prefijo)] = []
    st.session_state[_key_material_select(prefijo)] = ""
    st.session_state[_key_cantidad_input(prefijo)] = 1.0


def editor_materiales_simple(prefijo, titulo):
    inicializar_materiales_tmp(prefijo)
    st.markdown(f"#### {titulo}")

    opciones, _ = cargar_opciones_materiales_base()
    st.selectbox(
        "Material",
        options=opciones,
        index=None,
        key=_key_material_select(prefijo),
        placeholder="Escriba para sugerir o cargue uno nuevo",
        accept_new_options=True,
        filter_mode="contains",
    )

    st.caption("Puede elegir sugerencia o escribir material nuevo.")

    col_cantidad, col_add = st.columns([2, 1])
    with col_cantidad:
        st.number_input(
            "Cantidad",
            min_value=0.0,
            step=1.0,
            format="%.2f",
            key=_key_cantidad_input(prefijo),
        )
    with col_add:
        st.write("")
        st.button(
            "Agregar material",
            key=f"{prefijo}_agregar_material",
            type="primary",
            use_container_width=True,
            on_click=agregar_material_tmp,
            args=(prefijo,),
        )

    materiales_tmp = st.session_state.get(_key_materiales_tmp(prefijo), [])
    if materiales_tmp:
        st.caption("Materiales a guardar")
        st.dataframe(
            pd.DataFrame(materiales_tmp)[["Material", "cantidad"]],
            hide_index=True,
            use_container_width=True,
            height=180,
        )
        for idx, material in enumerate(materiales_tmp):
            col_txt, col_btn = st.columns([4, 1])
            with col_txt:
                st.caption(f"{idx + 1}. {material.get('Material')} | {material.get('cantidad', '')}")
            with col_btn:
                st.button(
                    "Quitar",
                    key=f"{prefijo}_quitar_{idx}",
                    type="secondary",
                    use_container_width=True,
                    on_click=quitar_material_tmp,
                    args=(prefijo, idx),
                )
        st.button(
            "Limpiar lista",
            key=f"{prefijo}_limpiar_lista",
            type="secondary",
            use_container_width=True,
            on_click=limpiar_materiales_tmp,
            args=(prefijo,),
        )

    return st.session_state.get(_key_materiales_tmp(prefijo), [])


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
        height=240,
    )


def nombre_archivo_pdf(orden, demanda):
    expediente = limpiar(demanda.get("expediente")).replace("/", "-").replace("\\", "-")
    if not expediente:
        expediente = "sin-expediente"
    return f"orden_N{orden.get('n_orden')}_expte_{expediente}.pdf"


def beneficiario(demanda):
    nombre_completo = f"{texto(demanda.get('apellido'))}, {texto(demanda.get('nombre'))}".strip(", ")
    return nombre_completo if nombre_completo else "-"


def domicilio_completo(demanda):
    domicilio = limpiar(demanda.get("domicilio"))
    barrio = limpiar(demanda.get("barrio"))
    if domicilio and barrio:
        return f"{domicilio} - {barrio}"
    return domicilio or barrio or "-"


def tipo_materiales_desde_obs(demanda):
    obs = limpiar(demanda.get("observaciones"))
    prefijo = "tipo materiales:"
    if obs.lower().startswith(prefijo):
        resto = obs[len(prefijo):].strip()
        return resto.split(".")[0].strip()
    return ""


def es_demanda_stock(demanda):
    accion = limpiar(demanda.get("accion")).lower()
    if accion not in {"materiales", "entregar materiales"}:
        return False
    tipo = tipo_materiales_desde_obs(demanda).lower()
    return tipo in TIPOS_STOCK


def mostrar_card_operativa(orden, demanda):
    with st.container(border=True):
        col_orden, col_estado, col_fecha = st.columns([1.1, 1, 1])
        with col_orden:
            st.caption("Orden")
            st.markdown(f"**N° {texto(orden.get('n_orden'))}**")
        with col_estado:
            st.caption("Estado de la orden")
            st.write(texto(orden.get("estado")))
        with col_fecha:
            st.caption("Fecha de emision")
            st.write(fecha_visible(orden.get("fecha_emision")))
            leyenda_entrega = leyenda_fecha_entrega(orden.get("estado"))
            if leyenda_entrega:
                st.caption(leyenda_entrega)
                st.write(fecha_visible(orden.get("fecha_entrega")))

        st.divider()

        if es_demanda_stock(demanda):
            col_expte, col_destino, col_tipo = st.columns([1, 1, 2])
            with col_expte:
                st.caption("Expediente")
                st.markdown(f"**{texto(demanda.get('expediente'))}**")
            with col_destino:
                st.caption("Destino")
                st.write("Deposito / Stock")
            with col_tipo:
                st.caption("Tipo")
                st.write(tipo_materiales_desde_obs(demanda) or "Gestion de stock")
        else:
            col_expte, col_beneficiario, col_dni = st.columns([1, 2, 1])
            with col_expte:
                st.caption("Expediente")
                st.markdown(f"**{texto(demanda.get('expediente'))}**")
            with col_beneficiario:
                st.caption("Beneficiario")
                st.markdown(f"**{beneficiario(demanda)}**")
            with col_dni:
                st.caption("DNI")
                st.markdown(f"**{texto(demanda.get('dni'))}**")

            col_domicilio, col_contacto = st.columns([2, 1])
            with col_domicilio:
                st.caption("Domicilio")
                st.write(domicilio_completo(demanda))
            with col_contacto:
                st.caption("Contacto")
                st.write(texto(demanda.get("contacto")))

        st.divider()

        col_origen, col_prioridad, col_accion, col_responsable = st.columns(4)
        with col_origen:
            st.caption("Origen / autoriza")
            st.write(texto(orden.get("origen")))
        with col_prioridad:
            st.caption("Prioridad")
            st.write(texto(demanda.get("prioridad")))
        with col_accion:
            st.caption("Accion")
            st.write(texto(demanda.get("accion")))
        with col_responsable:
            st.caption("Responsable")
            st.write(texto(demanda.get("responsable")))


def mostrar_bloque_instruccion(orden):
    with st.container(border=True):
        st.markdown("#### Instruccion / tarea")
        st.write(texto(orden.get("instrucciones_tarea")))


def mostrar_bloque_materiales(n_orden):
    with st.container(border=True):
        st.markdown("#### Listado de materiales")
        mostrar_materiales_orden(n_orden)


def mostrar_bloque_historial(historial):
    with st.container(border=True, height=260):
        st.markdown("#### Historial")
        entradas = [limpiar(entrada) for entrada in texto(historial).split("||") if limpiar(entrada)]
        if not entradas:
            st.info("Sin historial registrado.")
            return
        for entrada in entradas:
            st.write(entrada)
            st.divider()


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

    if es_demanda_stock(demanda):
        col_1, col_2, col_3, col_4 = st.columns(4)
        with col_1:
            st.metric("ID demanda", texto(demanda.get("id_demanda")))
            st.caption(f"Expte: {texto(demanda.get('expediente'))}")
        with col_2:
            st.write("**Destino:** Deposito / Stock")
            st.caption(f"Tipo: {tipo_materiales_desde_obs(demanda) or 'Gestion de stock'}")
        with col_3:
            st.write(f"**Origen:** {texto(demanda.get('origen'))}")
            st.caption(f"Prioridad: {texto(demanda.get('prioridad'))}")
        with col_4:
            st.write(f"**Accion:** {texto(demanda.get('accion'))}")
            st.caption(f"Responsable: {texto(demanda.get('responsable'))}")
    else:
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


def nueva_orden_tab():
    demandas = listar_demandas_abiertas()
    demandas = [
        demanda
        for demanda in demandas
        if limpiar(demanda.get("accion")).lower() in {"obra", "emergencia", "emerencia"} or es_demanda_stock(demanda)
    ]
    if not demandas:
        st.info("No hay demandas abiertas con accion Obra/Emergencia para vincular una orden.")
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
    estado_default = "Pedido retiro" if es_demanda_stock(demanda) else "Pedido entrega"
    estado = st.selectbox("Estado inicial", ESTADOS_ORDEN, index=ESTADOS_ORDEN.index(estado_default))

    agregar_materiales = st.checkbox("Agregar materiales asociados")
    materiales_nuevos = []
    if agregar_materiales:
        materiales_nuevos = editor_materiales_simple(
            "nueva_orden", "Materiales asociados a la orden (opcional)"
        )

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
            if orden and materiales_nuevos:
                crear_materiales_orden(orden["n_orden"], materiales_nuevos)
                limpiar_materiales_tmp("nueva_orden")
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
    with st.expander("Filtros", expanded=False):
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
    incluir_cerradas = st.toggle("Incluir cerradas", value=False)
    ordenes = listar_ordenes_con_demanda(incluir_cerradas=incluir_cerradas)
    if not ordenes:
        if incluir_cerradas:
            st.info("No hay ordenes para mostrar.")
        else:
            st.info("No hay ordenes pendientes.")
        return

    df = pd.DataFrame(ordenes)
    df["beneficiario"] = df.apply(
        lambda fila: f"{texto(fila.get('apellido'))}, {texto(fila.get('nombre'))}".strip(", "),
        axis=1,
    )
    df_filtrado = aplicar_filtros_ordenes(df)
    if df_filtrado.empty:
        st.info("No hay ordenes que coincidan con los filtros.")
        return

    columnas = [
        "n_orden",
        "fecha_emision",
        "id_demanda",
        "expediente",
        "beneficiario",
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
        height=240,
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

    st.divider()
    st.markdown(f"### Orden seleccionada N° {texto(orden.get('n_orden'))}")

    col_info, col_acciones = st.columns([2, 1])
    with col_info:
        mostrar_card_operativa(orden, demanda)
        mostrar_bloque_instruccion(orden)
        mostrar_bloque_materiales(orden.get("n_orden"))
        mostrar_bloque_historial(orden.get("historial"))

    with col_acciones:
        st.markdown("#### Acciones")
        if orden.get("fecha_cierre") or orden.get("estado") in ESTADOS_CIERRE:
            st.warning("Esta orden esta cerrada y no se puede editar.")
            return

        agregar_materiales = st.checkbox("Agregar nuevos materiales")
        materiales_nuevos = []
        if agregar_materiales:
            materiales_nuevos = editor_materiales_simple(
                f"orden_{orden.get('n_orden')}", "Agregar materiales a esta orden"
            )

        with st.container(border=True):
            st.markdown("##### Actualizar orden")
            estado_actual = orden.get("estado") if orden.get("estado") in ESTADOS_ORDEN else "Pedido entrega"
            clave_estado = f"estado_orden_{orden.get('n_orden')}"
            if clave_estado not in st.session_state:
                st.session_state[clave_estado] = estado_actual
            nuevo_estado = st.selectbox(
                "Estado",
                ESTADOS_ORDEN,
                index=ESTADOS_ORDEN.index(st.session_state[clave_estado]),
                key=clave_estado,
            )

            with st.form("actualizar_orden_material_form"):
                fecha_entrega_ingresada = ""
                if nuevo_estado not in {"Pedido entrega", "Pedido retiro"}:
                    fecha_entrega_ingresada = st.text_input(
                        "Fecha de entrega (DD/MM/AA)",
                        value=fecha_corta_visible(orden.get("fecha_entrega")),
                        placeholder="28/05/26",
                    )
                comentario = st.text_area(
                    "Comentario para historial",
                    height=100,
                    placeholder="Se coordina retiro con deposito.",
                )
                actualizar = st.form_submit_button("Actualizar orden", type="primary", use_container_width=True)

        st.divider()
        st.markdown("##### Descarga / emitir")
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

        st.divider()
        st.markdown("#### Zona de peligro")
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
        fecha_entrega_iso = parsear_fecha_corta_ddmmaa(fecha_entrega_ingresada)
        fecha_entrega_actual_iso = limpiar(orden.get("fecha_entrega")) or None
        fecha_entrega_cambio = fecha_entrega_iso != fecha_entrega_actual_iso
        estado_cambio = nuevo_estado != estado_actual

        if nuevo_estado in {"Pedido entrega", "Pedido retiro"}:
            fecha_entrega_iso = None
            fecha_entrega_cambio = fecha_entrega_actual_iso is not None

        if estado_cambio and nuevo_estado not in {"Pedido entrega", "Pedido retiro"} and not fecha_entrega_iso:
            st.warning("Cuando cambia el estado debes cargar la fecha de entrega en formato DD/MM/AA.")
            return

        if nuevo_estado not in {"Pedido entrega", "Pedido retiro"} and limpiar(fecha_entrega_ingresada) and not fecha_entrega_iso:
            st.warning("Fecha invalida. Usa formato DD/MM/AA, por ejemplo 28/05/26.")
            return

        if not estado_cambio and not limpiar(comentario) and not materiales_nuevos and not fecha_entrega_cambio:
            st.warning("No hay cambios para actualizar.")
            return
        try:
            if estado_cambio or limpiar(comentario) or fecha_entrega_cambio:
                actualizar_orden_material(
                    orden["n_orden"],
                    nuevo_estado,
                    comentario,
                    fecha_entrega=fecha_entrega_iso,
                )
            if materiales_nuevos:
                crear_materiales_orden(orden["n_orden"], materiales_nuevos)
                limpiar_materiales_tmp(f"orden_{orden.get('n_orden')}")
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
    tab_nueva, tab_seguimiento = st.tabs(["Nueva orden", "Seguimiento de ordenes"])
    with tab_nueva:
        nueva_orden_tab()
    with tab_seguimiento:
        seguimiento_ordenes_tab()


st.set_page_config(page_title="Obras", layout="wide")
st.title("Obras")

seccion = st.tabs(["Ordenes"])
with seccion[0]:
    ordenes_section()


