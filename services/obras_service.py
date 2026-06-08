from datetime import date, datetime

from services.supabase_client import get_supabase_client


def _texto(valor):
    return "" if valor is None else str(valor)


def _limpiar(valor):
    return _texto(valor).strip()


def _hoy_iso():
    return date.today().isoformat()


def _hoy_ddmmyyyy():
    return date.today().strftime("%d/%m/%Y")


def _ahora_iso():
    return datetime.now().isoformat()


def _agregar_historial(historial_actual, mensaje):
    historial_actual = _limpiar(historial_actual)
    entrada = f"{_hoy_ddmmyyyy()} - {_limpiar(mensaje)}"
    if historial_actual:
        return f"{entrada} || {historial_actual}"
    return entrada


def crear_obra(data):
    supabase = get_supabase_client()
    payload = {
        "id_demanda": data.get("id_demanda"),
        "tipo_obra_programa": data.get("tipo_obra_programa"),
        "modalidad_ejecucion": data.get("modalidad_ejecucion"),
        "estado_obra": data.get("estado_obra"),
        "responsable_tecnico": data.get("responsable_tecnico"),
        "descripcion_obra": data.get("descripcion_obra"),
        "obs_obras": data.get("obs_obras"),
        "fecha_creacion": data.get("fecha_creacion") or _hoy_iso(),
        "ultima_actualizacion_semanal": data.get("ultima_actualizacion_semanal"),
    }
    historial_manual = _limpiar(data.get("historial"))
    if historial_manual:
        payload["historial"] = historial_manual
    else:
        mensaje = f"Obra creada. Estado: {payload['estado_obra']}."
        if _limpiar(payload.get("descripcion_obra")):
            mensaje = f"{mensaje} Descripcion: {_limpiar(payload.get('descripcion_obra'))[:120]}"
        payload["historial"] = _agregar_historial("", mensaje)
    response = supabase.table("obras").insert(payload).execute()
    return response.data[0] if response.data else None


def listar_obras():
    supabase = get_supabase_client()
    response = supabase.table("obras").select("*").order("id_obra", desc=True).execute()
    return response.data or []


def listar_obras_activas():
    obras = listar_obras()
    return [o for o in obras if _limpiar(o.get("estado_obra")) not in {"Cerrada", "Cancelada"}]


def _demandas_por_id(ids_demanda):
    ids = [id_demanda for id_demanda in ids_demanda if id_demanda is not None]
    if not ids:
        return {}
    supabase = get_supabase_client()
    response = supabase.table("demandas").select("*").in_("id_demanda", ids).execute()
    return {d["id_demanda"]: d for d in response.data or []}


def listar_obras_con_demanda():
    obras = listar_obras()
    demandas = _demandas_por_id([o.get("id_demanda") for o in obras])
    resultado = []
    for obra in obras:
        demanda = demandas.get(obra.get("id_demanda"), {})
        fila = {**obra, "demanda": demanda}
        fila["expediente"] = demanda.get("expediente")
        fila["apellido"] = demanda.get("apellido")
        fila["nombre"] = demanda.get("nombre")
        fila["domicilio"] = demanda.get("domicilio")
        fila["barrio"] = demanda.get("barrio")
        fila["contacto"] = demanda.get("contacto")
        fila["prioridad"] = demanda.get("prioridad")
        fila["accion"] = demanda.get("accion")
        fila["tipo_intervencion"] = demanda.get("tipo_intervencion")
        resultado.append(fila)
    return resultado


def listar_obras_asistencia():
    supabase = get_supabase_client()
    obras = (
        supabase.table("obras")
        .select("id_obra,id_demanda,estado_obra,modalidad_ejecucion")
        .in_("estado_obra", ["En ejecucion", "En Ejecucion", "En ejecución", "En Ejecución"])
        .in_("modalidad_ejecucion", ["Cuadrilla HAVITA", "Mixta"])
        .order("id_obra")
        .execute()
    ).data or []

    demandas = {}
    ids = [o.get("id_demanda") for o in obras if o.get("id_demanda") is not None]
    if ids:
        demandas_rows = (
            supabase.table("demandas")
            .select("id_demanda,expediente,apellido,nombre,domicilio,barrio,contacto")
            .in_("id_demanda", ids)
            .execute()
        ).data or []
        demandas = {d.get("id_demanda"): d for d in demandas_rows}

    resultado = []
    for obra in obras:
        demanda = demandas.get(obra.get("id_demanda"), {})
        resultado.append(
            {
                **obra,
                "demanda": demanda,
                "expediente": demanda.get("expediente"),
                "apellido": demanda.get("apellido"),
                "nombre": demanda.get("nombre"),
                "domicilio": demanda.get("domicilio"),
                "barrio": demanda.get("barrio"),
                "contacto": demanda.get("contacto"),
            }
        )
    return resultado


