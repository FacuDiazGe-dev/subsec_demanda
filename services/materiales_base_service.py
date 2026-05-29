from services.supabase_client import get_supabase_client


def listar_materiales_base_activos():
    supabase = get_supabase_client()
    response = (
        supabase.table("materiales_base")
        .select("id_material,tipo,material,unidad")
        .eq("activo", True)
        .order("material")
        .execute()
    )
    return response.data or []


def buscar_materiales_base(texto_busqueda, limite=10):
    texto_busqueda = (texto_busqueda or "").strip()
    if not texto_busqueda:
        return []

    supabase = get_supabase_client()
    response = (
        supabase.table("materiales_base")
        .select("id_material,tipo,material,unidad")
        .eq("activo", True)
        .ilike("material", f"%{texto_busqueda}%")
        .order("material")
        .limit(limite)
        .execute()
    )
    return response.data or []
