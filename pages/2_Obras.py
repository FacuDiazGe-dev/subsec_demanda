from datetime import date, datetime
from html import escape
import unicodedata

import pandas as pd
import streamlit as st

from utils.auth import require_login
from services import obras_service
from services.demandas_service import crear_demanda, listar_demandas_abiertas
from services.listado_tareas_service import listar_tareas_base
from services.materiales_base_service import listar_materiales_base_activos
from services.materiales_orden_service import crear_materiales_orden
from services.notas_rapidas_obra_service import actualizar_nota_rapida, crear_nota_rapida, listar_notas_rapidas
from services.ordenes_service import crear_orden_material
from services.seguimiento_obra_service import crear_seguimiento
from services.tareas_obra_service import (
    actualizar_tarea_cantidad_estado,
    actualizar_tarea_obra,
    crear_tarea_obra,
    eliminar_tarea_obra,
    listar_tareas_por_obra,
)
from utils.operational_card_component import operational_card
from utils.operational_list_editor_component import operational_list_editor

actualizar_obra_servicio = obras_service.actualizar_obra
crear_obra = obras_service.crear_obra
listar_obras_con_demanda = obras_service.listar_obras_con_demanda
obtener_obra_con_demanda = obras_service.obtener_obra_con_demanda
actualizar_obs_obras = getattr(obras_service, "actualizar_obs_obras", None)
agregar_obs_obras_del_dia = getattr(obras_service, "agregar_obs_obras_del_dia", None)

TIPOS_OBRA_PROGRAMA = ["HAVITA", "MI BANO", "EMERGENCIA HABITACIONAL", "OTROS"]
MODALIDADES_EJECUCION = ["Cuadrilla HAVITA", "Mano de obra propia", "Mixta", "Cuadrilla municipal"]
ESTADOS_OBRA = ["Para firmar acta", "Acta firmada", "Para obra", "En ejecucion", "Suspendida", "Ejecutada", "Cancelada"]
ESTADOS_GESTION_OBRA = ["En Ejecucion", "Ejecutada", "Cerrada", "Suspendida"]
RESPONSABLES_TECNICOS = ["Facundo", "Pedro", "Bea", "Iris", "Guillo"]
ACCIONES_DEMANDA_GESTION = ["Visitar", "Obra", "Emergencia", "Entregar materiales", "Informe / Actuacion", "Consulta / Seguimiento"]
ORIGENES_DEMANDA_GESTION = ["Subdirectora", "Vecino / consulta directa", "Intendencia", "Expediente", "Gestion de Obras", "Otra area municipal"]


def txt(v): return "" if v is None else str(v)
def clean(v): return txt(v).strip()


def normalizar(v):
    s = clean(v)
    try:
        s = s.encode("latin1").decode("utf-8")
    except Exception:
        pass
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()


def fecha_corta(v):
    v = clean(v)
    if not v:
        return "-"
    p = v[:10].split("-")
    return f"{p[2]}/{p[1]}/{p[0][2:]}" if len(p) == 3 else v


def show_error(error):
    st.error(f"No se pudo completar la operacion en Supabase: {error}")


def prioridad_rank(p):
    p = clean(p).lower()
    if p.startswith("1"):
        return 1
    if p.startswith("2"):
        return 2
    if p.startswith("3"):
        return 3
    if p.startswith("4"):
        return 4
    if p.startswith("5"):
        return 5
    return 9


def parse_cant(v):
    v = clean(v)
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return "__INVALID__"


def parse_fecha_input(v):
    v = clean(v)
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            pass
    return "__INVALID__"


def agregar_obs_bitacora(obs_actual, mensaje):
    entrada = f"|| {date.today().strftime('%d/%m/%y')} - {mensaje}"
    return f"{entrada} {clean(obs_actual)}" if clean(obs_actual) else entrada


def nombre_titular(item):
    apellido = clean(item.get("apellido")).upper()
    nombre = clean(item.get("nombre"))
    if apellido and nombre:
        return f"{apellido}, {nombre}"
    return apellido or nombre or "Sin titular"


def resumen(valor, largo=180):
    valor = clean(valor)
    if len(valor) <= largo:
        return valor
    return f"{valor[:largo].rstrip()}..."


def variant_obra(estado):
    estado_norm = normalizar(estado)
    if estado_norm == "en ejecucion":
        return "success"
    if estado_norm == "para firmar acta":
        return "highlight"
    if estado_norm == "suspendida":
        return "warning"
    if estado_norm == "ejecutada":
        return "success"
    if estado_norm == "cancelada":
        return "muted"
    return "default"


def color_obra_estado(estado):
    estado_norm = normalizar(estado)
    colores = {
        "en ejecucion": "#16A34A",
        "suspendida": "#D97706",
        "ejecutada": "#16A34A",
        "cancelada": "#64748B",
        "para obra": "#0284C7",
        "acta firmada": "#0F766E",
        "para firmar acta": "#1D4ED8",
    }
    return colores.get(estado_norm, "#94A3B8")


def color_accion_demanda(accion):
    accion_norm = normalizar(accion)
    if accion_norm == "emergencia":
        return "#DC2626"
    if accion_norm == "obra":
        return "#D97706"
    return "#94A3B8"


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
    vistos = st.session_state.setdefault("_obras_card_eventos_vistos", [])
    if event_id in vistos:
        return False
    vistos.append(event_id)
    st.session_state["_obras_card_eventos_vistos"] = vistos[-100:]
    return True


def obra_linea_1(obra):
    return f"Expte. {txt(obra.get('expediente')) or '-'} - {nombre_titular(obra)}"


def obra_linea_2(obra):
    domicilio = txt(obra.get("domicilio")) or "-"
    barrio = txt(obra.get("barrio")) or "-"
    return f"{domicilio} - {barrio}"


@st.cache_data(ttl=300)
def tareas_base_opciones():
    cat = listar_tareas_base()
    opts, mapa = [], {}
    for it in cat:
        d = clean(it.get("descripcion_tarea"))
        u = clean(it.get("unidad_tarea"))
        if not d:
            continue
        opts.append(f"{d} | {u}" if u else d)
        mapa[d] = u
    return opts, mapa


@st.cache_data(ttl=300)
def catalogo_materiales_operativo():
    materiales = listar_materiales_base_activos()
    catalogo = []
    for item in materiales:
        material = clean(item.get("material"))
        if not material:
            continue
        catalogo.append(
            {
                "id": item.get("id_material") or material,
                "label": material,
                "unit": clean(item.get("unidad")),
            }
        )
    return catalogo


def render_tareas_obra(obra, edicion_directa=False):
    st.markdown("#### Tareas de la obra")
    try:
        tareas = listar_tareas_por_obra(obra.get("id_obra"))
    except Exception as e:
        show_error(e)
        return

    # estado visual / edicion
    mk = f"modo_tareas_{obra.get('id_obra')}"
    if mk not in st.session_state:
        st.session_state[mk] = False
    edit_mode = True if edicion_directa else st.session_state[mk]

    if not edicion_directa:
        c1, c2 = st.columns([1, 3])
        with c1:
            if st.button("Salir de edicion" if edit_mode else "Activar modo edicion", key=f"toggle_{obra.get('id_obra')}", use_container_width=True):
                st.session_state[mk] = not edit_mode
                st.rerun()
        with c2:
            st.caption("Visual: solo lectura. Edicion: editar tabla y agregar tareas.")
    else:
        st.caption("Edicion directa: catalogo de tareas, cantidad, estado ejecutada y eliminacion.")

    if tareas and not edit_mode:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "id_tarea": t.get("id_tarea"),
                        "descripcion_tarea": txt(t.get("descripcion_tarea")),
                        "unidad_tarea": txt(t.get("unidad_tarea")),
                        "cant_tarea": txt(t.get("cant_tarea")),
                        "estado_tarea": "Ejecutada" if t.get("estado_tarea") else "Sin ejecutar",
                        "fecha_actualizacion": fecha_corta(t.get("fecha_actualizacion")),
                    }
                    for t in tareas
                ]
            ),
            hide_index=True,
            use_container_width=True,
            height=220,
        )
    elif not tareas and not edit_mode:
        st.info("Esta obra no tiene tareas cargadas.")

    opts, mapa_unidad = tareas_base_opciones()
    if not opts:
        st.warning("No hay tareas en listado_tareas.")
        return

    if edit_mode:
        catalogo = []
        for opt in opts:
            desc = clean(opt.split(" | ")[0])
            if not desc:
                continue
            catalogo.append({"id": desc, "label": desc, "unit": mapa_unidad.get(desc, "")})
        rows = [
            {
                "id": t.get("id_tarea"),
                "item_id": clean(t.get("descripcion_tarea")),
                "item_label": clean(t.get("descripcion_tarea")),
                "unit": clean(t.get("unidad_tarea")),
                "quantity": t.get("cant_tarea") or "",
                "status": bool(t.get("estado_tarea")),
                "deleted": False,
            }
            for t in tareas
        ]
        resultado = operational_list_editor(
            title="Tareas de la obra",
            rows=rows,
            catalog=catalogo,
            help_text="Selecciona tareas del catalogo, ajusta cantidad, marca ejecutada o elimina.",
            add_label="Agregar tarea",
            save_label="Guardar cambios de tareas",
            item_label="Tarea",
            show_status=True,
            status_label="Ejecutada",
            allow_delete=True,
            mark_deleted=True,
            key=f"op_tareas_obra_{obra.get('id_obra')}",
        )
        if resultado and resultado.get("action") == "save":
            mapa_actual = {str(t.get("id_tarea")): t for t in tareas}
            try:
                for r in resultado.get("rows") or []:
                    tid = clean(r.get("id"))
                    desc = clean(r.get("item_label"))
                    unidad = clean(r.get("unit"))
                    cn = parse_cant(r.get("quantity"))
                    if cn == "__INVALID__":
                        st.warning(f"Cantidad invalida en tarea {desc or tid}.")
                        return
                    en = bool(r.get("status"))
                    if tid in mapa_actual:
                        act = mapa_actual[tid]
                        if bool(r.get("deleted")):
                            eliminar_tarea_obra(tid)
                            if agregar_obs_obras_del_dia:
                                agregar_obs_obras_del_dia(obra.get("id_obra"), f"Se elimino tarea: {clean(act.get('descripcion_tarea'))}")
                            continue
                        ca = parse_cant(act.get("cant_tarea"))
                        ea = bool(act.get("estado_tarea"))
                        if cn != ca or en != ea:
                            actualizar_tarea_cantidad_estado(tid, cn, en)
                            if agregar_obs_obras_del_dia:
                                cambios = []
                                if cn != ca:
                                    cambios.append(f"cantidad {ca if ca is not None else '-'} -> {cn if cn is not None else '-'}")
                                if en != ea:
                                    cambios.append(f"estado {'Ejecutada' if ea else 'Sin ejecutar'} -> {'Ejecutada' if en else 'Sin ejecutar'}")
                                agregar_obs_obras_del_dia(obra.get("id_obra"), f"Se modifico tarea: {clean(act.get('descripcion_tarea'))}. {'; '.join(cambios)}")
                    elif desc and not bool(r.get("deleted")):
                        crear_tarea_obra(obra.get("id_obra"), desc, unidad or None, cn)
                        if agregar_obs_obras_del_dia:
                            agregar_obs_obras_del_dia(obra.get("id_obra"), f"Se agrego tarea: {desc}")
            except Exception as e:
                show_error(e)
                return
            st.success("Cambios de tareas guardados.")
            st.rerun()

    if not edit_mode:
        return


