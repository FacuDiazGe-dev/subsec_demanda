from datetime import date, datetime

from services.supabase_client import get_supabase_client


def listar_tareas_por_obra(id_obra):
    supabase = get_supabase_client()
    response = (
        supabase.table("tareas_x_obras")
        .select("*")
        .eq("id_obra", id_obra)
        .order("id_tarea", desc=False)
        .execute()
    )
    return response.data or []


def crear_tarea_obra(id_obra, descripcion_tarea, unidad_tarea=None, cant_tarea=None):
    supabase = get_supabase_client()
    payload = {
        "id_obra": id_obra,
        "descripcion_tarea": descripcion_tarea,
        "unidad_tarea": unidad_tarea,
        "cant_tarea": cant_tarea,
        "estado_tarea": False,
        "fecha_actualizacion": None,
    }
    response = supabase.table("tareas_x_obras").insert(payload).execute()
    return response.data[0] if response.data else None


def actualizar_tarea_obra(id_tarea, descripcion_tarea, unidad_tarea=None, cant_tarea=None):
    supabase = get_supabase_client()
    payload = {
        "descripcion_tarea": descripcion_tarea,
        "unidad_tarea": unidad_tarea,
        "cant_tarea": cant_tarea,
        "updated_at": datetime.now().isoformat(),
    }
    response = supabase.table("tareas_x_obras").update(payload).eq("id_tarea", id_tarea).execute()
    return response.data[0] if response.data else None


def actualizar_tarea_cantidad_estado(id_tarea, cant_tarea=None, estado_tarea=None):
    supabase = get_supabase_client()
    payload = {
        "cant_tarea": cant_tarea,
        "fecha_actualizacion": date.today().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    if estado_tarea is not None:
        payload["estado_tarea"] = bool(estado_tarea)
    response = supabase.table("tareas_x_obras").update(payload).eq("id_tarea", id_tarea).execute()
    return response.data[0] if response.data else None


def eliminar_tarea_obra(id_tarea):
    supabase = get_supabase_client()
    response = supabase.table("tareas_x_obras").delete().eq("id_tarea", id_tarea).execute()
    return response.data or []
