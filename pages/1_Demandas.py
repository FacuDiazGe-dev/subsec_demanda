from datetime import date
import re

import pandas as pd
import streamlit as st

from utils.ui_styles import (
    aplicar_estilos_globales,
    page_header,
    section_header,
    prioridad_badge,
    estado_badge,
)

from services.demandas_service import (
    actualizar_demanda,
    cerrar_demanda,
    crear_demanda,
    listar_demandas_pendientes,
)
from services.sociohabitacional_service import obtener_estados_por_accion
from services.expedientes_service import buscar_expediente


ORIGENES = [
    "Subdirectora",
    "Area administrativa",
    "Subsecretaria",
    "Secretaria",
    "Secretaria de Gobierno",
    "Intendenta",
    "Noguera",
    "Orden judicial",
    "Defensoria del Pueblo",
    "Vecino / consulta directa",
    "Equipo tecnico",
    "Deposito",
    "Cuadrilla",
    "Otro",
]

PRIORIDADES = [
    "1 - Urgente",
    "2 - Prioritario",
    "3 - Normal",
    "4 - Bajo",
    "5 - En espera",
]

ACCIONES = [
    "Visitar",
    "Hacer nota",
    "Actuacion",
    "Obra",
    "Entregar materiales",
    "Informe",
    "Seguimiento",
    "Emergencia",
    "Otro",
]

TIPOS_MATERIALES = [
    "Gestion de stock",
    "Compra para emergencias",
    "Reposicion de deposito",
    "Insumos internos",
    "Herramientas / equipamiento",
    "Otro",
]

TIPOS_STOCK = {
    "gestion de stock",
    "compra para emergencias",
    "reposicion de deposito",
    "insumos internos",
    "herramientas / equipamiento",
}

RESPONSABLES = ["Facundo", "Pedro", "Guillo", "Bea", "Iris", "Deposito"]

ESTADOS_POR_ACCION = {
    "Visitar": [
        "Pendiente",
        "Para visita",
        "Visita programada",
        "Visita Social",
        "Visita Tecnica",
        "Visitado",
        "Informe Social",
        "Informe Tecnico",
        "Completo",
        "Cerrado",
    ],
    "Hacer nota": ["Pendiente", "Para Hacer", "En elaboración", "Presentado", "Cerrado"],
    "Actuacion": ["Pendiente", "Para Hacer", "En elaboración", "Presentado", "Cerrado"],
    "Obra": [
        "Sin acta",
        "Acta compromiso / inicio firmada",
        "Para iniciar obra",
        "En ejecucion",
        "Suspendida",
        "Ejecutada",
        "Acta de fin pendiente",
        "Fin de obra",
        "Cerrado",
    ],
    "Emergencia": [
        "Ingresada",
        "Visita programada",
        "Relevado",
        "Informe de emergencia",
        "Intervencion",
        "Resuelta",
        "Derivada",
        "Cerrado",
    ],
    "Entregar materiales": [
        "Solicitud recibida",
        "En gestion",
        "Autorizacion recibida",
        "Pendiente de entrega",
        "Entrega programada",
        "Materiales entregados",
        "Firma pendiente",
        "Cerrado",
    ],
    "Informe": ["Pendiente", "Para Hacer", "En elaboración", "Presentado", "Cerrado"],
    "Seguimiento": ["Pendiente", "Para Hacer", "En elaboración", "Presentado", "Cerrado"],
    "Otro": ["Pendiente", "Para Hacer", "En elaboración", "Presentado", "Cerrado"],
}


def texto(valor):
    return "" if valor is None else str(valor)


def limpiar(valor):
    return texto(valor).strip()

def fecha_corta(v):
    v = limpiar(v)
    if not v:
        return "-"
    p = v[:10].split("-")
    # Convierte YYYY-MM-DD a DD/MM/AA
    return f"{p[2]}/{p[1]}/{p[0][2:]}" if len(p) == 3 else v

def parsear_expediente(valor):
    valor = limpiar(valor)
    match = re.search(r"(\d{1,})\s*(?:/\s*[A-Za-z])?\s*/\s*(\d{2,4})", valor)
    if not match:
        return "", "", ""

    numero = match.group(1).lstrip("0") or match.group(1)
    anio = match.group(2)
    if len(anio) == 2:
        anio = f"20{anio}"
    return numero, anio, f"{numero}/{anio}"


