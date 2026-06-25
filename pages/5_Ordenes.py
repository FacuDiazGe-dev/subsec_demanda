from html import escape

import streamlit as st

from utils.auth import require_login
from services.demandas_service import listar_demandas_pendientes
from services.materiales_base_service import listar_materiales_base_activos
from services.materiales_orden_service import (
    crear_materiales_orden,
    eliminar_materiales_por_orden,
    listar_materiales_por_orden,
    reemplazar_materiales_orden,
)
from services.ordenes_service import (
    actualizar_orden_detalle,
    crear_orden_material,
    eliminar_orden_material,
    listar_ordenes_con_demanda,
    obtener_datos_pdf_orden,
)
from services.pdf_orden_service import generar_pdf_orden
from utils.operational_card_component import operational_card
from utils.operational_list_editor_component import operational_list_editor


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


def mostrar_error_supabase(error):
    mensaje = str(error)
    if "row-level security" in mensaje:
        st.error("Supabase bloqueo la operacion por RLS. Revisa policies de la tabla.")
        return
    st.error(f"No se pudo completar la operacion en Supabase: {mensaje}")


@st.cache_data(ttl=300)
def opciones_materiales_base():
    materiales = listar_materiales_base_activos()
    opciones = []
    mapa = {}
    for item in materiales:
        material = limpiar(item.get("material"))
        if not material:
            continue
        tipo = limpiar(item.get("tipo"))
        unidad = limpiar(item.get("unidad"))
        etiqueta = " - ".join([x for x in [material, tipo, unidad] if x])
        opciones.append(etiqueta)
        mapa[etiqueta] = material
    return opciones, mapa


def nombre_pdf(orden, demanda):
    expte = limpiar(demanda.get("expediente")).replace("/", "-").replace("\\", "-") or "sin-expediente"
    return f"orden_N{orden.get('n_orden')}_expte_{expte}.pdf"


def sin_dato(valor):
    valor = limpiar(valor)
    return valor if valor and valor.lower() not in {"nan", "none", "null", "-"} else "Sin dato"


def normalizar_texto(valor):
    return limpiar(valor).lower()


def nombre_persona_orden(orden):
    apellido = limpiar(orden.get("apellido")).upper()
    nombre = limpiar(orden.get("nombre"))
    if apellido and nombre:
        return f"{apellido}, {nombre}"
    return apellido or nombre or "Sin titular"


def estado_variante_orden(estado):
    estado_n = normalizar_texto(estado)
    if "cancel" in estado_n:
        return "danger"
    if "entregado" in estado_n:
        return "success"
    if "parcial" in estado_n:
        return "warning"
    if "pendiente" in estado_n:
        return "highlight"
    if "deposito" in estado_n:
        return "default"
    if "pedido" in estado_n:
        return "warning"
    return "muted"


def color_estado_orden(estado):
    estado_n = normalizar_texto(estado)
    if "cancel" in estado_n:
        return "#dc2626"
    if "entregado" in estado_n:
        return "#16a34a"
    if "parcial" in estado_n:
        return "#d97706"
    if "pendiente" in estado_n:
        return "#1d4ed8"
    if "deposito" in estado_n:
        return "#0f766e"
    if "pedido" in estado_n:
        return "#f59e0b"
    return "#94a3b8"


def card_event_once(resultado, card_key, action=None):
    if not isinstance(resultado, dict):
        return False
    if resultado.get("card_key") != card_key:
        return False
    if action and resultado.get("action") != action:
        return False
    event_id = resultado.get("event_id")
    if not event_id:
        return False
    vistos = st.session_state.setdefault("_ordenes_card_eventos_vistos", [])
    if event_id in vistos:
        return False
    vistos.append(event_id)
    st.session_state["_ordenes_card_eventos_vistos"] = vistos[-100:]
    return True


