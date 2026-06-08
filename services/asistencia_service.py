from collections import defaultdict
import calendar
from datetime import date

from services.supabase_client import get_supabase_client


def listar_personal_activo():
    supabase = get_supabase_client()
    response = supabase.table("personal_base").select("*").eq("activo", True).order("apellido").execute()
    return response.data or []


def listar_asistencia_por_fecha(fecha_jornada):
    supabase = get_supabase_client()
    response = (
        supabase.table("asistencia_jornada")
        .select("*")
        .eq("fecha_jornada", fecha_jornada)
        .order("id_obras")
        .order("id_persona")
        .execute()
    )
    return response.data or []


def listar_asistencia_por_obra_fecha(fecha_jornada, id_obra):
    supabase = get_supabase_client()
    response = (
        supabase.table("asistencia_jornada")
        .select("*")
        .eq("fecha_jornada", fecha_jornada)
        .eq("id_obras", id_obra)
        .order("id_persona")
        .execute()
    )
    return response.data or []


def listar_ultima_asignacion_por_obra(id_obra, fecha_jornada):
    supabase = get_supabase_client()
    fechas = (
        supabase.table("asistencia_jornada")
        .select("fecha_jornada")
        .eq("id_obras", id_obra)
        .lt("fecha_jornada", fecha_jornada)
        .order("fecha_jornada", desc=True)
        .limit(1)
        .execute()
    ).data or []
    if not fechas:
        return []
    fecha_ref = fechas[0].get("fecha_jornada")
    if not fecha_ref:
        return []
    return listar_asistencia_por_obra_fecha(fecha_ref, id_obra)


def upsert_asistencia_jornada(rows):
    if not rows:
        return []
    supabase = get_supabase_client()
    guardadas = []
    for row in rows:
        fecha = row.get("fecha_jornada")
        persona = row.get("id_persona")
        if fecha is None or persona is None:
            continue

        existente = (
            supabase.table("asistencia_jornada")
            .select("id_jornada")
            .eq("fecha_jornada", fecha)
            .eq("id_persona", persona)
            .limit(1)
            .execute()
        ).data or []

        payload = {
            "fecha_jornada": fecha,
            "id_obras": row.get("id_obras"),
            "id_persona": persona,
            "asistencia": row.get("asistencia"),
            "cant_hs": row.get("cant_hs"),
        }
        if existente:
            data = (
                supabase.table("asistencia_jornada")
                .update(payload)
                .eq("id_jornada", existente[0].get("id_jornada"))
                .execute()
            ).data or []
        else:
            data = supabase.table("asistencia_jornada").insert(payload).execute().data or []
        guardadas.extend(data)
    return guardadas


def actualizar_cant_hs_persona_fecha(fecha_jornada, id_persona, cant_hs):
    supabase = get_supabase_client()
    response = (
        supabase.table("asistencia_jornada")
        .update({"cant_hs": cant_hs, "asistencia": "Presente" if float(cant_hs) > 0 else "Ausente"})
        .eq("fecha_jornada", fecha_jornada)
        .eq("id_persona", id_persona)
        .execute()
    )
    return response.data or []


def upsert_cant_hs_persona_fecha(fecha_jornada, id_persona, cant_hs):
    supabase = get_supabase_client()
    existe = (
        supabase.table("asistencia_jornada")
        .select("*")
        .eq("fecha_jornada", fecha_jornada)
        .eq("id_persona", id_persona)
        .limit(1)
        .execute()
    ).data or []

    asistencia_txt = "Presente" if float(cant_hs) > 0 else "Ausente"
    if existe:
        return (
            supabase.table("asistencia_jornada")
            .update({"cant_hs": cant_hs, "asistencia": asistencia_txt})
            .eq("fecha_jornada", fecha_jornada)
            .eq("id_persona", id_persona)
            .execute()
        ).data or []

    ult = (
        supabase.table("asistencia_jornada")
        .select("id_obras")
        .eq("id_persona", id_persona)
        .order("fecha_jornada", desc=True)
        .limit(1)
        .execute()
    ).data or []
    if not ult:
        return []

    payload = {
        "fecha_jornada": fecha_jornada,
        "id_obras": ult[0].get("id_obras"),
        "id_persona": id_persona,
        "asistencia": asistencia_txt,
        "cant_hs": cant_hs,
    }
    return supabase.table("asistencia_jornada").insert(payload).execute().data or []