def mostrar_error_supabase(error):
    mensaje = str(error)
    if "row-level security" in mensaje:
        st.error(
            "Supabase no permite esta operacion con la anon key. "
            "Revisar las politicas RLS de la tabla demandas."
        )
        return
    st.error(f"No se pudo completar la operacion en Supabase: {mensaje}")


def inicializar_carga():
    defaults = {
        "carga_expediente": "",
        "carga_pedido": "",
    }

    if st.session_state.pop("limpiar_carga_pendiente", False):
        for key in defaults:
            st.session_state[key] = ""
        st.session_state.pop("expediente_carga", None)
        st.session_state.pop("busqueda_carga_realizada", None)

    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    if st.session_state.pop("demanda_guardada", False):
        st.success(st.session_state.pop("mensaje_demanda_guardada", "Demanda guardada correctamente."))


def cargar_datos_expediente(expediente):
    st.session_state["expediente_carga"] = expediente


def valor_personal(expediente, columna_expte):
    if expediente:
        return limpiar(expediente.get(columna_expte)) or None
    return None


def limpiar_carga():
    for key in [
        "carga_expediente",
        "carga_pedido",
    ]:
        st.session_state[key] = ""
    st.session_state.pop("expediente_carga", None)
    st.session_state.pop("busqueda_carga_realizada", None)


def cargar_demanda_tab():
    inicializar_carga()
    section_header(
    "Nueva demanda",    
        "Registrá una solicitud nueva a partir de expediente, pedido recibido y clasificación inicial.",
    )

    st.text_input("Expediente", key="carga_expediente", placeholder="20373/24")

    st.text_area(
        "Pedido",
        key="carga_pedido",
        height=95,
        placeholder="Texto que llega por mensaje, llamada o resumen breve.",
    )

    col_accion, col_origen, col_responsable = st.columns(3)
    with col_accion:
        accion = st.selectbox("Accion", ACCIONES)
    with col_origen:
        origen = st.selectbox("Origen", ORIGENES, index=0)
    with col_responsable:
        responsable = st.selectbox("Responsable", [""] + RESPONSABLES)

    tipo_materiales = None
    if accion == "Entregar materiales":
        tipo_materiales = st.selectbox("Tipo (Materiales)", TIPOS_MATERIALES)

    col_guardar, col_limpiar = st.columns([2, 1])
    with col_guardar:
        guardar = st.button("Guardar demanda", type="primary", use_container_width=True)
    with col_limpiar:
        st.button("Limpiar", use_container_width=True, on_click=limpiar_carga)

    if guardar:
        expte_numero, expte_anio, expediente_texto = parsear_expediente(st.session_state["carga_expediente"])
        pedido = limpiar(st.session_state["carga_pedido"])
        tipo_materiales_txt = limpiar(tipo_materiales)
        es_stock = (
            accion == "Entregar materiales"
            and tipo_materiales_txt.lower() in TIPOS_STOCK
        )

        if not expediente_texto and not es_stock:
            st.error("Carga el expediente con formato numero/anio, por ejemplo 20373/24.")
            return

        if not pedido:
            st.error("Completa el pedido antes de guardar.")
            return

        if es_stock:
            expediente = None
            expte_numero = None
            expte_anio = None
            expediente_texto = "DEP/STOCK"
        else:
            expediente = buscar_expediente(expte_numero, expte_anio)

        observaciones = pedido
        if accion == "Entregar materiales" and tipo_materiales_txt:
            observaciones = f"Tipo materiales: {tipo_materiales_txt}. Pedido: {pedido}"

        datos = {
            "fecha_ingreso": date.today().isoformat(),
            "origen": origen,
            "prioridad": "3 - Normal",
            "expte_numero": expte_numero or None,
            "expte_anio": expte_anio or None,
            "expediente": expediente_texto,
            "apellido": valor_personal(expediente, "apellido"),
            "nombre": valor_personal(expediente, "nombre"),
            "dni": valor_personal(expediente, "dni"),
            "domicilio": valor_personal(expediente, "direccion"),
            "barrio": valor_personal(expediente, "barrio"),
            "contacto": valor_personal(expediente, "contacto"),
            "accion": accion,
            "estado": "Ingresada",
            "responsable": responsable or None,
            "observaciones": observaciones,
        }
        try:
            crear_demanda(datos)
        except Exception as error:
            mostrar_error_supabase(error)
            return
        st.session_state["demanda_guardada"] = True
        if expediente:
            st.session_state["mensaje_demanda_guardada"] = "Demanda guardada con datos del expediente."
        else:
            st.session_state["mensaje_demanda_guardada"] = (
                "Demanda guardada. No se encontro el expediente en la base general; "
                "los datos personales quedaron vacios o con la carga manual."
            )
        st.session_state["limpiar_carga_pendiente"] = True
        st.rerun()


