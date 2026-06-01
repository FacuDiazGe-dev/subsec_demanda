from datetime import date, datetime
import unicodedata

import pandas as pd
import streamlit as st

from services import obras_service
from services.demandas_service import crear_demanda, listar_demandas_abiertas
from services.listado_tareas_service import listar_tareas_base
from services.materiales_orden_service import crear_materiales_orden
from services.notas_rapidas_obra_service import actualizar_nota_rapida, crear_nota_rapida, listar_notas_rapidas
from services.ordenes_service import crear_orden_material
from services.seguimiento_obra_service import crear_seguimiento
from services.tareas_obra_service import (
    actualizar_tarea_cantidad_estado,
    crear_tarea_obra,
    eliminar_tarea_obra,
    listar_tareas_por_obra,
)

actualizar_obra_servicio = obras_service.actualizar_obra
crear_obra = obras_service.crear_obra
listar_obras_con_demanda = obras_service.listar_obras_con_demanda
obtener_obra_con_demanda = obras_service.obtener_obra_con_demanda
actualizar_obs_obras = getattr(obras_service, "actualizar_obs_obras", None)
agregar_obs_obras_del_dia = getattr(obras_service, "agregar_obs_obras_del_dia", None)

TIPOS_OBRA_PROGRAMA = ["HAVITA", "MI BANO", "EMERGENCIA HABITACIONAL", "OTROS"]
MODALIDADES_EJECUCION = ["Cuadrilla HAVITA", "Mano de obra propia", "Mixta", "Cuadrilla municipal"]
ESTADOS_OBRA = ["Para firmar acta", "Acta firmada", "Para obra", "En ejecucion", "Suspendida", "Ejecutada", "Cancelada"]
ESTADOS_GESTION_OBRA = ["En Ejecucion", "Seguimiento", "Ejecutada", "Cerrada", "Suspendida"]
RESPONSABLES_TECNICOS = ["Facundo", "Pedro", "Bea", "Iris", "Guillo"]


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