def eliminar_asistencia_jornada(fecha_jornada, id_obra, id_persona):
    supabase = get_supabase_client()
    response = (
        supabase.table("asistencia_jornada")
        .delete()
        .eq("fecha_jornada", fecha_jornada)
        .eq("id_obras", id_obra)
        .eq("id_persona", id_persona)
        .execute()
    )
    return response.data or []


def personas_asignadas_a_otras_obras(fecha_jornada, id_obra):
    rows = listar_asistencia_por_fecha(fecha_jornada)
    return {r.get("id_persona") for r in rows if r.get("id_obras") != id_obra and r.get("id_persona") is not None}


def obtener_planilla_asistencia(fecha_desde, fecha_hasta):
    supabase = get_supabase_client()
    rows = (
        supabase.table("asistencia_jornada")
        .select("*")
        .gte("fecha_jornada", fecha_desde)
        .lte("fecha_jornada", fecha_hasta)
        .order("fecha_jornada")
        .execute()
    ).data or []

    ids_persona = [r.get("id_persona") for r in rows if r.get("id_persona") is not None]
    personal = {}
    if ids_persona:
        pres = supabase.table("personal_base").select("*").in_("id_personal", ids_persona).execute().data or []
        personal = {p.get("id_personal"): p for p in pres}

    resumen = defaultdict(lambda: {"presentes": 0, "ausentes": 0, "justificados": 0})
    detalle = []
    for r in rows:
        pid = r.get("id_persona")
        p = personal.get(pid, {})
        asistencia = (r.get("asistencia") or "").strip()
        if asistencia == "Presente":
            resumen[pid]["presentes"] += 1
        elif asistencia == "Justificado":
            resumen[pid]["justificados"] += 1
        else:
            resumen[pid]["ausentes"] += 1
        detalle.append(
            {
                "id_jornada": r.get("id_jornada"),
                "fecha": r.get("fecha_jornada"),
                "id_obras": r.get("id_obras"),
                "id_personal": pid,
                "persona": f"{p.get('apellido','')}, {p.get('nombre','')}".strip(", "),
                "asistencia": asistencia or "Ausente",
            }
        )

    resumen_rows = []
    for pid, vals in resumen.items():
        p = personal.get(pid, {})
        resumen_rows.append(
            {
                "id_personal": pid,
                "apellido": p.get("apellido"),
                "nombre": p.get("nombre"),
                "categoria": p.get("categoria"),
                "presentes": vals["presentes"],
                "ausentes": vals["ausentes"],
                "justificados": vals["justificados"],
            }
        )

    return {"resumen": resumen_rows, "detalle": detalle}


def _puntaje_asistencia(valor):
    v = (valor or "").strip().lower()
    if v in {"presente", "justificado"}:
        return 5
    if v in {"ausente", ""}:
        return 0
    if valor is True:
        return 5
    return 0


def obtener_planilla_mensual(anio, mes):
    supabase = get_supabase_client()
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    desde = date(anio, mes, 1).isoformat()
    hasta = date(anio, mes, ultimo_dia).isoformat()

    personal = (
        supabase.table("personal_base")
        .select("id_personal,apellido,nombre,dni_cuil,categoria,activo")
        .order("apellido")
        .execute()
    ).data or []

    asistencias = (
        supabase.table("asistencia_jornada")
        .select("fecha_jornada,id_persona,asistencia,cant_hs")
        .gte("fecha_jornada", desde)
        .lte("fecha_jornada", hasta)
        .execute()
    ).data or []

    por_persona_dia = defaultdict(dict)
    for a in asistencias:
        pid = a.get("id_persona")
        fecha = (a.get("fecha_jornada") or "")[:10]
        if not pid or not fecha:
            continue
        dia = int(fecha[-2:])
        cant = a.get("cant_hs")
        if cant is None:
            puntaje = _puntaje_asistencia(a.get("asistencia"))
        else:
            try:
                puntaje = float(cant)
            except Exception:
                puntaje = _puntaje_asistencia(a.get("asistencia"))
        previo = por_persona_dia[pid].get(dia, 0)
        if puntaje > previo:
            por_persona_dia[pid][dia] = puntaje

    return {
        "anio": anio,
        "mes": mes,
        "dias_mes": ultimo_dia,
        "personal": personal,
        "por_persona_dia": dict(por_persona_dia),
    }