def estados_para_demanda(demanda):
    accion = demanda.get("accion")
    return accion, obtener_estados_por_accion(accion)

def valor_para_historial(valor):
    valor = limpiar(valor)
    return valor if valor else "(vacio)"


def detectar_cambios(demanda, nuevos_valores):
    etiquetas = {
        "estado": "Estado",
        "prioridad": "Prioridad",
        "responsable": "Responsable",
    }
    cambios = []
    for campo, etiqueta in etiquetas.items():
        anterior = limpiar(demanda.get(campo))
        nuevo = limpiar(nuevos_valores.get(campo))
        if anterior != nuevo:
            cambios.append(f"{etiqueta}: {valor_para_historial(anterior)} -> {valor_para_historial(nuevo)}")

    campos_personales = ["apellido", "nombre", "dni", "domicilio", "barrio", "contacto"]
    if any(limpiar(demanda.get(campo)) != limpiar(nuevos_valores.get(campo)) for campo in campos_personales):
        cambios.append("Cambio en datos personales")

    return cambios


def agregar_al_historial(historial_actual, nueva_accion, cambios):
    historial_actual = limpiar(historial_actual)
    partes = []

    nueva_accion = limpiar(nueva_accion)
    if nueva_accion:
        partes.append(f"Actualizacion: {nueva_accion}")
    partes.extend(cambios)

    if not partes:
        return historial_actual or None

    hoy = date.today().strftime('%d/%m/%y')
    texto_cambios = "; ".join(partes)
    # Unificamos al formato usado en SocioHabitacional: || DD/MM/AA - cambios.
    nueva_entrada = f"|| {hoy} - {texto_cambios}."
    return f"{nueva_entrada} {historial_actual}".strip()

def opciones_filtro(df, columna):
    if columna not in df.columns:
        return []
    valores = [limpiar(valor) for valor in df[columna].dropna().tolist()]
    return sorted({valor for valor in valores if valor})