def render_tareas_obra(obra):
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
    edit_mode = st.session_state[mk]

    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("Salir de edicion" if edit_mode else "Activar modo edicion", key=f"toggle_{obra.get('id_obra')}", use_container_width=True):
            st.session_state[mk] = not edit_mode
            st.rerun()
    with c2:
        st.caption("Visual: solo lectura. Edicion: editar tabla y agregar tareas.")

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
    elif not tareas:
        st.info("Esta obra no tiene tareas cargadas.")

    opts, mapa_unidad = tareas_base_opciones()
    if not opts:
        st.warning("No hay tareas en listado_tareas.")
        return

    if edit_mode and tareas:
        st.markdown("##### Edicion directa de tareas")
        df_edit = pd.DataFrame(
            [
                {
                    "id_tarea": t.get("id_tarea"),
                    "descripcion_tarea": txt(t.get("descripcion_tarea")),
                    "unidad_tarea": txt(t.get("unidad_tarea")),
                    "cant_tarea": txt(t.get("cant_tarea")),
                    "estado_tarea": bool(t.get("estado_tarea")),
                    "Eliminar": False,
                }
                for t in tareas
            ]
        )
        edited = st.data_editor(
            df_edit,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "id_tarea": st.column_config.NumberColumn(disabled=True),
                "descripcion_tarea": st.column_config.TextColumn(disabled=True),
                "unidad_tarea": st.column_config.TextColumn(disabled=True),
                "Eliminar": st.column_config.CheckboxColumn(),
                "estado_tarea": st.column_config.CheckboxColumn(),
            },
            key=f"editor_{obra.get('id_obra')}",
        )
        if st.button("Guardar cambios de tabla", key=f"save_tab_{obra.get('id_obra')}", type="primary"):
            mapa_actual = {t.get("id_tarea"): t for t in tareas}
            try:
                for _, r in edited.iterrows():
                    tid = int(r["id_tarea"])
                    act = mapa_actual.get(tid)
                    if not act:
                        continue
                    if bool(r.get("Eliminar")):
                        eliminar_tarea_obra(tid)
                        if agregar_obs_obras_del_dia:
                            agregar_obs_obras_del_dia(obra.get("id_obra"), f"Se elimino tarea: {clean(act.get('descripcion_tarea'))}")
                        continue
                    dn = clean(act.get("descripcion_tarea"))
                    cn = parse_cant(r.get("cant_tarea"))
                    if cn == "__INVALID__":
                        st.warning(f"cant_tarea invalida en #{tid}.")
                        return
                    ca = parse_cant(act.get("cant_tarea"))
                    en = bool(r.get("estado_tarea"))
                    ea = bool(act.get("estado_tarea"))
                    if cn != ca or en != ea:
                        actualizar_tarea_cantidad_estado(tid, cn, en)
                        if agregar_obs_obras_del_dia:
                            cambios = []
                            if cn != ca:
                                cambios.append(f"cantidad {ca if ca is not None else '-'} -> {cn if cn is not None else '-'}")
                            if en != ea:
                                cambios.append(
                                    f"estado {'Ejecutada' if ea else 'Sin ejecutar'} -> {'Ejecutada' if en else 'Sin ejecutar'}"
                                )
                            detalle = "; ".join(cambios) if cambios else "sin detalle"
                            agregar_obs_obras_del_dia(obra.get("id_obra"), f"Se modifico tarea: {dn}. {detalle}")
            except Exception as e:
                show_error(e)
                return
            st.success("Cambios guardados.")
            st.rerun()

    if not edit_mode:
        return

    st.markdown("##### Agregar nueva tarea")
    with st.form(f"add_t_{obra.get('id_obra')}"):
        sel = st.selectbox("Tarea", options=opts, index=None, placeholder="Selecciona tarea", accept_new_options=False, filter_mode="contains")
        desc = clean(sel.split(" | ")[0]) if sel else ""
        unidad = mapa_unidad.get(desc, "")
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("unidad_tarea", value=unidad, disabled=True)
        with c2:
            cant = st.text_input("cant_tarea")
        add = st.form_submit_button("Agregar tarea", type="primary")
    if add:
        if not desc:
            st.warning("Selecciona una tarea existente.")
            return
        cn = parse_cant(cant)
        if cn == "__INVALID__":
            st.warning("cant_tarea debe ser numerica.")
            return
        try:
            crear_tarea_obra(obra.get("id_obra"), desc, unidad or None, cn)
            if agregar_obs_obras_del_dia:
                agregar_obs_obras_del_dia(obra.get("id_obra"), f"Se agrego tarea: {desc}")
        except Exception as e:
            show_error(e)
            return
        st.success("Tarea agregada.")
        st.rerun()


def tablero_tab():
    st.subheader("Tablero de obras")
    obras = listar_obras_con_demanda()
    st.markdown("### Obras registradas")
    for o in obras:
        with st.container(border=True):
            st.markdown(f"**{clean(o.get('apellido'))}, {clean(o.get('nombre'))} — Expte. {txt(o.get('expediente')) or '-'}**")
            st.caption(f"Estado: {txt(o.get('estado_obra'))} | Modalidad: {txt(o.get('modalidad_ejecucion')) or '-'} | Responsable: {txt(o.get('responsable_tecnico')) or '-'}")
            st.caption((txt(o.get("descripcion_obra")) or "-")[:160])
    st.divider()
    st.markdown("### Demandas para generar obra")
    ids = {o.get("id_demanda") for o in obras if o.get("id_demanda") is not None}
    dms = [d for d in listar_demandas_abiertas() if clean(d.get("accion")).lower() in {"obra", "emergencia"} and d.get("id_demanda") not in ids]
    dms.sort(key=lambda d: (prioridad_rank(d.get("prioridad")), d.get("id_demanda") or 999999))
    if not dms:
        st.info("No hay demandas pendientes para crear obra.")
        return
    for d in dms:
        with st.container(border=True):
            st.markdown(f"**{txt(d.get('apellido'))}, {txt(d.get('nombre'))} — Expte. {txt(d.get('expediente')) or '-'}**")
            st.caption(f"Accion: {txt(d.get('accion'))} | Prioridad: {txt(d.get('prioridad')) or '-'}")
            col_chk, col_txt = st.columns([1.2, 2.8])
            clave_chk = f"tb_validar_{d.get('id_demanda')}"
            with col_chk:
                validar = st.checkbox("Validar pedido", key=clave_chk)
            with col_txt:
                st.caption("Activa para habilitar creacion de obra con datos por defecto.")

            if validar:
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
                    crear = st.form_submit_button("Validar y crear obra", type="primary", use_container_width=True)

                if crear:
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
    st.markdown(f"### Obra N° {oid}")
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


