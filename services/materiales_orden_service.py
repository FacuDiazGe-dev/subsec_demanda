from services.supabase_client import get_supabase_client


def listar_materiales_por_orden(id_orden):
    supabase = get_supabase_client()
    response = (
        supabase.table("mat_orden")
        .select("*")
        .eq("id_orden", id_orden)
        .execute()
    )
    return response.data or []


def crear_material_orden(id_orden, material, cantidad):
    supabase = get_supabase_client()
    payload = {
        "id_orden": id_orden,
        "Material": (material or "").strip(),
        "cantidad": (cantidad or "").strip(),
    }
    response = supabase.table("mat_orden").insert(payload).execute()
    return response.data[0] if response.data else None


def crear_materiales_orden(id_orden, materiales):
    if not materiales:
        return []

    payload = [
        {
            "id_orden": id_orden,
            "Material": material["Material"],
            "cantidad": material.get("cantidad", ""),
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
    supabase = get_supabase_client()
    response = supabase.table("mat_orden").delete().eq("id_orden", id_orden).execute()
    return response.data or []