def render_demandas_kpis(df):
    """Muestra los indicadores superiores calculados del DataFrame actual."""
    total = len(df)
    
    # En gestión: distinto de Pendiente, Ingresada, Cerrado
    en_gestion = 0
    if "estado" in df.columns:
        estados_iniciales = {"Pendiente", "Ingresada", "Cerrado", "Cerrada"}
        en_gestion = df[~df["estado"].fillna("").isin(estados_iniciales)].shape[0]
        
    # Urgentes/Prioritarias: empieza con 1 o 2
    urgentes = 0
    if "prioridad" in df.columns:
        urgentes = df["prioridad"].fillna("").astype(str).str.contains(r"^[12]", regex=True).sum()
        
    # Sin responsable
    sin_resp = 0
    if "responsable" in df.columns:
        sin_resp = df[df["responsable"].fillna("").str.strip() == ""].shape[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pendientes", total)
    c2.metric("En gestión", en_gestion)
    c3.metric("Urgentes/Prioritarias", urgentes)
    c4.metric("Sin responsable", sin_resp)

def render_filtros_demandas_compactos(df):
    """Barra de filtros horizontal y compacta."""
    if df.empty:
        return df, False

    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([2, 1.2, 1.2, 1.2, 0.6])
        with c1:
            q = st.text_input("Buscador", placeholder="Expediente, nombre, barrio...", label_visibility="collapsed")
        with c2:
            f_estado = st.multiselect("Estado", opciones_filtro(df, "estado"), placeholder="Estado", label_visibility="collapsed")
        with c3:
            f_prioridad = st.multiselect("Prioridad", opciones_filtro(df, "prioridad"), placeholder="Prioridad", label_visibility="collapsed")
        with c4:
            f_accion = st.multiselect("Acción", opciones_filtro(df, "accion"), placeholder="Acción", label_visibility="collapsed")
        with c5:
            limpiar_f = st.button("🔄", help="Limpiar filtros", use_container_width=True)

    if limpiar_f:
        st.rerun()

    filtrado = df.copy()
    filtros = {"estado": f_estado, "prioridad": f_prioridad, "accion": f_accion}
    for columna, valores in filtros.items():
        if valores and columna in filtrado.columns:
            filtrado = filtrado[filtrado[columna].fillna("").astype(str).isin(valores)]

    q = limpiar(q).lower()
    if q:
        columnas_busqueda = ["id_demanda", "expediente", "apellido", "nombre", "barrio", "domicilio", "observaciones", "accion"]
        columnas_busqueda = [col for col in columnas_busqueda if col in filtrado.columns]
        mascara = filtrado[columnas_busqueda].fillna("").astype(str).agg(" ".join, axis=1).str.lower().str.contains(q, regex=False)
        filtrado = filtrado[mascara]

    return filtrado

def pendientes_tab():
    demandas = listar_demandas_pendientes()
    if not demandas:
        st.info("No hay demandas pendientes.")
        return
    df = pd.DataFrame(demandas)

    # 1. KPIs Superiores
    render_demandas_kpis(df)

    # 2. Filtros Compactos
    df_filtrado = render_filtros_demandas_compactos(df)

    if df_filtrado.empty:
        st.info("No hay demandas pendientes que coincidan con los filtros.")
        return

    # 3. Tabla de consulta con Scroll
    columnas_tabla = ["expediente", "fecha_ingreso", "apellido", "nombre", "barrio", "accion", "estado", "prioridad"]
    df_tabla = df_filtrado[columnas_tabla]

    st.markdown("### Listado de demandas")
    with st.container(height=350):
        seleccion_tabla = st.dataframe(
            df_tabla,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="tabla_demandas_operativa",
        )

    # 4. Detalle de demanda seleccionada
    idx_sel = seleccion_tabla.selection.rows
    if not idx_sel:
        st.info("Selecciona una demanda desde la tabla para editarla.")
        return

    demanda = df_filtrado.iloc[idx_sel[0]].to_dict()
    did = demanda["id_demanda"]

    st.markdown(f"#### 🔎 Detalle de demanda #{did}")

    # Control de modo edición
    if "editar_demanda_id" not in st.session_state:
        st.session_state["editar_demanda_id"] = None

    modo_edicion = st.session_state["editar_demanda_id"] == did

    col_main, col_actions = st.columns([0.72, 0.28])

    with col_main:
        # --- MODO CONSULTA: FICHA TÉCNICA (HTML) ---
        historial_html = texto(demanda.get("observaciones")) or "Sin historial cargado."
        
        # Construcción de la card visual
        ficha_html = f"""
<div style="background-color: white; border: 1px solid #D9E6E4; border-radius: 18px; padding: 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
<div style="font-size: 22px; font-weight: 800; color: #004F4C;">
    {limpiar(demanda.get('apellido'))}, {limpiar(demanda.get('nombre'))}
</div>
<div style="display: flex; gap: 6px;">
    {estado_badge(demanda.get('estado'))}
    {prioridad_badge(demanda.get('prioridad'))}
</div>
</div>

<div style="display: grid; grid-template-columns: 1fr 1.2fr; gap: 20px; font-size: 14px; line-height: 1.6;">
<div>
    <div style="color: #667879; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.05em; margin-bottom: 4px;">Información del Expediente</div>
    <b>Expte:</b> {texto(demanda.get('expediente')) or 'S/E'}<br>
    <b>Origen:</b> {texto(demanda.get('origen'))}<br>
    <b>Acción:</b> {texto(demanda.get('accion'))}<br>
    <b>Responsable:</b> {texto(demanda.get('responsable')) or 'Sin asignar'}
</div>
<div>
    <div style="color: #667879; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.05em; margin-bottom: 4px;">Ubicación y Contacto</div>
    📍 {texto(demanda.get('domicilio'))} — <span style="color: #006B68; font-weight: 600;">{texto(demanda.get('barrio'))}</span><br>
    📞 {texto(demanda.get('contacto'))}<br>
    🆔 DNI: {texto(demanda.get('dni'))}<br>
    📅 Ingreso: {fecha_corta(demanda.get('fecha_ingreso'))}
</div>
</div>

<div style="margin-top: 25px;">
<div style="font-weight: 700; color: #1F2D2F; margin-bottom: 10px; font-size: 14px; display: flex; align-items: center; gap: 8px;">
    📜 Historial acumulado
</div>
<div class="historial-box" style="max-height: 160px; font-size: 13px;">{historial_html}</div>
</div>
</div>
        """
        st.markdown(ficha_html, unsafe_allow_html=True)

        # --- MODO EDICIÓN: FORMULARIO (WIDGETS) ---
        if modo_edicion:
            st.divider()
            st.markdown("##### 📝 Formulario de Edición")
            
            with st.container(border=True):
                categoria, estados = estados_para_demanda(demanda)
                
                # Fila 1: Gestión
                ce1, ce2, ce3 = st.columns(3)
                estado_val = ce1.selectbox("Estado", estados, index=estados.index(demanda.get("estado")) if demanda.get("estado") in estados else 0)
                prioridad_val = ce2.selectbox("Prioridad", PRIORIDADES, index=PRIORIDADES.index(demanda.get("prioridad")) if demanda.get("prioridad") in PRIORIDADES else 2)
                responsable_val = ce3.selectbox("Responsable", [""] + RESPONSABLES, index=([""] + RESPONSABLES).index(demanda.get("responsable") or ""))
                
                # Fila 2: Titular
                ce4, ce5, ce6 = st.columns(3)
                apellido_v = ce4.text_input("Apellido", value=texto(demanda.get("apellido")))
                nombre_v = ce5.text_input("Nombre", value=texto(demanda.get("nombre")))
                dni_v = ce6.text_input("DNI", value=texto(demanda.get("dni")))
                
                # Fila 3: Ubicación
                ce7, ce8, ce9 = st.columns(3)
                dom_v = ce7.text_input("Domicilio", value=texto(demanda.get("domicilio")))
                bar_v = ce8.text_input("Barrio", value=texto(demanda.get("barrio")))
                con_v = ce9.text_input("Contacto", value=texto(demanda.get("contacto")))
                
            nueva_acc_v = st.text_area(
                "🆕 Nueva acción / actualización de historial", 
                height=100, 
                placeholder="Escribí aquí el resumen de la gestión realizada...", 
                key=f"nueva_acc_{did}"
            )

    with col_actions:
        st.markdown("#### Acciones")
        if not modo_edicion:
            if st.button("🔓 Habilitar edición", use_container_width=True, help="Habilita los campos para modificar los datos"):
                st.session_state["editar_demanda_id"] = did
                st.rerun()
        else:
            if st.button("💾 Guardar cambios", type="primary", use_container_width=True):
                nuevos_valores = {
                    "estado": estado_val, 
                    "prioridad": prioridad_val, 
                    "responsable": responsable_val or None,
                    "apellido": apellido_v.strip() or None, 
                    "nombre": nombre_v.strip() or None, 
                    "dni": dni_v.strip() or None,
                    "domicilio": dom_v.strip() or None, 
                    "barrio": bar_v.strip() or None, 
                    "contacto": con_v.strip() or None,
                }
                # Obtenemos el texto del área de texto usando la clave única
                texto_nueva_accion = st.session_state.get(f"nueva_acc_{did}", "")
                cambios = detectar_cambios(demanda, nuevos_valores)
                
                if not cambios and not limpiar(texto_nueva_accion):
                    st.info("No hay cambios para guardar.")
                else:
                    try:
                        actualizar_demanda(did, {
                            **nuevos_valores,
                            "observaciones": agregar_al_historial(demanda.get("observaciones"), texto_nueva_accion, cambios)
                        })
                        st.toast("✅ Cambios guardados con éxito.")
                        st.session_state["editar_demanda_id"] = None
                        if f"nueva_acc_{did}" in st.session_state:
                            del st.session_state[f"nueva_acc_{did}"]
                        st.rerun()
                    except Exception as e:
                        mostrar_error_supabase(e)

            if st.button("🚫 Cancelar edición", use_container_width=True):
                st.session_state["editar_demanda_id"] = None
                st.rerun()

        # --- CIERRE DE DEMANDA (Siempre visible) ---
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("📁 Finalizar Expediente", expanded=False):
            st.write("Marcar como resuelta y archivar.")
            confirma_cierre = st.checkbox("Confirmo el cierre definitivo", key=f"conf_cierre_{did}")
            if st.button("📁 Cerrar demanda", disabled=not confirma_cierre, use_container_width=True, type="secondary"):
                try:
                    cerrar_demanda(did)
                    st.toast(f"Demanda #{did} cerrada correctamente.")
                    st.rerun()
                except Exception as e:
                    mostrar_error_supabase(e)


st.set_page_config(page_title="Demandas", layout="wide")

aplicar_estilos_globales()

page_header(
    "Demandas",
    "Carga, consulta y actualización de solicitudes ingresadas al área.",
    "Municipalidad de Tafí Viejo",
)

tab_cargar, tab_pendientes = st.tabs(["Cargar demanda", "Pendientes"])

with tab_cargar:
    cargar_demanda_tab()

with tab_pendientes:
    pendientes_tab()
