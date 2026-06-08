import streamlit as st

from utils.auth import require_login
from utils.ui_components import render_operational_card
from utils.operational_card_component import operational_card
from utils.operational_attendance_board_component import operational_attendance_board
from utils.operational_list_editor_component import operational_list_editor
from utils.operational_table_component import render_operational_editable_table
from utils.ui_styles import aplicar_estilos_globales
from services.demandas_service import listar_demandas_abiertas
from services.listado_tareas_service import listar_tareas_base
from services.materiales_base_service import listar_materiales_base_activos
from services.obras_service import listar_obras_con_demanda
from services.tareas_obra_service import listar_tareas_por_obra


require_login(["admin", "tecnico"])
aplicar_estilos_globales()

st.markdown(
    """
    <style>
    .lab-detail-panel {
        background: #fbfdff;
        border: 1px solid #dbeafe;
        border-radius: 10px 10px 0 0;
        padding: 18px 16px 12px;
        box-shadow: 0 1px 4px rgba(15, 23, 42, 0.03);
        margin-top: -14px;
        position: relative;
        z-index: 0;
    }
    .lab-detail-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px 14px;
    }
    .lab-detail-label {
        color: #64748b;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        margin-bottom: 2px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .lab-detail-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        border-radius: 999px;
        background: #dbeafe;
        color: #1d4ed8;
        font-size: 11px;
        line-height: 1;
    }
    .lab-detail-value {
        color: #1e293b;
        font-size: 13px;
        font-weight: 600;
        overflow-wrap: anywhere;
    }
    .lab-history-panel {
        background: #fbfdff;
        border: 1px solid #dbeafe;
        border-top: 0;
        border-radius: 0 0 10px 10px;
        padding: 10px 16px 13px;
        margin-top: 0;
        color: #334155;
        font-size: 13px;
        line-height: 1.45;
        max-height: 140px;
        overflow-y: auto;
    }
    .lab-history-title {
        border-top: 1px solid #dbeafe;
        padding-top: 10px;
        color: #1e293b;
        font-weight: 750;
        margin-bottom: 3px;
    }
    .lab-ficha-stack {
        border-left: 5px solid #2563eb;
        border-radius: 12px;
        background: #fbfdff;
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
        overflow: hidden;
    }
    .lab-ficha-stack iframe {
        position: relative;
        z-index: 2;
    }
    @media (max-width: 800px) {
        .lab-detail-grid { grid-template-columns: 1fr; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Laboratorio UI")

st.markdown("## Laboratorio - Asistencias v1")
st.caption("Carga diaria de personal por obra, deposito y tareas adicionales.")


def lab_asist_v1_fecha():
    hoy = __import__("datetime").date.today()
    return hoy.strftime("%d/%m/%Y")


def lab_asist_v1_blocks():
    return [
        {
            "id": "obra_1037",
            "line1": "Expte. 1037/26 - Ortiz Jorgelina",
            "line2": "San Martin 123 - Centro",
        },
        {
            "id": "obra_4869",
            "line1": "Expte. 4869/26 - Ramos Rita",
            "line2": "Callao ultima cuadra S/N - Colmena Norte",
        },
        {
            "id": "obra_781",
            "line1": "Expte. 781/26 - Perez Juan",
            "line2": "Reconquista 255 - Villa Rosa",
        },
        {
            "id": "deposito",
            "line1": "Deposito / Carga y descarga",
            "line2": "Bloque fijo operativo",
            "fixed": True,
        },
        {
            "id": "tareas_adicionales",
            "line1": "Tareas adicionales / Otras areas",
            "line2": "Bloque fijo operativo",
            "fixed": True,
        },
    ]


def lab_asist_v1_people():
    return [
        {"id": "p1", "name": "Coria Fabian - Oficial"},
        {"id": "p2", "name": "Palacio Omar - Ayudante"},
        {"id": "p3", "name": "Tevez Florencia - Administrativa"},
        {"id": "p4", "name": "Gomez Mario - Oficial"},
        {"id": "p5", "name": "Alderete Juan - Ayudante"},
        {"id": "p6", "name": "Medina Ramon - Ayudante"},
        {"id": "p7", "name": "Diaz Carlos - Oficial"},
    ]


def lab_asist_v1_seed():
    return [
        {"person_id": "p1", "block_id": "obra_1037", "status": "Presente"},
        {"person_id": "p2", "block_id": "obra_1037", "status": "Sin marcar"},
        {"person_id": "p3", "block_id": "obra_4869", "status": "Justificado"},
        {"person_id": "p4", "block_id": "obra_781", "status": "Sin marcar"},
        {"person_id": "p5", "block_id": "deposito", "status": "Ausente"},
    ]


def lab_asist_v1_pending(assignments, people, blocks):
    people_by_id = {str(p.get("id")): p for p in people}
    blocks_by_id = {str(b.get("id")): b for b in blocks}
    pendientes = []
    for row in assignments or []:
        if row.get("status") != "Sin marcar":
            continue
        person = people_by_id.get(str(row.get("person_id")), {})
        block = blocks_by_id.get(str(row.get("block_id")), {})
        pendientes.append(f"{person.get('name', 'Sin nombre')} - {block.get('line1', 'Sin bloque')}")
    return pendientes


lab_asist_blocks = lab_asist_v1_blocks()
lab_asist_people = lab_asist_v1_people()

if "lab_asist_v1_assignments" not in st.session_state:
    st.session_state["lab_asist_v1_assignments"] = lab_asist_v1_seed()

c_reset, c_note = st.columns([0.24, 0.76])
with c_reset:
    if st.button("Reiniciar demo", key="lab_asist_v1_reset", use_container_width=True):
        st.session_state["lab_asist_v1_assignments"] = lab_asist_v1_seed()
        st.rerun()
with c_note:
    st.info(f"Asistencias del dia - {lab_asist_v1_fecha()}. La fecha es automatica y no editable.")

resultado_asist_v1 = operational_attendance_board(
    title="Asistencias del dia",
    subtitle=f"{lab_asist_v1_fecha()} - carga rapida mobile-first",
    blocks=lab_asist_blocks,
    people=lab_asist_people,
    assignments=st.session_state["lab_asist_v1_assignments"],
    copy_label="Copiar parte",
    validate_label="Validar asistencia del dia",
    key="lab_asistencias_v1_board",
)

if resultado_asist_v1:
    asignaciones = resultado_asist_v1.get("assignments") or []
    if asignaciones:
        st.session_state["lab_asist_v1_assignments"] = asignaciones

    accion_asist = resultado_asist_v1.get("action")
    if accion_asist == "validate":
        pendientes = lab_asist_v1_pending(asignaciones, lab_asist_people, lab_asist_blocks)
        if pendientes:
            st.warning(f"No se puede validar. Quedan {len(pendientes)} personas sin marcar.")
            for item in pendientes:
                st.caption(item)
        else:
            st.success("Asistencia del dia validada en modo demo. No se guardo en Supabase.")
    elif accion_asist == "copy":
        st.success("Parte copiado en modo demo.")
    elif accion_asist:
        st.info(f"Evento demo: {accion_asist}")

    with st.expander("Resultado tecnico del componente", expanded=False):
        st.json(resultado_asist_v1)

st.divider()

st.markdown("## Card Operativa Base")
st.caption("Prueba visual de cards reutilizables para modulos operativos.")

cards = [
    dict(
        title="ORDONEZ, Nelida Del Valle",
        subtitle="Expte. 20737/24",
        status="Pendiente",
        priority="3 - Normal",
        meta=["Accion: Visitar", "Origen: Subdirectora", "Responsable: Guillo"],
        description="Realizar visita sociohabitacional por solicitud recibida.",
        footer="Ingreso: 27/05/26",
        variant="default",
    ),
    dict(
        title="RAMOS, Rita",
        subtitle="Expte. 4869/26",
        status="En ejecucion",
        priority=None,
        meta=["Modalidad: Cuadrilla HAVITA", "Responsable: Pedro"],
        description="Construccion y mejora de bano.",
        footer="Ultima actualizacion: 28/05/26",
        variant="highlight",
    ),
    dict(
        title="Orden #24",
        subtitle="RAMOS, Rita - Expte. 4869/26",
        status="Pendiente de entrega",
        priority="2 - Prioritario",
        meta=["Origen: Subdirectora", "Fecha entrega: 03/06/26"],
        description="Entrega de materiales para continuidad de obra.",
        footer="Materiales: 5 items",
        variant="warning",
    ),
    dict(
        title="PEREZ, Juan",
        subtitle="Expte. 1234/26",
        status="Programada",
        priority="2 - Prioritario",
        meta=["Fecha: 03/06/26", "Social: Programada", "Tecnica: Visitada"],
        description="Visita sociohabitacional para evaluacion de condiciones habitacionales.",
        footer="Informes pendientes",
        variant="highlight",
    ),
    dict(
        title="Entrega programada",
        subtitle="Orden #31 - Expte. 1037/26",
        status="Pendiente de entrega",
        priority="1 - Urgente",
        meta=["Destino: Barrio San Martin", "Fecha: 04/06/26"],
        description="Entrega de materiales de emergencia habitacional.",
        footer="Requiere coordinacion con cuadrilla",
        variant="danger",
    ),
    dict(
        title="Informe social",
        subtitle="Expte. 781/26",
        status="Informada",
        priority="3 - Normal",
        meta=["Responsable: Guillo", "Tipo: Informe"],
        description="Informe social presentado y registrado.",
        footer="Completado: 05/06/26",
        variant="success",
    ),
    dict(
        title="Demanda cerrada",
        subtitle="Expte. 900/26",
        status="Cerrada",
        priority="5 - En espera",
        meta=["Origen: Vecino / consulta directa", "Responsable: Facundo"],
        description="Demanda cerrada sin acciones pendientes.",
        footer="Cierre: 06/06/26",
        variant="muted",
    ),
]

for i in range(0, len(cards), 2):
    c1, c2 = st.columns(2)
    with c1:
        render_operational_card(**cards[i])
    with c2:
        if i + 1 < len(cards):
            render_operational_card(**cards[i + 1])

st.divider()
st.markdown("## Card Operativa Base + Acciones")

accion_1 = render_operational_card(
    title="Demanda de prueba",
    subtitle="Expte. 1001/26",
    status="Pendiente",
    priority="3 - Normal",
    meta=["Accion: Visitar", "Responsable: Guillo"],
    description="Card de prueba con una accion principal.",
    footer="Ingreso: 01/06/26",
    variant="default",
    actions=[{"label": "Ver detalle", "kind": "primary", "key": "view"}],
    card_key="lab_accion_1",
)
if accion_1:
    st.info(f"Accion presionada: {accion_1}")

accion_2 = render_operational_card(
    title="Obra de prueba",
    subtitle="Expte. 2044/26",
    status="En ejecucion",
    priority=None,
    meta=["Modalidad: Cuadrilla HAVITA", "Responsable: Pedro"],
    description="Card de prueba con dos acciones.",
    footer="Ultima actualizacion: 01/06/26",
    variant="highlight",
    actions=[
        {"label": "Ver detalle", "kind": "secondary", "key": "view"},
        {"label": "Editar", "kind": "primary", "key": "edit"},
    ],
    card_key="lab_accion_2",
)
if accion_2:
    st.info(f"Accion presionada: {accion_2}")

accion_3 = render_operational_card(
    title="Orden de prueba",
    subtitle="Orden #99 - Expte. 999/26",
    status="Pendiente de entrega",
    priority="2 - Prioritario",
    meta=["Origen: Subdirectora", "Fecha: 03/06/26"],
    description="Card de prueba con tres acciones.",
    footer="Materiales: 4 items",
    variant="warning",
    actions=[
        {"label": "PDF", "kind": "secondary", "key": "pdf"},
        {"label": "Actualizar", "kind": "primary", "key": "update"},
        {"label": "Cancelar", "kind": "danger", "key": "cancel"},
    ],
    card_key="lab_accion_3",
)
if accion_3:
    st.info(f"Accion presionada: {accion_3}")

render_operational_card(
    title="Card seleccionada",
    subtitle="Expte. 3000/26",
    status="Programada",
    priority="2 - Prioritario",
    meta=["Visual: selected=True", "clickable=True"],
    description="Esta card prueba el estado visual seleccionado.",
    footer="Solo demo visual",
    variant="highlight",
    clickable=True,
    selected=True,
    actions=[
        {"label": "Ver detalle", "kind": "secondary", "key": "view"},
        {"label": "Editar", "kind": "primary", "key": "edit"},
    ],
    card_key="lab_accion_selected",
)

st.divider()
st.markdown("## OperationalCard (Custom Component React)")
st.caption("Demo del componente real con eventos de botones, click y seleccion.")

res_1 = operational_card(
    title="Card simple",
    subtitle="Sin acciones",
    status="Pendiente",
    priority="3 - Normal",
    meta=["Modulo: Laboratorio"],
    description="Card base sin botones para validar render.",
    footer="Sin interaccion",
    variant="default",
    card_key="react_simple",
    key="react_simple",
)
st.caption(f"Resultado: {res_1}")

res_2 = operational_card(
    title="Card clickeable",
    subtitle="Click en cuerpo",
    status="Programada",
    priority=None,
    meta=["clickable=True"],
    description="Al clickear la card devuelve action='card_click'.",
    footer="Click de prueba",
    variant="highlight",
    card_key="react_click",
    clickable=True,
    key="react_click",
)
st.caption(f"Resultado: {res_2}")

res_3 = operational_card(
    title="Card seleccionable",
    subtitle="Con checkbox",
    status="En ejecucion",
    priority="2 - Prioritario",
    meta=["selectable=True"],
    description="Al cambiar checkbox devuelve action='toggle_select'.",
    footer="Seleccion de prueba",
    variant="success",
    card_key="react_select",
    selectable=True,
    selected=False,
    key="react_select",
)
st.caption(f"Resultado: {res_3}")

res_4 = operational_card(
    title="Card 1 boton",
    subtitle="Boton primario",
    status="Pendiente",
    priority="3 - Normal",
    meta=["Acciones: 1"],
    description="Debe devolver key del boton presionado.",
    footer="Verificacion de eventos",
    variant="default",
    card_key="react_a1",
    actions=[{"label": "Ver detalle", "kind": "primary", "key": "view"}],
    key="react_a1",
)
st.caption(f"Resultado: {res_4}")

res_5 = operational_card(
    title="Card 2 botones",
    subtitle="Secondary + Primary",
    status="En revision",
    priority="2 - Prioritario",
    meta=["Acciones: 2"],
    description="Prueba con 2 acciones.",
    footer="Verificacion de eventos",
    variant="warning",
    card_key="react_a2",
    actions=[
        {"label": "Ver detalle", "kind": "secondary", "key": "view"},
        {"label": "Editar", "kind": "primary", "key": "edit"},
    ],
    key="react_a2",
)
st.caption(f"Resultado: {res_5}")

res_6 = operational_card(
    title="Card 3 botones",
    subtitle="PDF / Cancelar / Actualizar",
    status="Pendiente de entrega",
    priority="1 - Urgente",
    meta=["Acciones: 3"],
    description="Prueba con 3 acciones integradas.",
    footer="Verificacion de eventos",
    variant="danger",
    card_key="react_a3",
    actions=[
        {"label": "PDF", "key": "pdf", "kind": "secondary"},
        {"label": "Cancelar", "key": "cancel", "kind": "danger"},
        {"label": "Actualizar", "key": "update", "kind": "primary"},
    ],
    key="react_a3",
)
st.caption(f"Resultado: {res_6}")

res_7 = operational_card(
    title="Card selected=True",
    subtitle="Visual de seleccion activa",
    status="En ejecucion",
    priority="2 - Prioritario",
    meta=["selected=True"],
    description="Borde y fondo resaltado cuando selected=True.",
    footer="Estado visual",
    variant="highlight",
    card_key="react_selected",
    selected=True,
    selectable=True,
    key="react_selected",
)
st.caption(f"Resultado: {res_7}")

for variant in ["danger", "warning", "success", "muted"]:
    res_v = operational_card(
        title=f"Variant {variant}",
        subtitle="Prueba visual",
        status="Demo",
        priority=None,
        meta=[f"variant={variant}"],
        description=f"Card de prueba para variante {variant}.",
        footer="Preview variante",
        variant=variant,
        card_key=f"react_var_{variant}",
        key=f"react_var_{variant}",
    )
    st.caption(f"{variant}: {res_v}")

st.divider()
st.markdown("## Ficha Demanda Seleccionada")
st.caption("Prototipo visual para el detalle de una demanda seleccionada. No modifica el modulo Demandas.")

col_ficha, col_acciones = st.columns([0.72, 0.28])

with col_ficha:
    st.markdown('<div class="lab-ficha-stack">', unsafe_allow_html=True)
    operational_card(
        title="ORDONEZ, Nelida Del Valle",
        subtitle="Expte. 20737/2024",
        status="Pendiente",
        priority="3 - Normal",
        meta=[
            "Visitar",
            "Ingreso: 27/05/26",
        ],
        description="Realizar visita sociohabitacional por solicitud recibida.",
        variant="default",
        accent_color="#2563EB",
        card_key="lab_demanda_detalle_header",
        key="lab_demanda_detalle_header",
    )

    st.markdown(
        """
        <div class="lab-detail-panel">
            <div class="lab-detail-grid">
                <div>
                    <div class="lab-detail-label"><span class="lab-detail-icon">ðŸ›</span>Origen</div>
                    <div class="lab-detail-value">Subdirectora</div>
                </div>
                <div>
                    <div class="lab-detail-label"><span class="lab-detail-icon">ðŸ‘¤</span>Responsable</div>
                    <div class="lab-detail-value">Guillo</div>
                </div>
                <div>
                    <div class="lab-detail-label"><span class="lab-detail-icon">ðŸªª</span>DNI</div>
                    <div class="lab-detail-value">23.456.789</div>
                </div>
                <div>
                    <div class="lab-detail-label"><span class="lab-detail-icon">ðŸ </span>Domicilio</div>
                    <div class="lab-detail-value">Reconquista 255</div>
                </div>
                <div>
                    <div class="lab-detail-label"><span class="lab-detail-icon">ðŸ¢</span>Barrio</div>
                    <div class="lab-detail-value">Villa Rosa</div>
                </div>
                <div>
                    <div class="lab-detail-label"><span class="lab-detail-icon">â˜Ž</span>Contacto</div>
                    <div class="lab-detail-value">381 555-1234</div>
                </div>
            </div>
        </div>
        <div class="lab-history-panel">
            <div class="lab-history-title">Historial / observaciones</div>
            27/05/26 - Demanda ingresada por pedido de visita sociohabitacional.
            || 28/05/26 - Se coordina contacto con la familia para programar visita.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Vista de formulario nativo en modo edicion", expanded=False):
        ce1, ce2, ce3 = st.columns(3)
        ce1.selectbox("Estado", ["Pendiente", "Para visita", "Visitado", "Cerrado"], key="lab_dem_estado")
        ce2.selectbox("Prioridad", ["1 - Urgente", "2 - Prioritario", "3 - Normal"], key="lab_dem_prioridad")
        ce3.selectbox("Responsable", ["", "Facundo", "Pedro", "Guillo"], key="lab_dem_resp")
        st.text_area("Nueva accion / actualizacion", key="lab_dem_historial")

with col_acciones:
    st.markdown("#### Acciones")
    st.button("Habilitar edicion", type="primary", use_container_width=True, key="lab_dem_edit")
    with st.expander("Finalizar expediente", expanded=False):
        st.checkbox("Confirmo cierre", key="lab_dem_confirm")
        st.button("Cerrar demanda", use_container_width=True, key="lab_dem_close")

st.divider()
st.markdown("## Tabla Operativa Editable")
st.caption(
    "Primer prototipo para listados de materiales, tareas o planillas. "
    "No guarda en base de datos; solo valida flujo visual y cambios detectados."
)


@st.cache_data(ttl=300)
def lab_materiales_base_opciones():
    fallback = [
        {"material": "Cemento x25kg", "unidad": "bolsa"},
        {"material": "Cal", "unidad": "bolsa"},
        {"material": "Chapa 1.10 x 4.00", "unidad": "unidad"},
        {"material": "Hierro 8", "unidad": "barra"},
        {"material": "Arena", "unidad": "m3"},
    ]
    try:
        materiales = listar_materiales_base_activos()
    except Exception:
        materiales = fallback

    opciones = []
    unidades = set()
    for item in materiales or fallback:
        material = str(item.get("material") or "").strip()
        unidad = str(item.get("unidad") or "").strip()
        if material and material not in opciones:
            opciones.append(material)
        if unidad:
            unidades.add(unidad)

    for item in fallback:
        material = item["material"]
        unidad = item["unidad"]
        if not opciones and material not in opciones:
            opciones.append(material)
        unidades.add(unidad)

    return sorted(opciones), sorted(unidades)


materiales_base_opciones, unidades_base_opciones = lab_materiales_base_opciones()
materiales_demo_opciones = materiales_base_opciones or ["Cemento x25kg", "Cal", "Chapa 1.10 x 4.00"]
unidades_demo_opciones = unidades_base_opciones or ["unidad", "bolsa", "kg", "m2", "m3", "metro", "litro"]

materiales_demo = [
    {
        "material": materiales_demo_opciones[0],
        "unidad": unidades_demo_opciones[0],
        "cantidad": 10,
        "observacion": "Retirar de corralon",
    },
    {
        "material": materiales_demo_opciones[1] if len(materiales_demo_opciones) > 1 else materiales_demo_opciones[0],
        "unidad": unidades_demo_opciones[0],
        "cantidad": 5,
        "observacion": "",
    },
    {
        "material": materiales_demo_opciones[2] if len(materiales_demo_opciones) > 2 else materiales_demo_opciones[0],
        "unidad": unidades_demo_opciones[0],
        "cantidad": 6,
        "observacion": "Verificar estado",
    },
]

if st.button("Restaurar datos demo", key="lab_table_reset"):
    st.session_state.pop("lab_materiales_base_rows", None)
    st.session_state.pop("lab_materiales_editor", None)
    st.rerun()

resultado_tabla = render_operational_editable_table(
    title="Listado de materiales",
    rows=materiales_demo,
    columns=[
        {
            "key": "material",
            "label": "Material",
            "type": "select",
            "options": materiales_base_opciones,
            "required": True,
            "width": "large",
        },
        {
            "key": "unidad",
            "label": "Unidad",
            "type": "select",
            "options": unidades_demo_opciones,
            "width": "small",
        },
        {
            "key": "cantidad",
            "label": "Cantidad",
            "type": "number",
            "required": True,
            "min_value": 0,
            "step": 1,
            "format": "%d",
            "width": "small",
        },
        {
            "key": "observacion",
            "label": "Observacion",
            "type": "text",
            "width": "large",
        },
    ],
    key="lab_materiales",
    help_text=(
        "El material se elige desde el padron materiales_base para evitar nombres raros. "
        "Agregue filas desde el editor, modifique celdas o marque Eliminar."
    ),
    allow_add=True,
    allow_delete=True,
    totals=[{"key": "cantidad", "label": "Total unidades/items"}],
)

col_guardar_tabla, col_estado_tabla = st.columns([0.28, 0.72])
with col_guardar_tabla:
    if st.button(
        "Guardar cambios demo",
        type="primary",
        use_container_width=True,
        key="lab_table_save",
        disabled=not resultado_tabla["has_changes"],
    ):
        st.session_state["lab_materiales_base_rows"] = resultado_tabla["commit_rows"]
        st.success("Cambios consolidados en la demo.")
        st.rerun()

with col_estado_tabla:
    if resultado_tabla["has_changes"]:
        st.info(
            f"Cambios detectados: {len(resultado_tabla['added'])} altas, "
            f"{len(resultado_tabla['updated'])} modificaciones, "
            f"{len(resultado_tabla['deleted'])} eliminaciones."
        )
    else:
        st.caption("Sin cambios pendientes.")

with st.expander("Ver datos y cambios detectados", expanded=False):
    st.markdown("**Filas activas**")
    st.json(resultado_tabla["rows"])
    st.markdown("**Altas**")
    st.json(resultado_tabla["added"])
    st.markdown("**Modificaciones**")
    st.json(resultado_tabla["updated"])
    st.markdown("**Eliminaciones**")
    st.json(resultado_tabla["deleted"])

st.markdown("### OperationalListEditor Â· Custom element")
st.caption(
    "Primer prototipo custom para listas operativas tactiles. "
    "Usa catalogo controlado de materiales y devuelve eventos a Python."
)

catalogo_demo = [
    {"id": f"mat_{idx}", "label": material, "unit": unidades_demo_opciones[0]}
    for idx, material in enumerate(materiales_demo_opciones[:8])
]
if not catalogo_demo:
    catalogo_demo = [
        {"id": "cemento", "label": "Cemento x25kg", "unit": "bolsa"},
        {"id": "cal", "label": "Cal", "unit": "bolsa"},
    ]

filas_editor_demo = [
    {
        "id": "r1",
        "item_id": catalogo_demo[0]["id"],
        "item_label": catalogo_demo[0]["label"],
        "unit": catalogo_demo[0]["unit"],
        "quantity": 10,
    }
]
if len(catalogo_demo) > 1:
    filas_editor_demo.append(
        {
            "id": "r2",
            "item_id": catalogo_demo[1]["id"],
            "item_label": catalogo_demo[1]["label"],
            "unit": catalogo_demo[1]["unit"],
            "quantity": 5,
        }
    )

if "lab_ole_materiales_rows" not in st.session_state:
    st.session_state["lab_ole_materiales_rows"] = filas_editor_demo

if st.button("Restaurar custom list demo", key="lab_ole_reset"):
    st.session_state["lab_ole_materiales_rows"] = filas_editor_demo
    st.rerun()

resultado_custom_lista = operational_list_editor(
    title="Materiales de orden",
    rows=st.session_state["lab_ole_materiales_rows"],
    catalog=catalogo_demo,
    help_text="Seleccione materiales del padron, cargue cantidad y quite filas. Los cambios se consolidan al guardar.",
    add_label="Agregar material",
    save_label="Guardar demo",
    key="lab_operational_list_editor_materiales",
)

if resultado_custom_lista:
    filas_devueltas = resultado_custom_lista.get("rows") or []
    if filas_devueltas:
        st.session_state["lab_ole_materiales_rows"] = filas_devueltas
    st.info(f"Evento: {resultado_custom_lista.get('action')}")
    with st.expander("Resultado devuelto por el custom element", expanded=False):
        st.json(resultado_custom_lista)

st.divider()
st.markdown("## Laboratorio Â· Asistencias")
st.caption(
    "Prototipo controlado para carga diaria desde celular. "
    "Usa datos mock y no guarda en Supabase."
)

st.markdown(
    """
    <style>
    .lab-att-header {
        background: #ffffff;
        border: 1px solid #dbeafe;
        border-radius: 14px;
        padding: 14px 16px;
        margin-bottom: 10px;
        box-shadow: 0 1px 6px rgba(15, 23, 42, 0.04);
    }
    .lab-att-title {
        font-size: 22px;
        font-weight: 800;
        color: #1e293b;
        margin: 0;
    }
    .lab-att-date {
        color: #64748b;
        font-size: 13px;
        font-weight: 650;
        margin-top: 2px;
    }
    .lab-att-card {
        background: #ffffff;
        border: 1px solid #dbeafe;
        border-left: 5px solid #006b68;
        border-radius: 14px;
        padding: 12px;
        margin: 10px 0;
        box-shadow: 0 1px 6px rgba(15, 23, 42, 0.04);
    }
    .lab-att-card-fixed { border-left-color: #64748b; }
    .lab-att-line-main {
        font-size: 15px;
        font-weight: 800;
        color: #1e293b;
        line-height: 1.25;
    }
    .lab-att-line-sub {
        color: #64748b;
        font-size: 13px;
        font-weight: 600;
        line-height: 1.25;
        margin-top: 2px;
    }
    .lab-att-person {
        border-top: 1px solid #e2e8f0;
        padding-top: 8px;
        margin-top: 8px;
    }
    .lab-att-person-name {
        color: #1e293b;
        font-size: 14px;
        font-weight: 750;
        margin-bottom: 5px;
    }
    .lab-att-empty {
        border-top: 1px dashed #cbd5e1;
        margin-top: 8px;
        padding-top: 9px;
        color: #64748b;
        font-size: 13px;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def lab_att_today():
    from datetime import date

    return date.today().strftime("%d/%m/%Y")


def lab_att_seed():
    return {
        "blocks": [
            {
                "id": "obra_1037",
                "kind": "obra",
                "line1": "Expte. 1037/26 Â· Ortiz Jorgelina",
                "line2": "Calle San Martin 123 Â· Barrio Centro",
            },
            {
                "id": "obra_4869",
                "kind": "obra",
                "line1": "Expte. 4869/26 Â· Ramos Rita",
                "line2": "Callao ultima cuadra S/N Â· Colmena Norte",
            },
            {
                "id": "obra_217",
                "kind": "obra",
                "line1": "Expte. 217/2026 Â· Ramos Rita Sara",
                "line2": "Reconquista 255 Â· Villa Rosa",
            },
            {
                "id": "dd",
                "kind": "fixed",
                "line1": "Deposito / Carga y descarga",
                "line2": "Bloque fijo operativo",
            },
            {
                "id": "otras",
                "kind": "fixed",
                "line1": "Tareas adicionales / Otras areas",
                "line2": "Bloque fijo operativo",
            },
        ],
        "people": [
            {"id": "p1", "name": "Coria Fabian"},
            {"id": "p2", "name": "Palacio Omar"},
            {"id": "p3", "name": "Tevez Florencia"},
            {"id": "p4", "name": "Gomez Mario"},
            {"id": "p5", "name": "Alderete Juan"},
            {"id": "p6", "name": "Roldan Esteban"},
        ],
        "assignments": {
            "p1": {"block_id": "obra_1037", "status": "Sin marcar"},
            "p2": {"block_id": "obra_1037", "status": "Sin marcar"},
            "p3": {"block_id": "obra_4869", "status": "Sin marcar"},
            "p4": {"block_id": "obra_217", "status": "Sin marcar"},
        },
    }


def lab_att_state():
    if "lab_attendance" not in st.session_state:
        st.session_state["lab_attendance"] = lab_att_seed()
    return st.session_state["lab_attendance"]


def lab_att_person_name(state, person_id):
    for person in state["people"]:
        if person["id"] == person_id:
            return person["name"]
    return person_id


def lab_att_set_status(person_id, status):
    st.session_state["lab_attendance"]["assignments"][person_id]["status"] = status


def lab_att_move_person(person_id, block_id):
    st.session_state["lab_attendance"]["assignments"][person_id] = {
        "block_id": block_id,
        "status": "Presente",
    }


def lab_att_summary(state):
    counts = {"Presente": 0, "Ausente": 0, "Justificado": 0, "Sin marcar": 0}
    for assignment in state["assignments"].values():
        status = assignment.get("status") or "Sin marcar"
        counts[status] = counts.get(status, 0) + 1
    return counts


def lab_att_render_person(state, person_id):
    person_name = lab_att_person_name(state, person_id)
    status = state["assignments"][person_id].get("status") or "Sin marcar"
    st.markdown(
        f"""
        <div class="lab-att-person">
            <div class="lab-att-person-name">{person_name}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    c1.button(
        "Presente" if status != "Presente" else "âœ“ Presente",
        key=f"lab_att_pres_{person_id}",
        use_container_width=True,
        type="primary" if status == "Presente" else "secondary",
        on_click=lab_att_set_status,
        args=(person_id, "Presente"),
    )
    c2.button(
        "Ausente" if status != "Ausente" else "âœ“ Ausente",
        key=f"lab_att_aus_{person_id}",
        use_container_width=True,
        type="primary" if status == "Ausente" else "secondary",
        on_click=lab_att_set_status,
        args=(person_id, "Ausente"),
    )
    c3.button(
        "Justificado" if status != "Justificado" else "âœ“ Justificado",
        key=f"lab_att_jus_{person_id}",
        use_container_width=True,
        type="primary" if status == "Justificado" else "secondary",
        on_click=lab_att_set_status,
        args=(person_id, "Justificado"),
    )
    if status == "Sin marcar":
        st.caption("Sin marcar")


def lab_att_render_block(state, block):
    css_class = "lab-att-card lab-att-card-fixed" if block["kind"] == "fixed" else "lab-att-card"
    st.markdown(
        f"""
        <div class="{css_class}">
            <div class="lab-att-line-main">{block["line1"]}</div>
            <div class="lab-att-line-sub">{block["line2"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    assigned = [
        person_id
        for person_id, assignment in state["assignments"].items()
        if assignment.get("block_id") == block["id"]
    ]
    if assigned:
        for person_id in assigned:
            lab_att_render_person(state, person_id)
    else:
        st.markdown(
            '<div class="lab-att-empty">Esta obra/bloque todavia no tiene personal asignado.</div>',
            unsafe_allow_html=True,
        )

    available = [p for p in state["people"] if p["id"] not in assigned]
    labels = ["Seleccionar persona"] + [p["name"] for p in available]
    selected_label = st.selectbox(
        "+ Agregar persona",
        labels,
        key=f"lab_att_add_select_{block['id']}",
    )
    if st.button("Agregar a este bloque", key=f"lab_att_add_btn_{block['id']}", use_container_width=True):
        if selected_label == "Seleccionar persona":
            st.warning("Seleccione una persona del padron.")
        else:
            person_id = next(p["id"] for p in available if p["name"] == selected_label)
            lab_att_move_person(person_id, block["id"])
            st.rerun()


state = lab_att_state()
counts = lab_att_summary(state)

st.markdown(
    f"""
    <div class="lab-att-header">
        <div class="lab-att-title">Asistencias del dia</div>
        <div class="lab-att-date">Fecha automatica: {lab_att_today()}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Presentes", counts.get("Presente", 0))
k2.metric("Ausentes", counts.get("Ausente", 0))
k3.metric("Justificados", counts.get("Justificado", 0))
k4.metric("Sin marcar", counts.get("Sin marcar", 0))

if st.button("Reiniciar demo de asistencias", key="lab_att_reset"):
    st.session_state["lab_attendance"] = lab_att_seed()
    st.rerun()

for block in state["blocks"]:
    lab_att_render_block(state, block)

st.markdown("### Validacion")
if st.button("Validar asistencia del dia", type="primary", use_container_width=True, key="lab_att_validate"):
    pending = []
    block_by_id = {block["id"]: block for block in state["blocks"]}
    for person_id, assignment in state["assignments"].items():
        if assignment.get("status") == "Sin marcar":
            block = block_by_id.get(assignment.get("block_id"), {})
            pending.append(f"{lab_att_person_name(state, person_id)} Â· {block.get('line1', 'Sin bloque')}")
    if pending:
        st.warning(f"No se puede validar. Quedan {len(pending)} personas sin marcar.")
        for item in pending:
            st.caption(item)
    else:
        st.success("Asistencia del dia validada en modo demo. No se guardo en Supabase.")

st.markdown("### OperationalAttendanceBoard Â· Custom element")
st.caption(
    "Prueba del mismo flujo como custom element: estados locales fluidos, movimiento de personas "
    "entre bloques y evento de validacion/guardado hacia Python."
)

attendance_blocks_demo = [
    {"id": "obra_1037", "line1": "Expte. 1037/26 Â· Ortiz Jorgelina", "line2": "Calle San Martin 123 Â· Barrio Centro"},
    {"id": "obra_4869", "line1": "Expte. 4869/26 Â· Ramos Rita", "line2": "Callao ultima cuadra S/N Â· Colmena Norte"},
    {"id": "dd", "line1": "DD Â· Deposito / Carga y descarga", "line2": "Bloque fijo operativo", "fixed": True},
    {"id": "oe", "line1": "OE Â· Obra externa / Otras areas", "line2": "Bloque fijo operativo", "fixed": True},
]
attendance_people_demo = [
    {"id": "p1", "name": "Coria Fabian"},
    {"id": "p2", "name": "Palacio Omar"},
    {"id": "p3", "name": "Tevez Florencia"},
    {"id": "p4", "name": "Gomez Mario"},
    {"id": "p5", "name": "Alderete Juan"},
]
attendance_assignments_seed = [
    {"person_id": "p1", "block_id": "obra_1037", "status": "Sin marcar"},
    {"person_id": "p2", "block_id": "obra_1037", "status": "Sin marcar"},
    {"person_id": "p3", "block_id": "obra_4869", "status": "Sin marcar"},
]

if "lab_oab_assignments" not in st.session_state:
    st.session_state["lab_oab_assignments"] = attendance_assignments_seed

if st.button("Restaurar attendance board demo", key="lab_oab_reset"):
    st.session_state["lab_oab_assignments"] = attendance_assignments_seed
    st.rerun()

resultado_attendance_board = operational_attendance_board(
    title="Asistencias del dia",
    subtitle=f"Fecha automatica: {lab_att_today()}",
    blocks=attendance_blocks_demo,
    people=attendance_people_demo,
    assignments=st.session_state["lab_oab_assignments"],
    copy_label="Copiar demo",
    validate_label="Validar demo",
    key="lab_operational_attendance_board",
)

if resultado_attendance_board:
    asignaciones = resultado_attendance_board.get("assignments") or []
    if asignaciones:
        st.session_state["lab_oab_assignments"] = asignaciones
    accion = resultado_attendance_board.get("action")
    if accion == "validate":
        pendientes = [a for a in asignaciones if a.get("status") == "Sin marcar"]
        if pendientes:
            st.warning(f"No se puede validar. Quedan {len(pendientes)} personas sin marcar.")
        else:
            st.success("Validacion demo correcta. No se guardo en Supabase.")
    elif accion:
        st.info(f"Evento: {accion}")
    with st.expander("Resultado devuelto por OperationalAttendanceBoard", expanded=False):
        st.json(resultado_attendance_board)


st.divider()
st.markdown("## Laboratorio - Obras")
st.caption("Prueba controlada de tablero maestro-detalle para obras. Lectura real si esta disponible; guardado simulado.")


def lab_txt(v):
    return "" if v is None else str(v)


def lab_clean(v):
    return lab_txt(v).strip()


def lab_mock_obras():
    return [
        {
            "id_obra": 101,
            "id_demanda": 1001,
            "expediente": "1037/26",
            "apellido": "Ortiz",
            "nombre": "Jorgelina",
            "domicilio": "San Martin 123",
            "barrio": "Centro",
            "estado_obra": "En ejecucion",
            "modalidad_ejecucion": "Cuadrilla HAVITA",
            "responsable_tecnico": "Pedro",
            "tipo_obra_programa": "HAVITA",
            "descripcion_obra": "Mejora integral de bano y reparaciones menores.",
            "obs_obras": "Demo - obra usada solo para laboratorio.",
        },
        {
            "id_obra": 102,
            "id_demanda": 1002,
            "expediente": "4869/26",
            "apellido": "Ramos",
            "nombre": "Rita",
            "domicilio": "Callao ultima cuadra S/N",
            "barrio": "Colmena Norte",
            "estado_obra": "Para firmar acta",
            "modalidad_ejecucion": "Mixta",
            "responsable_tecnico": "Facundo",
            "tipo_obra_programa": "MI BANO",
            "descripcion_obra": "Construccion y mejora de nucleo sanitario.",
            "obs_obras": "",
        },
        {
            "id_obra": 103,
            "id_demanda": 1003,
            "expediente": "217/2026",
            "apellido": "Ramos",
            "nombre": "Rita Sara",
            "domicilio": "Reconquista 255",
            "barrio": "Villa Rosa",
            "estado_obra": "Suspendida",
            "modalidad_ejecucion": "Cuadrilla municipal",
            "responsable_tecnico": "Bea",
            "tipo_obra_programa": "EMERGENCIA HABITACIONAL",
            "descripcion_obra": "Intervencion menor por filtraciones.",
            "obs_obras": "Suspendida por materiales.",
        },
    ]


def lab_mock_demandas_obra():
    return [
        {
            "id_demanda": 2001,
            "expediente": "900/26",
            "apellido": "Perez",
            "nombre": "Juan",
            "domicilio": "Belgrano 450",
            "barrio": "Lomas",
            "accion": "Obra",
            "prioridad": "2 - Prioritario",
            "estado": "Pendiente",
        },
        {
            "id_demanda": 2002,
            "expediente": "901/26",
            "apellido": "Gomez",
            "nombre": "Carolina",
            "domicilio": "Aconquija 80",
            "barrio": "El Molino",
            "accion": "Emergencia",
            "prioridad": "1 - Urgente",
            "estado": "Pendiente",
        },
    ]


def lab_mock_catalogo_tareas():
    return [
        {"descripcion_tarea": "Contrapiso", "unidad_tarea": "m2"},
        {"descripcion_tarea": "Instalacion electrica", "unidad_tarea": "gl"},
        {"descripcion_tarea": "Colocacion de artefactos", "unidad_tarea": "u"},
        {"descripcion_tarea": "Revoque fino", "unidad_tarea": "m2"},
    ]


def lab_mock_tareas_obra(id_obra):
    base = {
        101: [
            {"id_tarea": "101-a", "descripcion_tarea": "Contrapiso", "unidad_tarea": "m2", "cant_tarea": 12, "estado_tarea": False},
            {"id_tarea": "101-b", "descripcion_tarea": "Instalacion electrica", "unidad_tarea": "gl", "cant_tarea": 1, "estado_tarea": True},
        ],
        102: [
            {"id_tarea": "102-a", "descripcion_tarea": "Colocacion de artefactos", "unidad_tarea": "u", "cant_tarea": 3, "estado_tarea": False},
        ],
    }
    return base.get(int(id_obra or 0), [])


@st.cache_data(ttl=120)
def lab_obras_data():
    try:
        data = listar_obras_con_demanda()
        return (data or lab_mock_obras(), "real")
    except Exception:
        return (lab_mock_obras(), "mock")


@st.cache_data(ttl=120)
def lab_demandas_obra_data(ids_con_obra):
    try:
        abiertas = listar_demandas_abiertas()
        ids = {str(x) for x in ids_con_obra}
        data = [
            d for d in abiertas
            if lab_clean(d.get("accion")) in {"Obra", "Emergencia"}
            and str(d.get("id_demanda")) not in ids
        ]
        return (data[:8] or lab_mock_demandas_obra(), "real")
    except Exception:
        return (lab_mock_demandas_obra(), "mock")


@st.cache_data(ttl=120)
def lab_catalogo_tareas_data():
    try:
        data = listar_tareas_base()
        return (data or lab_mock_catalogo_tareas(), "real")
    except Exception:
        return (lab_mock_catalogo_tareas(), "mock")


@st.cache_data(ttl=120)
def lab_tareas_obra_data(id_obra):
    try:
        data = listar_tareas_por_obra(id_obra)
        return (data if data else lab_mock_tareas_obra(id_obra), "real" if data else "mock")
    except Exception:
        return (lab_mock_tareas_obra(id_obra), "mock")


def lab_obra_linea_1(obra):
    titular = f"{lab_clean(obra.get('apellido'))} {lab_clean(obra.get('nombre'))}".strip()
    return f"Expte. {lab_clean(obra.get('expediente')) or 'S/E'} - {titular or 'Sin titular'}"


def lab_obra_linea_2(obra):
    domicilio = lab_clean(obra.get("domicilio")) or "-"
    barrio = lab_clean(obra.get("barrio")) or "-"
    return f"{domicilio} - {barrio}"


def lab_variant_estado_obra(estado):
    e = lab_clean(estado).lower()
    if "ejec" in e:
        return "success"
    if "suspend" in e:
        return "warning"
    if "cancel" in e:
        return "muted"
    if "acta" in e:
        return "highlight"
    return "default"


def lab_card_event(resultado, card_key):
    if not isinstance(resultado, dict):
        return False
    if resultado.get("card_key") != card_key:
        return False
    event_id = resultado.get("event_id")
    if not event_id:
        return False
    vistos = st.session_state.setdefault("_lab_obras_eventos_vistos", [])
    if event_id in vistos:
        return False
    vistos.append(event_id)
    st.session_state["_lab_obras_eventos_vistos"] = vistos[-80:]
    return True


def lab_filtro_obras(obras, q, estado, responsable, modalidad):
    qn = lab_clean(q).lower()
    salida = []
    for obra in obras:
        blob = " ".join(
            lab_clean(obra.get(k))
            for k in ["id_obra", "id_demanda", "expediente", "apellido", "nombre", "domicilio", "barrio"]
        ).lower()
        if qn and qn not in blob:
            continue
        if estado != "Todos" and lab_clean(obra.get("estado_obra")) != estado:
            continue
        if responsable != "Todos" and lab_clean(obra.get("responsable_tecnico")) != responsable:
            continue
        if modalidad != "Todos" and lab_clean(obra.get("modalidad_ejecucion")) != modalidad:
            continue
        salida.append(obra)
    return salida


obras_lab, origen_obras = lab_obras_data()
ids_con_obra_lab = [o.get("id_demanda") for o in obras_lab if o.get("id_demanda") is not None]
demandas_lab, origen_demandas = lab_demandas_obra_data(tuple(ids_con_obra_lab))
catalogo_lab, origen_catalogo = lab_catalogo_tareas_data()

st.caption(
    f"Datos: obras={origen_obras}, demandas={origen_demandas}, catalogo_tareas={origen_catalogo}. "
    "Los cambios de esta prueba son simulados."
)

f1, f2, f3, f4 = st.columns([2.4, 1.4, 1.4, 1.4])
with f1:
    lab_buscar = st.text_input("Busqueda libre", key="lab_obras_buscar", placeholder="Expediente, apellido, barrio, domicilio")
with f2:
    estados = ["Todos"] + sorted({lab_clean(o.get("estado_obra")) for o in obras_lab if lab_clean(o.get("estado_obra"))})
    lab_estado = st.selectbox("Estado", estados, key="lab_obras_estado")
with f3:
    responsables = ["Todos"] + sorted({lab_clean(o.get("responsable_tecnico")) for o in obras_lab if lab_clean(o.get("responsable_tecnico"))})
    lab_responsable = st.selectbox("Responsable", responsables, key="lab_obras_responsable")
with f4:
    modalidades = ["Todos"] + sorted({lab_clean(o.get("modalidad_ejecucion")) for o in obras_lab if lab_clean(o.get("modalidad_ejecucion"))})
    lab_modalidad = st.selectbox("Modalidad", modalidades, key="lab_obras_modalidad")

obras_filtradas_lab = lab_filtro_obras(obras_lab, lab_buscar, lab_estado, lab_responsable, lab_modalidad)
if "lab_obra_seleccionada_id" not in st.session_state and obras_filtradas_lab:
    st.session_state["lab_obra_seleccionada_id"] = obras_filtradas_lab[0].get("id_obra")

col_listado, col_ficha = st.columns([0.4, 0.6])

with col_listado:
    st.markdown("### Obras registradas")
    if not obras_filtradas_lab:
        st.info("No hay obras con esos filtros.")
    for obra in obras_filtradas_lab:
        oid = obra.get("id_obra")
        ck = f"lab_obra_{oid}"
        seleccionada = str(st.session_state.get("lab_obra_seleccionada_id", "")) == str(oid)
        resultado = operational_card(
            title=lab_obra_linea_1(obra),
            subtitle=lab_obra_linea_2(obra),
            status=lab_clean(obra.get("estado_obra")) or None,
            priority=None,
            meta=[],
            description=None,
            footer=None,
            variant=lab_variant_estado_obra(obra.get("estado_obra")),
            clickable=True,
            selected=seleccionada,
            card_key=ck,
            key=f"lab_obra_card_{oid}",
        )
        if lab_card_event(resultado, ck):
            st.session_state["lab_obra_seleccionada_id"] = oid
            st.rerun()

    st.markdown("---")
    st.markdown("### Demandas para validar")
    st.caption("Bandeja secundaria. Crear obra es simulado.")
    if not demandas_lab:
        st.info("No hay demandas pendientes para generar obra.")
    else:
        for demanda in demandas_lab[:6]:
            dkey = f"lab_demanda_obra_{demanda.get('id_demanda')}"
            accion = operational_card(
                title=f"Expte. {lab_clean(demanda.get('expediente')) or 'S/E'} - {lab_clean(demanda.get('apellido'))} {lab_clean(demanda.get('nombre'))}".strip(),
                subtitle=f"{lab_clean(demanda.get('domicilio')) or '-'} - {lab_clean(demanda.get('barrio')) or '-'}",
                status=lab_clean(demanda.get("accion")) or "Obra",
                priority=lab_clean(demanda.get("prioridad")) or None,
                meta=[f"Estado: {lab_clean(demanda.get('estado')) or '-'}"],
                description=None,
                footer=f"Demanda #{demanda.get('id_demanda')}",
                variant="highlight",
                actions=[{"label": "Crear obra", "key": "crear_obra", "kind": "primary"}],
                actions_layout="corner",
                card_key=dkey,
                key=f"lab_demanda_obra_card_{demanda.get('id_demanda')}",
            )
            if lab_card_event(accion, dkey) and accion.get("action") == "crear_obra":
                st.info(f"Crear obra simulado para demanda #{demanda.get('id_demanda')}.")

with col_ficha:
    st.markdown("### Ficha de obra")
    obra_sel = next((o for o in obras_lab if str(o.get("id_obra")) == str(st.session_state.get("lab_obra_seleccionada_id"))), None)
    if not obra_sel:
        st.info("Selecciona una obra del listado para ver o editar su ficha.")
    else:
        st.markdown(f"**{lab_obra_linea_1(obra_sel)}**")
        st.caption(lab_obra_linea_2(obra_sel))
        with st.expander("Datos generales", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                st.selectbox(
                    "estado_obra",
                    ["Para firmar acta", "Acta firmada", "Para obra", "En ejecucion", "Suspendida", "Ejecutada", "Cancelada"],
                    index=0,
                    key=f"lab_estado_obra_{obra_sel.get('id_obra')}",
                )
                st.text_input("responsable_tecnico", value=lab_clean(obra_sel.get("responsable_tecnico")), key=f"lab_resp_{obra_sel.get('id_obra')}")
                st.text_input("tipo_obra_programa", value=lab_clean(obra_sel.get("tipo_obra_programa")), key=f"lab_tipo_{obra_sel.get('id_obra')}")
            with c2:
                st.text_input("modalidad_ejecucion", value=lab_clean(obra_sel.get("modalidad_ejecucion")), key=f"lab_mod_{obra_sel.get('id_obra')}")
                st.text_area("descripcion_obra", value=lab_clean(obra_sel.get("descripcion_obra")), height=82, key=f"lab_desc_{obra_sel.get('id_obra')}")
                st.text_area("obs_obras", value=lab_clean(obra_sel.get("obs_obras")), height=82, key=f"lab_obs_{obra_sel.get('id_obra')}")

        with st.expander("Tareas asignadas", expanded=True):
            tareas_key = f"lab_tareas_rows_{obra_sel.get('id_obra')}"
            if tareas_key not in st.session_state:
                tareas_ini, origen_tareas = lab_tareas_obra_data(obra_sel.get("id_obra"))
                st.session_state[tareas_key] = [
                    {
                        "id": t.get("id_tarea") or f"tmp_{idx}",
                        "item_id": lab_clean(t.get("descripcion_tarea")),
                        "item_label": lab_clean(t.get("descripcion_tarea")),
                        "unit": lab_clean(t.get("unidad_tarea")),
                        "quantity": t.get("cant_tarea") or "",
                        "status": bool(t.get("estado_tarea")),
                        "deleted": False,
                    }
                    for idx, t in enumerate(tareas_ini)
                ]
                st.session_state[f"{tareas_key}_origen"] = origen_tareas

            st.caption(f"Tareas: {st.session_state.get(f'{tareas_key}_origen', 'mock')}. Edicion simulada, sin Supabase.")
            catalogo_tareas_editor = [
                {
                    "id": lab_clean(t.get("descripcion_tarea")),
                    "label": lab_clean(t.get("descripcion_tarea")),
                    "unit": lab_clean(t.get("unidad_tarea")),
                }
                for t in catalogo_lab
                if lab_clean(t.get("descripcion_tarea"))
            ]
            tareas_resultado = operational_list_editor(
                title="Tareas de la obra",
                rows=st.session_state[tareas_key],
                catalog=catalogo_tareas_editor,
                help_text="Prototipo: catalogo de tareas, unidad automatica, cantidad, ejecutada y eliminar.",
                add_label="Agregar tarea",
                save_label="Guardar tareas simuladas",
                item_label="Tarea",
                show_status=True,
                status_label="Ejecutada",
                allow_delete=True,
                mark_deleted=True,
                key=f"lab_operational_list_editor_tareas_{obra_sel.get('id_obra')}",
            )
            if tareas_resultado and tareas_resultado.get("rows") is not None:
                st.session_state[tareas_key] = tareas_resultado.get("rows") or []
                if tareas_resultado.get("action") == "save":
                    st.success("Tareas simuladas guardadas en memoria. No se guardo nada en Supabase.")

        if st.button("Guardar cambios simulados", type="primary", use_container_width=True, key=f"lab_save_obra_{obra_sel.get('id_obra')}"):
            st.success("Cambios simulados en Laboratorio. No se guardo nada en Supabase.")


st.divider()
st.markdown("## Sistema visual v1")
st.caption("Prueba mock de biblioteca visual base. No lee ni guarda datos reales.")

st.markdown(
    """
    <style>
    .sv1-shell {
        background: #f6f8fb;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 10px;
        margin: 8px 0 12px;
    }
    .sv1-section-header {
        background: #ffffff;
        border: 1px solid #dbe7ee;
        border-left: 5px solid #006b68;
        border-radius: 14px;
        padding: 12px 14px;
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.045);
        margin-bottom: 8px;
    }
    .sv1-kicker {
        color: #006b68;
        font-size: 11px;
        font-weight: 850;
        letter-spacing: .08em;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .sv1-title {
        color: #0f2742;
        font-size: 22px;
        line-height: 1.15;
        font-weight: 850;
        margin: 0;
    }
    .sv1-subtitle {
        color: #64748b;
        font-size: 13px;
        line-height: 1.35;
        font-weight: 600;
        margin-top: 3px;
    }
    .sv1-controlbar {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 9px 10px;
        box-shadow: 0 1px 6px rgba(15, 23, 42, 0.035);
        margin-bottom: 10px;
    }
    .sv1-control-grid {
        display: grid;
        grid-template-columns: 2.2fr 1.2fr 1.2fr auto auto;
        gap: 8px;
        align-items: end;
    }
    .sv1-form-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 7px 9px;
        margin-top: 8px;
    }
    .sv1-field {
        display: flex;
        flex-direction: column;
        gap: 3px;
    }
    .sv1-field.full {
        grid-column: 1 / -1;
    }
    .sv1-field-label {
        color: #475569;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: .01em;
    }
    .sv1-input {
        box-sizing: border-box;
        width: 100%;
        min-height: 34px;
        border: 1px solid #d6e1ea;
        border-radius: 10px;
        background: #ffffff;
        color: #1e293b;
        padding: 7px 9px;
        font-size: 12.5px;
        font-weight: 650;
        box-shadow: inset 0 1px 0 rgba(15, 23, 42, 0.02);
    }
    .sv1-input.select {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .sv1-input.textarea {
        min-height: 58px;
        align-items: flex-start;
        line-height: 1.35;
    }
    .sv1-badge {
        display: inline-flex;
        align-items: center;
        width: fit-content;
        border: 1px solid #cbd5e1;
        border-radius: 999px;
        padding: 3px 8px;
        font-size: 11.5px;
        font-weight: 800;
        line-height: 1;
        margin: 2px 4px 2px 0;
        white-space: nowrap;
    }
    .sv1-badge.teal { background: #e6f4f1; border-color: #99d6ce; color: #004f4c; }
    .sv1-badge.blue { background: #eff6ff; border-color: #bfdbfe; color: #1d4ed8; }
    .sv1-badge.amber { background: #fff7ed; border-color: #fed7aa; color: #9a3412; }
    .sv1-badge.red { background: #fff1f2; border-color: #fecdd3; color: #be123c; }
    .sv1-badge.gray { background: #f1f5f9; border-color: #cbd5e1; color: #475569; }
    .sv1-list-card,
    .sv1-action-card,
    .sv1-detail-panel,
    .sv1-empty {
        background: #ffffff;
        border: 1px solid #dbe7ee;
        border-radius: 12px;
        box-shadow: 0 1px 7px rgba(15, 23, 42, 0.035);
    }
    .sv1-list-card {
        border-left: 5px solid #006b68;
        padding: 8px 10px;
        margin-bottom: 6px;
    }
    .sv1-list-card.selected {
        border-color: #99d6ce;
        border-left-color: #006b68;
        background: #fbfffe;
        box-shadow: 0 0 0 1px rgba(0, 107, 104, 0.12);
    }
    .sv1-row-top {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        align-items: flex-start;
    }
    .sv1-card-main {
        color: #1e293b;
        font-size: 13.5px;
        font-weight: 850;
        line-height: 1.25;
    }
    .sv1-card-sub {
        color: #64748b;
        font-size: 12px;
        font-weight: 650;
        line-height: 1.25;
        margin-top: 2px;
    }
    .sv1-action-card {
        padding: 9px 10px;
        border-left: 5px solid #f59e0b;
        margin-bottom: 6px;
    }
    .sv1-action-footer {
        display: flex;
        justify-content: flex-end;
        margin-top: 6px;
    }
    .sv1-btn {
        border: 1px solid #006b68;
        background: #006b68;
        color: #fff;
        border-radius: 9px;
        padding: 7px 11px;
        font-size: 12.5px;
        font-weight: 850;
    }
    .sv1-btn.secondary {
        background: #fff;
        color: #334155;
        border-color: #cbd5e1;
    }
    .sv1-detail-panel {
        padding: 10px 12px;
    }
    .sv1-panel-title {
        color: #0f2742;
        font-size: 17px;
        font-weight: 850;
        margin-bottom: 5px;
    }
    .sv1-panel-block {
        border-top: 1px solid #e2e8f0;
        margin-top: 8px;
        padding-top: 8px;
    }
    .sv1-smart-row {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 8px;
        align-items: center;
        border: 1px solid #e2e8f0;
        background: #fbfdff;
        border-radius: 12px;
        padding: 6px 8px;
        margin-bottom: 4px;
    }
    .sv1-smart-name {
        color: #1e293b;
        font-size: 12.5px;
        font-weight: 800;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .sv1-smart-meta {
        color: #64748b;
        font-size: 11.5px;
        font-weight: 650;
    }
    .sv1-empty {
        border-style: dashed;
        padding: 16px;
        text-align: center;
        color: #64748b;
        font-size: 13px;
        font-weight: 700;
    }
    @media (max-width: 760px) {
        .sv1-control-grid,
        .sv1-form-grid { grid-template-columns: 1fr; }
        .sv1-row-top { flex-direction: column; gap: 4px; }
        .sv1-smart-row { grid-template-columns: 1fr; }
        .sv1-smart-name { white-space: normal; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def sv1_badge(text, tone="gray"):
    return f'<span class="sv1-badge {tone}">{text}</span>'


def sv1_section_header(title, subtitle):
    st.markdown(
        f"""
        <div class="sv1-section-header">
            <div class="sv1-kicker">MUNICIPALIDAD DE TAFI VIEJO</div>
            <h2 class="sv1-title">{title}</h2>
            <div class="sv1-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sv1_list_card(line1, line2, badges="", selected=False):
    st.markdown(
        f"""
        <div class="sv1-list-card {'selected' if selected else ''}">
            <div class="sv1-row-top">
                <div>
                    <div class="sv1-card-main">{line1}</div>
                    <div class="sv1-card-sub">{line2}</div>
                </div>
                <div>{badges}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sv1_action_card(line1, line2, badges, button_label):
    st.markdown(
        f"""
        <div class="sv1-action-card">
            <div class="sv1-row-top">
                <div>
                    <div class="sv1-card-main">{line1}</div>
                    <div class="sv1-card-sub">{line2}</div>
                    <div>{badges}</div>
                </div>
            </div>
            <div class="sv1-action-footer"><button class="sv1-btn">{button_label}</button></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sv1_smart_row(name, meta, badge_html):
    st.markdown(
        f"""
        <div class="sv1-smart-row">
            <div>
                <div class="sv1-smart-name">{name}</div>
                <div class="sv1-smart-meta">{meta}</div>
            </div>
            <div>{badge_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sv1_smart_row_html(name, meta, badge_html):
    return f"""
        <div class="sv1-smart-row">
            <div>
                <div class="sv1-smart-name">{name}</div>
                <div class="sv1-smart-meta">{meta}</div>
            </div>
            <div>{badge_html}</div>
        </div>
    """


def sv1_form_field_html(label, value, kind="input", full=False):
    extra = " full" if full else ""
    kind_class = " textarea" if kind == "textarea" else " select" if kind == "select" else ""
    caret = '<span style="color:#64748b;">▾</span>' if kind == "select" else ""
    return f"""
        <div class="sv1-field{extra}">
            <div class="sv1-field-label">{label}</div>
            <div class="sv1-input{kind_class}"><span>{value}</span>{caret}</div>
        </div>
    """


def sv1_form_field(label, value, kind="input", full=False):
    extra = " full" if full else ""
    kind_class = " textarea" if kind == "textarea" else " select" if kind == "select" else ""
    caret = '<span style="color:#64748b;">▾</span>' if kind == "select" else ""
    st.markdown(
        f"""
        <div class="sv1-field{extra}">
            <div class="sv1-field-label">{label}</div>
            <div class="sv1-input{kind_class}"><span>{value}</span>{caret}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


sv1_section_header(
    "Obras",
    "Registro, edicion y seguimiento de intervenciones habitacionales.",
)

st.markdown(
    """
    <div class="sv1-controlbar">
        <div class="sv1-control-grid">
            <div class="sv1-field">
                <div class="sv1-field-label">Busqueda libre</div>
                <div class="sv1-input">Expediente, apellido, barrio</div>
            </div>
            <div class="sv1-field">
                <div class="sv1-field-label">Estado</div>
                <div class="sv1-input select"><span>Todos</span><span style="color:#64748b;">▾</span></div>
            </div>
            <div class="sv1-field">
                <div class="sv1-field-label">Responsable</div>
                <div class="sv1-input select"><span>Pedro</span><span style="color:#64748b;">▾</span></div>
            </div>
            <button class="sv1-btn">Buscar</button>
            <button class="sv1-btn secondary">Limpiar</button>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("### StatusBadge")
st.markdown(
    " ".join(
        [
            sv1_badge("Ingresada", "amber"),
            sv1_badge("Pendiente", "amber"),
            sv1_badge("Relevada", "blue"),
            sv1_badge("Cerrada", "gray"),
            sv1_badge("Para firmar acta", "blue"),
            sv1_badge("En ejecucion", "teal"),
            sv1_badge("Suspendida", "red"),
            sv1_badge("Ejecutada", "teal"),
            sv1_badge("Pedido", "amber"),
            sv1_badge("Pendiente entrega", "blue"),
            sv1_badge("En deposito", "gray"),
            sv1_badge("Entregado", "teal"),
            sv1_badge("Presente", "teal"),
            sv1_badge("Ausente", "red"),
            sv1_badge("Justificado", "blue"),
            sv1_badge("Sin marcar", "gray"),
        ]
    ),
    unsafe_allow_html=True,
)

st.markdown("### ListCard / ActionCard")
lc1, lc2 = st.columns(2)
with lc1:
    sv1_list_card("Expte. 1037/26 - Ortiz Jorgelina", "San Martin 123 - Barrio Centro", sv1_badge("En ejecucion", "teal"), selected=True)
    sv1_list_card("Expte. 4869/26 - Valdez Segundo", "Las Heras 456 - Barrio Norte", sv1_badge("Obra", "blue") + sv1_badge("Normal", "amber"))
    sv1_list_card("Orden N 24 - Ortiz Jorgelina", "Materiales para reparacion de cubierta", sv1_badge("Pendiente entrega", "blue"))
with lc2:
    sv1_action_card("Expte. 20/2020 - Sin titular", "Estado: Ingresada", sv1_badge("Obra", "blue") + sv1_badge("Normal", "amber"), "Crear obra")
    sv1_action_card("Nota rapida - Obra 1037/26", "Faltan flexibles y griferia", sv1_badge("Pendiente", "amber"), "Aplicar")

st.markdown("### DetailPanel / SmartList / EmptyState")
dp1, dp2 = st.columns([0.6, 0.4])
with dp1:
    st.markdown(
        f"""
        <div class="sv1-detail-panel">
            <div class="sv1-panel-title">Ficha de obra</div>
            <div class="sv1-card-main">Expte. 1037/26 - Ortiz Jorgelina</div>
            <div class="sv1-card-sub">San Martin 123 - Barrio Centro</div>
            <div class="sv1-panel-block">
                <div class="sv1-card-main">Datos generales</div>
                <div class="sv1-form-grid">
                    {sv1_form_field_html("Estado de obra", "En ejecucion", "select")}
                    {sv1_form_field_html("Modalidad", "Cuadrilla HAVITA", "select")}
                    {sv1_form_field_html("Responsable tecnico", "Pedro")}
                    {sv1_form_field_html("Tipo de obra / programa", "HAVITA", "select")}
                    {sv1_form_field_html("Descripcion de obra", "Mejora integral de bano y reparaciones menores.", "textarea", full=True)}
                    {sv1_form_field_html("Observaciones", "Avance normal.", "textarea", full=True)}
                </div>
            </div>
            <div class="sv1-panel-block">
                <div class="sv1-card-main">Tareas asignadas</div>
                {sv1_smart_row_html("Revoque exterior", "25 m2", sv1_badge("Pendiente", "amber"))}
                {sv1_smart_row_html("Contrapiso", "18 m2", sv1_badge("Ejecutada", "teal"))}
            </div>
            <button class="sv1-btn" style="width:100%; margin-top:6px;">Guardar cambios</button>
        </div>
        """,
        unsafe_allow_html=True,
    )
with dp2:
    st.markdown('<div class="sv1-empty">Selecciona una obra del listado para ver o editar su ficha.</div>', unsafe_allow_html=True)
    st.markdown("#### SmartList materiales")
    sv1_smart_row("Cemento - 5 bolsas", "Listado de materiales", sv1_badge("Material", "gray"))
    sv1_smart_row("Arena - 2 m3", "Listado de materiales", sv1_badge("Material", "gray"))
    st.markdown("#### SmartList asistencia")
    sv1_smart_row("Juan Perez", "Oficial", sv1_badge("Presente", "teal") + sv1_badge("Ausente", "gray") + sv1_badge("Justif.", "gray"))
    sv1_smart_row("Carlos Diaz", "Ayudante", sv1_badge("Presente", "gray") + sv1_badge("Ausente", "red") + sv1_badge("Justif.", "gray"))

st.markdown("### Maqueta maestro-detalle")
st.markdown('<div class="sv1-shell">', unsafe_allow_html=True)
m1, m2 = st.columns([0.4, 0.6])
with m1:
    st.markdown("#### Obras registradas")
    sv1_list_card("Expte. 1037/26 - Ortiz Jorgelina", "San Martin 123 - Barrio Centro", sv1_badge("En ejecucion", "teal"), selected=True)
    sv1_list_card("Expte. 4869/26 - Ramos Rita", "Callao S/N - Colmena Norte", sv1_badge("Para firmar acta", "blue"))
    st.markdown("#### Demandas para validar")
    sv1_action_card("Expte. 900/26 - Gomez Carolina", "Aconquija 80 - El Molino", sv1_badge("Emergencia", "red"), "Crear obra")
with m2:
    st.markdown(
        """
        <div class="sv1-detail-panel">
            <div class="sv1-panel-title">Ficha de obra seleccionada</div>
            <div class="sv1-card-main">Expte. 1037/26 - Ortiz Jorgelina</div>
            <div class="sv1-card-sub">San Martin 123 - Barrio Centro</div>
            <div class="sv1-panel-block">
                <div class="sv1-card-main">Flujo mock: buscar obra -> seleccionar -> editar ficha y tareas -> guardar</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
st.markdown("</div>", unsafe_allow_html=True)
