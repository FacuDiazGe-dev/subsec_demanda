from datetime import datetime

from services.supabase_client import get_supabase_client

TABLAS_NOTAS = ["notas_rapidas_obras", "notas_rapidas_obra"]


def _ahora_iso():
    return datetime.now().isoformat()


def _es_error_tabla_no_encontrada(error):
    texto = str(error or "").lower()
    return "could not find the table" in texto or "pgrst205" in texto


def _insert_con_fallback(payload):
    supabase = get_supabase_client()
    ultimo_error = None
    for tabla in TABLAS_NOTAS:
        try:
            response = supabase.table(tabla).insert(payload).execute()
            return response.data[0] if response.data else None
        except Exception as error:
            ultimo_error = error
            if not _es_error_tabla_no_encontrada(error):
                raise
    raise ultimo_error


def _select_con_fallback(estado=None, id_obra=None):
    supabase = get_supabase_client()
    ultimo_error = None
    for tabla in TABLAS_NOTAS:
        try:
            query = supabase.table(tabla).select("*")
            if estado:
                query = query.eq("estado_nota", estado)
            if id_obra is not None:
                query = query.eq("id_obra", id_obra)
            response = query.order("fecha_nota", desc=True).order("id_nota", desc=True).execute()
            return response.data or []
        except Exception as error:
            ultimo_error = error
            if not _es_error_tabla_no_encontrada(error):
                raise
    raise ultimo_error


def _update_con_fallback(id_nota, payload):
    supabase = get_supabase_client()
    ultimo_error = None
    for tabla in TABLAS_NOTAS:
        try:
            response = supabase.table(tabla).update(payload).eq("id_nota", id_nota).execute()
            return response.data[0] if response.data else None
        except Exception as error:
            ultimo_error = error
            if not _es_error_tabla_no_encontrada(error):
                raise
    raise ultimo_error


def crear_nota_rapida(data):
    payload = {
        "id_obra": data.get("id_obra"),
        "fecha_nota": data.get("fecha_nota"),
        "responsable_tecnico": data.get("responsable_tecnico"),
        "nota": data.get("nota"),
        "estado_nota": data.get("estado_nota") or "Pendiente",
    }
    return _insert_con_fallback(payload)


def listar_notas_rapidas(estado=None, id_obra=None):
    return _select_con_fallback(estado=estado, id_obra=id_obra)


def actualizar_nota_rapida(id_nota, data):
    payload = dict(data or {})
    payload["updated_at"] = _ahora_iso()
    return _update_con_fallback(id_nota, payload)


def contar_notas_pendientes_por_obra():
    notas = listar_notas_rapidas(estado="Pendiente")
    conteo = {}
    for nota in notas:
        id_obra = nota.get("id_obra")
        if id_obra is None:
            continue
        conteo[id_obra] = conteo.get(id_obra, 0) + 1
    return conteo
