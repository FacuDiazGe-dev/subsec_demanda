from datetime import date
import html
import re
import unicodedata

import pandas as pd
import streamlit as st

from utils.auth import require_login
from utils.operational_card_component import operational_card
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
from services.sociohabitacional_service import listar_visitas_detalladas
from services.obras_service import listar_obras_con_demanda
from services.ordenes_service import listar_ordenes_con_demanda
from services.expedientes_service import (
    actualizar_expediente_desde_demanda,
    buscar_expediente,
    sincronizar_demanda_desde_expediente,
)


ORIGENES = [
    "Subdirectora",
    "Área administrativa",
    "Subsecretaría",
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
    "Actuación",
    "Obra",
    "Entregar materiales",
    "Informe",
    "Seguimiento",
    "Emergencia",
    "Otro",
]

TIPOS_MATERIALES = [
    "Gestión de stock",
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
    "Actuación": ["Pendiente", "Para Hacer", "En elaboración", "Presentado", "Cerrado"],
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
        "En gestión",
        "Autorización recibida",
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
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    return str(valor)


def limpiar(valor):
    return texto(valor).strip()


def valor_visible(valor, fallback="Sin dato"):
    valor = limpiar(valor)
    if not valor or valor.lower() in {"nan", "none", "null"}:
        return fallback
    return valor


def normalizar_texto(valor):
    valor = limpiar(valor).lower()
    valor = unicodedata.normalize("NFKD", valor)
    return "".join(ch for ch in valor if not unicodedata.combining(ch))

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


def expediente_demanda(demanda):
    numero = limpiar(demanda.get("expte_numero"))
    anio = limpiar(demanda.get("expte_anio"))
    if numero and anio:
        return numero, anio
    numero_parseado, anio_parseado, _ = parsear_expediente(demanda.get("expediente"))
    return numero_parseado, anio_parseado


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
        accion = st.selectbox("Acción", ACCIONES)
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
    accion = limpiar(demanda.get("accion"))
    accion_norm = normalizar_texto(accion)
    for accion_ref, estados in ESTADOS_POR_ACCION.items():
        if normalizar_texto(accion_ref) == accion_norm:
            estados_posibles = list(estados)
            break
    else:
        estados_posibles = ["Ingresada", "En gestion", "Resuelta", "Entregado", "Cerrado"]

    estado_actual = limpiar(demanda.get("estado"))
    if estado_actual and estado_actual not in estados_posibles:
        estados_posibles = [estado_actual] + estados_posibles

    return accion, estados_posibles

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
        partes.append(f"Actualización: {nueva_accion}")
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
            limpiar_f = st.button("Limpiar", help="Limpiar filtros", use_container_width=True)

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


def nombre_demanda_card(demanda):
    apellido = limpiar(demanda.get("apellido")).upper()
    nombre = limpiar(demanda.get("nombre"))
    if apellido and nombre:
        return f"{apellido}, {nombre}"
    return apellido or nombre or "Sin titular"


def ubicacion_demanda_card(demanda):
    domicilio = limpiar(demanda.get("domicilio"))
    barrio = limpiar(demanda.get("barrio"))
    if domicilio and barrio:
        return f"{domicilio} - {barrio}"
    return domicilio or barrio or "Sin domicilio"


def card_click_resultado(resultado, card_key):
    if isinstance(resultado, dict):
        if resultado.get("action") != "card_click" or resultado.get("card_key") != card_key:
            return False
        event_id = resultado.get("event_id")
        if not event_id:
            return False
        vistos = st.session_state.setdefault("_demandas_card_eventos_vistos", [])
        if event_id in vistos:
            return False
        vistos.append(event_id)
        st.session_state["_demandas_card_eventos_vistos"] = vistos[-80:]
        return True
    return resultado == card_key


def color_accion_demanda(accion):
    colores = {
        "Visitar": "#2563EB",
        "Hacer nota": "#7C3AED",
        "Actuacion": "#0F766E",
        "Actuación": "#0F766E",
        "Obra": "#D97706",
        "Entregar materiales": "#0284C7",
        "Informe": "#16A34A",
        "Seguimiento": "#64748B",
        "Emergencia": "#DC2626",
        "Otro": "#94A3B8",
    }
    return colores.get(limpiar(accion), "#94A3B8")


def cargar_estilos_demandas_v2():
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] main .block-container {
            max-width: 1380px;
            padding-top: 1.1rem;
        }
        .dem-v2-header {
            margin-bottom: 8px;
        }
        .dem-v2-title {
            color: #0f2742;
            font-size: 25px;
            line-height: 1.1;
            font-weight: 850;
            margin: 0;
        }
        .dem-v2-subtitle {
            color: #64748b;
            font-size: 13px;
            font-weight: 600;
            margin-top: 2px;
        }
        .dem-v2-section-title {
            color: #0f2742;
            font-size: 16px;
            font-weight: 850;
            line-height: 1.2;
            margin: 0;
        }
        .dem-v2-section-caption {
            color: #64748b;
            font-size: 12px;
            font-weight: 650;
            margin: 2px 0 8px;
        }
        .dem-v2-detail-titleblock {
            margin-bottom: 20px;
        }
        .dem-v2-list-head-wrap {
            margin-bottom: 4px;
        }
        .dem-v2-kpi {
            background: rgba(255, 255, 255, 0.97);
            border: 1px solid #d7e0e8;
            border-left: 5px solid #006b68;
            border-radius: 14px;
            min-height: 94px;
            padding: 10px 14px;
            box-shadow: 0 1px 7px rgba(15, 23, 42, 0.04);
        }
        .dem-v2-kpi-header {
            display: flex;
            align-items: center;
            gap: 7px;
            border-bottom: 1px solid #e5edf3;
            padding-bottom: 6px;
            margin-bottom: 7px;
        }
        .dem-v2-kpi-icon {
            color: #64748b;
            font-size: 12px;
            font-weight: 850;
            line-height: 1;
        }
        .dem-v2-kpi-title {
            color: #46576a;
            font-size: 11px;
            font-weight: 850;
            letter-spacing: 0.045em;
            text-transform: uppercase;
            line-height: 1.1;
        }
        .dem-v2-kpi-body {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .dem-v2-kpi-main {
            min-width: 0;
            padding-right: 10px;
        }
        .dem-v2-kpi-main + .dem-v2-kpi-main {
            border-left: 1px solid #e5edf3;
            padding-left: 12px;
            padding-right: 0;
        }
        .dem-v2-kpi-metric-label {
            color: #607086;
            font-size: 10px;
            font-weight: 750;
            letter-spacing: 0.025em;
            line-height: 1.1;
            text-transform: uppercase;
        }
        .dem-v2-kpi-metric-value {
            color: #0f2742;
            font-size: 28px;
            font-weight: 850;
            line-height: 1.08;
            margin-top: 3px;
        }
        .dem-v2-kpi-footer {
            display: grid;
            grid-template-columns: repeat(var(--items, 1), minmax(0, 1fr));
            border-top: 1px solid #e5edf3;
            color: #475569;
            font-size: 11.5px;
            font-weight: 800;
            margin-top: 8px;
            padding-top: 6px;
            text-align: center;
        }
        .dem-v2-kpi-footer-item + .dem-v2-kpi-footer-item {
            border-left: 1px solid #e5edf3;
        }
        .dem-v2-kpi-green { border-left-color: #006b68; }
        .dem-v2-kpi-blue { border-left-color: #2563eb; }
        .dem-v2-kpi-amber { border-left-color: #f59e0b; }
        .dem-v2-kpi-red { border-left-color: #dc2626; }
        .dem-v2-kpi-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 14px;
            margin-bottom: 8px;
        }
        .dem-v2-kpi-chip {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #fff7ed;
            border: 1px solid #fed7aa;
            border-radius: 999px;
            color: #9a3412;
            font-size: 12px;
            font-weight: 800;
            padding: 5px 10px;
            margin: 2px 0 10px;
        }
        .dem-v2-kpi-row {
            margin-bottom: 10px;
        }
        div[class*="st-key-dem_v2_filtros"] {
            margin-top: 14px !important;
            clear: both !important;
        }
        .dem-v2-list-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            margin-bottom: 6px;
        }
        .dem-v2-empty {
            background: #ffffff;
            border: 1px dashed #cbd5e1;
            border-radius: 12px;
            padding: 18px 16px;
            color: #64748b;
            font-size: 14px;
            font-weight: 650;
            text-align: center;
        }
        .dem-v2-detail-meta {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px 10px;
            background: #ffffff;
            border: 1px solid #dbe7ee;
            border-radius: 12px;
            padding: 10px 12px;
            margin-top: 6px;
            box-shadow: 0 1px 5px rgba(15, 23, 42, 0.035);
        }
        .dem-v2-field-label {
            color: #64748b;
            font-size: 10.5px;
            font-weight: 800;
            letter-spacing: 0.02em;
            text-transform: uppercase;
            margin-bottom: 2px;
        }
        .dem-v2-field-value {
            color: #1e293b;
            font-size: 13px;
            font-weight: 650;
            overflow-wrap: anywhere;
        }
        .dem-v2-actions {
            background: #ffffff;
            border: 1px solid #dbe7ee;
            border-radius: 12px;
            padding: 10px;
            margin-top: 8px;
        }
        div[class*="st-key-dem_v2_detail_panel"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 255, 255, 0.97) !important;
            border-color: #dbe7ee !important;
            border-radius: 14px !important;
            padding: 12px 14px !important;
            box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04) !important;
        }
        div[class*="st-key-dem_v2_demand_data_panel"] [data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #f8fafc !important;
            background: #f8fafc !important;
            border-color: #dbe7ee !important;
            border-radius: 12px !important;
            padding: 10px 12px 12px !important;
            box-shadow: none !important;
        }
        div[class*="st-key-dem_v2_demand_data_panel"] {
            background: #f8fafc !important;
            border-radius: 12px !important;
        }
        div[class*="st-key-dem_v2_demand_data_panel"] {
            margin-top: 6px !important;
        }
        div[class*="st-key-dem_v2_edit_panel"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: #f8fafc !important;
            border-color: #dbe7ee !important;
            border-radius: 12px !important;
            padding: 10px 12px 12px !important;
            box-shadow: none !important;
        }
        div[class*="st-key-dem_v2_edit_panel"] {
            margin-top: 6px !important;
            background: #f8fafc !important;
            border-radius: 12px !important;
        }
        div[class*="st-key-dem_v2_detail_panel"] iframe.stCustomComponentV1,
        div[class*="st-key-dem_v2_detail_panel"] iframe[title*="operational_card"] {
            margin-bottom: -10px !important;
        }
        .dem-v2-subblock-title {
            color: #0f2742;
            font-size: 13px;
            font-weight: 850;
            margin: 6px 0 6px;
        }
        .dem-v2-data-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px 10px;
            margin-bottom: 10px;
        }
        .dem-v2-data-field {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 8px 10px;
            min-height: 58px;
        }
        .dem-v2-data-label {
            color: #64748b;
            font-size: 10.5px;
            font-weight: 800;
            letter-spacing: 0.02em;
            text-transform: uppercase;
            line-height: 1.1;
            margin-bottom: 5px;
        }
        .dem-v2-data-value {
            color: #0f2742;
            font-size: 13px;
            font-weight: 700;
            line-height: 1.25;
            overflow-wrap: anywhere;
        }
        .dem-v2-observaciones-box {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            color: #334155;
            font-size: 13px;
            line-height: 1.45;
            max-height: 170px;
            overflow-y: auto;
            padding: 9px 10px;
            margin-bottom: 10px;
        }
        .dem-v2-actions-inline {
            border-top: 1px solid #e2e8f0;
            padding-top: 10px;
            margin-top: 4px;
        }
        div[data-testid="stExpander"] {
            background: #ffffff !important;
            border-color: #dbe7ee !important;
            box-shadow: 0 1px 5px rgba(15, 23, 42, 0.025) !important;
        }
        div[class*="st-key-dem_v2_filtros"] [data-testid="stVerticalBlockBorderWrapper"],
        div[class*="st-key-dem_v2_form"] [data-testid="stVerticalBlockBorderWrapper"],
        div[class*="st-key-dem_v2_edit"] [data-testid="stVerticalBlockBorderWrapper"],
        div[class*="st-key-dem_v2_datos"] [data-testid="stVerticalBlockBorderWrapper"],
        div[class*="st-key-dem_v2_acciones"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: #f8fafc !important;
            border-color: #dbe7ee !important;
            padding: 7px 10px !important;
            box-shadow: none !important;
        }
        div[class*="st-key-dem_v2_filtros"] [data-testid="stHorizontalBlock"] {
            align-items: end !important;
        }
        div[class*="st-key-dem_v2_filtros"] label,
        div[class*="st-key-dem_v2_form"] label,
        div[class*="st-key-dem_v2_edit"] label {
            color: #475569 !important;
            font-size: 11px !important;
            font-weight: 650 !important;
        }
        div[class*="st-key-dem_v2_filtros"] input,
        div[class*="st-key-dem_v2_filtros"] [data-baseweb="select"] > div,
        div[class*="st-key-dem_v2_form"] input,
        div[class*="st-key-dem_v2_form"] textarea,
        div[class*="st-key-dem_v2_form"] [data-baseweb="select"] > div,
        div[class*="st-key-dem_v2_edit"] input,
        div[class*="st-key-dem_v2_edit"] textarea,
        div[class*="st-key-dem_v2_edit"] [data-baseweb="select"] > div {
            min-height: 31px !important;
            font-size: 12.5px !important;
            background: #ffffff !important;
        }
        div[class*="st-key-dem_v2_form"] textarea,
        div[class*="st-key-dem_v2_edit"] textarea {
            min-height: 72px !important;
            max-height: 96px !important;
        }
        div[class*="st-key-dem_v2_limpiar_filtros"] button {
            min-height: 48px !important;
            height: 48px !important;
            padding-top: 6px !important;
            padding-bottom: 6px !important;
            font-size: 12.5px !important;
            margin-top: 0 !important;
        }
        div[class*="st-key-dem_v2_btn_crear"] button,
        div[class*="st-key-dem_v2_btn_guardar"] button,
        div[class*="st-key-dem_v2_btn_editar"] button,
        div[class*="st-key-dem_v2_guardar_edit"] button,
        div[class*="st-key-dem_v2_btn_guardar_crear"] button {
            background: #006b68 !important;
            border-color: #006b68 !important;
            color: #ffffff !important;
            box-shadow: none !important;
        }
        div[class*="st-key-dem_v2_btn_crear"],
        div[class*="st-key-dem_v2_btn_crear"] > div {
            display: flex !important;
            justify-content: flex-end !important;
        }
        div[class*="st-key-dem_v2_btn_crear"] button {
            min-height: 36px !important;
            height: 36px !important;
            width: 170px !important;
            max-width: 170px !important;
            padding-left: 14px !important;
            padding-right: 14px !important;
            white-space: nowrap !important;
            font-size: 13px !important;
            float: none;
        }
        div[class*="st-key-dem_v2_guardar_edit"] button,
        div[class*="st-key-dem_v2_cancel_edit"] button,
        div[class*="st-key-dem_v2_btn_guardar_crear"] button,
        div[class*="st-key-dem_v2_cancelar_crear"] button,
        div[class*="st-key-dem_v2_btn_editar"] button {
            min-height: 36px !important;
            height: 36px !important;
            padding-top: 4px !important;
            padding-bottom: 4px !important;
            font-size: 13px !important;
            white-space: nowrap !important;
        }
        @media (max-width: 900px) {
            .dem-v2-kpi-grid { grid-template-columns: 1fr; }
            .dem-v2-detail-meta { grid-template-columns: 1fr; }
            .dem-v2-data-grid { grid-template-columns: 1fr; }
            .dem-v2-list-head { align-items: stretch; flex-direction: column; }
            div[class*="st-key-dem_v2_btn_crear"],
            div[class*="st-key-dem_v2_btn_crear"] > div {
                display: block !important;
            }
            div[class*="st-key-dem_v2_btn_crear"] button {
                width: 100% !important;
                max-width: 100% !important;
                float: none;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def contar_sin_responsable(df):
    if df.empty or "responsable" not in df.columns:
        return 0
    estados_cierre = {"cerrado", "cerrada", "finalizada", "cancelada"}
    df_activo = df.copy()
    if "estado" in df_activo.columns:
        df_activo = df_activo[~df_activo["estado"].fillna("").map(normalizar_texto).isin(estados_cierre)]
    return df_activo[df_activo["responsable"].fillna("").astype(str).str.strip() == ""].shape[0]


def obtener_obras_para_kpi():
    try:
        return listar_obras_con_demanda()
    except Exception:
        return []


def obtener_ordenes_para_kpi():
    try:
        return listar_ordenes_con_demanda(incluir_cerradas=False)
    except Exception:
        return []


def obtener_visitas_para_kpi():
    try:
        return listar_visitas_detalladas()
    except Exception:
        return []


def calcular_kpis_obras(df):
    obras = obtener_obras_para_kpi()
    activas = [o for o in obras if normalizar_texto(o.get("estado_obra")) == "en ejecucion"]
    ha = [
        o for o in activas
        if "havita" in normalizar_texto(o.get("modalidad_ejecucion"))
        or "havita" in normalizar_texto(o.get("tipo_obra_programa"))
        or "cuadrilla havita" in normalizar_texto(o.get("modalidad_ejecucion"))
    ]
    mo = [
        o for o in activas
        if "mano de obra propia" in normalizar_texto(o.get("modalidad_ejecucion"))
        or normalizar_texto(o.get("modalidad_ejecucion")) in {"mo", "mo propia"}
    ]

    pendientes_ids = set()
    ids_demandas_con_obra = {o.get("id_demanda") for o in obras if o.get("id_demanda") is not None}
    estados_excluidos_obra = {"en ejecucion", "ejecutada", "finalizada", "cerrada", "cerrado", "cancelada"}

    for obra in obras:
        estado_obra = normalizar_texto(obra.get("estado_obra"))
        if estado_obra and estado_obra not in estados_excluidos_obra:
            id_demanda = obra.get("id_demanda")
            pendientes_ids.add(f"d:{id_demanda}" if id_demanda is not None else f"o:{obra.get('id_obra')}")

    if not df.empty and "accion" in df.columns:
        acciones_obra = df["accion"].fillna("").map(normalizar_texto).isin({"obra", "emergencia"})
        demandas_sin_obra = df[acciones_obra & ~df["id_demanda"].isin(ids_demandas_con_obra)] if "id_demanda" in df.columns else df[acciones_obra]
        if "estado" in df.columns:
            estados_excluidos_demanda = {"ejecutada", "finalizada", "cerrada", "cerrado", "cancelada", "cancelado"}
            demandas_pendientes = demandas_sin_obra[
                ~demandas_sin_obra["estado"].fillna("").map(normalizar_texto).isin(estados_excluidos_demanda)
            ]
        else:
            demandas_pendientes = demandas_sin_obra
        for _, demanda in demandas_pendientes.iterrows():
            pendientes_ids.add(f"d:{demanda.get('id_demanda', len(pendientes_ids))}")

    return {"activas": len(activas), "pendientes": len(pendientes_ids), "ha": len(ha), "mo": len(mo)}


def calcular_kpis_visitas(df):
    visitas_registradas = obtener_visitas_para_kpi()
    estados_cierre = {"cerrada", "cerrado", "finalizada", "finalizado", "cancelada", "cancelado"}
    informes = {"informe"}
    informe_social = 0
    informe_tecnico = 0
    completos = 0

    for visita in visitas_registradas:
        campos_estado = [
            visita.get("estado"),
            visita.get("estado_visita"),
            visita.get("d_estado"),
            visita.get("est_soc"),
            visita.get("est_tec"),
        ]
        if any(normalizar_texto(valor) in estados_cierre for valor in campos_estado):
            continue

        soc_informe = normalizar_texto(visita.get("est_soc")) in informes
        tec_informe = normalizar_texto(visita.get("est_tec")) in informes

        if soc_informe and tec_informe:
            completos += 1
        elif soc_informe:
            informe_social += 1
        elif tec_informe:
            informe_tecnico += 1

    if df.empty or "accion" not in df.columns:
        return {
            "para_visita": 0,
            "programadas": 0,
            "informe_tecnico": informe_tecnico,
            "informe_social": informe_social,
            "completos": completos,
        }
    visitas = df[df["accion"].fillna("").map(normalizar_texto) == "visitar"]
    estados = visitas["estado"].fillna("").map(normalizar_texto) if "estado" in visitas.columns else pd.Series([], dtype=str)
    estados_para_visita = {"pendiente", "ingresada", "para visita", "sin programar"}
    estados_programadas = {"visita programada", "programada", "para visita con fecha"}
    return {
        "para_visita": int(estados.isin(estados_para_visita).sum()),
        "programadas": int(estados.isin(estados_programadas).sum()),
        "informe_tecnico": informe_tecnico,
        "informe_social": informe_social,
        "completos": completos,
    }


def calcular_kpis_ordenes():
    ordenes = obtener_ordenes_para_kpi()
    estados_pendientes = {
        "pedido entrega",
        "pedido retiro",
        "pedido",
        "en deposito",
        "en deposito parcial",
        "entrega parcial",
    }
    estados_programadas = {"pendiente de entrega", "pendiente de retiro"}
    pendientes = 0
    programadas = 0
    entrega = 0
    retiro = 0
    deposito = 0
    for orden in ordenes:
        estado = normalizar_texto(orden.get("estado"))
        if "entrega" in estado:
            entrega += 1
        if "retiro" in estado:
            retiro += 1
        if "deposito" in estado:
            deposito += 1
        if estado in estados_programadas:
            programadas += 1
        elif estado in estados_pendientes:
            pendientes += 1
    return {
        "pendientes": pendientes,
        "programadas": programadas,
        "entrega": entrega,
        "retiro": retiro,
        "deposito": deposito,
    }


def compact_kpi_card_html(
    title,
    icon,
    tone,
    label_1,
    value_1,
    label_2,
    value_2,
    footer_items=None,
):
    footer_items = [str(item) for item in (footer_items or []) if str(item).strip()]
    footer_html = ""
    if footer_items:
        items_html = "".join(
            f'<div class="dem-v2-kpi-footer-item">{html.escape(item)}</div>'
            for item in footer_items[:3]
        )
        footer_html = (
            f'<div class="dem-v2-kpi-footer" style="--items:{len(footer_items[:3])};">'
            f'{items_html}'
            '</div>'
        )
    icon_html = f'<span class="dem-v2-kpi-icon">{html.escape(icon)}</span>' if icon else ""
    return (
        f'<div class="dem-v2-kpi dem-v2-kpi-{tone}">'
        '<div class="dem-v2-kpi-header">'
        f'{icon_html}<div class="dem-v2-kpi-title">{html.escape(title)}</div>'
        '</div>'
        '<div class="dem-v2-kpi-body">'
        '<div class="dem-v2-kpi-main">'
        f'<div class="dem-v2-kpi-metric-label">{html.escape(label_1)}</div>'
        f'<div class="dem-v2-kpi-metric-value">{value_1}</div>'
        '</div>'
        '<div class="dem-v2-kpi-main">'
        f'<div class="dem-v2-kpi-metric-label">{html.escape(label_2)}</div>'
        f'<div class="dem-v2-kpi-metric-value">{value_2}</div>'
        '</div>'
        '</div>'
        f'{footer_html}'
        '</div>'
    )


def render_compact_kpi_card(
    title,
    icon,
    accent_color,
    label_1,
    value_1,
    label_2,
    value_2,
    footer_items=None,
):
    st.markdown(
        compact_kpi_card_html(
            title,
            icon,
            accent_color,
            label_1,
            value_1,
            label_2,
            value_2,
            footer_items,
        ),
        unsafe_allow_html=True,
    )


def render_demandas_kpis_v2(df):
    obras = calcular_kpis_obras(df)
    visitas = calcular_kpis_visitas(df)
    ordenes = calcular_kpis_ordenes()
    sin_resp = contar_sin_responsable(df)

    cards = [
        compact_kpi_card_html(
            "Obras",
            "O",
            "amber",
            "En ejecución",
            obras["activas"],
            "Pendientes",
            obras["pendientes"],
            footer_items=[f"HA {obras['ha']}", f"MO {obras['mo']}"],
        ),
        compact_kpi_card_html(
            "Visitas",
            "V",
            "blue",
            "Programadas",
            visitas["programadas"],
            "Pendientes",
            visitas["para_visita"],
            footer_items=[
                f"IT {visitas['informe_tecnico']}",
                f"IS {visitas['informe_social']}",
                f"C {visitas['completos']}",
            ],
        ),
        compact_kpi_card_html(
            "Órdenes",
            "OR",
            "green",
            "Programadas",
            ordenes["programadas"],
            "Pendientes",
            ordenes["pendientes"],
            footer_items=[f"E {ordenes['entrega']}", f"R {ordenes['retiro']}", f"D {ordenes['deposito']}"],
        ),
    ]
    kpi_html = f'<div class="dem-v2-kpi-grid">{"".join(cards)}</div>'
    if hasattr(st, "html"):
        st.html(kpi_html)
    else:
        st.markdown(kpi_html, unsafe_allow_html=True)
    if sin_resp:
        st.markdown(f'<div class="dem-v2-kpi-chip">! {sin_resp} sin responsable</div>', unsafe_allow_html=True)

def compactar_espaciado_operational_cards(scope_key="dem_v2_card_list"):
    st.markdown(
        f"""
        <style>
        div[class*="st-key-{scope_key}"] div[data-testid="stVerticalBlock"]:has(iframe.stCustomComponentV1) {{
            gap: 0.28rem !important;
        }}
        div[class*="st-key-{scope_key}"] div[data-testid="element-container"]:has(iframe.stCustomComponentV1),
        div[class*="st-key-{scope_key}"] div[data-testid="element-container"]:has(iframe[title*="operational_card"]) {{
            margin-bottom: 6px !important;
            padding-bottom: 0 !important;
        }}
        div[class*="st-key-{scope_key}"] iframe.stCustomComponentV1,
        div[class*="st-key-{scope_key}"] iframe[title*="operational_card"] {{
            display: block !important;
            margin-bottom: 0 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def estilos_ficha_demanda_seleccionada():
    st.markdown(
        """
        <style>
        .dem-detail-panel {
            background: #fbfdff;
            border: 1px solid #dbeafe;
            border-radius: 10px 10px 0 0;
            padding: 12px 16px;
            box-shadow: 0 1px 4px rgba(15, 23, 42, 0.03);
            margin-top: 6px;
        }
        .dem-detail-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px 14px;
        }
        .dem-detail-label {
            color: #64748b;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            margin-bottom: 2px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .dem-detail-icon {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 20px;
            height: 20px;
            border-radius: 999px;
            background: #dbeafe;
            color: #1d4ed8;
            font-size: 12px;
            line-height: 1;
        }
        .dem-detail-value {
            color: #1e293b;
            font-size: 13px;
            font-weight: 600;
            overflow-wrap: anywhere;
        }
        .dem-history-panel {
            background: #fbfdff;
            border: 1px solid #dbeafe;
            border-top: 0;
            border-radius: 0 0 10px 10px;
            padding: 10px 16px 13px;
            color: #334155;
            font-size: 13px;
            line-height: 1.45;
            max-height: 160px;
            overflow-y: auto;
        }
        .dem-history-title {
            border-top: 1px solid #dbeafe;
            padding-top: 10px;
            color: #1e293b;
            font-weight: 750;
            margin-bottom: 3px;
        }
        @media (max-width: 800px) {
            .dem-detail-grid { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_ficha_demanda_seleccionada(demanda):
    estilos_ficha_demanda_seleccionada()
    historial_html = texto(demanda.get("observaciones")) or "Sin historial cargado."
    operational_card(
        title=nombre_demanda_card(demanda),
        subtitle=f"Expte. {texto(demanda.get('expediente')) or 'S/E'}",
        status=texto(demanda.get("estado")) or None,
        priority=texto(demanda.get("prioridad")) or None,
        meta=[
            texto(demanda.get("accion")) or "Sin acción",
            f"Ingreso: {fecha_corta(demanda.get('fecha_ingreso'))}",
        ],
        description=texto(demanda.get("pedido")) or "",
        variant="default",
        accent_color=color_accion_demanda(demanda.get("accion")),
        card_key=f"demanda_detalle_{demanda.get('id_demanda')}",
        key=f"demanda_detalle_card_{demanda.get('id_demanda')}",
    )
    st.markdown(
        f"""
        <div class="dem-detail-panel">
            <div class="dem-detail-grid">
                <div>
                    <div class="dem-detail-label"><span class="dem-detail-icon">&#x1F3DB;&#xFE0F;</span>Origen</div>
                    <div class="dem-detail-value">{texto(demanda.get('origen')) or '-'}</div>
                </div>
                <div>
                    <div class="dem-detail-label"><span class="dem-detail-icon">&#x1F464;</span>Responsable</div>
                    <div class="dem-detail-value">{texto(demanda.get('responsable')) or 'Sin asignar'}</div>
                </div>
                <div>
                    <div class="dem-detail-label"><span class="dem-detail-icon">&#x1FAAA;</span>DNI</div>
                    <div class="dem-detail-value">{texto(demanda.get('dni')) or '-'}</div>
                </div>
                <div>
                    <div class="dem-detail-label"><span class="dem-detail-icon">&#x1F3E0;</span>Domicilio</div>
                    <div class="dem-detail-value">{texto(demanda.get('domicilio')) or '-'}</div>
                </div>
                <div>
                    <div class="dem-detail-label"><span class="dem-detail-icon">&#x1F3E2;</span>Barrio</div>
                    <div class="dem-detail-value">{texto(demanda.get('barrio')) or '-'}</div>
                </div>
                <div>
                    <div class="dem-detail-label"><span class="dem-detail-icon">&#x260E;&#xFE0F;</span>Contacto</div>
                    <div class="dem-detail-value">{texto(demanda.get('contacto')) or '-'}</div>
                </div>
            </div>
        </div>
        <div class="dem-history-panel">
            <div class="dem-history-title">Historial / observaciones</div>
            {historial_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


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

    # 3. Listado compacto de demandas
    st.markdown("### Listado de demandas")
    compactar_espaciado_operational_cards("dem_v1_card_list")
    with st.container(height=350, key="dem_v1_card_list"):
        for _, fila in df_filtrado.iterrows():
            demanda_card = fila.to_dict()
            did_card = demanda_card.get("id_demanda")
            card_key = f"demanda_{did_card}"
            seleccionada = str(st.session_state.get("demanda_seleccionada_id", "")) == str(did_card)
            resultado = operational_card(
                title=nombre_demanda_card(demanda_card),
                subtitle=f"Expte. {texto(demanda_card.get('expediente')) or 'S/E'}",
                status=texto(demanda_card.get("estado")) or None,
                priority=texto(demanda_card.get("prioridad")) or None,
                meta=[
                    texto(demanda_card.get("accion")) or "Sin acción",
                    ubicacion_demanda_card(demanda_card),
                    f"Ingreso: {fecha_corta(demanda_card.get('fecha_ingreso'))}",
                ],
                variant="default",
                accent_color=color_accion_demanda(demanda_card.get("accion")),
                clickable=True,
                selected=seleccionada,
                card_key=card_key,
                key=f"demanda_card_{did_card}",
            )
            if (
                card_click_resultado(resultado, card_key)
                and str(st.session_state.get("demanda_seleccionada_id", "")) != str(did_card)
            ):
                st.session_state["demanda_seleccionada_id"] = did_card
                st.rerun()

    # 4. Detalle de demanda seleccionada
    demanda_seleccionada_id = st.session_state.get("demanda_seleccionada_id")
    if demanda_seleccionada_id is None:
        st.info("Selecciona una demanda desde el listado para editarla.")
        return

    demanda_sel = df_filtrado[df_filtrado["id_demanda"].astype(str) == str(demanda_seleccionada_id)]
    if demanda_sel.empty:
        st.session_state.pop("demanda_seleccionada_id", None)
        st.info("Selecciona una demanda desde el listado para editarla.")
        return

    demanda = demanda_sel.iloc[0].to_dict()
    did = demanda["id_demanda"]

    st.markdown(f"#### Demanda seleccionada #{did}")

    # Control de modo edición
    if "editar_demanda_id" not in st.session_state:
        st.session_state["editar_demanda_id"] = None

    modo_edicion = st.session_state["editar_demanda_id"] == did

    col_main, col_actions = st.columns([0.72, 0.28])

    with col_main:
        render_ficha_demanda_seleccionada(demanda)

        # --- MODO EDICIÓN: FORMULARIO (WIDGETS) ---
        if modo_edicion:
            st.divider()
            st.markdown("##### Formulario de edicion")
            
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
                "Nueva acción / actualización de historial",
                height=100, 
                placeholder="Escribí aquí el resumen de la gestión realizada...",
                key=f"nueva_acc_{did}"
            )

    with col_actions:
        st.markdown("#### Acciones")
        if not modo_edicion:
            if st.button("Habilitar edicion", type="primary", use_container_width=True, help="Habilita los campos para modificar los datos"):
                st.session_state["editar_demanda_id"] = did
                st.rerun()
        else:
            if st.button("Guardar cambios", type="primary", use_container_width=True):
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
                        st.toast("Cambios guardados con exito.")
                        st.session_state["editar_demanda_id"] = None
                        if f"nueva_acc_{did}" in st.session_state:
                            del st.session_state[f"nueva_acc_{did}"]
                        st.rerun()
                    except Exception as e:
                        mostrar_error_supabase(e)

            if st.button("Cancelar edicion", use_container_width=True):
                st.session_state["editar_demanda_id"] = None
                st.rerun()

        # --- CIERRE DE DEMANDA (Siempre visible) ---
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("Finalizar expediente", expanded=False):
            st.write("Marcar como resuelta y archivar.")
            confirma_cierre = st.checkbox("Confirmo el cierre definitivo", key=f"conf_cierre_{did}")
            if st.button("Cerrar demanda", disabled=not confirma_cierre, use_container_width=True, type="secondary"):
                try:
                    cerrar_demanda(did)
                    st.toast(f"Demanda #{did} cerrada correctamente.")
                    st.rerun()
                except Exception as e:
                    mostrar_error_supabase(e)


def set_modo_demandas_v2(modo, demanda_id=None):
    st.session_state["demandas_v2_modo"] = modo
    if demanda_id is not None:
        st.session_state["demanda_seleccionada_id"] = demanda_id
    if modo != "editar":
        st.session_state["editar_demanda_id"] = None


def limpiar_filtros_demandas_v2():
    for key in ["dem_v2_busqueda", "dem_v2_f_estado", "dem_v2_f_prioridad", "dem_v2_f_accion"]:
        st.session_state.pop(key, None)


def render_filtros_demandas_v2(df):
    if df.empty:
        return df

    with st.container(border=True, key="dem_v2_filtros"):
        c1, c2, c3, c4, c5 = st.columns([2, 1.15, 1.15, 1.15, 0.7])
        with c1:
            q = st.text_input("Búsqueda libre", placeholder="Expediente, nombre, barrio...", key="dem_v2_busqueda")
        with c2:
            f_estado = st.multiselect("Estado", opciones_filtro(df, "estado"), placeholder="Seleccionar", key="dem_v2_f_estado")
        with c3:
            f_prioridad = st.multiselect("Prioridad", opciones_filtro(df, "prioridad"), placeholder="Seleccionar", key="dem_v2_f_prioridad")
        with c4:
            f_accion = st.multiselect("Acción", opciones_filtro(df, "accion"), placeholder="Seleccionar", key="dem_v2_f_accion")
        with c5:
            st.button(
                "Limpiar",
                use_container_width=True,
                key="dem_v2_limpiar_filtros",
                on_click=limpiar_filtros_demandas_v2,
            )

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


def crear_demanda_panel_v2():
    st.markdown('<div class="dem-v2-section-title">Nueva demanda</div>', unsafe_allow_html=True)
    st.markdown('<div class="dem-v2-section-caption">Carga contextual desde el panel derecho.</div>', unsafe_allow_html=True)

    with st.container(border=True, key="dem_v2_form"):
        expediente_input = st.text_input("Expediente", placeholder="20373/24", key="dem_v2_carga_expediente")
        pedido = st.text_area(
            "Pedido",
            height=90,
            placeholder="Texto que llega por mensaje, llamada o resumen breve.",
            key="dem_v2_carga_pedido",
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            accion = st.selectbox("Acción", ACCIONES, key="dem_v2_carga_accion")
        with c2:
            origen = st.selectbox("Origen", ORIGENES, key="dem_v2_carga_origen")
        with c3:
            responsable = st.selectbox("Responsable", [""] + RESPONSABLES, key="dem_v2_carga_responsable")

        tipo_materiales = None
        if accion == "Entregar materiales":
            tipo_materiales = st.selectbox("Tipo materiales", TIPOS_MATERIALES, key="dem_v2_carga_tipo_mat")

        b1, b2 = st.columns([1, 1])
        with b1:
            guardar = st.button("Guardar demanda", type="primary", use_container_width=True, key="dem_v2_btn_guardar_crear")
        with b2:
            cancelar = st.button("Cancelar", use_container_width=True, key="dem_v2_cancelar_crear")

    if cancelar:
        set_modo_demandas_v2("detalle" if st.session_state.get("demanda_seleccionada_id") else "empty")
        st.rerun()

    if not guardar:
        return

    expte_numero, expte_anio, expediente_texto = parsear_expediente(expediente_input)
    pedido_limpio = limpiar(pedido)
    tipo_materiales_txt = limpiar(tipo_materiales)
    es_stock = accion == "Entregar materiales" and tipo_materiales_txt.lower() in TIPOS_STOCK

    if not expediente_texto and not es_stock:
        st.error("Carga el expediente con formato numero/anio, por ejemplo 20373/24.")
        return
    if not pedido_limpio:
        st.error("Completa el pedido antes de guardar.")
        return

    if es_stock:
        expediente = None
        expte_numero = None
        expte_anio = None
        expediente_texto = "DEP/STOCK"
    else:
        expediente = buscar_expediente(expte_numero, expte_anio)

    observaciones = pedido_limpio
    if accion == "Entregar materiales" and tipo_materiales_txt:
        observaciones = f"Tipo materiales: {tipo_materiales_txt}. Pedido: {pedido_limpio}"

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
        nueva = crear_demanda(datos)
    except Exception as error:
        mostrar_error_supabase(error)
        return

    st.toast("Demanda guardada correctamente.")
    for key in ["dem_v2_carga_expediente", "dem_v2_carga_pedido"]:
        st.session_state.pop(key, None)
    if nueva and nueva.get("id_demanda"):
        set_modo_demandas_v2("detalle", nueva.get("id_demanda"))
    else:
        set_modo_demandas_v2("detalle")
    st.rerun()


def render_datos_demanda_v2(demanda):
    campos = [
        ("Origen", demanda.get("origen")),
        ("Responsable", demanda.get("responsable")),
        ("DNI", demanda.get("dni")),
        ("Domicilio", demanda.get("domicilio")),
        ("Barrio", demanda.get("barrio")),
        ("Contacto", demanda.get("contacto")),
    ]
    items = []
    for label, value in campos:
        items.append(
            '<div class="dem-v2-data-field">'
            f'<div class="dem-v2-data-label">{html.escape(label)}</div>'
            f'<div class="dem-v2-data-value">{html.escape(valor_visible(value))}</div>'
            '</div>'
        )
    st.markdown(
        f'<div class="dem-v2-data-grid">{"".join(items)}</div>',
        unsafe_allow_html=True,
    )


def render_resumen_demanda_v2(demanda):
    did = demanda.get("id_demanda")
    card_key = f"demanda_v2_resumen_{did}"
    operational_card(
        title=nombre_demanda_card(demanda),
        subtitle=f"Expte. {valor_visible(demanda.get('expediente'), 'S/E')}",
        status=valor_visible(demanda.get("estado"), ""),
        priority=valor_visible(demanda.get("prioridad"), ""),
        meta=[
            valor_visible(demanda.get("accion"), "Sin acción"),
            f"Ingreso: {fecha_corta(demanda.get('fecha_ingreso'))}",
        ],
        description=None,
        footer=None,
        variant="default",
        accent_color=color_accion_demanda(demanda.get("accion")),
        selected=True,
        card_key=card_key,
        key=f"{card_key}_card",
    )


def detalle_demanda_panel_v2(demanda):
    did = demanda.get("id_demanda")
    st.markdown(
        f"""
        <div class="dem-v2-detail-titleblock">
        <div class="dem-v2-section-title">Demanda seleccionada</div>
        <div class="dem-v2-section-caption">ID demanda #{valor_visible(did)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_resumen_demanda_v2(demanda)
    with st.container(border=True, key="dem_v2_demand_data_panel"):
        st.markdown('<div class="dem-v2-subblock-title">Datos de la demanda</div>', unsafe_allow_html=True)
        render_datos_demanda_v2(demanda)
        observaciones = valor_visible(demanda.get("observaciones"))
        st.markdown('<div class="dem-v2-subblock-title">Historial / observaciones</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="dem-v2-observaciones-box">{html.escape(observaciones)}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="dem-v2-actions-inline"></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Habilitar edición", type="primary", use_container_width=True, key="dem_v2_btn_editar"):
            set_modo_demandas_v2("editar", did)
            st.session_state["editar_demanda_id"] = did
            st.rerun()
    with c2:
        if st.button("Sincronizar expediente", use_container_width=True, key=f"dem_v2_sync_exp_{did}"):
            expte_numero, expte_anio = expediente_demanda(demanda)
            if not expte_numero or not expte_anio:
                st.warning("La demanda no tiene expediente válido para sincronizar.")
            else:
                try:
                    actualizada = sincronizar_demanda_desde_expediente(did, expte_numero, expte_anio)
                    if actualizada:
                        st.toast("Datos sincronizados desde expedientes.")
                        st.rerun()
                    else:
                        st.warning("No se encontró ese expediente en la base general.")
                except Exception as error:
                    mostrar_error_supabase(error)

    with c3:
        with st.expander("Finalizar expediente", expanded=False):
            st.write("Marcar como resuelta y archivar.")
            confirma_cierre = st.checkbox("Confirmo cierre definitivo", key=f"dem_v2_conf_cierre_{did}")
            if st.button("Cerrar demanda", disabled=not confirma_cierre, use_container_width=True, type="secondary", key=f"dem_v2_cerrar_{did}"):
                try:
                    cerrar_demanda(did)
                    st.toast(f"Demanda #{did} cerrada correctamente.")
                    st.session_state.pop("demanda_seleccionada_id", None)
                    set_modo_demandas_v2("empty")
                    st.rerun()
                except Exception as error:
                    mostrar_error_supabase(error)



def editar_demanda_panel_v2(demanda):
    did = demanda.get("id_demanda")
    st.markdown(
        f"""
        <div class="dem-v2-detail-titleblock">
        <div class="dem-v2-section-title">Editar demanda</div>
        <div class="dem-v2-section-caption">ID demanda #{valor_visible(did)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_resumen_demanda_v2(demanda)
    with st.container(border=True, key="dem_v2_edit_panel"):
        with st.container(border=True, key="dem_v2_edit"):
            categoria, estados = estados_para_demanda(demanda)
            c1, c2, c3 = st.columns(3)
            estado_val = c1.selectbox(
                "Estado",
                estados,
                index=estados.index(demanda.get("estado")) if demanda.get("estado") in estados else 0,
                key=f"dem_v2_estado_{did}",
            )
            prioridad_val = c2.selectbox(
                "Prioridad",
                PRIORIDADES,
                index=PRIORIDADES.index(demanda.get("prioridad")) if demanda.get("prioridad") in PRIORIDADES else 2,
                key=f"dem_v2_prioridad_{did}",
            )
            responsable_val = c3.selectbox(
                "Responsable",
                [""] + RESPONSABLES,
                index=([""] + RESPONSABLES).index(demanda.get("responsable") or "") if demanda.get("responsable") in RESPONSABLES else 0,
                key=f"dem_v2_responsable_{did}",
            )

            c4, c5, c6 = st.columns(3)
            apellido_v = c4.text_input("Apellido", value=texto(demanda.get("apellido")), key=f"dem_v2_apellido_{did}")
            nombre_v = c5.text_input("Nombre", value=texto(demanda.get("nombre")), key=f"dem_v2_nombre_{did}")
            dni_v = c6.text_input("DNI", value=texto(demanda.get("dni")), key=f"dem_v2_dni_{did}")

            c7, c8, c9 = st.columns(3)
            dom_v = c7.text_input("Domicilio", value=texto(demanda.get("domicilio")), key=f"dem_v2_dom_{did}")
            bar_v = c8.text_input("Barrio", value=texto(demanda.get("barrio")), key=f"dem_v2_barrio_{did}")
            con_v = c9.text_input("Contacto", value=texto(demanda.get("contacto")), key=f"dem_v2_contacto_{did}")

            nueva_accion = st.text_area(
                "Nueva acción / actualización de historial",
                height=90,
                placeholder="Resumen de la gestión realizada...",
                key=f"dem_v2_nueva_acc_{did}",
            )

            actualizar_base_exp = st.checkbox(
                "Actualizar también la base general de expedientes con estos datos personales",
                value=False,
                key=f"dem_v2_sync_base_exp_{did}",
            )

            b1, b2 = st.columns([1, 1])
            with b1:
                guardar = st.button("Guardar cambios", type="primary", use_container_width=True, key=f"dem_v2_guardar_edit_{did}")
            with b2:
                cancelar = st.button("Cancelar edición", use_container_width=True, key=f"dem_v2_cancel_edit_{did}")

    if cancelar:
        set_modo_demandas_v2("detalle", did)
        st.rerun()

    if not guardar:
        return

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
    cambios = detectar_cambios(demanda, nuevos_valores)
    if not cambios and not limpiar(nueva_accion):
        st.info("No hay cambios para guardar.")
        return
    try:
        actualizar_demanda(
            did,
            {
                **nuevos_valores,
                "observaciones": agregar_al_historial(demanda.get("observaciones"), nueva_accion, cambios),
            },
        )
        if actualizar_base_exp:
            expte_numero, expte_anio = expediente_demanda(demanda)
            if expte_numero and expte_anio:
                actualizar_expediente_desde_demanda(expte_numero, expte_anio, nuevos_valores)
    except Exception as error:
        mostrar_error_supabase(error)
        return
    st.toast("Cambios guardados con éxito.")
    set_modo_demandas_v2("detalle", did)
    st.rerun()


def demandas_v2():
    cargar_estilos_demandas_v2()
    st.markdown(
        """
        <div class="dem-v2-header">
            <h1 class="dem-v2-title">Demandas</h1>
            <div class="dem-v2-subtitle">Carga, consulta y actualizaci&oacute;n de solicitudes ingresadas al &aacute;rea.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    demandas = listar_demandas_pendientes()
    df = pd.DataFrame(demandas)
    render_demandas_kpis_v2(df)
    st.markdown('<div style="height: 14px;"></div>', unsafe_allow_html=True)
    df_filtrado = render_filtros_demandas_v2(df)

    st.session_state.setdefault("demandas_v2_modo", "detalle" if st.session_state.get("demanda_seleccionada_id") else "empty")
    compactar_espaciado_operational_cards("dem_v2_card_list")

    col_listado, col_detalle = st.columns([0.43, 0.57], gap="medium")
    with col_listado:
        h1, h2 = st.columns([1, 0.42], vertical_alignment="center")
        with h1:
            st.markdown(
                """
                <div class="dem-v2-section-title">Listado de demandas</div>
                <div class="dem-v2-section-caption">Demandas activas segun filtros aplicados.</div>
                """,
                unsafe_allow_html=True,
            )
        with h2:
            if st.button("+ Crear demanda", type="primary", use_container_width=False, key="dem_v2_btn_crear"):
                set_modo_demandas_v2("crear")
                st.rerun()

        if df_filtrado.empty:
            st.info("No hay demandas que coincidan con los filtros.")
        else:
            with st.container(height=690, key="dem_v2_card_list"):
                for _, fila in df_filtrado.iterrows():
                    demanda_card = fila.to_dict()
                    did_card = demanda_card.get("id_demanda")
                    card_key = f"demanda_v2_{did_card}"
                    seleccionada = str(st.session_state.get("demanda_seleccionada_id", "")) == str(did_card)
                    resultado = operational_card(
                        title=nombre_demanda_card(demanda_card),
                        subtitle=f"Expte. {valor_visible(demanda_card.get('expediente'), 'S/E')}",
                        status=valor_visible(demanda_card.get("estado"), ""),
                        priority=valor_visible(demanda_card.get("prioridad"), ""),
                        meta=[
                            valor_visible(demanda_card.get("accion"), "Sin acción"),
                            ubicacion_demanda_card(demanda_card),
                            f"Ingreso: {fecha_corta(demanda_card.get('fecha_ingreso'))}",
                        ],
                        variant="default",
                        accent_color=color_accion_demanda(demanda_card.get("accion")),
                        clickable=True,
                        selected=seleccionada,
                        card_key=card_key,
                        key=f"demanda_v2_card_{did_card}",
                    )
                    if card_click_resultado(resultado, card_key):
                        set_modo_demandas_v2("detalle", did_card)
                        st.rerun()

    with col_detalle:
        modo = st.session_state.get("demandas_v2_modo", "empty")
        demanda_seleccionada_id = st.session_state.get("demanda_seleccionada_id")

        if modo == "crear":
            crear_demanda_panel_v2()
            return

        if demanda_seleccionada_id is None:
            st.markdown('<div class="dem-v2-section-title">Demanda seleccionada</div>', unsafe_allow_html=True)
            st.markdown('<div class="dem-v2-empty">Selecciona una demanda del listado para ver detalle y acciones.</div>', unsafe_allow_html=True)
            return

        if df.empty or "id_demanda" not in df.columns:
            st.session_state.pop("demanda_seleccionada_id", None)
            set_modo_demandas_v2("empty")
            st.markdown('<div class="dem-v2-empty">No hay demandas activas para mostrar.</div>', unsafe_allow_html=True)
            return

        demanda_sel = df[df["id_demanda"].astype(str) == str(demanda_seleccionada_id)]
        if demanda_sel.empty:
            st.session_state.pop("demanda_seleccionada_id", None)
            set_modo_demandas_v2("empty")
            st.markdown('<div class="dem-v2-empty">La demanda seleccionada ya no esta disponible.</div>', unsafe_allow_html=True)
            return

        demanda = demanda_sel.iloc[0].to_dict()
        if modo == "editar":
            editar_demanda_panel_v2(demanda)
        else:
            detalle_demanda_panel_v2(demanda)


require_login(["admin", "tecnico"])

aplicar_estilos_globales()

demandas_v2()