def obtener_obra_con_demanda(id_obra):
    obras = [o for o in listar_obras_con_demanda() if o.get("id_obra") == id_obra]
    return obras[0] if obras else None


def listar_ordenes_por_demanda(id_demanda):
    supabase = get_supabase_client()
    response = (
        supabase.table("ordenes_materiales")
        .select("*")
        .eq("id_demanda", id_demanda)
        .order("n_orden", desc=True)
        .execute()
    )
    return response.data or []


def actualizar_obra(id_obra, data):
    obra_actual = obtener_obra_con_demanda(id_obra)
    if not obra_actual:
        return None

    payload = {k: v for k, v in data.items() if k != "historial_mensaje"}
    estado_nuevo = _limpiar(payload.get("estado_obra")) or _limpiar(obra_actual.get("estado_obra"))

    if estado_nuevo == "Acta firmada" and not _limpiar(obra_actual.get("fecha_acta")):
        payload["fecha_acta"] = _hoy_iso()
    if estado_nuevo == "En ejecución" and not _limpiar(obra_actual.get("fecha_inicio")):
        payload["fecha_inicio"] = _hoy_iso()
    if estado_nuevo == "Ejecutada" and not _limpiar(obra_actual.get("fecha_ejecutada")):
        payload["fecha_ejecutada"] = _hoy_iso()
    mensaje = _limpiar(data.get("historial_mensaje"))
    if not mensaje:
        mensaje = (
            f"Se actualiza obra. Estado: {estado_nuevo}. "
            f"Responsable: {_limpiar(payload.get('responsable_tecnico') or obra_actual.get('responsable_tecnico'))}. "
            f"Observacion: {_limpiar(payload.get('obs_obras') or '')}"
        )
    payload["historial"] = _agregar_historial(obra_actual.get("historial"), mensaje)
    payload["updated_at"] = _ahora_iso()

    supabase = get_supabase_client()
    response = supabase.table("obras").update(payload).eq("id_obra", id_obra).execute()
    return response.data[0] if response.data else None


def agregar_historial_obra(id_obra, mensaje):
    obra = obtener_obra_con_demanda(id_obra)
    if not obra:
        return None
    historial = _agregar_historial(obra.get("historial"), mensaje)
    supabase = get_supabase_client()
    response = (
        supabase.table("obras")
        .update({"historial": historial, "updated_at": _ahora_iso()})
        .eq("id_obra", id_obra)
        .execute()
    )
    return response.data[0] if response.data else None


def actualizar_obs_obras(id_obra, obs_obras):
    supabase = get_supabase_client()
    response = (
        supabase.table("obras")
        .update({"obs_obras": obs_obras, "updated_at": _ahora_iso()})
        .eq("id_obra", id_obra)
        .execute()
    )
    return response.data[0] if response.data else None


def agregar_obs_obras_del_dia(id_obra, mensaje):
    obra = obtener_obra_con_demanda(id_obra)
    if not obra:
        return None

    actual = _limpiar(obra.get("obs_obras"))
    prefijo = f"|| {date.today().strftime('%d/%m/%y')} - "
    msg = _limpiar(mensaje).rstrip(".")

    if actual.startswith(prefijo):
        resto = actual[len(prefijo):]
        partes = resto.split(" || ", 1)
        hoy_texto = partes[0].strip()
        cola = f" || {partes[1]}" if len(partes) > 1 else ""
        nuevo_hoy = f"{hoy_texto}; {msg}." if hoy_texto else f"{msg}."
        nuevo = f"{prefijo}{nuevo_hoy}{cola}"
    else:
        nuevo = f"{prefijo}{msg}."
        if actual:
            nuevo = f"{nuevo} {actual}"

    return actualizar_obs_obras(id_obra, nuevo)