def render_edicion_maestra_obra(obra):
    oid = obra.get("id_obra")
    st.markdown(f"### Ficha de obra #{oid}")
    st.markdown(f"**{obra_linea_1(obra)}**")
    st.caption(obra_linea_2(obra))

    with st.form(f"form_maestro_obra_{oid}"):
        c1, c2 = st.columns(2)
        with c1:
            tipo = st.selectbox(
                "tipo_obra_programa",
                TIPOS_OBRA_PROGRAMA,
                index=TIPOS_OBRA_PROGRAMA.index(obra.get("tipo_obra_programa")) if obra.get("tipo_obra_programa") in TIPOS_OBRA_PROGRAMA else 0,
                key=f"ma_tipo_{oid}",
            )
            estado = st.selectbox(
                "estado_obra",
                ESTADOS_OBRA,
                index=ESTADOS_OBRA.index(obra.get("estado_obra")) if obra.get("estado_obra") in ESTADOS_OBRA else 0,
                key=f"ma_estado_{oid}",
            )
            fecha_acta_in = st.text_input("fecha_acta", value=clean(obra.get("fecha_acta")), key=f"ma_fecha_acta_{oid}")
        with c2:
            modalidad = st.selectbox(
                "modalidad_ejecucion",
                MODALIDADES_EJECUCION,
                index=MODALIDADES_EJECUCION.index(obra.get("modalidad_ejecucion")) if obra.get("modalidad_ejecucion") in MODALIDADES_EJECUCION else 0,
                key=f"ma_modalidad_{oid}",
            )
            idx_resp = RESPONSABLES_TECNICOS.index(obra.get("responsable_tecnico")) if obra.get("responsable_tecnico") in RESPONSABLES_TECNICOS else 0
            resp = st.selectbox("responsable_tecnico", RESPONSABLES_TECNICOS, index=idx_resp, key=f"ma_resp_{oid}")
            fecha_inicio_in = st.text_input("fecha_inicio", value=clean(obra.get("fecha_inicio")), key=f"ma_fecha_inicio_{oid}")
        fecha_ejecutada_in = st.text_input("fecha_ejecutada", value=clean(obra.get("fecha_ejecutada")), key=f"ma_fecha_ejecutada_{oid}")
        descripcion = st.text_area("descripcion_obra", value=txt(obra.get("descripcion_obra")), height=90, key=f"ma_desc_{oid}")
        obs = st.text_area("obs_obras", value=txt(obra.get("obs_obras")), height=90, key=f"ma_obs_{oid}")
        guardar = st.form_submit_button("Guardar cambios de obra", type="primary", use_container_width=True)

    if guardar:
        fa = parse_fecha_input(fecha_acta_in)
        fi = parse_fecha_input(fecha_inicio_in)
        fe = parse_fecha_input(fecha_ejecutada_in)
        if "__INVALID__" in {fa, fi, fe}:
            st.warning("Formato de fecha invalido. Usa YYYY-MM-DD o DD/MM/AA.")
            return

        payload = {}
        cambios = []
        comparables = {
            "tipo_obra_programa": (clean(obra.get("tipo_obra_programa")), clean(tipo), "Tipo"),
            "modalidad_ejecucion": (clean(obra.get("modalidad_ejecucion")), clean(modalidad), "Modalidad"),
            "estado_obra": (clean(obra.get("estado_obra")), clean(estado), "Estado"),
            "responsable_tecnico": (clean(obra.get("responsable_tecnico")), clean(resp), "Responsable"),
            "descripcion_obra": (clean(obra.get("descripcion_obra")), clean(descripcion), "Descripcion"),
            "obs_obras": (clean(obra.get("obs_obras")), clean(obs), "Obs"),
            "fecha_acta": (clean(obra.get("fecha_acta")), clean(fa), "fecha_acta"),
            "fecha_inicio": (clean(obra.get("fecha_inicio")), clean(fi), "fecha_inicio"),
            "fecha_ejecutada": (clean(obra.get("fecha_ejecutada")), clean(fe), "fecha_ejecutada"),
        }
        for k, (old, new, label) in comparables.items():
            if old != new:
                payload[k] = new or None
                cambios.append(f"{label}: {old or '-'} -> {new or '-'}")

        auto = []
        hoy = date.today().isoformat()
        if estado == "Acta firmada" and not clean(payload.get("fecha_acta", obra.get("fecha_acta"))):
            payload["fecha_acta"] = hoy
            auto.append("fecha_acta registrada automaticamente")
        if estado == "En ejecucion" and not clean(payload.get("fecha_inicio", obra.get("fecha_inicio"))):
            payload["fecha_inicio"] = hoy
            auto.append("fecha_inicio registrada automaticamente")
        if estado == "Ejecutada" and not clean(payload.get("fecha_ejecutada", obra.get("fecha_ejecutada"))):
            payload["fecha_ejecutada"] = hoy
            auto.append("fecha_ejecutada registrada automaticamente")

        if not payload and not auto:
            st.info("No hay cambios para guardar.")
        else:
            msg = f"Actualizacion de obra. Cambios: {'; '.join(cambios) if cambios else 'sin cambios manuales'}"
            if auto:
                msg = f"{msg}; {'; '.join(auto)}"
            payload["historial_mensaje"] = msg
            try:
                actualizar_obra_servicio(oid, payload)
            except Exception as e:
                show_error(e)
                return
            st.success("Campos de obra actualizados.")
            st.rerun()

    render_tareas_obra(obra, edicion_directa=True)


def tablero_tab():
    st.subheader("Tablero de obras")
    obras = listar_obras_con_demanda()
    st.markdown("### Obras registradas")
    for o in obras:
        operational_card(
            title=nombre_titular(o),
            subtitle=f"Expte. {txt(o.get('expediente')) or '-'}",
            status=txt(o.get("estado_obra")) or "-",
            priority=None,
            meta=[
                f"Modalidad: {txt(o.get('modalidad_ejecucion')) or '-'}",
                f"Responsable: {txt(o.get('responsable_tecnico')) or '-'}",
            ],
            description=resumen(o.get("descripcion_obra")) or "-",
            footer=f"Ultima actualizaci?n: {fecha_corta(o.get('ultima_actualizacion_semanal'))}",
            variant=variant_obra(o.get("estado_obra")),
            accent_color=color_obra_estado(o.get("estado_obra")),
            card_key=f"obra_tablero_{o.get('id_obra')}",
            key=f"obra_tablero_{o.get('id_obra')}",
        )
    st.divider()
    st.markdown("### Demandas para generar obra")
    ids = {o.get("id_demanda") for o in obras if o.get("id_demanda") is not None}
    dms = [d for d in listar_demandas_abiertas() if clean(d.get("accion")).lower() in {"obra", "emergencia"} and d.get("id_demanda") not in ids]
    dms.sort(key=lambda d: (prioridad_rank(d.get("prioridad")), d.get("id_demanda") or 999999))
    if not dms:
        st.info("No hay demandas pendientes para crear obra.")
        return
    for d in dms:
        did_demanda = d.get("id_demanda")
        accion_card = operational_card(
            title=nombre_titular(d),
            subtitle=f"Expte. {txt(d.get('expediente')) or '-'}",
            status=txt(d.get("accion")) or "Demanda",
            priority=txt(d.get("prioridad")) or None,
            meta=[f"Origen: {txt(d.get('origen')) or '-'}", f"Estado: {txt(d.get('estado')) or '-'}"],
            description=resumen(d.get("observaciones")) or "Demanda pendiente de validaci?n para crear obra.",
            footer=f"Demanda #{did_demanda}",
            variant="warning",
            accent_color=color_accion_demanda(d.get("accion")),
            actions=[
                {"label": "Crear obra", "key": "crear_obra", "kind": "primary"},
            ],
            actions_layout="corner",
            card_key=f"demanda_obra_{did_demanda}",
            key=f"demanda_obra_{did_demanda}",
        )
        if (
            isinstance(accion_card, dict)
            and accion_card.get("action") == "crear_obra"
            and accion_card.get("card_key") == f"demanda_obra_{did_demanda}"
        ):
            st.session_state["tb_demanda_crear_obra_id"] = did_demanda
            st.rerun()

        if st.session_state.get("tb_demanda_crear_obra_id") == did_demanda:
            tipo_default = "EMERGENCIA HABITACIONAL" if clean(d.get("accion")).lower() == "emergencia" else "HAVITA"
            with st.form(f"tb_form_crear_{d.get('id_demanda')}"):
                c1, c2 = st.columns(2)
                with c1:
                    tipo = st.selectbox("tipo_obra_programa", TIPOS_OBRA_PROGRAMA, index=TIPOS_OBRA_PROGRAMA.index(tipo_default) if tipo_default in TIPOS_OBRA_PROGRAMA else 0)
                    modalidad = st.selectbox("modalidad_ejecucion", MODALIDADES_EJECUCION, index=MODALIDADES_EJECUCION.index("Cuadrilla HAVITA") if "Cuadrilla HAVITA" in MODALIDADES_EJECUCION else 0)
                with c2:
                    estado = st.selectbox("estado_obra", ESTADOS_OBRA, index=0)
                    responsable = st.selectbox("responsable_tecnico", RESPONSABLES_TECNICOS, index=0)
                descripcion = st.text_area("descripcion_obra", value=f"Obra generada desde tablero por validacion de demanda #{d.get('id_demanda')}.", height=80)
                c_crear, c_cancelar = st.columns([2, 1])
                with c_crear:
                    crear = st.form_submit_button("Validar y crear obra", type="primary", use_container_width=True)
                with c_cancelar:
                    cancelar = st.form_submit_button("Cancelar", use_container_width=True)

            if cancelar:
                st.session_state.pop("tb_demanda_crear_obra_id", None)
                st.rerun()
            elif crear:
                if d.get("id_demanda") in ids:
                    st.warning("Esta demanda ya tiene una obra creada.")
                else:
                    payload = {
                        "id_demanda": d.get("id_demanda"),
                        "tipo_obra_programa": tipo,
                        "modalidad_ejecucion": modalidad,
                        "estado_obra": estado,
                        "responsable_tecnico": responsable,
                        "descripcion_obra": clean(descripcion) or None,
                        "obs_obras": f"|| {date.today().strftime('%d/%m/%y')} - Obra creada desde tablero por validacion de demanda.",
                        "fecha_creacion": date.today().isoformat(),
                    }
                    try:
                        crear_obra(payload)
                    except Exception as e:
                        show_error(e)
                    else:
                        st.success("Obra creada correctamente.")
                        st.session_state.pop("tb_demanda_crear_obra_id", None)
                        st.rerun()