def editor_event_once(resultado, scope, action=None):
    if not isinstance(resultado, dict):
        return False
    if action and resultado.get("action") != action:
        return False
    event_id = resultado.get("event_id")
    if not event_id:
        return False
    key = f"_ordenes_editor_eventos_vistos_{scope}"
    vistos = st.session_state.setdefault(key, [])
    if event_id in vistos:
        return False
    vistos.append(event_id)
    st.session_state[key] = vistos[-40:]
    return True


def filas_materiales_read(materiales):
    return [
        {
            "id": idx,
            "item_id": limpiar(m.get("Material")),
            "item_label": limpiar(m.get("Material")),
            "quantity": limpiar(m.get("cantidad")),
        }
        for idx, m in enumerate(materiales or [])
        if limpiar(m.get("Material"))
    ]


def materiales_desde_editor(rows):
    materiales = []
    for row in rows or []:
        if row.get("deleted"):
            continue
        material = limpiar(row.get("item_label") or row.get("item_id") or row.get("Material"))
        cantidad = limpiar(row.get("quantity") or row.get("cantidad"))
        if material:
            materiales.append({"Material": material, "cantidad": cantidad})
    return materiales


def numero_material(valor):
    valor = limpiar(valor).replace(",", ".")
    if not valor:
        return None
    try:
        numero = float(valor)
    except ValueError:
        return None
    return int(numero) if numero.is_integer() else numero


def consolidar_materiales_orden(materiales):
    consolidados = {}
    orden = []
    duplicados = set()
    for material in materiales:
        nombre = limpiar(material.get("Material"))
        if not nombre:
            continue
        clave = nombre.casefold()
        cantidad_raw = limpiar(material.get("cantidad"))
        cantidad_num = numero_material(cantidad_raw)
        if clave not in consolidados:
            consolidados[clave] = {
                "Material": nombre,
                "cantidad": cantidad_num if cantidad_num is not None else cantidad_raw,
                "_numerica": cantidad_num is not None,
            }
            orden.append(clave)
            continue

        duplicados.add(nombre)
        actual = consolidados[clave]
        if actual["_numerica"] and cantidad_num is not None:
            actual["cantidad"] = actual["cantidad"] + cantidad_num
        elif cantidad_raw and cantidad_raw not in str(actual["cantidad"]):
            actual["cantidad"] = f"{actual['cantidad']} + {cantidad_raw}"
            actual["_numerica"] = False

    resultado = []
    for clave in orden:
        item = consolidados[clave]
        cantidad = item["cantidad"]
        if isinstance(cantidad, float) and cantidad.is_integer():
            cantidad = int(cantidad)
        resultado.append({"Material": item["Material"], "cantidad": str(cantidad)})
    return resultado, sorted(duplicados)


def nombre_demanda(demanda):
    apellido = limpiar(demanda.get("apellido")).upper()
    nombre = limpiar(demanda.get("nombre"))
    if apellido and nombre:
        return f"{apellido}, {nombre}"
    return apellido or nombre or "Sin titular"


def catalogo_materiales_operativo():
    opciones, mapa = opciones_materiales_base()
    catalogo = []
    for etiqueta in opciones:
        material = limpiar(mapa.get(etiqueta, etiqueta))
        if not material:
            continue
        partes = [limpiar(p) for p in etiqueta.split(" - ")]
        unidad = partes[-1] if len(partes) >= 2 else ""
        catalogo.append({"id": material, "label": material, "unit": unidad})
    return catalogo


def demandas_para_crear_orden():
    try:
        demandas = listar_demandas_pendientes()
    except Exception:
        return []

    resultado = []
    for demanda in demandas:
        if limpiar(demanda.get("accion")) != "Entregar materiales":
            continue
        resultado.append(demanda)
    return resultado


