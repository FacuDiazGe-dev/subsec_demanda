from datetime import date

import streamlit as st

from services.notas_rapidas_obra_service import actualizar_nota_rapida, crear_nota_rapida, listar_notas_rapidas
from services.obras_service import listar_obras_con_demanda

RESPONSABLES_TECNICOS = ["Facundo", "Pedro", "Bea", "Iris", "Guillo"]


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


def show_error(error):
    st.error(f"No se pudo completar la operacion en Supabase: {error}")


def selector_obra(obras):
    opciones = {
        f"Obra {txt(o.get('id_obra'))} | {clean(o.get('apellido'))}, {clean(o.get('nombre'))} | Expte {txt(o.get('expediente')) or '-'}": o
        for o in obras
    }
    if not opciones:
        return None
    return st.selectbox("Seleccionar obra registrada", list(opciones.keys()), key="nr_sel_obra")


def cargar_nota_tab(obras):
    st.markdown("### Cargar nota rapida")
    sel = selector_obra(obras)
    if not sel:
        st.info("No hay obras disponibles.")
        return
    obra = {
        f"Obra {txt(o.get('id_obra'))} | {clean(o.get('apellido'))}, {clean(o.get('nombre'))} | Expte {txt(o.get('expediente')) or '-'}": o
        for o in obras
    }[sel]

    st.caption(
        f"Obra #{txt(obra.get('id_obra'))} | Expte {txt(obra.get('expediente')) or '-'} | "
        f"{clean(obra.get('apellido'))}, {clean(obra.get('nombre'))}"
    )
    st.caption(f"Domicilio: {txt(obra.get('domicilio')) or '-'} - {txt(obra.get('barrio')) or '-'}")

    with st.form("nr_form_carga"):
        c1, c2 = st.columns(2)
        with c1:
            fecha_nota = st.date_input("Fecha", value=date.today())
        with c2:
            responsable = st.selectbox("Responsable tecnico", RESPONSABLES_TECNICOS, index=0)
        nota = st.text_area("Nota de visita", height=140, placeholder="Escribe lo observado en obra...")
        st.caption("Estado inicial: Pendiente")
        guardar = st.form_submit_button("Guardar nota", type="primary", use_container_width=True)

    if guardar:
        if not clean(nota):
            st.warning("Escribe la nota antes de guardar.")
            return
        try:
            crear_nota_rapida(
                {
                    "id_obra": obra.get("id_obra"),
                    "fecha_nota": fecha_nota.isoformat(),
                    "responsable_tecnico": responsable,
                    "nota": clean(nota),
                    "estado_nota": "Pendiente",
                }
            )
        except Exception as e:
            show_error(e)
            return
        st.success("Nota rapida guardada.")
        st.rerun()


