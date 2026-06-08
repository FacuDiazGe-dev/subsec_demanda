from datetime import date
import unicodedata
import calendar

import pandas as pd
import streamlit as st

from services.asistencia_service import (
    eliminar_asistencia_jornada,
    listar_asistencia_por_fecha,
    listar_asistencia_por_obra_fecha,
    listar_ultima_asignacion_por_obra,
    listar_personal_activo,
    obtener_planilla_mensual,
    obtener_planilla_asistencia,
    personas_asignadas_a_otras_obras,
    upsert_cant_hs_persona_fecha,
    upsert_asistencia_jornada,
)
from services.obras_service import listar_obras_asistencia
from utils.auth import require_login
from utils.operational_attendance_board_component import operational_attendance_board


SIN_ASIGNACION_ID = 0


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
    try:
        obras = listar_obras_asistencia()
    except Exception as exc:
        st.warning(f"No se pudieron cargar las obras activas. Se muestran solo los bloques fijos. Detalle: {exc}")
        return []
    modalidades = {"cuadrilla havita", "mixta"}
    salida = []
    for o in obras:
        if norm(o.get("estado_obra")) == "en ejecucion" and norm(o.get("modalidad_ejecucion")) in modalidades:
            salida.append(o)
    return salida


def etiqueta_obra(o):
    titular = f"{texto(o.get('apellido'))}, {texto(o.get('nombre'))}".strip(", ")
    return f"Obra {o.get('id_obra')} | {titular or 'Sin titular'}"


def nombre_personal(persona):
    return f"{texto(persona.get('apellido'))}, {texto(persona.get('nombre'))}".strip(", ")


def nombre_personal_con_categoria(persona):
    nombre = nombre_personal(persona)
    categoria = limpiar(persona.get("categoria"))
    return f"{nombre} - {categoria}" if categoria else nombre


def asistencia_estado_key(fecha_jornada):
    return f"asistencia_dia_{fecha_jornada}"


def bloque_linea_1(obra):
    if obra.get("fijo"):
        return texto(obra.get("titulo"))
    titular = f"{texto(obra.get('apellido'))} {texto(obra.get('nombre'))}".strip()
    return f"Expte. {texto(obra.get('expediente')) or '-'} - {titular or 'Sin titular'}"


def bloque_linea_2(obra):
    if obra.get("fijo"):
        return "Bloque fijo operativo"
    domicilio = texto(obra.get("domicilio")) or "-"
    barrio = texto(obra.get("barrio")) or "-"
    return f"{domicilio} - {barrio}"


def bloques_asistencia():
    obras = obras_filtradas()
    return obras + [
        {"id_obra": -101, "titulo": "DD - Deposito / Carga y descarga", "fijo": True},
        {"id_obra": -102, "titulo": "OE - Obra externa / Otras areas", "fijo": True},
    ]


def inicializar_asistencia_dia(fecha_jornada, bloques):
    key = asistencia_estado_key(fecha_jornada)
    if key in st.session_state:
        return st.session_state[key]

    asignaciones = {}
    actuales = []
    try:
        actuales = listar_asistencia_por_fecha(fecha_jornada)
    except Exception:
        actuales = []

    for row in actuales:
        pid = row.get("id_persona")
        if pid is None:
            continue
        asignaciones[pid] = {
            "id_obra": row.get("id_obras"),
            "estado": limpiar(row.get("asistencia")) or "Ausente",
        }

    for bloque in bloques:
        if any(a.get("id_obra") == bloque.get("id_obra") for a in asignaciones.values()):
            continue
        try:
            ultimos = listar_ultima_asignacion_por_obra(bloque.get("id_obra"), fecha_jornada)
        except Exception:
            ultimos = []
        for row in ultimos:
            pid = row.get("id_persona")
            if pid is None or pid in asignaciones:
                continue
            asignaciones[pid] = {"id_obra": bloque.get("id_obra"), "estado": "Sin marcar"}

    st.session_state[key] = asignaciones
    return asignaciones


def asignaciones_para_componente(asignaciones):
    salida = []
    for pid, item in asignaciones.items():
        if item.get("id_obra") is None:
            continue
        salida.append(
            {
                "person_id": pid,
                "block_id": item.get("id_obra"),
                "status": item.get("estado") or "Sin marcar",
            }
        )
    return salida


