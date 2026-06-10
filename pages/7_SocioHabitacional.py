from datetime import date

import streamlit as st

from utils.auth import require_login
from utils.visit_followup_card_component import visit_followup_card
from services.sociohabitacional_service import (
    actualizar_estado_demanda_social,
    contar_indicadores_visitas,
    estado_sugerido_por_tipo,
    filtrar_socio_habitacional,
    listar_demandas_sociohabitacionales,
    listar_visitas_detalladas,
    obtener_estados_por_accion,
    registrar_informes_hitos,
    registrar_programacion_individual,
    registrar_visita_campo,
    validar_demanda_sociohabitacional,
)


def txt(v):
    return "" if v is None else str(v)


def clean(v):
    return txt(v).strip()


def fecha_corta(v):
    v = clean(v)
    if not v:
        return "-"
    p = v[:10].split("-")
    return f"{p[2]}/{p[1]}/{p[0][2:]}" if len(p) == 3 else v


def estado_programacion_visita(estado):
    estado = clean(estado)
    return "Programada" if estado in ["Programada", "Visitada", "Informe"] else "Sin programar"


def estado_visita_campo(estado):
    estado = clean(estado)
    return "Visitada" if estado in ["Visitada", "Informe"] else "Sin visita"


def estado_informe_visita(estado, marcado=False, tipo=""):
    estado = clean(estado)
    if estado == "Informe" or marcado:
        return f"Informe {tipo}".strip()
    return "Sin informe"


def render_card_socio(demanda, es_pendiente=False):
    n_id = demanda.get("id_demanda")
    titular = f"{clean(demanda.get('apellido'))}, {clean(demanda.get('nombre'))}"
    expte = clean(demanda.get("expediente")) or "Sin Expte."

    with st.container(border=True):
        st.markdown(f"**{titular} - Expte. {expte}**")
        st.caption(
            f"Ingreso: {fecha_corta(demanda.get('fecha_ingreso'))} | "
            f"Tipo: {clean(demanda.get('accion'))} | Prioridad: {clean(demanda.get('prioridad'))}"
        )
        obs = clean(demanda.get("observaciones"))
        resumen = obs.split("||")[0] if "||" in obs else obs
        st.write(resumen[:150] + ("..." if len(resumen) > 150 else ""))

        if es_pendiente:
            clave_chk = f"val_chk_{n_id}"
            validar = st.checkbox("Validar demanda", key=clave_chk)

            if validar:
                st.divider()
                st.markdown("##### Validacion de demanda")
                estado_sug, accion_sug = estado_sugerido_por_tipo(demanda.get("accion"))
                with st.form(key=f"form_val_{n_id}"):
                    st.info(f"Estado sugerido: **{estado_sug}**")
                    obs_accion = st.text_input("Observacion / accion a realizar", value=accion_sug)
                    c1, c2 = st.columns(2)
                    btn_confirmar = c1.form_submit_button("Validar demanda", type="primary", use_container_width=True)
                    btn_cancelar = c2.form_submit_button("Cancelar", use_container_width=True)

                if btn_confirmar:
                    try:
                        res = validar_demanda_sociohabitacional(demanda, estado_sug, clean(obs_accion))
                        if res.get("visita"):
                            v_res = res["visita"]
                            if v_res.get("status") == "success":
                                st.success(f"Validada: {v_res.get('message')}")
                            elif v_res.get("status") == "warning":
                                st.warning(f"Validada: {v_res.get('message')}")
                        else:
                            st.success(f"Demanda #{n_id} validada correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al validar: {e}")

                if btn_cancelar:
                    st.rerun()


