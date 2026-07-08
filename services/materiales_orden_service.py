from services.supabase_client import get_supabase_client


def _normalizar_id_orden(id_orden):
    try:
        return int(id_orden)
    except (TypeError, ValueError):
        return id_orden


def listar_materiales_por_orden(id_orden):
    id_orden = _normalizar_id_orden(id_orden)
    supabase = get_supabase_client()
    response = (
        supabase.table("mat_orden")
        .select("*")
        .eq("id_orden", id_orden)
        .execute()
    )
    return response.data or []


def listar_materiales_por_ordenes(ids_ordenes):
    ids = []
    for id_orden in ids_ordenes or []:
        normalizado = _normalizar_id_orden(id_orden)
        if normalizado is None or normalizado in ids:
            continue
        ids.append(normalizado)

    if not ids:
        return {}

    supabase = get_supabase_client()
    response = (
        supabase.table("mat_orden")
        .select("*")
        .in_("id_orden", ids)
        .execute()
    )

    agrupados = {id_orden: [] for id_orden in ids}
    for fila in response.data or []:
        id_orden = _normalizar_id_orden(fila.get("id_orden"))
        agrupados.setdefault(id_orden, []).append(fila)
    return agrupados


def crear_material_orden(id_orden, material, cantidad):
    id_orden = _normalizar_id_orden(id_orden)
    supabase = get_supabase_client()
    payload = {
        "id_orden": id_orden,
        "Material": (material or "").strip(),
        "cantidad": (cantidad or "").strip(),
    }
    response = supabase.table("mat_orden").insert(payload).execute()
    return response.data[0] if response.data else None


def crear_materiales_orden(id_orden, materiales):
    id_orden = _normalizar_id_orden(id_orden)
    if not materiales:
        return []

    payload = [
        {
            "id_orden": id_orden,
            "Material": (material.get("Material") or "").strip(),
            "cantidad": str(material.get("cantidad", "") or "").strip(),
        }
        for material in materiales
        if material.get("Material")
    ]
    if not payload:
        return []

    supabase = get_supabase_client()
    response = supabase.table("mat_orden").insert(payload).execute()
    return response.data or []


def eliminar_materiales_por_orden(id_orden):
    id_orden = _normalizar_id_orden(id_orden)
    supabase = get_supabase_client()
    response = supabase.table("mat_orden").delete().eq("id_orden", id_orden).execute()
    return response.data or []


def reemplazar_materiales_orden(id_orden, materiales):
    """Reemplaza el listado completo de materiales de una orden."""
    id_orden = _normalizar_id_orden(id_orden)
    eliminar_materiales_por_orden(id_orden)
    restantes = listar_materiales_por_orden(id_orden)
    if restantes:
        eliminar_materiales_por_orden(id_orden)
        restantes = listar_materiales_por_orden(id_orden)
    if restantes:
        raise RuntimeError(
            f"No se pudieron borrar los materiales anteriores de la orden {id_orden}. "
            "No se insertaron materiales nuevos para evitar duplicados."
        )
    if not materiales:
        return []
    return crear_materiales_orden(id_orden, materiales)
