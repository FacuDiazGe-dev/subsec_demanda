from datetime import datetime

from services.obras_service import obtener_obra_con_demanda
from services.supabase_client import get_supabase_client
from postgrest.exceptions import APIError


def _texto(valor):
    return "" if valor is None else str(valor)


def _limpiar(valor):
    return _texto(valor).strip()


def _historial_entry(data):
    fecha = _limpiar(data.get("fecha_visita"))[:10]
    fecha_fmt = fecha.split("-")
    fecha_txt = f"{fecha_fmt[2]}/{fecha_fmt[1]}/{fecha_fmt[0]}" if len(fecha_fmt) == 3 else datetime.now().strftime("%d/%m/%Y")
    msg = (
        f"Seguimiento tecnico cargado por {_limpiar(data.get('responsable_tecnico'))}. "
        f"Tareas realizadas: {_limpiar(data.get('tareas_realizadas'))}; "
        f"Proxima semana: {_limpiar(data.get('tareas_semana_siguiente'))}; "
        f"Observaciones: {_limpiar(data.get('observaciones_tecnicas'))}"
    )
    if data.get("requiere_accion"):
        msg = f"{msg}. Requiere accion: {_limpiar(data.get('accion_requerida'))}"
    return f"{fecha_txt} - {msg}"


_TABLA_SEGUIMIENTO_CACHE = None
_TABLAS_CANDIDATAS = ["seguimiento_obra", "seguimiento_obras"]


def _tabla_seguimiento():
    global _TABLA_SEGUIMIENTO_CACHE
    if _TABLA_SEGUIMIENTO_CACHE:
        return _TABLA_SEGUIMIENTO_CACHE
    supabase = get_supabase_client()
    for tabla in _TABLAS_CANDIDATAS:
        try:
            supabase.table(tabla).select("id_seguimiento").limit(1).execute()
            _TABLA_SEGUIMIENTO_CACHE = tabla
            return tabla
        except APIError:
            continue
    return None


def _es_tabla_inexistente(error):
    return isinstance(error, APIError) and getattr(error, "code", None) == "PGRST205"


def _tabla_valida_o_none(tabla):
    if not tabla:
        return None
    supabase = get_supabase_client()
    try:
        supabase.table(tabla).select("id_seguimiento").limit(1).execute()
        return tabla
    except APIError:
        return None


def crear_seguimiento(data):
    global _TABLA_SEGUIMIENTO_CACHE
    supabase = get_supabase_client()
    candidatas = []
    cache = _tabla_valida_o_none(_TABLA_SEGUIMIENTO_CACHE)
    if cache:
        candidatas.append(cache)
    for t in _TABLAS_CANDIDATAS:
        if t not in candidatas:
            candidatas.append(t)

    ultimo_error = None
    for tabla in candidatas:
        try:
            response = supabase.table(tabla).insert(data).execute()
            _TABLA_SEGUIMIENTO_CACHE = tabla
            return response.data[0] if response.data else None
        except APIError as error:
            ultimo_error = error
            if not _es_tabla_inexistente(error):
                raise
            continue
    if ultimo_error:
        raise ultimo_error
    return None


def listar_seguimientos_por_obra(id_obra):
    global _TABLA_SEGUIMIENTO_CACHE
    supabase = get_supabase_client()
    candidatas = []
    cache = _tabla_valida_o_none(_TABLA_SEGUIMIENTO_CACHE)
    if cache:
        candidatas.append(cache)
    for t in _TABLAS_CANDIDATAS:
        if t not in candidatas:
            candidatas.append(t)

    ultimo_error = None
    for tabla in candidatas:
        try:
            response = (
                supabase.table(tabla)
                .select("*")
                .eq("id_obra", id_obra)
                .order("fecha_visita", desc=True)
                .execute()
            )
            _TABLA_SEGUIMIENTO_CACHE = tabla
            return response.data or []
        except APIError as error:
            ultimo_error = error
            if not _es_tabla_inexistente(error):
                raise
            continue
    if ultimo_error:
        raise ultimo_error
    return []


def cargar_seguimiento_y_actualizar_obra(data):
    from services.obras_service import actualizar_obra

    seg = crear_seguimiento(data)
    if not seg:
        return None

    obra = obtener_obra_con_demanda(data.get("id_obra"))
    historial_actual = _limpiar(obra.get("historial")) if obra else ""
    entrada = _historial_entry(data)
    historial = f"{entrada} || {historial_actual}" if historial_actual else entrada

    actualizar_obra(
        data.get("id_obra"),
        {
            "ultima_actualizacion_semanal": data.get("fecha_visita"),
            "responsable_tecnico": data.get("responsable_tecnico"),
            "obs_obras": data.get("observaciones_tecnicas"),
            "historial": historial,
            "updated_at": datetime.now().isoformat(),
        },
    )
    return seg
