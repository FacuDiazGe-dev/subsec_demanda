from datetime import date
import unicodedata
import calendar

import pandas as pd
import streamlit as st

from services.asistencia_service import (
    eliminar_asistencia_jornada,
    listar_asistencia_por_obra_fecha,
    listar_ultima_asignacion_por_obra,
    listar_personal_activo,
    obtener_planilla_mensual,
    obtener_planilla_asistencia,
    personas_asignadas_a_otras_obras,
    upsert_cant_hs_persona_fecha,
    upsert_asistencia_jornada,
)
from services.obras_service import listar_obras_con_demanda


def texto(v):
    return "" if v is None else str(v)


def limpiar(v):
    return texto(v).strip()


def norm(v):
    s = limpiar(v).lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def fecha_iso(f):
    return f.isoformat()


def to_int_safe(v, default=0):
    if v is None:
        return default
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    s = str(v).strip()
    if not s:
        return default
    try:
        return int(float(s))
    except Exception:
        return default


def obras_filtradas():
    obras = listar_obras_con_demanda()
    modalidades = {"cuadrilla havita", "mixta"}
    salida = []
    for o in obras:
        if norm(o.get("estado_obra")) == "en ejecucion" and norm(o.get("modalidad_ejecucion")) in modalidades:
            salida.append(o)
    return salida


def etiqueta_obra(o):
    titular = f"{texto(o.get('apellido'))}, {texto(o.get('nombre'))}".strip(", ")
    return f"Obra {o.get('id_obra')} | {titular or 'Sin titular'}"


def card_asistencia_obra(fecha_jornada, obra):
    personal = listar_personal_activo()
    if not personal:
        st.info("No hay personal activo.")
        return

    personal_por_id = {p.get("id_personal"): p for p in personal}
    asignados_otros = personas_asignadas_a_otras_obras(fecha_jornada, obra.get("id_obra"))
    rows_bd = listar_asistencia_por_obra_fecha(fecha_jornada, obra.get("id_obra"))
    estado_key = f"as_rows_{fecha_jornada}_{obra.get('id_obra')}"
    if estado_key not in st.session_state:
        if rows_bd:
            seed = rows_bd
            st.session_state[estado_key] = [
                {
                    "id_personal": r.get("id_persona"),
                    "estado": limpiar(r.get("asistencia")) or "Ausente",
                }
                for r in seed
            ]
        else:
            seed = listar_ultima_asignacion_por_obra(obra.get("id_obra"), fecha_jornada)
            st.session_state[estado_key] = [
                {
                    "id_personal": r.get("id_persona"),
                    "estado": "Ausente",
                }
                for r in seed
            ]

    rows = st.session_state[estado_key]

    with st.container(border=True):
        titular = f"{texto(obra.get('apellido'))}, {texto(obra.get('nombre'))}".strip(", ")
        st.markdown(f"### {titular or 'Sin beneficiario'}")
        st.caption(f"Obra {obra.get('id_obra')} - {texto(obra.get('contacto')) or '-'}")
        st.caption(f"Estado: {texto(obra.get('estado_obra')) or '-'}")

        disponibles = []
        for p in personal:
            pid = p.get("id_personal")
            if pid in asignados_otros:
                continue
            if any(x.get("id_personal") == pid for x in rows):
                continue
            disponibles.append(p)
        opciones = {f"{texto(p.get('apellido'))}, {texto(p.get('nombre'))}": p.get("id_personal") for p in disponibles}

        c1, c2 = st.columns([5, 1])
        with c1:
            persona_sel = st.selectbox("Agregar personal", [""] + list(opciones.keys()), key=f"as_add_sel_{obra.get('id_obra')}")
        with c2:
            st.write("")
            if st.button("+", key=f"as_add_btn_{obra.get('id_obra')}", use_container_width=True):
                if persona_sel:
                    rows.append({"id_personal": opciones[persona_sel], "estado": "Ausente"})
                    st.session_state[estado_key] = rows
                    st.rerun()

        if not rows:
            st.info("Esta obra aun no tiene personal asignado.")
            return

        st.markdown("#### Personal asignado")
        st.markdown("ID | Nombre | Asistencia |")
        to_remove = []
        for idx, row in enumerate(rows):
            pid = row.get("id_personal")
            p = personal_por_id.get(pid, {})
            nombre = f"{texto(p.get('apellido'))}, {texto(p.get('nombre'))}".strip(", ") or f"ID {pid}"

            c1, c2, c3, c4 = st.columns([1, 4.5, 2, 0.8])
            with c1:
                st.write(str(pid))
            with c2:
                st.write(nombre)
            with c3:
                estado = st.selectbox(
                    "Asistencia",
                    ["Ausente", "Presente", "Justificado"],
                    index=["Ausente", "Presente", "Justificado"].index(row.get("estado")) if row.get("estado") in {"Ausente", "Presente", "Justificado"} else 0,
                    key=f"as_est_{fecha_jornada}_{obra.get('id_obra')}_{pid}_{idx}",
                    label_visibility="collapsed",
                )
            with c4:
                if st.button("-", key=f"as_rm_{obra.get('id_obra')}_{pid}_{idx}", use_container_width=True):
                    to_remove.append(idx)
            row["estado"] = estado

        if to_remove:
            for idx in sorted(to_remove, reverse=True):
                pid = rows[idx].get("id_personal")
                eliminar_asistencia_jornada(fecha_jornada, obra.get("id_obra"), pid)
                rows.pop(idx)
            st.session_state[estado_key] = rows
            st.rerun()

        if st.button("Confirmar cargas", key=f"as_save_{obra.get('id_obra')}", type="primary", use_container_width=True):
            payload = []
            for row in rows:
                estado = row.get("estado") or "Ausente"
                cant_hs = 5 if estado in {"Presente", "Justificado"} else 0
                payload.append(
                    {
                        "fecha_jornada": fecha_jornada,
                        "id_obras": obra.get("id_obra"),
                        "id_persona": row.get("id_personal"),
                        "asistencia": estado,
                        "cant_hs": cant_hs,
                    }
                )
            upsert_asistencia_jornada(payload)
            st.success("Cargas guardadas.")