def editar_obra_tab():
    st.subheader("Editar obra")
    obras = listar_obras_con_demanda()
    q = st.text_input("Busqueda libre", placeholder="id_obra, expediente, apellido, nombre o barrio")
    qn = normalizar(q)
    filtradas = [o for o in obras if not qn or any(qn in normalizar(o.get(c)) for c in ["id_obra", "expediente", "apellido", "nombre", "barrio"])]
    st.caption(f"Obras encontradas: {len(filtradas)}")
    for o in sorted(filtradas, key=lambda x: x.get("id_obra") or 0, reverse=True):
        with st.container(border=True):
            st.markdown(f"**Obra #{txt(o.get('id_obra'))}** | {txt(o.get('apellido'))}, {txt(o.get('nombre'))} | Expte {txt(o.get('expediente')) or '-'}")
            if st.button("Editar", key=f"e_{o.get('id_obra')}"):
                st.session_state["obra_edit_sel"] = o.get("id_obra")
                st.rerun()
    oid = st.session_state.get("obra_edit_sel")
    if not oid:
        return
    obra = obtener_obra_con_demanda(oid)
    if not obra:
        return
    st.divider()
    st.markdown(f"### Obra N? {oid}")
    with st.form(f"form_editar_obra_{oid}"):
        c1, c2 = st.columns(2)
        with c1:
            tipo = st.selectbox(
                "tipo_obra_programa",
                TIPOS_OBRA_PROGRAMA,
                index=TIPOS_OBRA_PROGRAMA.index(obra.get("tipo_obra_programa")) if obra.get("tipo_obra_programa") in TIPOS_OBRA_PROGRAMA else 0,
            )
            estado = st.selectbox(
                "estado_obra",
                ESTADOS_OBRA,
                index=ESTADOS_OBRA.index(obra.get("estado_obra")) if obra.get("estado_obra") in ESTADOS_OBRA else 0,
            )
            fecha_acta_in = st.text_input("fecha_acta", value=clean(obra.get("fecha_acta")))
        with c2:
            modalidad = st.selectbox(
                "modalidad_ejecucion",
                MODALIDADES_EJECUCION,
                index=MODALIDADES_EJECUCION.index(obra.get("modalidad_ejecucion")) if obra.get("modalidad_ejecucion") in MODALIDADES_EJECUCION else 0,
            )
            idx_resp = RESPONSABLES_TECNICOS.index(obra.get("responsable_tecnico")) if obra.get("responsable_tecnico") in RESPONSABLES_TECNICOS else 0
            resp = st.selectbox("responsable_tecnico", RESPONSABLES_TECNICOS, index=idx_resp)
            fecha_inicio_in = st.text_input("fecha_inicio", value=clean(obra.get("fecha_inicio")))
        fecha_ejecutada_in = st.text_input("fecha_ejecutada", value=clean(obra.get("fecha_ejecutada")))
        descripcion = st.text_area("descripcion_obra", value=txt(obra.get("descripcion_obra")), height=90)
        obs = st.text_area("obs_obras", value=txt(obra.get("obs_obras")), height=90)
        b1, b2 = st.columns(2)
        guardar = b1.form_submit_button("Guardar cambios de obra", type="primary", use_container_width=True)
        cancelar = b2.form_submit_button("Cancelar edicion", use_container_width=True)

    if cancelar:
        st.session_state.pop("obra_edit_sel", None)
        st.rerun()

    if guardar:
        fa = parse_fecha_input(fecha_acta_in)
        fi = parse_fecha_input(fecha_inicio_in)
        fe = parse_fecha_input(fecha_ejecutada_in)
        if "__INVALID__" in {fa, fi, fe}:
            st.warning("Formato de fecha invalido. Usa YYYY-MM-DD o DD/MM/AA.")
            return

        payload = {}
        cambios = []
        comparables = {
            "tipo_obra_programa": (clean(obra.get("tipo_obra_programa")), clean(tipo), "Tipo"),
            "modalidad_ejecucion": (clean(obra.get("modalidad_ejecucion")), clean(modalidad), "Modalidad"),
            "estado_obra": (clean(obra.get("estado_obra")), clean(estado), "Estado"),
            "responsable_tecnico": (clean(obra.get("responsable_tecnico")), clean(resp), "Responsable"),
            "descripcion_obra": (clean(obra.get("descripcion_obra")), clean(descripcion), "Descripcion"),
            "obs_obras": (clean(obra.get("obs_obras")), clean(obs), "Obs"),
            "fecha_acta": (clean(obra.get("fecha_acta")), clean(fa), "fecha_acta"),
            "fecha_inicio": (clean(obra.get("fecha_inicio")), clean(fi), "fecha_inicio"),
            "fecha_ejecutada": (clean(obra.get("fecha_ejecutada")), clean(fe), "fecha_ejecutada"),
        }
        for k, (old, new, label) in comparables.items():
            if old != new:
                payload[k] = new or None
                cambios.append(f"{label}: {old or '-'} -> {new or '-'}")

        auto = []
        hoy = date.today().isoformat()
        if estado == "Acta firmada" and not clean(payload.get("fecha_acta", obra.get("fecha_acta"))):
            payload["fecha_acta"] = hoy
            auto.append("fecha_acta registrada automaticamente")
        if estado == "En ejecucion" and not clean(payload.get("fecha_inicio", obra.get("fecha_inicio"))):
            payload["fecha_inicio"] = hoy
            auto.append("fecha_inicio registrada automaticamente")
        if estado == "Ejecutada" and not clean(payload.get("fecha_ejecutada", obra.get("fecha_ejecutada"))):
            payload["fecha_ejecutada"] = hoy
            auto.append("fecha_ejecutada registrada automaticamente")

        if not payload and not auto:
            st.info("No hay cambios para guardar.")
        else:
            msg = f"Actualizacion de obra. Cambios: {'; '.join(cambios) if cambios else 'sin cambios manuales'}"
            if auto:
                msg = f"{msg}; {'; '.join(auto)}"
            payload["historial_mensaje"] = msg
            try:
                actualizar_obra_servicio(oid, payload)
            except Exception as e:
                show_error(e)
                return
            st.success("Campos de obra actualizados.")
            st.session_state.pop("obra_edit_sel", None)
            st.rerun()

    render_tareas_obra(obra)


def tablero_tab():
    st.subheader("Tablero / Edicion maestra")
    st.caption("Bandeja de obras y demandas para validar, con ficha editable en la misma pantalla.")

    try:
        obras = listar_obras_con_demanda()
    except Exception as e:
        show_error(e)
        return

    f1, f2, f3, f4 = st.columns([2.2, 1.2, 1.2, 1.2])
    with f1:
        q = st.text_input("Busqueda libre", placeholder="Expediente, apellido, barrio, domicilio", key="tb_maestro_q")
    with f2:
        estados = ["Todos"] + sorted({clean(o.get("estado_obra")) for o in obras if clean(o.get("estado_obra"))})
        estado_f = st.selectbox("Estado", estados, key="tb_maestro_estado")
    with f3:
        responsables = ["Todos"] + sorted({clean(o.get("responsable_tecnico")) for o in obras if clean(o.get("responsable_tecnico"))})
        resp_f = st.selectbox("Responsable", responsables, key="tb_maestro_resp")
    with f4:
        modalidades = ["Todos"] + sorted({clean(o.get("modalidad_ejecucion")) for o in obras if clean(o.get("modalidad_ejecucion"))})
        mod_f = st.selectbox("Modalidad", modalidades, key="tb_maestro_mod")

    qn = normalizar(q)
    obras_filtradas = []
    for o in obras:
        blob = " ".join(clean(o.get(c)) for c in ["id_obra", "id_demanda", "expediente", "apellido", "nombre", "barrio", "domicilio"])
        if qn and qn not in normalizar(blob):
            continue
        if estado_f != "Todos" and clean(o.get("estado_obra")) != estado_f:
            continue
        if resp_f != "Todos" and clean(o.get("responsable_tecnico")) != resp_f:
            continue
        if mod_f != "Todos" and clean(o.get("modalidad_ejecucion")) != mod_f:
            continue
        obras_filtradas.append(o)

    ids = {o.get("id_demanda") for o in obras if o.get("id_demanda") is not None}
    try:
        dms = [
            d for d in listar_demandas_abiertas()
            if clean(d.get("accion")).lower() in {"obra", "emergencia"} and d.get("id_demanda") not in ids
        ]
    except Exception as e:
        show_error(e)
        dms = []
    dms.sort(key=lambda d: (prioridad_rank(d.get("prioridad")), d.get("id_demanda") or 999999))

    if "tb_obra_sel" not in st.session_state and obras_filtradas:
        st.session_state["tb_obra_sel"] = obras_filtradas[0].get("id_obra")

    col_lista, col_ficha = st.columns([0.4, 0.6])

    with col_lista:
        st.markdown("### Obras registradas")
        if not obras_filtradas:
            st.info("No hay obras con esos filtros.")
        for o in sorted(obras_filtradas, key=lambda x: x.get("id_obra") or 0, reverse=True):
            oid = o.get("id_obra")
            ck = f"tb_obra_{oid}"
            resultado = operational_card(
                title=obra_linea_1(o),
                subtitle=obra_linea_2(o),
                status=txt(o.get("estado_obra")) or "-",
                priority=None,
                meta=[],
                description=None,
                footer=None,
                variant=variant_obra(o.get("estado_obra")),
                accent_color=color_obra_estado(o.get("estado_obra")),
                clickable=True,
                selected=str(st.session_state.get("tb_obra_sel", "")) == str(oid),
                card_key=ck,
                key=f"tb_obra_card_{oid}",
            )
            if card_event_once(resultado, ck, "card_click"):
                st.session_state["tb_obra_sel"] = oid
                st.rerun()

        st.markdown("---")
        st.markdown("### Demandas para validar")
        if not dms:
            st.info("No hay demandas pendientes para crear obra.")
        for d in dms[:8]:
            did_demanda = d.get("id_demanda")
            ck = f"demanda_obra_{did_demanda}"
            accion_card = operational_card(
                title=f"Expte. {txt(d.get('expediente')) or '-'} - {nombre_titular(d)}",
                subtitle=f"{txt(d.get('domicilio')) or '-'} - {txt(d.get('barrio')) or '-'}",
                status=txt(d.get("accion")) or "Demanda",
                priority=txt(d.get("prioridad")) or None,
                meta=[f"Estado: {txt(d.get('estado')) or '-'}"],
                description=None,
                footer=f"Demanda #{did_demanda}",
                variant="warning",
                accent_color=color_accion_demanda(d.get("accion")),
                actions=[{"label": "Crear obra", "key": "crear_obra", "kind": "primary"}],
                actions_layout="corner",
                card_key=ck,
                key=f"tb_demanda_obra_card_{did_demanda}",
            )
            if card_event_once(accion_card, ck, "crear_obra"):
                st.session_state["tb_demanda_crear_obra_id"] = did_demanda
                st.rerun()

            if st.session_state.get("tb_demanda_crear_obra_id") == did_demanda:
                tipo_default = "EMERGENCIA HABITACIONAL" if clean(d.get("accion")).lower() == "emergencia" else "HAVITA"
                with st.form(f"tb_form_crear_{d.get('id_demanda')}"):
                    tipo = st.selectbox("tipo_obra_programa", TIPOS_OBRA_PROGRAMA, index=TIPOS_OBRA_PROGRAMA.index(tipo_default) if tipo_default in TIPOS_OBRA_PROGRAMA else 0)
                    modalidad = st.selectbox("modalidad_ejecucion", MODALIDADES_EJECUCION, index=MODALIDADES_EJECUCION.index("Cuadrilla HAVITA") if "Cuadrilla HAVITA" in MODALIDADES_EJECUCION else 0)
                    estado = st.selectbox("estado_obra", ESTADOS_OBRA, index=0)
                    responsable = st.selectbox("responsable_tecnico", RESPONSABLES_TECNICOS, index=0)
                    descripcion = st.text_area("descripcion_obra", value=f"Obra generada desde tablero por validacion de demanda #{d.get('id_demanda')}.", height=80)
                    c_crear, c_cancelar = st.columns([2, 1])
                    crear = c_crear.form_submit_button("Validar y crear", type="primary", use_container_width=True)
                    cancelar = c_cancelar.form_submit_button("Cancelar", use_container_width=True)

                if cancelar:
                    st.session_state.pop("tb_demanda_crear_obra_id", None)
                    st.rerun()
                elif crear:
                    if d.get("id_demanda") in ids:
                        st.warning("Esta demanda ya tiene una obra creada.")
                    else:
                        payload = {
                            "id_demanda": d.get("id_demanda"),
                            "tipo_obra_programa": tipo,
                            "modalidad_ejecucion": modalidad,
                            "estado_obra": estado,
                            "responsable_tecnico": responsable,
                            "descripcion_obra": clean(descripcion) or None,
                            "obs_obras": f"|| {date.today().strftime('%d/%m/%y')} - Obra creada desde tablero por validacion de demanda.",
                            "fecha_creacion": date.today().isoformat(),
                        }
                        try:
                            nueva = crear_obra(payload)
                        except Exception as e:
                            show_error(e)
                        else:
                            st.success("Obra creada correctamente.")
                            st.session_state.pop("tb_demanda_crear_obra_id", None)
                            if nueva:
                                st.session_state["tb_obra_sel"] = nueva.get("id_obra")
                            st.rerun()

    with col_ficha:
        oid = st.session_state.get("tb_obra_sel")
        obra = obtener_obra_con_demanda(oid) if oid else None
        if not obra:
            st.info("Selecciona una obra del listado para ver o editar su ficha.")
            return
        render_edicion_maestra_obra(obra)