def tab_seguimiento_visitas():
    try:
        visitas_all = listar_visitas_detalladas()
    except Exception as e:
        st.error(f"Error al cargar visitas: {e}")
        return

    c_para, c_prog, c_inf, c_comp = contar_indicadores_visitas(visitas_all)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Para visita", c_para)
    k2.metric("Programados", c_prog)
    k3.metric("Informes pendientes", c_inf)
    k4.metric("Completados", c_comp)

    st.divider()
    busqueda = st.text_input("Filtro por nombre / expediente", placeholder="Ej: Perez o 1234").strip().lower()
    visitas = visitas_all
    if busqueda:
        visitas = [
            v
            for v in visitas_all
            if busqueda in clean(v.get("d_apellido")).lower()
            or busqueda in clean(v.get("d_nombre")).lower()
            or busqueda in clean(v.get("d_expediente")).lower()
        ]

    t_visitas, t_varios = st.tabs(["Seguimiento de visitas", "Seguimiento varios"])

    with t_visitas:
        col_izq, col_der = st.columns([0.75, 0.25])
        with col_izq:
            st.markdown("#### Seguimiento general")
            visitas_seleccionadas_key = "socio_visitas_programar_ids"
            st.session_state.setdefault(visitas_seleccionadas_key, [])
            selected_ids = {str(v_id) for v_id in st.session_state.get(visitas_seleccionadas_key, [])}

            with st.container(border=True):
                c_fecha, c_btn = st.columns([0.55, 0.45], vertical_alignment="bottom")
                with c_fecha:
                    fecha_programacion = st.date_input("Fecha para programar visitas seleccionadas", value=date.today(), key="socio_fecha_programacion_masiva")
                with c_btn:
                    programar_seleccionadas = st.button(
                        f"Programar seleccionadas ({len(selected_ids)})",
                        type="primary",
                        use_container_width=True,
                        disabled=not selected_ids,
                        key="socio_btn_programar_masivo",
                    )

            if programar_seleccionadas:
                try:
                    for id_visit in selected_ids:
                        registrar_programacion_individual(int(id_visit), fecha_programacion, "")
                    st.session_state[visitas_seleccionadas_key] = []
                    st.toast(f"Se programaron {len(selected_ids)} visita/s.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al programar visitas: {e}")

            for v in visitas:
                vid = v["id_visit"]
                vid_str = str(vid)
                v_soc_actual = clean(v.get("est_soc"))
                v_tec_actual = clean(v.get("est_tec"))
                st.session_state.setdefault(f"chk_inf_{vid}_s", v_soc_actual == "Informe")
                st.session_state.setdefault(f"chk_inf_{vid}_t", v_tec_actual == "Informe")

                resultado_card = visit_followup_card(
                    title=f"{clean(v.get('d_apellido')).upper()}, {clean(v.get('d_nombre'))}",
                    subtitle=f"Expte. {clean(v.get('d_expediente')) or 'S/E'}",
                    address=f"{clean(v.get('d_domicilio'))} - {clean(v.get('d_barrio'))}".strip(" -"),
                    contact=clean(v.get("d_contacto")),
                    priority=clean(v.get("d_prioridad")),
                    scheduled_date=fecha_corta(v.get("fec_program")),
                    rows=[
                        {
                            "label": "Social",
                            "program_status": estado_programacion_visita(v_soc_actual),
                            "visit_status": estado_visita_campo(v_soc_actual),
                            "report_status": estado_informe_visita(v_soc_actual, st.session_state.get(f"chk_inf_{vid}_s"), "Social"),
                            "report_checked": st.session_state.get(f"chk_inf_{vid}_s"),
                            "report_enabled": True,
                            "target": "s",
                        },
                        {
                            "label": "Tecnico",
                            "program_status": estado_programacion_visita(v_tec_actual),
                            "visit_status": estado_visita_campo(v_tec_actual),
                            "report_status": estado_informe_visita(v_tec_actual, st.session_state.get(f"chk_inf_{vid}_t"), "Tecnico"),
                            "report_checked": st.session_state.get(f"chk_inf_{vid}_t"),
                            "report_enabled": True,
                            "target": "t",
                        },
                    ],
                    selectable=True,
                    selected=vid_str in selected_ids,
                    card_key=f"visit_{vid}",
                    key=f"visit_card_{vid}",
                )

                if isinstance(resultado_card, dict):
                    event_id = resultado_card.get("event_id")
                    last_event_key = f"visit_card_last_event_{vid}"
                    if event_id and st.session_state.get(last_event_key) == event_id:
                        resultado_card = None
                    elif event_id:
                        st.session_state[last_event_key] = event_id

                if isinstance(resultado_card, dict):
                    accion = resultado_card.get("action")
                    target = resultado_card.get("target")
                    if accion == "toggle_select":
                        if vid_str in selected_ids:
                            selected_ids.remove(vid_str)
                        else:
                            selected_ids.add(vid_str)
                        st.session_state[visitas_seleccionadas_key] = sorted(selected_ids)
                        st.rerun()
                    if accion == "toggle_report" and target in {"s", "t"}:
                        key_chk = f"chk_inf_{vid}_{target}"
                        st.session_state[key_chk] = not bool(st.session_state.get(key_chk))
                        st.rerun()
                    if accion == "validate_reports":
                        chk_s = st.session_state.get(f"chk_inf_{vid}_s")
                        chk_t = st.session_state.get(f"chk_inf_{vid}_t")
                        err_s = chk_s and v_soc_actual not in ["Visitada", "Informe"]
                        err_t = chk_t and v_tec_actual not in ["Visitada", "Informe"]
                        if err_s or err_t:
                            st.error("No se puede marcar informe sin visita realizada.")
                        else:
                            registrar_informes_hitos(vid, chk_s, chk_t)
                            st.rerun()

        with col_der:
            st.markdown("#### Visitas programadas")
            prog_list = [v for v in visitas if clean(v.get("est_soc")) == "Programada" or clean(v.get("est_tec")) == "Programada"]
            prog_list.sort(key=lambda x: clean(x.get("fec_program")))
            if not prog_list:
                st.caption("No hay visitas pendientes de realizacion.")
            else:
                current_date = None
                for v in prog_list:
                    f_v = clean(v.get("fec_program"))
                    if f_v != current_date:
                        st.markdown(f"**{fecha_corta(f_v)}**" if f_v else "**Sin fecha asignada**")
                        current_date = f_v
                    vid = v["id_visit"]
                    with st.container(border=True):
                        st.markdown(f"**{clean(v.get('d_apellido'))}**")
                        st.caption(f"Exp. {clean(v.get('d_expediente'))}")
                        s_v_done = clean(v.get("est_soc")) in ["Visitada", "Informe"]
                        t_v_done = clean(v.get("est_tec")) in ["Visitada", "Informe"]
                        chk_s = st.toggle("Visita Social OK", value=s_v_done, disabled=s_v_done, key=f"v_s_ok_{vid}")
                        chk_t = st.toggle("Visita Tecnica OK", value=t_v_done, disabled=t_v_done, key=f"v_t_ok_{vid}")
                        if st.button("Validar visita", key=f"btn_v_campo_{vid}", type="primary", use_container_width=True):
                            registrar_visita_campo(vid, chk_s, chk_t)
                            st.rerun()

    with t_varios:
        try:
            todas_soc = listar_demandas_sociohabitacionales()
            registradas = filtrar_socio_habitacional(todas_soc, bloque="registradas")
            varios = [d for d in registradas if clean(d.get("accion")) != "Visitar" and clean(d.get("estado")) not in ["Entregado", "Cerrado"]]
        except Exception as e:
            st.error(f"Error al cargar seguimientos varios: {e}")
            varios = []

        if varios and busqueda:
            varios = [d for d in varios if busqueda in clean(d.get("apellido")).lower() or busqueda in clean(d.get("nombre")).lower()]

        if not varios:
            st.info("No hay gestiones varias registradas para mostrar.")
        else:
            cols_v = st.columns(2)
            for i, d in enumerate(varios):
                with cols_v[i % 2]:
                    with st.container(border=True):
                        titular = f"{clean(d.get('apellido'))}, {clean(d.get('nombre'))}"
                        st.markdown(f"**{titular} - Expte. {clean(d.get('expediente')) or 'S/E'}**")
                        st.caption(f"{clean(d.get('domicilio'))} - {clean(d.get('contacto'))}")
                        st.caption(f"Estado: {clean(d.get('estado'))}")
                        st.caption(f"Tipo: {clean(d.get('accion'))} | Prioridad: {clean(d.get('prioridad'))}")
                        obs = clean(d.get("observaciones"))
                        resumen = obs.split("||")[0] if "||" in obs else obs
                        st.write(resumen[:140] + "..." if len(resumen) > 140 else resumen)
                        estados_posibles = obtener_estados_por_accion(d.get("accion"))
                        est_actual = clean(d.get("estado"))
                        idx_init = estados_posibles.index(est_actual) if est_actual in estados_posibles else 0
                        with st.form(key=f"form_est_var_{d.get('id_demanda')}"):
                            nuevo_est = st.selectbox("Cambiar estado", options=estados_posibles, index=idx_init)
                            if st.form_submit_button("Confirmar cambio", use_container_width=True):
                                try:
                                    actualizar_estado_demanda_social(d.get("id_demanda"), nuevo_est)
                                    st.success("Estado actualizado.")
                                    st.rerun()
                                except Exception as err:
                                    st.error(f"Error al actualizar: {err}")


def render_tablero_principal():
    try:
        todas = listar_demandas_sociohabitacionales()
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return

    st.subheader("Demandas registradas")
    registradas = filtrar_socio_habitacional(todas, bloque="registradas")
    if not registradas:
        st.info("No hay demandas registradas en proceso.")
    else:
        cols = st.columns(2)
        for i, d in enumerate(registradas):
            with cols[i % 2]:
                render_card_socio(d, es_pendiente=False)

    st.divider()
    st.subheader("Demandas pendientes")
    pendientes = filtrar_socio_habitacional(todas, bloque="pendientes")
    if not pendientes:
        st.success("Buen trabajo. No hay demandas pendientes de validacion.")
    else:
        for d in pendientes:
            render_card_socio(d, es_pendiente=True)


def main():
    require_login(["admin", "tecnico"])
    st.title("SocioHabitacional")
    st.markdown("Tablero operativo de demandas sociohabitacionales y seguimiento de informes.")
    t1, t2 = st.tabs(["Tablero Operativo", "Seguimiento Socio Habitacional"])
    with t1:
        render_tablero_principal()
    with t2:
        tab_seguimiento_visitas()


if __name__ == "__main__":
    main()