def editar_notas_tab(obras):
    st.markdown("### Editar notas emitidas")
    try:
        notas = listar_notas_rapidas()
    except Exception as e:
        show_error(e)
        return

    if not notas:
        st.info("No hay notas cargadas.")
        return

    obras_por_id = {o.get("id_obra"): o for o in obras}

    if "nr_filtros" not in st.session_state:
        st.session_state["nr_filtros"] = {"estado": "Todos", "responsable": "Todos", "obra": "Todas"}

    estado_opts = ["Todos", "Pendiente", "Aplicada", "Descartada"]
    resp_opts = ["Todos"] + RESPONSABLES_TECNICOS
    obra_opts = ["Todas"] + [str(k) for k in sorted({n.get("id_obra") for n in notas if n.get("id_obra") is not None})]

    with st.form("nr_filtros_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            e_idx = estado_opts.index(st.session_state["nr_filtros"]["estado"]) if st.session_state["nr_filtros"]["estado"] in estado_opts else 0
            estado_in = st.selectbox("Estado", estado_opts, index=e_idx)
        with c2:
            r_idx = resp_opts.index(st.session_state["nr_filtros"]["responsable"]) if st.session_state["nr_filtros"]["responsable"] in resp_opts else 0
            resp_in = st.selectbox("Responsable", resp_opts, index=r_idx)
        with c3:
            o_idx = obra_opts.index(st.session_state["nr_filtros"]["obra"]) if st.session_state["nr_filtros"]["obra"] in obra_opts else 0
            obra_in = st.selectbox("Obra", obra_opts, index=o_idx)
        aplicar = st.form_submit_button("Aplicar filtros", type="primary", use_container_width=True)

    if aplicar:
        st.session_state["nr_filtros"] = {"estado": estado_in, "responsable": resp_in, "obra": obra_in}

    estado_f = st.session_state["nr_filtros"]["estado"]
    resp_f = st.session_state["nr_filtros"]["responsable"]
    obra_f = st.session_state["nr_filtros"]["obra"]

    filtradas = []
    for n in notas:
        if estado_f != "Todos" and clean(n.get("estado_nota")) != estado_f:
            continue
        if resp_f != "Todos" and clean(n.get("responsable_tecnico")) != resp_f:
            continue
        if obra_f != "Todas" and str(n.get("id_obra")) != obra_f:
            continue
        filtradas.append(n)

    st.caption(f"Notas encontradas: {len(filtradas)}")

    for n in filtradas:
        obra = obras_por_id.get(n.get("id_obra"), {})
        titulo = f"Nota #{txt(n.get('id_nota'))} | Obra {txt(n.get('id_obra'))} | {fecha_corta(n.get('fecha_nota'))} | {txt(n.get('estado_nota'))}"
        with st.expander(titulo, expanded=False):
            st.caption(
                f"{clean(obra.get('apellido'))}, {clean(obra.get('nombre'))} | Expte {txt(obra.get('expediente')) or '-'} | "
                f"{txt(n.get('responsable_tecnico')) or '-'}"
            )
            with st.form(f"edit_nota_{n.get('id_nota')}"):
                fecha_ed = st.date_input("Fecha", value=date.fromisoformat(clean(n.get("fecha_nota"))[:10]) if clean(n.get("fecha_nota")) else date.today(), key=f"f_{n.get('id_nota')}")
                resp_ed = st.selectbox(
                    "Responsable tecnico",
                    RESPONSABLES_TECNICOS,
                    index=RESPONSABLES_TECNICOS.index(n.get("responsable_tecnico")) if n.get("responsable_tecnico") in RESPONSABLES_TECNICOS else 0,
                    key=f"r_{n.get('id_nota')}",
                )
                nota_ed = st.text_area("Nota", value=txt(n.get("nota")), height=130, key=f"t_{n.get('id_nota')}")
                estado_ed = st.selectbox("Estado", ["Pendiente", "Aplicada", "Descartada"], index=["Pendiente", "Aplicada", "Descartada"].index(clean(n.get("estado_nota"))) if clean(n.get("estado_nota")) in {"Pendiente", "Aplicada", "Descartada"} else 0, key=f"e_{n.get('id_nota')}")
                guardar = st.form_submit_button("Guardar cambios", type="primary", use_container_width=True)
            if guardar:
                if not clean(nota_ed):
                    st.warning("La nota no puede quedar vacia.")
                    continue
                try:
                    actualizar_nota_rapida(
                        n.get("id_nota"),
                        {
                            "fecha_nota": fecha_ed.isoformat(),
                            "responsable_tecnico": resp_ed,
                            "nota": clean(nota_ed),
                            "estado_nota": estado_ed,
                        },
                    )
                except Exception as e:
                    show_error(e)
                    continue
                st.success("Nota actualizada.")
                st.rerun()


def main():
    st.set_page_config(page_title="Notas rapidas", layout="wide")
    st.title("Notas rapidas de obra")
    st.caption("Registro de campo para tecnico en obra. Estado por defecto: Pendiente.")

    try:
        obras = listar_obras_con_demanda()
    except Exception as e:
        show_error(e)
        return

    with st.container(border=True):
        st.markdown("### Nueva nota")
        cargar_nota_tab(obras)
    with st.expander("Editar notas emitidas", expanded=False):
        editar_notas_tab(obras)


main()
