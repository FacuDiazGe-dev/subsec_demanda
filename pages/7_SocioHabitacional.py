from datetime import date

import streamlit as st

from utils.auth import require_login
from utils.operational_card_component import operational_card
from utils.operational_kpi_component import operational_kpis
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


def sin_dato(v):
    valor = clean(v)
    return valor if valor and valor.lower() not in {"nan", "none", "null", "-"} else "Sin dato"


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


def visita_tiene_estado(v, estados):
    estados = set(estados)
    return clean(v.get("est_soc")) in estados or clean(v.get("est_tec")) in estados


def visita_sin_programar(v):
    estados_sin_programar = {"", "Para visita"}
    return clean(v.get("est_soc")) in estados_sin_programar or clean(v.get("est_tec")) in estados_sin_programar


def visita_estado_dispar(v):
    return clean(v.get("est_soc")) != clean(v.get("est_tec"))


def visita_match_estado(v, filtro_estado):
    if filtro_estado == "Todos":
        return True
    if filtro_estado == "Sin programar":
        return visita_sin_programar(v)
    if filtro_estado == "Programadas":
        return visita_tiene_estado(v, {"Programada"})
    if filtro_estado == "Visitadas":
        return visita_tiene_estado(v, {"Visitada"})
    if filtro_estado == "Con informe":
        return visita_tiene_estado(v, {"Informe"})
    if filtro_estado == "Estados dispares":
        return visita_estado_dispar(v)
    return True


def visita_match_informes(v, filtro_informes):
    est_soc = clean(v.get("est_soc"))
    est_tec = clean(v.get("est_tec"))
    if filtro_informes == "Todos":
        return True
    if filtro_informes == "Social pendiente":
        return est_soc == "Visitada"
    if filtro_informes == "Tecnico pendiente":
        return est_tec == "Visitada"
    if filtro_informes == "Algun pendiente":
        return est_soc == "Visitada" or est_tec == "Visitada"
    if filtro_informes == "Completos":
        return est_soc == "Informe" and est_tec == "Informe"
    if filtro_informes == "Sin pendientes":
        return est_soc != "Visitada" and est_tec != "Visitada"
    return True


def limpiar_filtros_socio_visitas():
    for key in ["socio_busqueda_visitas", "socio_estado_visitas", "socio_informes_visitas"]:
        st.session_state.pop(key, None)