def ordenes_v2_css():
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1380px !important;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
        }
        .ord-v2-header-title {
            color: #0f2742;
            font-size: 25px;
            font-weight: 850;
            line-height: 1.15;
            margin: 0 0 2px;
        }
        .ord-v2-header-subtitle {
            color: #64748b;
            font-size: 13px;
            font-weight: 650;
            margin: 0 0 10px;
        }
        .ord-v2-kpi-grid {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 8px;
            margin: 8px 0 10px;
        }
        .ord-v2-kpi {
            background: #ffffff;
            border: 1px solid #dbe7ee;
            border-left: 4px solid #006b68;
            border-radius: 10px;
            padding: 7px 9px;
            min-height: 48px;
            box-shadow: 0 1px 6px rgba(15, 23, 42, 0.035);
        }
        .ord-v2-kpi-label {
            color: #64748b;
            font-size: 10px;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: 0.02em;
        }
        .ord-v2-kpi-value {
            color: #0f2742;
            font-size: 19px;
            font-weight: 850;
            line-height: 1.05;
            margin-top: 3px;
        }
        div[class*="st-key-ord_v2_filtros"] [data-testid="stVerticalBlockBorderWrapper"],
        div[class*="st-key-ord_v2_detail_panel"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff !important;
            border-color: #dbe7ee !important;
            border-radius: 13px !important;
            padding: 11px 12px !important;
            box-shadow: 0 1px 7px rgba(15, 23, 42, 0.035) !important;
        }
        div[class*="st-key-ord_v2_filtros"] label,
        div[class*="st-key-ord_v2_detail_panel"] label {
            color: #475569 !important;
            font-size: 12px !important;
            font-weight: 700 !important;
            margin-bottom: 2px !important;
        }
        div[class*="st-key-ord_v2_filtros"] input,
        div[class*="st-key-ord_v2_filtros"] [data-baseweb="select"] > div,
        div[class*="st-key-ord_v2_detail_panel"] input,
        div[class*="st-key-ord_v2_detail_panel"] textarea,
        div[class*="st-key-ord_v2_detail_panel"] [data-baseweb="select"] > div {
            background: #f8fafc !important;
            border-color: #dbe7ee !important;
            font-size: 13px !important;
        }
        div[class*="st-key-ord_v2_detail_panel"] [data-testid="stFormSubmitButton"] button {
            min-height: 36px !important;
            height: 36px !important;
            border-radius: 10px !important;
            font-size: 13px !important;
            font-weight: 750 !important;
            box-shadow: none !important;
        }
        div[class*="st-key-ord_v2_detail_panel"] [data-testid="stFormSubmitButton"] button[kind="primary"],
        div[class*="st-key-ord_v2_detail_panel"] button[kind="primary"] {
            background: #006b68 !important;
            border-color: #006b68 !important;
            color: #ffffff !important;
        }
        div[class*="st-key-ord_v2_detail_panel"] [data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
        div[class*="st-key-ord_v2_detail_panel"] button[kind="primary"]:hover {
            background: #004f4c !important;
            border-color: #004f4c !important;
        }
        div[class*="st-key-ord_v2_del_"] button {
            background: #fff1f2 !important;
            border-color: #fecdd3 !important;
            color: #be123c !important;
            font-weight: 800 !important;
            box-shadow: none !important;
        }
        div[class*="st-key-ord_v2_del_"] button:hover {
            background: #ffe4e6 !important;
            border-color: #fb7185 !important;
            color: #9f1239 !important;
        }
        .ord-v2-section-title {
            color: #0f2742;
            font-size: 18px;
            font-weight: 850;
            margin: 2px 0 2px;
        }
        .ord-v2-section-caption {
            color: #64748b;
            font-size: 12px;
            font-weight: 650;
            margin: 0 0 8px;
        }
        .ord-v2-field-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px;
            margin: 8px 0;
        }
        .ord-v2-field {
            background: #f8fafc;
            border: 1px solid #dbe7ee;
            border-radius: 10px;
            padding: 8px 9px;
        }
        .ord-v2-field-label {
            color: #64748b;
            font-size: 10px;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: 0.02em;
            margin-bottom: 3px;
        }
        .ord-v2-field-value {
            color: #0f2742;
            font-size: 13px;
            font-weight: 750;
            overflow-wrap: anywhere;
        }
        .ord-v2-textbox {
            background: #f8fafc;
            border: 1px solid #dbe7ee;
            border-radius: 10px;
            color: #0f2742;
            font-size: 13px;
            line-height: 1.35;
            padding: 9px 10px;
            margin: 8px 0 10px;
            max-height: 120px;
            overflow-y: auto;
        }
        .ord-v2-subblock {
            border-top: 1px solid #e2e8f0;
            margin-top: 12px;
            padding-top: 10px;
        }
        .ord-v2-subtitle {
            color: #0f2742;
            font-size: 15px;
            font-weight: 850;
            margin: 0 0 3px;
        }
        .ord-v2-subcaption {
            color: #64748b;
            font-size: 12px;
            font-weight: 650;
            margin: 0 0 8px;
        }
        .ord-v2-empty {
            background: #ffffff;
            border: 1px dashed #cbd5e1;
            border-radius: 12px;
            color: #64748b;
            font-size: 13px;
            font-weight: 700;
            padding: 14px;
        }
        @media (max-width: 900px) {
            .ord-v2-kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .ord-v2-field-grid { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_kpis_ordenes(ordenes):
    def cuenta(pred):
        return sum(1 for o in ordenes if pred(limpiar(o.get("estado"))))

    kpis = [
        ("Pedidos", cuenta(lambda e: e in {"Pedido entrega", "Pedido retiro", "Pedido"})),
        ("Programadas", cuenta(lambda e: e in {"Pendiente de entrega", "Pendiente de retiro"})),
        ("En deposito", cuenta(lambda e: "deposito" in e.lower())),
        ("Entregadas", cuenta(lambda e: e == "Entregado")),
        ("Parciales", cuenta(lambda e: "parcial" in e.lower())),
        ("Canceladas", cuenta(lambda e: e in {"Cancelado", "Cerrado"})),
    ]
    html = '<div class="ord-v2-kpi-grid">'
    for label, value in kpis:
        html += (
            '<div class="ord-v2-kpi">'
            f'<div class="ord-v2-kpi-label">{escape(label)}</div>'
            f'<div class="ord-v2-kpi-value">{value}</div>'
            '</div>'
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def aplicar_filtros_ordenes_v2(ordenes):
    with st.container(border=True, key="ord_v2_filtros"):
        c1, c2, c3, c4 = st.columns([2.0, 1.2, 1.2, 1.2])
        with c1:
            q = st.text_input("Busqueda libre", placeholder="N orden, expediente, apellido, barrio...", key="ord_v2_q")
        with c2:
            estados = sorted({limpiar(o.get("estado")) for o in ordenes if limpiar(o.get("estado"))})
            f_estado = st.multiselect("Estado", estados, placeholder="Todos", key="ord_v2_estado")
        with c3:
            origenes = sorted({limpiar(o.get("origen")) for o in ordenes if limpiar(o.get("origen"))})
            f_origen = st.multiselect("Origen", origenes, placeholder="Todos", key="ord_v2_origen")
        with c4:
            prioridades = sorted({limpiar(o.get("prioridad_demanda")) for o in ordenes if limpiar(o.get("prioridad_demanda"))})
            f_prioridad = st.multiselect("Prioridad", prioridades, placeholder="Todas", key="ord_v2_prioridad")

    qn = limpiar(q).lower()
    filtradas = []
    for orden in ordenes:
        if f_estado and limpiar(orden.get("estado")) not in f_estado:
            continue
        if f_origen and limpiar(orden.get("origen")) not in f_origen:
            continue
        if f_prioridad and limpiar(orden.get("prioridad_demanda")) not in f_prioridad:
            continue
        if qn:
            valores = [
                orden.get("n_orden"),
                orden.get("id_demanda"),
                orden.get("expediente"),
                orden.get("apellido"),
                orden.get("nombre"),
                orden.get("dni"),
                orden.get("domicilio"),
                orden.get("barrio"),
                orden.get("instrucciones_tarea"),
            ]
            if not any(qn in limpiar(v).lower() for v in valores):
                continue
        filtradas.append(orden)
    return filtradas


def crear_orden_panel():
    st.markdown('<div class="ord-v2-section-title">Nueva orden</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ord-v2-section-caption">Genera una orden desde una demanda de entrega de materiales.</div>',
        unsafe_allow_html=True,
    )

    demandas = demandas_para_crear_orden()
    if not demandas:
        st.markdown(
            '<div class="ord-v2-empty">No hay demandas activas de tipo Entregar materiales para generar ordenes.</div>',
            unsafe_allow_html=True,
        )
        return

    opciones = {
        f"Demanda #{texto(d.get('id_demanda'))} | {nombre_demanda(d)} | Expte. {sin_dato(d.get('expediente'))}": d
        for d in demandas
    }
    etiquetas = list(opciones.keys())
    seleccion_actual = st.session_state.get("ord_v2_crear_demanda_label")
    if seleccion_actual not in opciones:
        seleccion_actual = etiquetas[0]
        st.session_state["ord_v2_crear_demanda_label"] = seleccion_actual

    seleccion = st.selectbox(
        "Demanda origen",
        etiquetas,
        index=etiquetas.index(seleccion_actual),
        key="ord_v2_crear_demanda_label",
    )
    demanda = opciones.get(seleccion)
    if not demanda:
        st.markdown('<div class="ord-v2-empty">Selecciona una demanda para continuar.</div>', unsafe_allow_html=True)
        return

    operational_card(
        title=f"{nombre_demanda(demanda)} · Expte. {sin_dato(demanda.get('expediente'))}",
        subtitle=f"Demanda #{texto(demanda.get('id_demanda'))} · {sin_dato(demanda.get('domicilio'))} - {sin_dato(demanda.get('barrio'))}",
        status=sin_dato(demanda.get("estado")),
        priority=limpiar(demanda.get("prioridad")) or None,
        meta=[
            f"Accion: {sin_dato(demanda.get('accion'))}",
            f"Origen: {sin_dato(demanda.get('origen'))}",
            f"Contacto: {sin_dato(demanda.get('contacto'))}",
        ],
        description=limpiar(demanda.get("observaciones")),
        footer=f"DNI: {sin_dato(demanda.get('dni'))}",
        variant="highlight",
        accent_color="#0284c7",
        selected=True,
        card_key=f"ord_v2_demanda_{texto(demanda.get('id_demanda'))}",
        key=f"ord_v2_demanda_card_{texto(demanda.get('id_demanda'))}",
    )

    estado_orden = st.selectbox(
        "Tipo de orden",
        ["Pedido entrega", "Pedido retiro"],
        key=f"ord_v2_crear_tipo_{texto(demanda.get('id_demanda'))}",
    )
    instrucciones = st.text_area(
        "Instruccion",
        value=limpiar(demanda.get("observaciones")) or f"Orden creada desde Demanda #{texto(demanda.get('id_demanda'))}.",
        height=92,
        key=f"ord_v2_crear_instr_{texto(demanda.get('id_demanda'))}",
    )
    resultado_mats = operational_list_editor(
        title="Materiales de la orden",
        rows=st.session_state.setdefault("ord_v2_crear_materiales", []),
        catalog=catalogo_materiales_operativo(),
        help_text="Seleccione materiales del catalogo y cargue la cantidad solicitada.",
        add_label="Agregar material",
        save_label="Generar orden",
        item_label="Material",
        mode="build",
        show_unit=True,
        allow_delete=True,
        embedded=True,
        key="ord_v2_crear_materiales_editor",
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Cancelar", use_container_width=True, key="ord_v2_cancelar_crear"):
            st.session_state["ord_v2_modo"] = "detalle"
            st.rerun()
    with c2:
        st.empty()

    if editor_event_once(resultado_mats, "crear_orden", "save"):
        filas_editor = resultado_mats.get("rows") or []
        st.session_state["ord_v2_crear_materiales"] = filas_editor
        materiales, duplicados = consolidar_materiales_orden(materiales_desde_editor(filas_editor))
        if not materiales:
            st.warning("Agrega al menos un material para generar la orden.")
            return

        try:
            nueva = crear_orden_material(
                {
                    "id_demanda": demanda.get("id_demanda"),
                    "origen": limpiar(demanda.get("origen")) or "Demandas",
                    "estado": estado_orden,
                    "instrucciones_tarea": limpiar(instrucciones) or f"Orden creada desde Demanda #{texto(demanda.get('id_demanda'))}.",
                }
            )
            if nueva:
                crear_materiales_orden(nueva.get("n_orden"), materiales)
        except Exception as error:
            mostrar_error_supabase(error)
        else:
            if duplicados:
                st.warning(f"Se unificaron materiales repetidos: {', '.join(duplicados)}.")
            st.success("Orden generada.")
            st.session_state["orden_v2_sel"] = nueva.get("n_orden") if nueva else None
            st.session_state["ord_v2_modo"] = "detalle"
            st.session_state["ord_v2_crear_materiales"] = []
            st.rerun()


def ordenes_v2_tab():
    ordenes_v2_css()
    st.markdown('<div class="ord-v2-header-title">Ordenes</div>', unsafe_allow_html=True)
    st.markdown('<div class="ord-v2-header-subtitle">Consulta, seguimiento y gestion de ordenes de materiales.</div>', unsafe_allow_html=True)
    st.session_state.setdefault("ord_v2_modo", "detalle")
    st.session_state.setdefault("ord_v2_crear_materiales", [])

    try:
        ordenes = listar_ordenes_con_demanda(incluir_cerradas=True)
    except Exception as error:
        mostrar_error_supabase(error)
        return
    if not ordenes:
        st.info("No hay ordenes cargadas.")
        return

    render_kpis_ordenes(ordenes)
    filtradas = aplicar_filtros_ordenes_v2(ordenes)

    col_list, col_detail = st.columns([0.45, 0.55])
    with col_list:
        h1, h2 = st.columns([1, 0.42], vertical_alignment="center")
        with h1:
            st.markdown('<div class="ord-v2-section-title">Listado de ordenes</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="ord-v2-section-caption">{len(filtradas)} ordenes segun filtros aplicados.</div>', unsafe_allow_html=True)
        with h2:
            if st.button("+ Crear orden", type="primary", use_container_width=False, key="ord_v2_btn_crear"):
                st.session_state["ord_v2_modo"] = "crear"
                st.session_state["ord_v2_crear_materiales"] = []
                st.rerun()
        if not filtradas:
            st.markdown('<div class="ord-v2-empty">Sin resultados con esos filtros.</div>', unsafe_allow_html=True)
        ordenes_activas = [o for o in filtradas if limpiar(o.get("estado")) not in {"Entregado", "Cancelado", "Cerrado"}]
        ordenes_archivadas = [o for o in filtradas if limpiar(o.get("estado")) in {"Entregado", "Cancelado", "Cerrado"}]

        def render_card_orden_lista(orden, sufijo=""):
            n_orden = orden.get("n_orden")
            ck = f"orden_v2_{sufijo}{n_orden}"
            selected = st.session_state.get("orden_v2_sel") == n_orden
            accion = operational_card(
                title=f"{nombre_persona_orden(orden)} · Expte. {sin_dato(orden.get('expediente'))}",
                subtitle=f"Orden N° {texto(n_orden)} · {sin_dato(orden.get('domicilio'))} - {sin_dato(orden.get('barrio'))}",
                status=sin_dato(orden.get("estado")),
                priority=limpiar(orden.get("prioridad_demanda")) or None,
                meta=[
                    f"Emision: {fecha_visible(orden.get('fecha_emision'))}",
                    f"Origen: {sin_dato(orden.get('origen'))}",
                ],
                description=limpiar(orden.get("instrucciones_tarea")),
                footer=f"Demanda ID: {sin_dato(orden.get('id_demanda'))}",
                variant=estado_variante_orden(orden.get("estado")),
                accent_color=color_estado_orden(orden.get("estado")),
                clickable=True,
                selected=selected,
                card_key=ck,
                key=f"{ck}_card",
            )
            if card_event_once(accion, ck, "card_click"):
                st.session_state["orden_v2_sel"] = n_orden
                st.session_state["ord_v2_modo"] = "detalle"
                st.rerun()

        for orden in ordenes_activas:
            render_card_orden_lista(orden)

        if ordenes_archivadas:
            with st.expander(f"Entregadas / canceladas ({len(ordenes_archivadas)})", expanded=False):
                for orden in ordenes_archivadas:
                    render_card_orden_lista(orden, sufijo="arch_")

    with col_detail:
        if st.session_state.get("ord_v2_modo") == "crear":
            crear_orden_panel()
            return

        st.markdown('<div class="ord-v2-section-title">Orden seleccionada</div>', unsafe_allow_html=True)
        n_sel = st.session_state.get("orden_v2_sel")
        orden = next((o for o in ordenes if o.get("n_orden") == n_sel), None) if n_sel else None
        if not orden:
            st.markdown('<div class="ord-v2-empty">Selecciona una orden del listado para ver detalle y acciones.</div>', unsafe_allow_html=True)
            return

        demanda = orden.get("demanda") or {}
        with st.container(border=True, key=f"ord_v2_detail_panel_{n_sel}"):
            operational_card(
                title=f"Orden N° {texto(n_sel)}",
                subtitle=f"{nombre_persona_orden(orden)} · Expte. {sin_dato(orden.get('expediente'))}",
                status=sin_dato(orden.get("estado")),
                priority=limpiar(demanda.get("prioridad")) or None,
                meta=[
                    f"Origen: {sin_dato(orden.get('origen'))}",
                    f"Accion: {sin_dato(demanda.get('accion'))}",
                    f"Responsable: {sin_dato(demanda.get('responsable'))}",
                    f"Emision: {fecha_visible(orden.get('fecha_emision'))}",
                    f"Entrega: {fecha_visible(orden.get('fecha_entrega'))}",
                ],
                description=limpiar(orden.get("instrucciones_tarea")),
                footer=f"Domicilio: {sin_dato(demanda.get('domicilio'))} - {sin_dato(demanda.get('barrio'))}",
                variant=estado_variante_orden(orden.get("estado")),
                accent_color=color_estado_orden(orden.get("estado")),
                selected=True,
                card_key=f"orden_v2_detail_{n_sel}",
                key=f"orden_v2_detail_card_{n_sel}",
            )

            st.markdown(
                f"""
                <div class="ord-v2-field-grid">
                    <div class="ord-v2-field"><div class="ord-v2-field-label">ID demanda</div><div class="ord-v2-field-value">{escape(sin_dato(orden.get('id_demanda')))}</div></div>
                    <div class="ord-v2-field"><div class="ord-v2-field-label">DNI</div><div class="ord-v2-field-value">{escape(sin_dato(demanda.get('dni')))}</div></div>
                    <div class="ord-v2-field"><div class="ord-v2-field-label">Contacto</div><div class="ord-v2-field-value">{escape(sin_dato(demanda.get('contacto')))}</div></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            historial = limpiar(orden.get("historial"))
            with st.expander("Historial", expanded=False):
                st.write(historial or "Sin historial registrado.")

            st.markdown(
                """
                <div class="ord-v2-subblock">
                    <div class="ord-v2-subtitle">Editar orden</div>
                    <div class="ord-v2-subcaption">Actualiza estado, instruccion y listado de materiales.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            estado_actual = orden.get("estado")
            estado_idx = ESTADOS_ORDEN.index(estado_actual) if estado_actual in ESTADOS_ORDEN else 0
            nuevo_estado = st.selectbox("Estado", ESTADOS_ORDEN, index=estado_idx, key=f"ord_v2_estado_{n_sel}")
            instrucciones_edit = st.text_area(
                "Instruccion",
                value=texto(orden.get("instrucciones_tarea")),
                height=92,
                key=f"ord_v2_instr_{n_sel}",
            )

            try:
                materiales = listar_materiales_por_orden(n_sel)
            except Exception as error:
                mostrar_error_supabase(error)
                materiales = []
            resultado_mats = operational_list_editor(
                title="Materiales de la orden",
                rows=filas_materiales_read(materiales),
                catalog=catalogo_materiales_operativo(),
                help_text="Edite cantidades, agregue o quite materiales. El boton actualiza la orden completa.",
                add_label="Agregar material",
                save_label="Actualizar orden",
                item_label="Material",
                mode="build",
                show_unit=True,
                allow_delete=True,
                embedded=True,
                key=f"ord_v2_edit_materiales_{n_sel}",
            )
            if editor_event_once(resultado_mats, f"materiales_{n_sel}", "save"):
                filas_editor = resultado_mats.get("rows") or []
                nuevos = []
                for row in filas_editor:
                    if row.get("deleted"):
                        continue
                    material = limpiar(row.get("item_label") or row.get("item_id") or row.get("Material"))
                    cantidad = limpiar(row.get("quantity") or row.get("cantidad"))
                    if material:
                        nuevos.append({"Material": material, "cantidad": cantidad})
                nuevos, duplicados = consolidar_materiales_orden(nuevos)
                try:
                    actualizar_orden_detalle(n_sel, nuevo_estado, instrucciones_edit)
                    reemplazar_materiales_orden(n_sel, nuevos)
                except Exception as error:
                    mostrar_error_supabase(error)
                else:
                    if duplicados:
                        st.warning(f"Se unificaron materiales repetidos: {', '.join(duplicados)}.")
                    st.success("Orden actualizada.")
                    st.session_state.pop(f"ord_v2_edit_materiales_{n_sel}", None)
                    st.rerun()

            try:
                datos_pdf = obtener_datos_pdf_orden(n_sel)
                if datos_pdf:
                    pdf = generar_pdf_orden(datos_pdf["orden"], datos_pdf["demanda"], datos_pdf["materiales"])
                    st.download_button(
                        "Descargar orden PDF",
                        data=pdf,
                        file_name=nombre_pdf(datos_pdf["orden"], datos_pdf["demanda"]),
                        mime="application/pdf",
                        use_container_width=True,
                    )
            except Exception as error:
                mostrar_error_supabase(error)

            with st.expander("Zona de peligro", expanded=False):
                check = st.checkbox(f"Confirmo eliminar la orden {n_sel}", key=f"ord_v2_del_check_{n_sel}")
                if st.button("Eliminar orden", disabled=not check, use_container_width=True, key=f"ord_v2_del_{n_sel}"):
                    try:
                        eliminar_materiales_por_orden(n_sel)
                        eliminar_orden_material(n_sel)
                    except Exception as error:
                        mostrar_error_supabase(error)
                    else:
                        st.success("Orden eliminada.")
                        st.session_state.pop("orden_v2_sel", None)
                        st.rerun()


require_login(["admin", "tecnico"])
st.title("Ordenes")

ordenes_v2_tab()