def seguimiento_tecnico_tab():
    st.subheader("Gestion de Obras")
    st.caption("Buscar, seleccionar y actualizar obras en ejecucion.")

    try:
        obras = listar_obras_con_demanda()
    except Exception as e:
        show_error(e)
        return
    if not obras:
        st.info("No hay obras cargadas.")
        return

    if "go_filtros" not in st.session_state:
        st.session_state["go_filtros"] = {"q": "", "estado": "Todos", "responsable": "Todos", "prioridad": "Todas"}

    estados_opts = ["Todos"] + sorted({clean(o.get("estado_obra")) for o in obras if clean(o.get("estado_obra"))})
    resp_opts = ["Todos"] + sorted({clean(o.get("responsable_tecnico")) for o in obras if clean(o.get("responsable_tecnico"))})
    prio_opts = ["Todas"] + sorted({clean(o.get("prioridad")) for o in obras if clean(o.get("prioridad"))})

    with st.container(border=True):
        with st.form("go_filtros_form"):
            c1, c2, c3, c4 = st.columns([3, 1.2, 1.2, 1.2])
            with c1:
                q_in = st.text_input(
                    "Buscar obra",
                    value=st.session_state["go_filtros"]["q"],
                    placeholder="apellido, nombre, DNI, expediente, barrio, domicilio, id_obra, id_demanda",
                )
            with c2:
                est_idx = estados_opts.index(st.session_state["go_filtros"]["estado"]) if st.session_state["go_filtros"]["estado"] in estados_opts else 0
                estado_in = st.selectbox("Estado", estados_opts, index=est_idx)
            with c3:
                resp_idx = resp_opts.index(st.session_state["go_filtros"]["responsable"]) if st.session_state["go_filtros"]["responsable"] in resp_opts else 0
                resp_in = st.selectbox("Responsable", resp_opts, index=resp_idx)
            with c4:
                prio_idx = prio_opts.index(st.session_state["go_filtros"]["prioridad"]) if st.session_state["go_filtros"]["prioridad"] in prio_opts else 0
                prio_in = st.selectbox("Prioridad", prio_opts, index=prio_idx)
            aplicar = st.form_submit_button("Aplicar filtros", type="primary", use_container_width=True)

        if aplicar:
            st.session_state["go_filtros"] = {"q": q_in, "estado": estado_in, "responsable": resp_in, "prioridad": prio_in}

        qn = normalizar(st.session_state["go_filtros"]["q"])
        filtradas = []
        for o in obras:
            if st.session_state["go_filtros"]["estado"] != "Todos" and clean(o.get("estado_obra")) != st.session_state["go_filtros"]["estado"]:
                continue
            if st.session_state["go_filtros"]["responsable"] != "Todos" and clean(o.get("responsable_tecnico")) != st.session_state["go_filtros"]["responsable"]:
                continue
            if st.session_state["go_filtros"]["prioridad"] != "Todas" and clean(o.get("prioridad")) != st.session_state["go_filtros"]["prioridad"]:
                continue
            if qn and not any(qn in normalizar(o.get(c)) for c in ["id_obra", "id_demanda", "expediente", "apellido", "nombre", "dni", "barrio", "domicilio"]):
                continue
            filtradas.append(o)

        opciones = {
            f"Obra {txt(o.get('id_obra'))} | {clean(o.get('apellido'))}, {clean(o.get('nombre'))} | Expte {txt(o.get('expediente')) or '-'}": o
            for o in filtradas
        }
        if not opciones:
            st.warning("No hay obras que coincidan con los filtros.")
            return
        sel = st.selectbox("Seleccionar obra", list(opciones.keys()), key="go_sel")
        obra = opciones[sel]

    with st.container(border=True):
        st.markdown(f"**Obra #{txt(obra.get('id_obra'))} | Demanda #{txt(obra.get('id_demanda'))}**")
        st.caption(
            f"Expte: {txt(obra.get('expediente')) or '-'} | Beneficiario: {clean(obra.get('apellido'))}, {clean(obra.get('nombre'))} | "
            f"Domicilio: {(txt(obra.get('domicilio')) or '-')} - {(txt(obra.get('barrio')) or '-')}"
        )
        st.caption(
            f"Contacto: {txt(obra.get('contacto')) or '-'} | Estado: {txt(obra.get('estado_obra')) or '-'} | Responsable: {txt(obra.get('responsable_tecnico')) or '-'} | "
            f"Prioridad: {txt(obra.get('prioridad')) or '-'} | Inicio: {fecha_corta(obra.get('fecha_inicio'))} | Ultima actualizacion: {fecha_corta(obra.get('ultima_actualizacion_semanal'))}"
        )

    col_main, col_notas = st.columns([3, 1])

    with col_main:
        with st.container(border=True):
            st.markdown("#### A. Actualizacion de estado de obra")
            c1, c2 = st.columns([1, 2])
            with c1:
                st.text_input("Estado actual", value=txt(obra.get("estado_obra")) or "-", disabled=True, key=f"go_estado_actual_{obra.get('id_obra')}")
                nuevo_estado = st.selectbox("Nuevo estado", ESTADOS_GESTION_OBRA, key=f"go_new_estado_{obra.get('id_obra')}")
            with c2:
                obs_estado = st.text_input("Observacion breve", key=f"go_obs_estado_{obra.get('id_obra')}")
            if st.button("Actualizar estado", key=f"go_btn_estado_{obra.get('id_obra')}", type="primary"):
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

        with st.expander("B. Observaciones de obra", expanded=False):
            obs_texto = st.text_area("Observacion", height=100, key=f"go_obs_{obra.get('id_obra')}")
            if st.button("Guardar observacion", key=f"go_btn_obs_{obra.get('id_obra')}"):
                if not clean(obs_texto):
                    st.warning("Escribe una observacion.")
                else:
                    try:
                        if agregar_obs_obras_del_dia:
                            agregar_obs_obras_del_dia(obra.get("id_obra"), clean(obs_texto))
                    except Exception as e:
                        show_error(e)
                    else:
                        st.success("Observacion guardada.")
                        st.rerun()

        with st.expander("C. Listado de tareas de la obra", expanded=False):
            try:
                tareas = listar_tareas_por_obra(obra.get("id_obra"))
            except Exception as e:
                show_error(e)
                tareas = []
            if not tareas:
                st.info("Esta obra no tiene tareas vinculadas.")
            else:
                edit = pd.DataFrame(
                    [{"id_tarea": t.get("id_tarea"), "descripcion_tarea": txt(t.get("descripcion_tarea")), "cant_tarea": txt(t.get("cant_tarea")), "Ejecutada": bool(t.get("estado_tarea"))} for t in tareas]
                )
                out = st.data_editor(
                    edit,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "id_tarea": st.column_config.NumberColumn(disabled=True),
                        "descripcion_tarea": st.column_config.TextColumn(disabled=True),
                        "cant_tarea": st.column_config.TextColumn(disabled=True),
                        "Ejecutada": st.column_config.CheckboxColumn(),
                    },
                    key=f"go_tareas_{obra.get('id_obra')}",
                )
                cta1, cta2 = st.columns(2)
                actualizar = cta1.button("Actualizar tareas", key=f"go_btn_tareas_upd_{obra.get('id_obra')}", type="primary", use_container_width=True)
                cancelar = cta2.button("Cancelar cambios", key=f"go_btn_tareas_cancel_{obra.get('id_obra')}", use_container_width=True)
                if cancelar:
                    st.rerun()
                if actualizar:
                    cambios_txt = []
                    mapa = {t.get("id_tarea"): t for t in tareas}
                    try:
                        for _, row in out.iterrows():
                            tid = int(row["id_tarea"])
                            previo = bool(mapa[tid].get("estado_tarea"))
                            nuevo = bool(row["Ejecutada"])
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

        with st.expander("D. Generar orden", expanded=False):
            with st.form(f"go_form_orden_{obra.get('id_obra')}"):
                tipo = st.selectbox("Tipo de orden", ["Pendiente de retiro", "Pendiente de entrega"])
                autoriza = st.text_input("Quien autoriza (opcional)")
                instrucciones = st.text_area(
                    "Instrucciones",
                    value=f"Orden creada desde Gestion de obra desde obra {obra.get('id_obra')}.",
                    height=80,
                )
                mats = st.data_editor(
                    pd.DataFrame([{"Material": "", "cantidad": ""}]),
                    num_rows="dynamic",
                    hide_index=True,
                    use_container_width=True,
                    key=f"go_mat_orden_{obra.get('id_obra')}",
                )
                crear_o = st.form_submit_button("Generar orden", type="primary")
            if crear_o:
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
                    for _, r in mats.iterrows():
                        m = clean(r.get("Material"))
                        c = clean(r.get("cantidad"))
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
                    st.rerun()

        with st.expander("E. Generar demanda vinculada", expanded=False):
            with st.form(f"go_form_demanda_{obra.get('id_obra')}"):
                pedido = st.text_area("Pedido", height=90)
                accion = st.selectbox("Accion", ["Obra", "Emergencia", "Entregar materiales", "Informe / Actuacion", "Consulta / Seguimiento"])
                prioridad = st.selectbox("Prioridad", ["1 - Urgente", "2 - Prioritario", "3 - Normal", "4 - Bajo", "5 - En espera"], index=2)
                responsable = st.selectbox("Responsable", RESPONSABLES_TECNICOS, index=0)
                crear_d = st.form_submit_button("Generar demanda", type="primary")
            if crear_d:
                if not clean(pedido):
                    st.warning("Completa el pedido.")
                else:
                    try:
                        nueva_demanda = crear_demanda(
                            {
                                "fecha_ingreso": date.today().isoformat(),
                                "origen": "Gestion de Obras",
                                "prioridad": prioridad,
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
                        st.rerun()

    with col_notas:
        st.markdown("#### Notas rapidas")
        try:
            notas = listar_notas_rapidas(estado="Pendiente", id_obra=obra.get("id_obra"))
        except Exception as e:
            show_error(e)
            notas = []
        if not notas:
            st.caption("Sin notas pendientes.")
        for n in notas:
            with st.container(border=True):
                st.caption(f"{fecha_corta(n.get('fecha_nota'))} | {txt(n.get('responsable_tecnico')) or '-'}")
                st.write(txt(n.get("nota")))
                a1, a2 = st.columns(2)
                if a1.button("✓", key=f"nota_ap_{n.get('id_nota')}", help="Aplicar"):
                    st.session_state["nota_aplicar_id"] = n.get("id_nota")
                if a2.button("✕", key=f"nota_desc_{n.get('id_nota')}", help="Descartar"):
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


st.set_page_config(page_title="Obras", layout="wide")
st.title("Obras")
t1, t2, t3 = st.tabs(["Tablero", "Editar obra", "Gestion de Obras"])
with t1:
    tablero_tab()
with t2:
    editar_obra_tab()
with t3:
    seguimiento_tecnico_tab()