def aplicar_ancho_sociohabitacional():
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] main .block-container {
            max-width: 1380px !important;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def socio_card_event_once(resultado, card_key, action=None):
    if not isinstance(resultado, dict):
        return False
    if resultado.get("card_key") != card_key:
        return False
    if action and resultado.get("action") != action:
        return False
    event_id = resultado.get("event_id")
    if not event_id:
        return False
    key = "_socio_card_eventos_vistos"
    vistos = st.session_state.setdefault(key, [])
    if event_id in vistos:
        return False
    vistos.append(event_id)
    st.session_state[key] = vistos[-80:]
    return True


def render_filtros_visitas_socio(visitas_all):
    with st.container(border=True, key="socio_filtros_visitas"):
        c1, c2, c3, c4 = st.columns([2.1, 1.25, 1.35, 0.75])
        with c1:
            busqueda = st.text_input(
                "Buscar",
                placeholder="Nombre o expediente...",
                key="socio_busqueda_visitas",
            )
        with c2:
            filtro_estado = st.selectbox(
                "Estado de visita",
                ["Todos", "Sin programar", "Programadas", "Visitadas", "Con informe", "Estados dispares"],
                key="socio_estado_visitas",
            )
        with c3:
            filtro_informes = st.selectbox(
                "Informes",
                ["Todos", "Social pendiente", "Tecnico pendiente", "Algun pendiente", "Completos", "Sin pendientes"],
                key="socio_informes_visitas",
            )
        with c4:
            st.button("Limpiar", use_container_width=True, key="socio_limpiar_filtros", on_click=limpiar_filtros_socio_visitas)

    q = clean(busqueda).lower()
    visitas = visitas_all
    if q:
        visitas = [
            v
            for v in visitas
            if q in clean(v.get("d_apellido")).lower()
            or q in clean(v.get("d_nombre")).lower()
            or q in clean(v.get("d_expediente")).lower()
            or q in clean(v.get("id_demanda")).lower()
        ]

    visitas = [v for v in visitas if visita_match_estado(v, filtro_estado)]
    visitas = [v for v in visitas if visita_match_informes(v, filtro_informes)]
    return visitas, q


def render_kpis_sociohabitacional(c_para, c_prog, c_inf, c_comp):
    operational_kpis(
        [
            {
                "label": "Para visita",
                "value": c_para,
                "tone": "blue",
                "icon": "PV",
                "caption": "Sin programar",
            },
            {
                "label": "Programados",
                "value": c_prog,
                "tone": "green",
                "icon": "P",
                "caption": "Con fecha",
            },
            {
                "label": "Informes pendientes",
                "value": c_inf,
                "tone": "amber",
                "icon": "IP",
                "caption": "Visitadas",
            },
            {
                "label": "Completados",
                "value": c_comp,
                "tone": "muted",
                "icon": "C",
                "caption": "Informes",
            },
        ],
        key="socio_kpis_visitas",
    )


def render_card_socio(demanda, es_pendiente=False):
    n_id = demanda.get("id_demanda")
    apellido = clean(demanda.get("apellido")).upper()
    nombre = clean(demanda.get("nombre"))
    titular = ", ".join([x for x in [apellido, nombre] if x]) or "Sin titular"
    expte = clean(demanda.get("expediente")) or "Sin expediente"
    accion = clean(demanda.get("accion")) or "Sin accion"
    estado = clean(demanda.get("estado")) or "Sin estado"
    prioridad = clean(demanda.get("prioridad")) or None
    domicilio = sin_dato(demanda.get("domicilio"))
    barrio = sin_dato(demanda.get("barrio"))
    contacto = clean(demanda.get("contacto"))
    obs = clean(demanda.get("observaciones"))
    resumen = obs.split("||")[0] if "||" in obs else obs
    card_key = f"socio_demanda_{n_id}"

    accion_norm = accion.lower()
    if "visitar" in accion_norm:
        variant = "highlight"
        accent = "#1d4ed8"
    elif "informe" in accion_norm or "nota" in accion_norm:
        variant = "success"
        accent = "#0f766e"
    elif "actuacion" in accion_norm or "seguimiento" in accion_norm:
        variant = "warning"
        accent = "#f59e0b"
    else:
        variant = "default"
        accent = "#64748b"

    acciones = None
    if es_pendiente:
        acciones = [{"label": "Validar", "key": "validar", "kind": "primary"}]

    resultado = operational_card(
        title=titular,
        subtitle=f"Expte. {expte}",
        status=estado,
        priority=prioridad,
        meta=[
            f"Accion: {accion}",
            f"Ingreso: {fecha_corta(demanda.get('fecha_ingreso'))}",
            f"{domicilio} - {barrio}",
        ] + ([f"Contacto: {contacto}"] if contacto else []),
        description=resumen[:170] + ("..." if len(resumen) > 170 else ""),
        footer=f"Demanda #{n_id}",
        variant=variant,
        accent_color=accent,
        actions=acciones,
        actions_layout="corner",
        card_key=card_key,
        key=card_key,
    )

    if es_pendiente and socio_card_event_once(resultado, card_key, "validar"):
        st.session_state["socio_validando_demanda"] = n_id
        st.rerun()

    if es_pendiente and st.session_state.get("socio_validando_demanda") == n_id:
        with st.container(border=True, key=f"socio_validacion_{n_id}"):
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
                    st.session_state.pop("socio_validando_demanda", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al validar: {e}")

            if btn_cancelar:
                st.session_state.pop("socio_validando_demanda", None)
                st.rerun()


def tab_seguimiento_visitas():
    try:
        visitas_all = listar_visitas_detalladas()
    except Exception as e:
        st.error(f"Error al cargar visitas: {e}")
        return

    c_para, c_prog, c_inf, c_comp = contar_indicadores_visitas(visitas_all)
    render_kpis_sociohabitacional(c_para, c_prog, c_inf, c_comp)

    st.divider()
    st.markdown(
        """
        <style>
        div[class*="st-key-socio_filtros_visitas"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff !important;
            border: 1px solid #d9e2ec !important;
            border-radius: 14px !important;
            padding: 8px 10px 10px !important;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.035) !important;
        }
        div[class*="st-key-socio_filtros_visitas"] label {
            font-size: 12px !important;
            font-weight: 700 !important;
            color: #475569 !important;
        }
        div[class*="st-key-socio_filtros_visitas"] input,
        div[class*="st-key-socio_filtros_visitas"] [data-baseweb="select"] > div {
            min-height: 36px !important;
            background: #ffffff !important;
            border-radius: 12px !important;
            font-size: 13px !important;
        }
        div[class*="st-key-socio_limpiar_filtros"] button {
            min-height: 36px !important;
            height: 36px !important;
            margin-top: 0 !important;
            padding-top: 4px !important;
            padding-bottom: 4px !important;
            font-size: 13px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    visitas, busqueda = render_filtros_visitas_socio(visitas_all)

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
    aplicar_ancho_sociohabitacional()
    st.title("SocioHabitacional")
    st.markdown("Tablero operativo de demandas sociohabitacionales y seguimiento de informes.")
    t1, t2 = st.tabs(["Tablero Operativo", "Seguimiento Socio Habitacional"])
    with t1:
        render_tablero_principal()
    with t2:
        tab_seguimiento_visitas()


if __name__ == "__main__":
    main()