def guardar_ficha_obras_v2(obra):
    oid = obra.get("id_obra")
    valores = {
        "estado_obra": st.session_state.get(f"obras_v2_estado_edit_{oid}"),
        "responsable_tecnico": st.session_state.get(f"obras_v2_resp_edit_{oid}"),
        "modalidad_ejecucion": st.session_state.get(f"obras_v2_mod_edit_{oid}"),
        "tipo_obra_programa": st.session_state.get(f"obras_v2_tipo_edit_{oid}"),
        "descripcion_obra": st.session_state.get(f"obras_v2_desc_{oid}"),
        "obs_obras": st.session_state.get(f"obras_v2_obs_{oid}"),
    }
    etiquetas = {
        "estado_obra": "Estado",
        "responsable_tecnico": "Responsable",
        "modalidad_ejecucion": "Modalidad",
        "tipo_obra_programa": "Tipo de obra",
        "descripcion_obra": "Descripcion",
        "obs_obras": "Observaciones",
    }
    payload = {}
    cambios = []
    cambios_obs = []
    for campo, nuevo in valores.items():
        anterior = clean(obra.get(campo))
        nuevo_limpio = clean(nuevo)
        if anterior != nuevo_limpio:
            payload[campo] = nuevo_limpio
            cambios.append(f"{etiquetas[campo]}: {anterior or '-'} -> {nuevo_limpio or '-'}")
            if campo == "descripcion_obra":
                cambios_obs.append("Descripcion actualizada")
            elif campo == "obs_obras":
                cambios_obs.append("Observaciones editadas")
            else:
                cambios_obs.append(f"{etiquetas[campo]}: {anterior or '-'} -> {nuevo_limpio or '-'}")

    if not payload:
        return "sin_cambios", 0

    payload["historial_mensaje"] = f"Actualizacion desde Obras v2. Cambios: {'; '.join(cambios)}."
    actualizar_obra_servicio(oid, payload)
    if cambios_obs and agregar_obs_obras_del_dia:
        agregar_obs_obras_del_dia(oid, f"Se actualizaron datos de obra: {'; '.join(cambios_obs)}")
    return "guardado", len(cambios)


def es_id_real_supabase(valor):
    return clean(valor).isdigit()


def guardar_tareas_obras_v2(id_obra, filas_actuales, filas_originales):
    originales = {str(f.get("id")): f for f in filas_originales if es_id_real_supabase(f.get("id"))}
    ids_actuales = {str(f.get("id")) for f in filas_actuales if es_id_real_supabase(f.get("id")) and not f.get("deleted")}
    cambios = 0

    for id_original, fila_original in originales.items():
        if id_original not in ids_actuales:
            eliminar_tarea_obra(id_original)
            if agregar_obs_obras_del_dia:
                desc_original = clean(fila_original.get("item_label") or fila_original.get("item_id"))
                agregar_obs_obras_del_dia(id_obra, f"Se elimino tarea: {desc_original}")
            cambios += 1

    for fila in filas_actuales:
        id_tarea = fila.get("id")
        id_real = es_id_real_supabase(id_tarea)
        desc = clean(fila.get("item_label") or fila.get("item_id"))
        unidad = clean(fila.get("unit"))
        cant = parse_cant(fila.get("quantity"))
        if cant == "__INVALID__":
            raise ValueError(f"La cantidad de '{desc or 'tarea'}' debe ser numerica.")

        if fila.get("deleted"):
            continue

        if not desc:
            continue

        if id_real:
            original = originales.get(str(id_tarea), {})
            original_cant = parse_cant(original.get("quantity"))
            if (
                clean(original.get("item_label") or original.get("item_id")) != desc
                or clean(original.get("unit")) != unidad
                or original_cant != cant
            ):
                actualizar_tarea_obra(id_tarea, desc, unidad, cant)
                if agregar_obs_obras_del_dia:
                    agregar_obs_obras_del_dia(id_obra, f"Se modifico tarea: {desc}")
                cambios += 1
        else:
            crear_tarea_obra(id_obra, desc, unidad, cant)
            if agregar_obs_obras_del_dia:
                agregar_obs_obras_del_dia(id_obra, f"Se agrego tarea: {desc}")
            cambios += 1

    return cambios


def crear_obra_desde_demanda_v2(demanda, ids_con_obra):
    id_demanda = demanda.get("id_demanda")
    if not id_demanda:
        raise ValueError("La demanda no tiene id_demanda.")
    if id_demanda in ids_con_obra:
        return "duplicada", None

    accion = clean(demanda.get("accion")).lower()
    tipo_default = "EMERGENCIA HABITACIONAL" if accion == "emergencia" else "HAVITA"
    payload = {
        "id_demanda": id_demanda,
        "tipo_obra_programa": tipo_default,
        "modalidad_ejecucion": "Cuadrilla HAVITA",
        "estado_obra": "Para firmar acta",
        "responsable_tecnico": RESPONSABLES_TECNICOS[0] if RESPONSABLES_TECNICOS else None,
        "descripcion_obra": f"Obra generada desde Obras v2 por validacion de demanda #{id_demanda}.",
        "obs_obras": f"|| {date.today().strftime('%d/%m/%y')} - Obra creada desde Obras v2 por validacion de demanda.",
        "fecha_creacion": date.today().isoformat(),
    }
    return "creada", crear_obra(payload)


