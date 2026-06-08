from datetime import date, datetime

from services.supabase_client import get_supabase_client


ESTADOS_CIERRE = {"Entregado", "Cancelado", "Cerrado"}


def fecha_historial():
    return date.today().strftime("%d/%m/%Y")


def crear_historial_inicial(estado, instrucciones_tarea):
    return f"{fecha_historial()} - Orden creada. Estado: {estado}. Tarea: {instrucciones_tarea}"


def agregar_historial(historial_actual, entrada):
    historial_actual = (historial_actual or "").strip()
    entrada = (entrada or "").strip()
    if not entrada:
        return historial_actual or None
    if historial_actual:
        return f"{entrada} || {historial_actual}"
    return entrada


def crear_orden_material(data):
    supabase = get_supabase_client()
    estado = data.get("estado") or "Pedido entrega"
    instrucciones = (data.get("instrucciones_tarea") or "").strip()
    historial = data.get("historial") or crear_historial_inicial(estado, instrucciones)

    payload = {
        "fecha_emision": data.get("fecha_emision") or date.today().isoformat(),
        "id_demanda": data.get("id_demanda"),
        "origen": data.get("origen"),
        "estado": estado,
        "instrucciones_tarea": instrucciones,
        "historial": historial,
    }

    if estado in ESTADOS_CIERRE:
        payload["fecha_cierre"] = date.today().isoformat()

    response = supabase.table("ordenes_materiales").insert(payload).execute()
    return response.data[0] if response.data else None


def listar_ordenes_pendientes():
    supabase = get_supabase_client()
    response = (
        supabase.table("ordenes_materiales")
        .select("*")
        .is_("fecha_cierre", "null")
        .order("n_orden", desc=True)
        .execute()
    )
    return [orden for orden in response.data or [] if orden.get("estado") not in ESTADOS_CIERRE]


def listar_ordenes_todas():
    supabase = get_supabase_client()
    response = (
        supabase.table("ordenes_materiales")
        .select("*")
        .order("n_orden", desc=True)
        .execute()
    )
    return response.data or []


def _demandas_por_id(ids_demanda):
    ids = [id_demanda for id_demanda in ids_demanda if id_demanda is not None]
    if not ids:
        return {}

    supabase = get_supabase_client()
    response = supabase.table("demandas").select("*").in_("id_demanda", ids).execute()
    return {demanda["id_demanda"]: demanda for demanda in response.data or []}


def _unir_ordenes_con_demandas(ordenes):
    demandas = _demandas_por_id([orden.get("id_demanda") for orden in ordenes])
    resultado = []
    for orden in ordenes:
        demanda = demandas.get(orden.get("id_demanda"), {})
        fila = {**orden}
        fila["demanda"] = demanda
        fila["expediente"] = demanda.get("expediente")
        fila["apellido"] = demanda.get("apellido")
        fila["nombre"] = demanda.get("nombre")
        fila["dni"] = demanda.get("dni")
        fila["domicilio"] = demanda.get("domicilio")
        fila["barrio"] = demanda.get("barrio")
        fila["contacto"] = demanda.get("contacto")
        fila["prioridad_demanda"] = demanda.get("prioridad")
        fila["accion_demanda"] = demanda.get("accion")
        fila["estado_demanda"] = demanda.get("estado")
        fila["responsable_demanda"] = demanda.get("responsable")
        resultado.append(fila)
    return resultado


def listar_ordenes_con_demanda(incluir_cerradas=False):
    if incluir_cerradas:
        ordenes = listar_ordenes_todas()
    else:
        ordenes = listar_ordenes_pendientes()
    return _unir_ordenes_con_demandas(ordenes)


def obtener_orden_por_id(n_orden):
    supabase = get_supabase_client()
    response = (
        supabase.table("ordenes_materiales")
        .select("*")
        .eq("n_orden", n_orden)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return _unir_ordenes_con_demandas(response.data)[0]


def actualizar_orden_material(n_orden, estado, comentario, fecha_entrega=None):
    orden = obtener_orden_por_id(n_orden)
    if not orden:
        return None
    if orden.get("fecha_cierre") or orden.get("estado") in ESTADOS_CIERRE:
        raise ValueError("La orden ya esta cerrada y no se puede editar.")

    estado_anterior = orden.get("estado")
    comentario = (comentario or "").strip()
    partes = []
    if comentario:
        partes.append(comentario)
    if estado != estado_anterior:
        partes.append(f"Estado: {estado}")

    cerrar = estado in ESTADOS_CIERRE
    if cerrar:
        partes.append("Cierre de orden")

    entrada = f"{fecha_historial()} - {'; '.join(partes) if partes else f'Estado: {estado}'}"
    payload = {
        "estado": estado,
        "historial": agregar_historial(orden.get("historial"), entrada),
        "updated_at": datetime.now().isoformat(),
    }
    if fecha_entrega is not None:
        payload["fecha_entrega"] = fecha_entrega

    if cerrar:
        payload["fecha_cierre"] = date.today().isoformat()

    supabase = get_supabase_client()
    response = (
        supabase.table("ordenes_materiales")
        .update(payload)
        .eq("n_orden", n_orden)
        .execute()
    )
    return response.data[0] if response.data else None


def actualizar_orden_detalle(n_orden, estado, instrucciones_tarea):
    orden = obtener_orden_por_id(n_orden)
    if not orden:
        return None
    if orden.get("fecha_cierre") or orden.get("estado") in ESTADOS_CIERRE:
        raise ValueError("La orden ya esta cerrada y no se puede editar.")

    estado_anterior = orden.get("estado")
    instrucciones_anteriores = (orden.get("instrucciones_tarea") or "").strip()
    instrucciones_nuevas = (instrucciones_tarea or "").strip()

    partes = []
    if estado != estado_anterior:
        partes.append(f"Estado: {estado_anterior} -> {estado}")
    if instrucciones_nuevas != instrucciones_anteriores:
        partes.append("Instruccion actualizada")
    partes.append("Materiales actualizados")

    cerrar = estado in ESTADOS_CIERRE
    if cerrar:
        partes.append("Cierre de orden")

    payload = {
        "estado": estado,
        "instrucciones_tarea": instrucciones_nuevas,
        "historial": agregar_historial(orden.get("historial"), f"{fecha_historial()} - {'; '.join(partes)}"),
        "updated_at": datetime.now().isoformat(),
    }
    if cerrar:
        payload["fecha_cierre"] = date.today().isoformat()
    else:
        payload["fecha_cierre"] = None

    supabase = get_supabase_client()
    response = (
        supabase.table("ordenes_materiales")
        .update(payload)
        .eq("n_orden", n_orden)
        .execute()
    )
    return response.data[0] if response.data else None


def eliminar_orden_material(n_orden):
    supabase = get_supabase_client()
    response = (
        supabase.table("ordenes_materiales")
        .delete()
        .eq("n_orden", n_orden)
        .execute()
    )
    return response.data or []


def obtener_datos_pdf_orden(n_orden):
    from services.materiales_orden_service import listar_materiales_por_orden

    orden = obtener_orden_por_id(n_orden)
    if not orden:
        return None

    return {
        "orden": orden,
        "demanda": orden.get("demanda") or {},
        "materiales": listar_materiales_por_orden(n_orden),
    }
