from services.supabase_client import get_supabase_client


DESCRIPCION_KEYS = ["descripcion_tarea", "descripcion", "tarea", "nombre_tarea", "detalle"]
UNIDAD_KEYS = ["unidad_tarea", "unidad", "u_medida", "unidad_medida"]


def _first_key(row, candidates):
    for key in candidates:
        if key in row:
            return key
    return None


def listar_tareas_base():
    supabase = get_supabase_client()
    response = supabase.table("listado_tareas").select("*").order("id", desc=False).execute()
    data = response.data or []
    if not data:
        return []

    desc_key = _first_key(data[0], DESCRIPCION_KEYS)
    unidad_key = _first_key(data[0], UNIDAD_KEYS)
    if not desc_key:
        return []

    resultado = []
    for row in data:
        descripcion = str(row.get(desc_key) or "").strip()
        if not descripcion:
            continue
        unidad = str(row.get(unidad_key) or "").strip() if unidad_key else ""
        resultado.append({"descripcion_tarea": descripcion, "unidad_tarea": unidad})
    return resultado