def obras_v2_tab():
    st.subheader("Obras v2")
    st.caption("Vista paralela de prueba: lectura real segura y guardado controlado de ficha, tareas y alta de obra desde demanda.")

    st.markdown(
        """
        <style>
        div[class*="st-key-obras_v2_ficha"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff !important;
            border-color: #dbe7ee !important;
            padding: 10px 12px !important;
            box-shadow: 0 1px 7px rgba(15, 23, 42, 0.045) !important;
        }
        div[class*="st-key-obras_v2_ficha"] [data-testid="stVerticalBlock"] {
            gap: 0.22rem !important;
        }
        div[class*="st-key-obras_v2_ficha"] [data-testid="column"] [data-testid="stVerticalBlock"] {
            gap: 0.16rem !important;
        }
        div[class*="st-key-obras_v2_ficha"] label {
            font-size: 12px !important;
            font-weight: 650 !important;
            color: #475569 !important;
            margin-bottom: 2px !important;
        }
        div[class*="st-key-obras_v2_ficha"] input {
            background: #ffffff !important;
            min-height: 34px !important;
            height: 34px !important;
            padding-top: 4px !important;
            padding-bottom: 4px !important;
            font-size: 13px !important;
        }
        div[class*="st-key-obras_v2_ficha"] [data-baseweb="select"],
        div[class*="st-key-obras_v2_ficha"] [data-baseweb="select"] > div {
            background: #ffffff !important;
            min-height: 34px !important;
            height: 34px !important;
        }
        div[class*="st-key-obras_v2_ficha"] textarea {
            background: #ffffff !important;
            min-height: 54px !important;
            height: 54px !important;
            max-height: 150px !important;
            padding-top: 5px !important;
            padding-bottom: 5px !important;
            font-size: 13px !important;
            line-height: 1.25 !important;
        }
        div[class*="st-key-obras_v2_desc_"] textarea {
            min-height: 58px !important;
            height: 58px !important;
        }
        div[class*="st-key-obras_v2_obs_"] textarea {
            min-height: 112px !important;
            height: 112px !important;
            max-height: 180px !important;
            line-height: 1.32 !important;
        }
        div[class*="st-key-obras_v2_ficha"] [data-testid="stExpander"] {
            background: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 10px !important;
        }
        .obras-v2-title {
            color: #0f2742;
            font-size: 16px;
            font-weight: 850;
            line-height: 1.15;
            margin-bottom: 2px;
        }
        .obras-v2-subtitle {
            color: #64748b;
            font-size: 12px;
            font-weight: 650;
            line-height: 1.2;
        }
        .obras-v2-block-title {
            border-top: 1px solid #e2e8f0;
            color: #1e293b;
            font-size: 13px;
            font-weight: 850;
            margin-top: 10px;
            padding-top: 9px;
            margin-bottom: 5px;
        }
        .obras-v2-block-title:first-child {
            margin-top: 7px;
        }
        .obras-v2-section-title {
            color: #0f2742;
            font-size: 18px;
            font-weight: 850;
            margin: 0 0 6px;
        }
        .obras-v2-empty {
            background: #ffffff;
            border: 1px dashed #cbd5e1;
            border-radius: 14px;
            color: #64748b;
            font-size: 13px;
            font-weight: 750;
            padding: 24px 16px;
            text-align: center;
        }
        div[class*="st-key-obras_v2_btn_buscar"] button,
        div[class*="st-key-obras_v2_ficha"] [data-testid="stFormSubmitButton"] button {
            background: #006b68 !important;
            border-color: #006b68 !important;
            color: #ffffff !important;
            box-shadow: none !important;
        }
        div[class*="st-key-obras_v2_btn_buscar"] button:hover,
        div[class*="st-key-obras_v2_ficha"] [data-testid="stFormSubmitButton"] button:hover {
            background: #004f4c !important;
            border-color: #004f4c !important;
            color: #ffffff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    try:
        obras = listar_obras_con_demanda()
    except Exception as e:
        show_error(e)
        return

    ids_con_obra = {o.get("id_demanda") for o in obras if o.get("id_demanda") is not None}
    try:
        demandas = [
            d for d in listar_demandas_abiertas()
            if clean(d.get("accion")).lower() in {"obra", "emergencia"}
            and d.get("id_demanda") not in ids_con_obra
        ]
    except Exception as e:
        show_error(e)
        demandas = []
    demandas.sort(key=lambda d: (prioridad_rank(d.get("prioridad")), d.get("id_demanda") or 999999))

    with st.container(border=True):
        f1, f2, f3, f4, f5 = st.columns([2.4, 1.3, 1.3, 1.3, 1.0])
        with f1:
            q = st.text_input("Busqueda libre", placeholder="Expediente, apellido, barrio, domicilio", key="obras_v2_q")
        with f2:
            estados = ["Todos"] + sorted({clean(o.get("estado_obra")) for o in obras if clean(o.get("estado_obra"))})
            estado_f = st.selectbox("Estado de obra", estados, key="obras_v2_estado")
        with f3:
            responsables = ["Todos"] + sorted({clean(o.get("responsable_tecnico")) for o in obras if clean(o.get("responsable_tecnico"))})
            resp_f = st.selectbox("Responsable", responsables, key="obras_v2_resp")
        with f4:
            modalidades = ["Todos"] + sorted({clean(o.get("modalidad_ejecucion")) for o in obras if clean(o.get("modalidad_ejecucion"))})
            mod_f = st.selectbox("Modalidad", modalidades, key="obras_v2_mod")
        with f5:
            st.write("")
            st.button("Buscar", type="primary", use_container_width=True, key="obras_v2_btn_buscar")

    qn = normalizar(q)
    obras_filtradas = []
    for o in obras:
        blob = " ".join(clean(o.get(c)) for c in ["id_obra", "id_demanda", "expediente", "apellido", "nombre", "barrio", "domicilio"])
        if qn and qn not in normalizar(blob):
            continue
        if estado_f != "Todos" and clean(o.get("estado_obra")) != estado_f:
            continue
        if resp_f != "Todos" and clean(o.get("responsable_tecnico")) != resp_f:
            continue
        if mod_f != "Todos" and clean(o.get("modalidad_ejecucion")) != mod_f:
            continue
        obras_filtradas.append(o)

    if "obras_v2_sel" not in st.session_state and obras_filtradas:
        st.session_state["obras_v2_sel"] = obras_filtradas[0].get("id_obra")

    col_lista, col_ficha = st.columns([0.4, 0.6])

    with col_lista:
        st.markdown('<div class="obras-v2-section-title">Obras registradas</div>', unsafe_allow_html=True)
        if not obras_filtradas:
            st.info("No hay obras con esos filtros.")
        for o in sorted(obras_filtradas, key=lambda x: x.get("id_obra") or 0, reverse=True):
            oid = o.get("id_obra")
            ck = f"obras_v2_obra_{oid}"
            resultado = operational_card(
                title=obra_linea_1(o).replace(" - ", " - ", 1),
                subtitle=obra_linea_2(o).replace(" - ", " - ", 1),
                status=txt(o.get("estado_obra")) or "-",
                priority=None,
                meta=[],
                description=None,
                footer=None,
                variant=variant_obra(o.get("estado_obra")),
                accent_color=color_obra_estado(o.get("estado_obra")),
                clickable=True,
                selected=str(st.session_state.get("obras_v2_sel", "")) == str(oid),
                card_key=ck,
                key=f"obras_v2_obra_card_{oid}",
            )
            if card_event_once(resultado, ck, "card_click"):
                st.session_state["obras_v2_sel"] = oid
                st.rerun()

    with col_ficha:
        st.markdown('<div class="obras-v2-section-title">Ficha de obra</div>', unsafe_allow_html=True)
        oid = st.session_state.get("obras_v2_sel")
        obra = obtener_obra_con_demanda(oid) if oid else None
        if not obra:
            st.markdown('<div class="obras-v2-empty">Selecciona una obra del listado para ver o editar su ficha.</div>', unsafe_allow_html=True)
        else:
            with st.container(border=True, key=f"obras_v2_ficha_{obra.get('id_obra')}", gap="small"):
                st.markdown(
                    f"""
                    <div class="obras-v2-title">{obra_linea_1(obra).replace(" - ", " - ", 1)}</div>
                    <div class="obras-v2-subtitle">{obra_linea_2(obra).replace(" - ", " - ", 1)}</div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.form(f"obras_v2_form_{obra.get('id_obra')}", border=False):
                    st.markdown('<div class="obras-v2-block-title">Descripcion de obra</div>', unsafe_allow_html=True)
                    st.text_area(
                        "Descripcion de obra",
                        value=txt(obra.get("descripcion_obra")),
                        height=58,
                        key=f"obras_v2_desc_{obra.get('id_obra')}",
                        label_visibility="collapsed",
                    )
                    st.markdown('<div class="obras-v2-block-title obras-v2-block-title-general">Datos generales</div>', unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    with c1:
                        st.selectbox(
                            "Estado de obra",
                            ESTADOS_OBRA,
                            index=ESTADOS_OBRA.index(obra.get("estado_obra")) if obra.get("estado_obra") in ESTADOS_OBRA else 0,
                            key=f"obras_v2_estado_edit_{obra.get('id_obra')}",
                        )
                        idx_resp = RESPONSABLES_TECNICOS.index(obra.get("responsable_tecnico")) if obra.get("responsable_tecnico") in RESPONSABLES_TECNICOS else 0
                        st.selectbox("Responsable tecnico", RESPONSABLES_TECNICOS, index=idx_resp, key=f"obras_v2_resp_edit_{obra.get('id_obra')}")
                    with c2:
                        st.selectbox(
                            "Modalidad",
                            MODALIDADES_EJECUCION,
                            index=MODALIDADES_EJECUCION.index(obra.get("modalidad_ejecucion")) if obra.get("modalidad_ejecucion") in MODALIDADES_EJECUCION else 0,
                            key=f"obras_v2_mod_edit_{obra.get('id_obra')}",
                        )
                        st.selectbox(
                            "Tipo de obra / programa",
                            TIPOS_OBRA_PROGRAMA,
                            index=TIPOS_OBRA_PROGRAMA.index(obra.get("tipo_obra_programa")) if obra.get("tipo_obra_programa") in TIPOS_OBRA_PROGRAMA else 0,
                            key=f"obras_v2_tipo_edit_{obra.get('id_obra')}",
                        )
                    st.markdown('<div class="obras-v2-block-title obras-v2-block-title-history">Observaciones / historial</div>', unsafe_allow_html=True)
                    st.text_area(
                        "Observaciones / historial",
                        value=txt(obra.get("obs_obras")),
                        height=72,
                        key=f"obras_v2_obs_{obra.get('id_obra')}",
                        label_visibility="collapsed",
                    )
                    _, bcol = st.columns([1, 0.26])
                    with bcol:
                        guardar_datos = st.form_submit_button("Guardar", type="primary", use_container_width=True)
                if guardar_datos:
                    try:
                        estado_guardado, cant_cambios = guardar_ficha_obras_v2(obra)
                    except Exception as e:
                        show_error(e)
                    else:
                        if estado_guardado == "sin_cambios":
                            st.info("No hay cambios para guardar.")
                        else:
                            st.success(f"Ficha guardada. Cambios aplicados: {cant_cambios}.")
                            st.rerun()

            try:
                tareas = listar_tareas_por_obra(obra.get("id_obra"))
            except Exception as e:
                show_error(e)
                tareas = []

            tareas_key = f"obras_v2_tareas_rows_{obra.get('id_obra')}"
            tareas_original_key = f"obras_v2_tareas_original_{obra.get('id_obra')}"
            if tareas_key not in st.session_state:
                st.session_state[tareas_key] = [
                    {
                        "id": t.get("id_tarea"),
                        "item_id": clean(t.get("descripcion_tarea")),
                        "item_label": clean(t.get("descripcion_tarea")),
                        "unit": clean(t.get("unidad_tarea")),
                        "quantity": t.get("cant_tarea") or "",
                        "status": bool(t.get("estado_tarea")),
                        "deleted": False,
                    }
                    for t in tareas
                ]
                st.session_state[tareas_original_key] = [dict(row) for row in st.session_state[tareas_key]]

            opts, mapa_unidad = tareas_base_opciones()
            catalogo = [
                {"id": clean(opt.split(" | ")[0]), "label": clean(opt.split(" | ")[0]), "unit": mapa_unidad.get(clean(opt.split(" | ")[0]), "")}
                for opt in opts
                if clean(opt.split(" | ")[0])
            ]
            resultado_tareas = operational_list_editor(
                title="Tareas asignadas",
                rows=st.session_state[tareas_key],
                catalog=catalogo,
                help_text="Guardado controlado: altas, cambios y eliminaciones impactan en tareas_x_obras.",
                add_label="Agregar tarea",
                save_label="Guardar tareas",
                item_label="Tarea",
                mode="build",
                allow_delete=True,
                mark_deleted=False,
                key=f"obras_v2_tareas_editor_{obra.get('id_obra')}",
            )
            if resultado_tareas and resultado_tareas.get("rows") is not None:
                st.session_state[tareas_key] = resultado_tareas.get("rows") or []
                if resultado_tareas.get("action") == "save":
                    try:
                        cant_cambios = guardar_tareas_obras_v2(
                            obra.get("id_obra"),
                            st.session_state[tareas_key],
                            st.session_state.get(tareas_original_key, []),
                        )
                    except Exception as e:
                        show_error(e)
                    else:
                        if cant_cambios:
                            st.success(f"Tareas guardadas. Cambios aplicados: {cant_cambios}.")
                            st.session_state.pop(tareas_key, None)
                            st.session_state.pop(tareas_original_key, None)
                            st.rerun()
                        else:
                            st.info("No hay cambios de tareas para guardar.")

    st.markdown("### Demandas pendientes para generar obra")
    st.caption("Seccion secundaria de Obras v2. Crear obra genera un registro real con valores iniciales por defecto.")
    if not demandas:
        st.info("No hay demandas pendientes para crear obra.")
    else:
        dcols = st.columns(3)
        for idx, d in enumerate(demandas[:9]):
            with dcols[idx % 3]:
                did = d.get("id_demanda")
                ck = f"obras_v2_demanda_{did}"
                accion = operational_card(
                    title=f"Expte. {txt(d.get('expediente')) or '-'} - {nombre_titular(d)}",
                    subtitle=f"{txt(d.get('domicilio')) or '-'} - {txt(d.get('barrio')) or '-'}",
                    status=txt(d.get("accion")) or "Demanda",
                    priority=txt(d.get("prioridad")) or None,
                    meta=[f"Estado: {txt(d.get('estado')) or '-'}"],
                    description=None,
                    footer=f"Demanda #{did}",
                    variant="warning",
                    accent_color=color_accion_demanda(d.get("accion")),
                    actions=[{"label": "Crear obra", "key": "crear_obra", "kind": "primary"}],
                    actions_layout="corner",
                    card_key=ck,
                    key=f"obras_v2_demanda_card_{did}",
                )
                if card_event_once(accion, ck, "crear_obra"):
                    try:
                        estado_creacion, nueva_obra = crear_obra_desde_demanda_v2(d, ids_con_obra)
                    except Exception as e:
                        show_error(e)
                    else:
                        if estado_creacion == "duplicada":
                            st.warning("Esta demanda ya tiene una obra creada.")
                        else:
                            st.success(f"Obra creada desde demanda #{did}.")
                            if nueva_obra:
                                st.session_state["obras_v2_sel"] = nueva_obra.get("id_obra")
                            st.rerun()


def seguimiento_tecnico_tab():
    st.subheader("Gestion de Obras")
    st.caption("Seguimiento operativo, avances y acciones derivadas de obra.")
    st.markdown(
        """
        <style>
        .go-section-title {
            color: #0f2742;
            font-size: 18px;
            font-weight: 850;
            margin: 0 0 2px;
        }
        .go-section-subtitle {
            color: #64748b;
            font-size: 12px;
            font-weight: 650;
            margin: 0 0 8px;
        }
        div[class*="st-key-go_filtros_panel"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff !important;
            border-color: #dbe7ee !important;
            padding: 10px 12px !important;
            box-shadow: 0 1px 7px rgba(15, 23, 42, 0.045) !important;
        }
        div[class*="st-key-go_filtros_panel"] [data-testid="stVerticalBlock"] {
            gap: 0.2rem !important;
        }
        div[class*="st-key-go_filtros_panel"] [data-testid="column"] [data-testid="stVerticalBlock"] {
            gap: 0.16rem !important;
        }
        div[class*="st-key-go_filtros_panel"] [data-testid="stHorizontalBlock"] {
            align-items: end !important;
        }
        div[class*="st-key-go_filtros_panel"] [data-testid="stForm"] {
            border: 0 !important;
            background: transparent !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        div[class*="st-key-go_filtros_panel"] [data-testid="stForm"] [data-testid="stVerticalBlock"] {
            gap: 0 !important;
        }
        div[class*="st-key-go_filtros_panel"] label {
            color: #475569 !important;
            font-size: 12px !important;
            font-weight: 650 !important;
            margin-bottom: 2px !important;
        }
        div[class*="st-key-go_filtros_panel"] input {
            background: #ffffff !important;
            min-height: 34px !important;
            height: 34px !important;
            padding-top: 4px !important;
            padding-bottom: 4px !important;
            font-size: 13px !important;
        }
        div[class*="st-key-go_filtros_panel"] [data-baseweb="select"],
        div[class*="st-key-go_filtros_panel"] [data-baseweb="select"] > div {
            background: #ffffff !important;
            border-color: #cbd5e1 !important;
            box-shadow: none !important;
            min-height: 34px !important;
            height: 34px !important;
        }
        div[class*="st-key-go_filtros_panel"] [data-baseweb="select"]:focus-within > div {
            border-color: #0f766e !important;
            box-shadow: 0 0 0 1px rgba(15, 118, 110, 0.18) !important;
        }
        div[class*="st-key-go_filtros_panel"] [aria-invalid="true"],
        div[class*="st-key-go_filtros_panel"] [aria-invalid="true"] > div {
            border-color: #cbd5e1 !important;
            box-shadow: none !important;
        }
        div[class*="st-key-go_filtros_panel"] [data-testid="stFormSubmitButton"] button {
            background: #006b68 !important;
            border-color: #006b68 !important;
            color: #ffffff !important;
            min-height: 34px !important;
            height: 34px !important;
            padding-top: 4px !important;
            padding-bottom: 4px !important;
            font-size: 13px !important;
            box-shadow: none !important;
        }
        div[class*="st-key-go_filtros_panel"] [data-testid="stFormSubmitButton"] button:hover {
            background: #004f4c !important;
            border-color: #004f4c !important;
            color: #ffffff !important;
        }
        div[class*="st-key-go_resumen_obra"] [data-testid="stVerticalBlockBorderWrapper"],
        div[class*="st-key-go_block_estado"] [data-testid="stVerticalBlockBorderWrapper"],
        div[class*="st-key-go_block_tareas"] [data-testid="stVerticalBlockBorderWrapper"],
        div[class*="st-key-go_block_acciones"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff !important;
            border-color: #dbe7ee !important;
            border-radius: 12px !important;
            padding: 12px 14px !important;
            box-shadow: 0 1px 7px rgba(15, 23, 42, 0.035) !important;
        }
        div[class*="st-key-go_block_estado"] label,
        div[class*="st-key-go_block_tareas"] label,
        div[class*="st-key-go_block_acciones"] label {
            color: #475569 !important;
            font-size: 12px !important;
            font-weight: 650 !important;
            margin-bottom: 2px !important;
        }
        div[class*="st-key-go_block_estado"] input,
        div[class*="st-key-go_block_acciones"] input,
        div[class*="st-key-go_block_acciones"] textarea,
        div[class*="st-key-go_block_estado"] [data-baseweb="select"],
        div[class*="st-key-go_block_estado"] [data-baseweb="select"] > div,
        div[class*="st-key-go_block_acciones"] [data-baseweb="select"],
        div[class*="st-key-go_block_acciones"] [data-baseweb="select"] > div {
            background: #ffffff !important;
            min-height: 34px !important;
            font-size: 13px !important;
        }
        div[class*="st-key-go_block_estado"] textarea,
        div[class*="st-key-go_block_estado"] [data-baseweb="select"],
        div[class*="st-key-go_block_estado"] [data-baseweb="select"] > div {
            background: #f8fafc !important;
        }
        div[class*="st-key-go_block_acciones"] input,
        div[class*="st-key-go_block_acciones"] textarea,
        div[class*="st-key-go_block_acciones"] [data-baseweb="select"],
        div[class*="st-key-go_block_acciones"] [data-baseweb="select"] > div {
            background: #f8fafc !important;
        }
        div[class*="st-key-go_block_acciones"] textarea {
            min-height: 72px !important;
            max-height: 96px !important;
        }
        div[class*="st-key-go_block_estado"] button,
        div[class*="st-key-go_block_tareas"] button,
        div[class*="st-key-go_block_acciones"] [data-testid="stFormSubmitButton"] button {
            min-height: 36px !important;
            height: 36px !important;
            font-size: 13px !important;
            box-shadow: none !important;
        }
        div[class*="st-key-go_block_estado"] button[kind="primary"],
        div[class*="st-key-go_block_tareas"] button[kind="primary"],
        div[class*="st-key-go_block_acciones"] [data-testid="stFormSubmitButton"] button {
            background: #006b68 !important;
            border-color: #006b68 !important;
            color: #ffffff !important;
        }
        .go-block-title {
            color: #0f2742;
            font-size: 15px;
            font-weight: 850;
            margin: 0 0 4px;
        }
        .go-block-caption {
            color: #64748b;
            font-size: 12px;
            font-weight: 650;
            margin: 0 0 8px;
        }
        .go-summary-title {
            color: #0f2742;
            font-size: 16px;
            font-weight: 850;
            margin-bottom: 8px;
        }
        .go-summary-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 8px;
        }
        .go-summary-field {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 8px 10px;
            min-height: 56px;
        }
        .go-summary-label {
            color: #64748b;
            font-size: 10px;
            font-weight: 850;
            letter-spacing: 0.02em;
            text-transform: uppercase;
            margin-bottom: 5px;
        }
        .go-summary-value {
            color: #0f2742;
            font-size: 13px;
            font-weight: 750;
            overflow-wrap: anywhere;
        }
        .go-action-card {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 9px 10px;
            margin-bottom: 8px;
        }
        .go-action-title {
            color: #0f2742;
            font-size: 13px;
            font-weight: 850;
        }
        .go-action-text {
            color: #64748b;
            font-size: 12px;
            font-weight: 650;
            margin-top: 2px;
        }
        div[class*="st-key-go_notas_panel"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 255, 255, 0.94) !important;
            border-color: #eadfc8 !important;
            border-radius: 12px !important;
            padding: 10px 11px !important;
            box-shadow: 0 1px 6px rgba(120, 89, 35, 0.04) !important;
        }
        div[class*="st-key-go_notas_panel"] [data-testid="stVerticalBlock"] {
            gap: 0.34rem !important;
        }
        div[class*="st-key-go_notas_panel"] button {
            min-height: 30px !important;
            height: 30px !important;
            padding: 3px 8px !important;
            font-size: 12px !important;
            box-shadow: none !important;
        }
        div[class*="st-key-go_notas_panel"] button[kind="primary"] {
            background: #ffffff !important;
            border-color: #0f766e !important;
            color: #0f766e !important;
        }
        .go-notes-title {
            color: #0f2742;
            font-size: 15px;
            font-weight: 850;
            margin: 0 0 2px;
        }
        .go-note-card {
            background: #fff8e8;
            border: 1px solid #f1dfb8;
            border-left: 4px solid #d6a647;
            border-radius: 11px;
            padding: 9px 10px;
            margin-bottom: 8px;
        }
        .go-note-meta {
            color: #7c6a46;
            font-size: 11px;
            font-weight: 750;
            margin-bottom: 5px;
        }
        .go-note-text {
            color: #1f2937;
            font-size: 13px;
            font-weight: 650;
            line-height: 1.32;
            margin-bottom: 8px;
            overflow-wrap: anywhere;
        }
        .go-note-empty {
            background: #fff8e8;
            border: 1px dashed #ead7ac;
            border-radius: 10px;
            color: #7c6a46;
            font-size: 12px;
            font-weight: 700;
            padding: 9px 10px;
        }
        @media (max-width: 900px) {
            .go-summary-grid { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    try:
        obras = listar_obras_con_demanda()
    except Exception as e:
        show_error(e)
        return
    if not obras:
        st.info("No hay obras cargadas.")
        return

    if "go_filtros" not in st.session_state:
        st.session_state["go_filtros"] = {"q": "", "estado": "Todos"}

    estados_opts = ["Todos"] + sorted({clean(o.get("estado_obra")) for o in obras if clean(o.get("estado_obra"))})

    with st.container(border=True, key="go_filtros_panel"):
        qn_actual = normalizar(st.session_state["go_filtros"]["q"])
        opciones_filtradas = []
        for o in obras:
            if st.session_state["go_filtros"]["estado"] != "Todos" and clean(o.get("estado_obra")) != st.session_state["go_filtros"]["estado"]:
                continue
            if qn_actual and not any(qn_actual in normalizar(o.get(c)) for c in ["id_obra", "id_demanda", "expediente", "apellido", "nombre", "dni", "barrio", "domicilio"]):
                continue
            opciones_filtradas.append(o)
        opciones = {
            f"Obra {txt(o.get('id_obra'))} | {clean(o.get('apellido'))}, {clean(o.get('nombre'))} | Expte {txt(o.get('expediente')) or '-'}": o
            for o in opciones_filtradas
        }

        sel_col, search_col = st.columns([2.0, 3.0])
        with sel_col:
            sel = st.selectbox("Obra seleccionada", list(opciones.keys()), key="go_sel") if opciones else None
        with search_col:
            with st.form("go_filtros_form"):
                f1, f2, f3 = st.columns([2.2, 1.1, 0.72])
                with f1:
                    q_in = st.text_input(
                        "Buscar obra",
                        value=st.session_state["go_filtros"]["q"],
                        placeholder="apellido, DNI, expediente, barrio...",
                    )
                with f2:
                    est_idx = estados_opts.index(st.session_state["go_filtros"]["estado"]) if st.session_state["go_filtros"]["estado"] in estados_opts else 0
                    estado_in = st.selectbox("Estado", estados_opts, index=est_idx)
                with f3:
                    st.markdown("<div style='height: 21px;'></div>", unsafe_allow_html=True)
                    aplicar = st.form_submit_button("Buscar", type="primary", use_container_width=True)

        if aplicar:
            st.session_state["go_filtros"] = {"q": q_in, "estado": estado_in}
            st.rerun()

        if not opciones:
            st.warning("No hay obras que coincidan con los filtros.")
            return
        obra = opciones[sel]

    def dato_obra(valor):
        valor = clean(valor)
        return valor if valor and valor.lower() not in {"nan", "none", "null", "- - -"} else "Sin dato"

    beneficiario_obra = dato_obra(f"{clean(obra.get('apellido'))}, {clean(obra.get('nombre'))}")
    ultima_actualizacion = fecha_corta(obra.get("ultima_actualizacion_semanal"))
    if ultima_actualizacion == "-":
        ultima_actualizacion = "Sin actualizacion"
    operational_card(
        title=f"Obra #{dato_obra(obra.get('id_obra'))} | Demanda #{dato_obra(obra.get('id_demanda'))}",
        subtitle=f"{beneficiario_obra} - Expte. {dato_obra(obra.get('expediente'))}",
        status=dato_obra(obra.get("estado_obra")),
        priority=dato_obra(obra.get("prioridad")),
        meta=[
            f"Domicilio: {dato_obra(obra.get('domicilio'))} - {dato_obra(obra.get('barrio'))}",
            f"Contacto: {dato_obra(obra.get('contacto'))}",
            f"Responsable: {dato_obra(obra.get('responsable_tecnico'))}",
            f"Inicio: {fecha_corta(obra.get('fecha_inicio'))}",
            f"Ultima actualizacion: {ultima_actualizacion}",
        ],
        description=None,
        footer=None,
        variant=variant_obra(obra.get("estado_obra")),
        accent_color=color_obra_estado(obra.get("estado_obra")),
        selected=True,
        card_key=f"go_obra_sel_{obra.get('id_obra')}",
        key=f"go_obra_sel_card_{obra.get('id_obra')}",
    )

    col_main, col_notas = st.columns([7, 3])

    with col_main:
        with st.container(border=True, key=f"go_block_estado_{obra.get('id_obra')}"):
            st.markdown('<div class="go-block-title">A. Parte de obra / Avance semanal</div>', unsafe_allow_html=True)
            st.markdown('<div class="go-block-caption">Actualiza el estado operativo y registra observaciones de avance o relevamiento.</div>', unsafe_allow_html=True)
            estado_actual = txt(obra.get("estado_obra"))
            estado_idx = ESTADOS_GESTION_OBRA.index(estado_actual) if estado_actual in ESTADOS_GESTION_OBRA else 0
            c1, _ = st.columns([0.5, 0.5])
            with c1:
                nuevo_estado = st.selectbox("Cambiar estado a", ESTADOS_GESTION_OBRA, index=estado_idx, key=f"go_new_estado_{obra.get('id_obra')}")
            obs_estado = st.text_area("Resumen del avance / relevamiento", height=90, key=f"go_obs_estado_{obra.get('id_obra')}")
            _, bcol = st.columns([1, 0.32])
            with bcol:
                guardar_avance = st.button("Guardar avance", key=f"go_btn_estado_{obra.get('id_obra')}", type="primary", use_container_width=True)
            if guardar_avance:
                payload = {"estado_obra": nuevo_estado, "historial_mensaje": f"Cambio de estado desde Gestion de Obras: {txt(obra.get('estado_obra'))} -> {nuevo_estado}"}
                try:
                    actualizar_obra_servicio(obra.get("id_obra"), payload)
                    if agregar_obs_obras_del_dia:
                        msg = f"Se modifico estado de obra: {txt(obra.get('estado_obra'))} -> {nuevo_estado}"
                        if clean(obs_estado):
                            msg = f"{msg}; {clean(obs_estado)}"
                        agregar_obs_obras_del_dia(obra.get("id_obra"), msg)
                except Exception as e:
                    show_error(e)
                else:
                    st.success("Estado actualizado.")
                    st.rerun()

        with st.container(border=True, key=f"go_block_tareas_{obra.get('id_obra')}"):
            st.markdown('<div class="go-block-title">B. Tareas de la obra</div>', unsafe_allow_html=True)
            st.markdown('<div class="go-block-caption">Revisa tareas vinculadas y marca las que fueron ejecutadas.</div>', unsafe_allow_html=True)
            try:
                tareas = listar_tareas_por_obra(obra.get("id_obra"))
            except Exception as e:
                show_error(e)
                tareas = []
            if not tareas:
                st.info("Esta obra no tiene tareas vinculadas.")
            else:
                rows_tareas = [
                    {
                        "id": t.get("id_tarea"),
                        "item_id": clean(t.get("descripcion_tarea")),
                        "item_label": clean(t.get("descripcion_tarea")),
                        "unit": clean(t.get("unidad_tarea")),
                        "quantity": t.get("cant_tarea") or "",
                        "status": bool(t.get("estado_tarea")),
                    }
                    for t in tareas
                ]
                out = operational_list_editor(
                    title="Tareas de la obra",
                    rows=rows_tareas,
                    catalog=[],
                    help_text="Marca las tareas ejecutadas. Tarea, unidad y cantidad se cargan desde Edicion maestra.",
                    save_label="Guardar tareas",
                    item_label="Tarea",
                    mode="progress",
                    status_label="Ejecutada",
                    show_unit=True,
                    embedded=True,
                    key=f"go_tareas_{obra.get('id_obra')}",
                )
                if out and out.get("action") == "save":
                    cambios_txt = []
                    mapa = {t.get("id_tarea"): t for t in tareas}
                    try:
                        for row in out.get("rows") or []:
                            tid = int(row.get("id"))
                            previo = bool(mapa[tid].get("estado_tarea"))
                            nuevo = bool(row.get("status"))
                            if previo != nuevo:
                                actualizar_tarea_cantidad_estado(tid, mapa[tid].get("cant_tarea"), nuevo)
                                cambios_txt.append(
                                    f"Se modifico tarea: {clean(mapa[tid].get('descripcion_tarea'))}, estado {'Ejecutada' if previo else 'Pendiente'} -> {'Ejecutada' if nuevo else 'Pendiente'}"
                                )
                        if cambios_txt and agregar_obs_obras_del_dia:
                            for c in cambios_txt:
                                agregar_obs_obras_del_dia(obra.get("id_obra"), c)
                    except Exception as e:
                        show_error(e)
                    else:
                        st.success("Tareas actualizadas.")
                        st.rerun()

        with st.container(border=True, key=f"go_block_acciones_{obra.get('id_obra')}"):
            st.markdown('<div class="go-block-title">C. Acciones derivadas</div>', unsafe_allow_html=True)
            st.markdown('<div class="go-block-caption">Genera pedidos o nuevas solicitudes relacionadas con esta obra.</div>', unsafe_allow_html=True)
            accion_key = f"go_accion_derivada_{obra.get('id_obra')}"
            accion_activa = st.session_state.get(accion_key)

            if not accion_activa:
                a1, a2 = st.columns(2)
                with a1:
                    ck_orden = f"go_card_orden_{obra.get('id_obra')}"
                    res_orden = operational_card(
                        title="Generar orden de materiales",
                        subtitle="Solicita materiales necesarios para la obra.",
                        status="Orden",
                        priority=None,
                        meta=["Depósito", "Materiales"],
                        description=None,
                        footer="Click para abrir formulario",
                        variant="highlight",
                        accent_color="#006b68",
                        clickable=True,
                        card_key=ck_orden,
                        key=f"{ck_orden}_card",
                    )
                    if card_event_once(res_orden, ck_orden, "card_click"):
                        st.session_state[accion_key] = "orden"
                        st.rerun()
                with a2:
                    ck_demanda = f"go_card_demanda_{obra.get('id_obra')}"
                    res_demanda = operational_card(
                        title="Generar demanda vinculada",
                        subtitle="Registra una nueva demanda relacionada.",
                        status="Demanda",
                        priority=None,
                        meta=["Vinculada", "Seguimiento"],
                        description=None,
                        footer="Click para abrir formulario",
                        variant="default",
                        accent_color="#0F766E",
                        clickable=True,
                        card_key=ck_demanda,
                        key=f"{ck_demanda}_card",
                    )
                    if card_event_once(res_demanda, ck_demanda, "card_click"):
                        st.session_state[accion_key] = "demanda"
                        st.rerun()

            if accion_activa == "orden":
                if st.button("Volver a acciones", key=f"go_cancel_accion_orden_{obra.get('id_obra')}"):
                    st.session_state.pop(accion_key, None)
                    st.rerun()
                orden_materiales_key = f"go_orden_materiales_{obra.get('id_obra')}"
                if orden_materiales_key not in st.session_state:
                    st.session_state[orden_materiales_key] = []
                orden_cols = st.columns([1, 1])
                with orden_cols[0]:
                    tipo = st.selectbox("Tipo de orden", ["Pendiente de retiro", "Pendiente de entrega"], key=f"go_tipo_orden_{obra.get('id_obra')}")
                    autoriza = st.text_input("Quien autoriza (opcional)", key=f"go_autoriza_orden_{obra.get('id_obra')}")
                with orden_cols[1]:
                    instrucciones = st.text_area(
                        "Instrucciones",
                        value=f"Orden creada desde Gestion de obra desde obra {obra.get('id_obra')}.",
                        height=92,
                        key=f"go_instr_orden_{obra.get('id_obra')}",
                    )
                resultado_materiales = operational_list_editor(
                    title="Materiales de la orden",
                    rows=st.session_state[orden_materiales_key],
                    catalog=catalogo_materiales_operativo(),
                    help_text="Seleccione materiales del catalogo y cargue la cantidad solicitada.",
                    add_label="Agregar material",
                    save_label="Generar orden",
                    item_label="Material",
                    mode="build",
                    show_unit=True,
                    allow_delete=True,
                    embedded=True,
                    key=f"go_mat_orden_{obra.get('id_obra')}",
                )
                if isinstance(resultado_materiales, dict) and resultado_materiales.get("action") == "save":
                    filas_editor = resultado_materiales.get("rows") or []
                    st.session_state[orden_materiales_key] = filas_editor
                    estado_orden = "Pendiente de retiro" if tipo == "Pendiente de retiro" else "Pendiente de entrega"
                    try:
                        nueva = crear_orden_material(
                            {
                                "id_demanda": obra.get("id_demanda"),
                                "origen": clean(autoriza) or obra.get("origen") or "Gestion de Obras",
                                "estado": estado_orden,
                                "instrucciones_tarea": clean(instrucciones) or f"Orden creada desde Gestion de obra desde obra {obra.get('id_obra')}.",
                            }
                        )
                        filas = []
                        for r in filas_editor:
                            if r.get("deleted"):
                                continue
                            m = clean(r.get("item_label") or r.get("item_id") or r.get("Material"))
                            c = clean(r.get("quantity") or r.get("cantidad"))
                            if m:
                                filas.append({"Material": m, "cantidad": c})
                        if nueva and filas:
                            crear_materiales_orden(nueva.get("n_orden"), filas)
                        if agregar_obs_obras_del_dia:
                            agregar_obs_obras_del_dia(obra.get("id_obra"), f"Se genero orden {estado_orden} desde Gestion de Obras")
                    except Exception as e:
                        show_error(e)
                    else:
                        st.success("Orden generada.")
                        st.session_state.pop(orden_materiales_key, None)
                        st.session_state.pop(accion_key, None)
                        st.rerun()

            if accion_activa == "demanda":
                if st.button("Volver a acciones", key=f"go_cancel_accion_demanda_{obra.get('id_obra')}"):
                    st.session_state.pop(accion_key, None)
                    st.rerun()
                with st.form(f"go_form_demanda_{obra.get('id_obra')}"):
                    st.markdown('<div class="go-block-title">Nueva demanda</div>', unsafe_allow_html=True)
                    st.markdown('<div class="go-block-caption">Carga contextual desde Gestion de Obras.</div>', unsafe_allow_html=True)
                    pedido = st.text_area(
                        "Pedido",
                        height=90,
                        placeholder="Texto que llega por mensaje, llamada o resumen breve.",
                        key=f"go_dem_pedido_{obra.get('id_obra')}",
                    )
                    d1, d2, d3 = st.columns(3)
                    with d1:
                        accion = st.selectbox("Accion", ACCIONES_DEMANDA_GESTION, key=f"go_dem_accion_{obra.get('id_obra')}")
                    with d2:
                        origen = st.selectbox("Origen", ORIGENES_DEMANDA_GESTION, index=4, key=f"go_dem_origen_{obra.get('id_obra')}")
                    with d3:
                        responsable = st.selectbox("Responsable", [""] + RESPONSABLES_TECNICOS, key=f"go_dem_resp_{obra.get('id_obra')}")
                    b1, b2 = st.columns([1, 1])
                    with b1:
                        crear_d = st.form_submit_button("Guardar demanda", type="primary", use_container_width=True)
                    with b2:
                        cancelar_d = st.form_submit_button("Cancelar", use_container_width=True)
                if cancelar_d:
                    st.session_state.pop(accion_key, None)
                    st.rerun()
                if crear_d:
                    if not clean(pedido):
                        st.warning("Completa el pedido.")
                    else:
                        try:
                            nueva_demanda = crear_demanda(
                                {
                                    "fecha_ingreso": date.today().isoformat(),
                                    "origen": origen,
                                    "prioridad": "3 - Normal",
                                    "expte_numero": obra.get("expte_numero"),
                                    "expte_anio": obra.get("expte_anio"),
                                    "expediente": obra.get("expediente"),
                                    "apellido": obra.get("apellido"),
                                    "nombre": obra.get("nombre"),
                                    "dni": obra.get("dni"),
                                    "domicilio": obra.get("domicilio"),
                                    "barrio": obra.get("barrio"),
                                    "contacto": obra.get("contacto"),
                                    "accion": accion,
                                    "estado": "Ingresada",
                                    "responsable": responsable,
                                    "observaciones": f"Demanda creada desde Gestion de Obras vinculada a obra {obra.get('id_obra')}. Pedido: {clean(pedido)}",
                                }
                            )
                            if agregar_obs_obras_del_dia:
                                agregar_obs_obras_del_dia(obra.get("id_obra"), f"Se genero demanda vinculada #{nueva_demanda.get('id_demanda') if nueva_demanda else '-'} desde Gestion de Obras")
                        except Exception as e:
                            show_error(e)
                        else:
                            st.success("Demanda generada.")
                            st.session_state.pop(accion_key, None)
                            st.rerun()

    with col_notas:
        with st.container(border=True, key=f"go_notas_panel_{obra.get('id_obra')}"):
            st.markdown('<div class="go-notes-title">Notas rápidas</div>', unsafe_allow_html=True)
            st.caption("Recordatorios pendientes de revisión.")
            try:
                notas = listar_notas_rapidas(estado="Pendiente", id_obra=obra.get("id_obra"))
            except Exception as e:
                show_error(e)
                notas = []
            if not notas:
                st.markdown('<div class="go-note-empty">Sin notas rápidas pendientes.</div>', unsafe_allow_html=True)
            for n in notas:
                nota_fecha = escape(fecha_corta(n.get("fecha_nota")))
                nota_autor = escape(txt(n.get("responsable_tecnico")) or "-")
                nota_texto = escape(txt(n.get("nota")))
                st.markdown(
                    f"""
                    <div class="go-note-card">
                        <div class="go-note-meta">{nota_fecha} · {nota_autor}</div>
                        <div class="go-note-text">{nota_texto}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                a1, a2 = st.columns(2)
                if a1.button("Aplicar", key=f"nota_ap_{n.get('id_nota')}", help="Aplicar", type="primary"):
                    st.session_state["nota_aplicar_id"] = n.get("id_nota")
                if a2.button("Descartar", key=f"nota_desc_{n.get('id_nota')}", help="Descartar"):
                    try:
                        actualizar_nota_rapida(n.get("id_nota"), {"estado_nota": "Descartada", "observacion_revision": "Descartada desde Gestion de Obras"})
                    except Exception as e:
                        show_error(e)
                    else:
                        st.success("Nota descartada.")
                        st.rerun()
        nota_aplicar_id = st.session_state.get("nota_aplicar_id")
        if nota_aplicar_id:
            nota_sel = next((x for x in notas if x.get("id_nota") == nota_aplicar_id), None)
            if nota_sel:
                st.divider()
                st.caption("Aplicar nota")
                accion_nota = st.selectbox(
                    "Convertir en",
                    ["Observacion de obra", "Cambio de estado", "Actualizar tarea", "Generar orden", "Generar demanda"],
                    key="go_accion_nota",
                )
                if st.button("Confirmar aplicacion", key="go_btn_apply_nota", type="primary"):
                    try:
                        if accion_nota == "Observacion de obra" and agregar_obs_obras_del_dia:
                            agregar_obs_obras_del_dia(obra.get("id_obra"), clean(nota_sel.get("nota")))
                        actualizar_nota_rapida(
                            nota_sel.get("id_nota"),
                            {
                                "estado_nota": "Aplicada",
                                "revisada_por": "Gestion de Obras",
                                "revisada_at": datetime.now().isoformat(),
                                "observacion_revision": f"Aplicada como: {accion_nota}",
                            },
                        )
                    except Exception as e:
                        show_error(e)
                    else:
                        st.success("Nota aplicada.")
                        st.session_state.pop("nota_aplicar_id", None)
                        st.rerun()

require_login(["admin", "tecnico"])
st.title("Obras")
t1, t2 = st.tabs(["Tablero / Edicion maestra", "Gestion de Obras"])
with t1:
    obras_v2_tab()
with t2:
    seguimiento_tecnico_tab()
