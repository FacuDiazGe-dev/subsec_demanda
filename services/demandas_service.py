from datetime import date

from services.supabase_client import get_supabase_client


def crear_demanda(datos):
    supabase = get_supabase_client()
    response = supabase.table("demandas").insert(datos).execute()
    return response.data[0] if response.data else None


def listar_demandas_pendientes():
    supabase = get_supabase_client()
    response = (
        supabase.table("demandas")
        .select("*")
        .neq("estado", "Cerrado")
        .is_("fecha_cierre", "null")
        .order("prioridad", desc=False)
        .order("fecha_ingreso", desc=False)
        .execute()
    )
    return response.data or []


def listar_demandas_abiertas():
    supabase = get_supabase_client()
    response = (
        supabase.table("demandas")
        .select("*")
        .neq("estado", "Cerrado")
        .is_("fecha_cierre", "null")
        .order("fecha_ingreso", desc=False)
        .execute()
    )
    return response.data or []


def listar_demandas_finalizadas():
    supabase = get_supabase_client()
    response = (
        supabase.table("demandas")
        .select("*")
        .not_.is_("fecha_cierre", "null")
        .order("fecha_cierre", desc=True)
        .order("prioridad", desc=False)
        .execute()
    )
    return response.data or []


def actualizar_demanda(id_demanda, datos):
    supabase = get_supabase_client()
    response = (
        supabase.table("demandas")
        .update(datos)
        .eq("id_demanda", id_demanda)
        .execute()
    )
    return response.data[0] if response.data else None


def cerrar_demanda(id_demanda):
    return actualizar_demanda(
        id_demanda,
        {
            "estado": "Cerrado",
            "fecha_cierre": date.today().isoformat(),
        },
    )