def asignaciones_desde_componente(rows):
    asignaciones = {}
    for row in rows or []:
        try:
            pid = int(row.get("person_id"))
            id_obra = int(row.get("block_id"))
        except Exception:
            continue
        asignaciones[pid] = {
            "id_obra": id_obra,
            "estado": limpiar(row.get("status")) or "Sin marcar",
        }
    return asignaciones


def completar_ausentes_default(asignaciones, personal):
    salida = dict(asignaciones)
    for persona in personal or []:
        pid = persona.get("id_personal")
        if pid is None or pid in salida:
            continue
        salida[pid] = {"id_obra": SIN_ASIGNACION_ID, "estado": "Ausente"}
    return salida


def resumen_asistencia(asignaciones):
    resumen = {"Presente": 0, "Ausente": 0, "Justificado": 0, "Sin marcar": 0}
    for item in asignaciones.values():
        estado = item.get("estado") or "Sin marcar"
        resumen[estado] = resumen.get(estado, 0) + 1
    return resumen


def guardar_asistencia_bloque(fecha_jornada, id_obra, asignaciones):
    payload = []
    for pid, item in asignaciones.items():
        if item.get("id_obra") != id_obra:
            continue
        estado = item.get("estado") or "Ausente"
        if estado == "Sin marcar":
            estado = "Ausente"
        payload.append(
            {
                "fecha_jornada": fecha_jornada,
                "id_obras": id_obra,
                "id_persona": pid,
                "asistencia": estado,
                "cant_hs": 5 if estado in {"Presente", "Justificado"} else 0,
            }
        )
    return upsert_asistencia_jornada(payload)


def guardar_asistencia_dia(fecha_jornada, asignaciones):
    payload = []
    for pid, item in asignaciones.items():
        estado = item.get("estado") or "Ausente"
        if estado == "Sin marcar":
            estado = "Ausente"
        payload.append(
            {
                "fecha_jornada": fecha_jornada,
                "id_obras": item.get("id_obra") if item.get("id_obra") is not None else SIN_ASIGNACION_ID,
                "id_persona": pid,
                "asistencia": estado,
                "cant_hs": 5 if estado in {"Presente", "Justificado"} else 0,
            }
        )
    return upsert_asistencia_jornada(payload)


def sincronizar_asistencia_dia(fecha_jornada, asignaciones):
    return guardar_asistencia_dia(fecha_jornada, asignaciones)


def render_estado_persona(fecha_jornada, pid, asignaciones):
    estado = asignaciones[pid].get("estado") or "Sin marcar"
    c1, c2, c3 = st.columns(3)
    for col, valor, label in [
        (c1, "Presente", "Presente"),
        (c2, "Ausente", "Ausente"),
        (c3, "Justificado", "Justificado"),
    ]:
        with col:
            if st.button(
                f"âœ“ {label}" if estado == valor else label,
                key=f"as_estado_{fecha_jornada}_{pid}_{valor}",
                type="primary" if estado == valor else "secondary",
                use_container_width=True,
            ):
                asignaciones[pid]["estado"] = valor
                st.rerun()