def tab_carga_diaria():
    st.subheader("Carga diaria")
    fecha = date.today()
    st.text_input("Fecha", value=fecha.strftime("%d/%m/%Y"), disabled=True)

    obras = obras_filtradas()
    obras = obras + [
        {"id_obra": -101, "apellido": "DD", "nombre": "Deposito", "contacto": "-", "estado_obra": "Frente fijo", "modalidad_ejecucion": "Fijo"},
        {"id_obra": -102, "apellido": "OE", "nombre": "Obra externa", "contacto": "-", "estado_obra": "Frente fijo", "modalidad_ejecucion": "Fijo"},
    ]
    opciones = {etiqueta_obra(o): o for o in obras}
    if not opciones:
        st.info("No hay obras en ejecución con modalidad Cuadrilla HAVITA o Mixta.")
        return

    sel = st.selectbox("Seleccionar obra", list(opciones.keys()), key="as_obra_sel")
    obra = opciones[sel]
    card_asistencia_obra(fecha_iso(fecha), obra)


def tab_planilla():
    st.subheader("Planilla de asistencia")
    valores_hora = {
        "OFICIAL": 3500,
        "MEDIO OFICIAL": 3200,
        "AYUDANTE": 2800,
        "ADMINISTRATIVO": 3000,
    }

    hoy = date.today()
    c1, c2 = st.columns(2)
    with c1:
        anio = st.number_input("Anio", min_value=2020, max_value=2100, value=hoy.year, step=1)
    with c2:
        mes = st.selectbox(
            "Mes",
            list(range(1, 13)),
            index=hoy.month - 1,
            format_func=lambda m: f"{m:02d} - {calendar.month_name[m]}",
        )
    ocultar_finde = st.checkbox("Ocultar sabados y domingos", value=True)

    ym_key = f"{int(anio)}-{int(mes):02d}"
    if st.button("Generar planilla mensual", type="primary", use_container_width=True):
        st.session_state["planilla_mensual_data"] = obtener_planilla_mensual(int(anio), int(mes))
        st.session_state["planilla_mensual_key"] = ym_key

    if st.session_state.get("planilla_mensual_key") == ym_key and st.session_state.get("planilla_mensual_data"):
        plan = st.session_state["planilla_mensual_data"]
        dias_mes = int(plan.get("dias_mes") or 30)
        visibles = []
        for d in range(1, dias_mes + 1):
            fecha_d = date(int(anio), int(mes), d)
            es_finde = fecha_d.weekday() >= 5
            if ocultar_finde and es_finde:
                continue
            visibles.append(d)

        codigos_key = f"planilla_codigos_{ym_key}"
        if codigos_key not in st.session_state:
            st.session_state[codigos_key] = {}
        with st.expander("Jornadas especiales", expanded=False):
            st.caption("Aplicar 5 horas para todo el personal en dias puntuales.")
            a1, a2, a3 = st.columns([1.5, 4, 1.5])
            with a1:
                tipo = st.selectbox("Tipo", ["F", "L", "N"], format_func=lambda x: {"F": "Feriado (F)", "L": "Lluvia (L)", "N": "No laborable (N)"}[x], key=f"tipo_esp_{ym_key}")
            with a2:
                dias_sel = st.multiselect("Dias", visibles, format_func=lambda d: f"{d:02d}/{int(mes):02d}", key=f"dias_esp_{ym_key}")
            with a3:
                st.write("")
                if st.button("Aplicar 5h", key=f"apply_esp_{ym_key}", use_container_width=True):
                    codigos = dict(st.session_state[codigos_key])
                    for d in dias_sel:
                        codigos[str(d)] = tipo
                    st.session_state[codigos_key] = codigos
                    st.rerun()
            b1, b2 = st.columns(2)
            with b1:
                if st.button("Quitar dias seleccionados", key=f"clear_esp_{ym_key}", use_container_width=True):
                    codigos = dict(st.session_state[codigos_key])
                    for d in dias_sel:
                        codigos.pop(str(d), None)
                    st.session_state[codigos_key] = codigos
                    st.rerun()
            with b2:
                if st.button("Limpiar todo", key=f"clear_all_esp_{ym_key}", use_container_width=True):
                    st.session_state[codigos_key] = {}
                    st.rerun()
            resumen = st.session_state.get(codigos_key, {})
            if resumen:
                items = [f"{int(k):02d}/{int(mes):02d} [{v}]" for k, v in sorted(resumen.items(), key=lambda kv: int(kv[0]))]
                st.caption("Aplicados: " + " | ".join(items))

        rows = []
        dias_semana = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
        codigos = st.session_state.get(codigos_key, {})
        for p in plan.get("personal", []):
            categoria = limpiar(p.get("categoria")).upper()
            valor_hora = valores_hora.get(categoria, 0)
            pid = p.get("id_personal")
            dias = plan.get("por_persona_dia", {}).get(pid, {})
            row = {
                "id_personal": pid,
                "apellido_nombre": f"{texto(p.get('apellido'))}, {texto(p.get('nombre'))}".strip(", "),
                "dni": texto(p.get("dni_cuil")),
                "categoria": texto(p.get("categoria")),
                "valor_hs": valor_hora,
            }
            hs_mensuales = 0
            for d in range(1, dias_mes + 1):
                fecha_d = date(int(anio), int(mes), d)
                es_finde = fecha_d.weekday() >= 5
                if ocultar_finde and es_finde:
                    continue
                codigo = codigos.get(str(d), "")
                v = 5 if codigo in {"F", "L", "N"} else int(dias.get(d, 0))
                etiqueta = f"{dias_semana[fecha_d.weekday()]} {d:02d}/{int(mes):02d}"
                if codigo:
                    etiqueta = f"{etiqueta} [{codigo}]"
                if es_finde:
                    etiqueta = f"{etiqueta} (FDS)"
                row[etiqueta] = v
                hs_mensuales += v
            row["hs_mensuales"] = hs_mensuales
            row["monto_mensual"] = hs_mensuales * valor_hora
            rows.append(row)

        st.caption("Planilla mensual")
        df_plan = pd.DataFrame(rows)
        editable_cols = [c for c in df_plan.columns if c.startswith(("Lun ", "Mar ", "Mie ", "Jue ", "Vie ", "Sab ", "Dom "))]
        edited = st.data_editor(
            df_plan,
            use_container_width=True,
            hide_index=True,
            height=520,
            num_rows="fixed",
            column_config={c: st.column_config.NumberColumn(step=1, min_value=0, max_value=24, format="%d") for c in editable_cols},
            disabled=["id_personal", "apellido_nombre", "dni", "categoria", "valor_hs", "hs_mensuales", "monto_mensual"],
            key=f"plan_edit_{ym_key}",
        )
        if st.button("Guardar horas editadas", use_container_width=True):
            cambios = 0
            for _, row_new in edited.iterrows():
                pid = row_new.get("id_personal")
                row_old = df_plan[df_plan["id_personal"] == pid]
                if row_old.empty:
                    continue
                row_old = row_old.iloc[0]
                for col in editable_cols:
                    old = to_int_safe(row_old.get(col), 0)
                    new = to_int_safe(row_new.get(col), 0)
                    if old != new:
                        partes = col.split(" ")
                        if len(partes) < 2:
                            continue
                        dmy = partes[1]
                        if len(dmy) < 5:
                            continue
                        dia = int(dmy[:2])
                        fecha_ref = date(int(anio), int(mes), dia).isoformat()
                        resp = upsert_cant_hs_persona_fecha(fecha_ref, int(pid), int(new))
                        if resp is not None:
                            cambios += 1
            if cambios:
                st.success(f"Horas actualizadas: {cambios} cambios.")
                st.session_state["planilla_mensual_data"] = obtener_planilla_mensual(int(anio), int(mes))
                st.rerun()
            else:
                st.info("No hay cambios para guardar.")
        st.caption("Referencia valor hora por categoria: OFICIAL=3500, MEDIO OFICIAL=3200, AYUDANTE=2800, ADMINISTRATIVO=3000")


st.set_page_config(page_title="Asistencia", layout="wide")
st.title("Asistencia")
t1, t2 = st.tabs(["Carga diaria", "Planilla de asistencia"])
with t1:
    tab_carga_diaria()
with t2:
    tab_planilla()