def render_bloque_asistencia(fecha_jornada, bloque, personal, personal_por_id, asignaciones):
    id_obra = bloque.get("id_obra")
    st.markdown(
        f"""
        <div class="as-card {'as-card-fixed' if bloque.get('fijo') else ''}">
            <div class="as-card-title">{bloque_linea_1(bloque)}</div>
            <div class="as-card-subtitle">{bloque_linea_2(bloque)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    asignados = [pid for pid, item in asignaciones.items() if item.get("id_obra") == id_obra]
    opciones = {nombre_personal(p): p.get("id_personal") for p in personal if p.get("id_personal") not in asignados}
    c_add, c_btn = st.columns([4, 1])
    with c_add:
        persona_sel = st.selectbox("Agregar persona", [""] + list(opciones.keys()), key=f"as_add_sel_{fecha_jornada}_{id_obra}")
    with c_btn:
        st.write("")
        if st.button("+", key=f"as_add_btn_{fecha_jornada}_{id_obra}", use_container_width=True):
            if persona_sel:
                pid = opciones[persona_sel]
                viejo = asignaciones.get(pid, {}).get("id_obra")
                if viejo is not None and viejo != id_obra:
                    eliminar_asistencia_jornada(fecha_jornada, viejo, pid)
                asignaciones[pid] = {"id_obra": id_obra, "estado": "Presente"}
                st.rerun()

    if not asignados:
        st.caption("Esta obra/bloque todavia no tiene personal asignado.")
    for pid in asignados:
        persona = personal_por_id.get(pid, {})
        nombre = nombre_personal(persona) or f"ID {pid}"
        st.markdown(f"**{nombre}**")
        render_estado_persona(fecha_jornada, pid, asignaciones)
        if asignaciones[pid].get("estado") == "Sin marcar":
            st.caption("Sin marcar")
        if st.button("Quitar de este bloque", key=f"as_rm_{fecha_jornada}_{id_obra}_{pid}", use_container_width=True):
            eliminar_asistencia_jornada(fecha_jornada, id_obra, pid)
            asignaciones.pop(pid, None)
            st.rerun()

    if st.button("Guardar bloque", key=f"as_save_{fecha_jornada}_{id_obra}", type="primary", use_container_width=True):
        guardar_asistencia_bloque(fecha_jornada, id_obra, asignaciones)
        st.success("Bloque guardado.")


def tab_carga_diaria():
    st.subheader("Carga diaria")
    fecha = date.today()
    fecha_jornada = fecha_iso(fecha)
    msg_key = f"asistencia_msg_{fecha_jornada}"
    if st.session_state.get(msg_key):
        st.success(st.session_state.pop(msg_key))

    bloques = bloques_asistencia()
    if not bloques:
        st.info("No hay obras en ejecucion con modalidad Cuadrilla HAVITA o Mixta.")
        return

    personal = listar_personal_activo()
    if not personal:
        st.info("No hay personal activo.")
        return

    personal_por_id = {p.get("id_personal"): p for p in personal}
    asignaciones = completar_ausentes_default(inicializar_asistencia_dia(fecha_jornada, bloques), personal)
    st.session_state[asistencia_estado_key(fecha_jornada)] = asignaciones

    st.caption(f"Asistencias del dia - {fecha.strftime('%d/%m/%Y')}. La fecha es automatica y no editable.")

    resultado = operational_attendance_board(
        title="Asistencias del dia",
        subtitle=f"{fecha.strftime('%d/%m/%Y')} - carga rapida por obra y bloque",
        blocks=[
            {
                "id": b.get("id_obra"),
                "line1": bloque_linea_1(b),
                "line2": bloque_linea_2(b),
                "fixed": bool(b.get("fijo")),
            }
            for b in bloques
        ],
        people=[
            {"id": p.get("id_personal"), "name": nombre_personal_con_categoria(p)}
            for p in personal
            if p.get("id_personal") is not None
        ],
        assignments=asignaciones_para_componente(asignaciones),
        copy_label="Copiar parte WhatsApp",
        validate_label="Validar asistencia del dia",
        key=f"asistencia_board_{fecha_jornada}",
    )

    if resultado and resultado.get("assignments") is not None:
        asignaciones = asignaciones_desde_componente(resultado.get("assignments"))
        st.session_state[asistencia_estado_key(fecha_jornada)] = asignaciones

    if resultado and resultado.get("action") == "copy":
        st.success("Parte copiado al portapapeles.")

    if resultado and resultado.get("action") == "validate":
        pendientes = []
        bloque_por_id = {b.get("id_obra"): b for b in bloques}
        for pid, item in asignaciones.items():
            if item.get("estado") == "Sin marcar":
                bloque = bloque_por_id.get(item.get("id_obra"), {})
                nombre = nombre_personal(personal_por_id.get(pid, {})) or f"ID {pid}"
                pendientes.append(f"{nombre} - {bloque_linea_1(bloque)}")
        if pendientes:
            st.warning(f"No se puede validar. Quedan {len(pendientes)} personas sin marcar.")
            for pendiente in pendientes:
                st.caption(pendiente)
        else:
            for item in asignaciones.values():
                if item.get("estado") == "Sin marcar":
                    item["estado"] = "Ausente"
            asignaciones = completar_ausentes_default(asignaciones, personal)
            st.session_state[asistencia_estado_key(fecha_jornada)] = asignaciones
            sincronizar_asistencia_dia(fecha_jornada, asignaciones)
            st.session_state[msg_key] = "Asistencia del dia validada y guardada."
            st.rerun()

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


require_login(["asistencia"])
st.title("Asistencia")
t1, t2 = st.tabs(["Carga diaria", "Planilla de asistencia"])
with t1:
    tab_carga_diaria()
with t2:
    tab_planilla()
