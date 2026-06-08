from datetime import date, datetime

from services.estados_service import normalizar_estado_cierre
from services.materiales_orden_service import crear_materiales_orden, listar_materiales_por_orden
from services.supabase_client import get_supabase_client


ESTADOS_PEDIDOS_DEPOSITO = {"Pedido entrega", "Pedido retiro", "En deposito", "En depósito", "Pedido"}
ESTADOS_PROGRAMADOS_DEPOSITO = {"Pendiente de entrega", "Pendiente de retiro"}
ESTADOS_ORDEN_DEPOSITO = {
    "Pedido entrega",
    "Pedido retiro",
    "Pendiente de entrega",
    "Pendiente de retiro",
    "En deposito",
    "En depósito",
    "Entregado",
    "Entregado parcial",
    "En deposito parcial",
    "En depósito parcial",
    "Cancelado",
    "Cerrado",
    "Pedido",
}


def _texto(valor):
    return "" if valor is None else str(valor)


def _limpiar(valor):
    return _texto(valor).strip()


def _hoy_iso():
    return date.today().isoformat()


def _hoy_ddmmyyyy():
    return date.today().strftime("%d/%m/%Y")


def agregar_historial(historial_actual, mensaje):
    historial_actual = _limpiar(historial_actual)
    entrada = f"{_hoy_ddmmyyyy()} - {_limpiar(mensaje)}"
    if historial_actual:
        return f"{entrada} || {historial_actual}"
    return entrada


def _demandas_por_id(ids_demanda):
    ids = [id_demanda for id_demanda in ids_demanda if id_demanda is not None]
    if not ids:
        return {}
    supabase = get_supabase_client()
    response = supabase.table("demandas").select("*").in_("id_demanda", ids).execute()
    return {demanda["id_demanda"]: demanda for demanda in response.data or []}


def _prioridad_num(prioridad):
    texto = _limpiar(prioridad)
    if not texto:
        return 99
    prefijo = texto.split("-")[0].strip()
    try:
        return int(prefijo)
    except ValueError:
        return 99


def _enriquecer_ordenes(ordenes, incluir_materiales=False):
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
        fila["prioridad"] = demanda.get("prioridad")
        fila["accion"] = demanda.get("accion")
        fila["responsable"] = demanda.get("responsable")
        fila["prioridad_num"] = _prioridad_num(demanda.get("prioridad"))
        if incluir_materiales:
            fila["materiales"] = listar_materiales_por_orden(orden.get("n_orden"))
        resultado.append(fila)
    return resultado


def listar_pedidos_deposito():
    supabase = get_supabase_client()
    response = (
        supabase.table("ordenes_materiales")
        .select("*")
        .in_("estado", list(ESTADOS_PEDIDOS_DEPOSITO))
        .is_("fecha_cierre", "null")
        .execute()
    )
    ordenes = _enriquecer_ordenes(response.data or [], incluir_materiales=False)
    return sorted(
        ordenes,
        key=lambda fila: (
            fila.get("prioridad_num", 99),
            _limpiar(fila.get("fecha_emision")),
        ),
    )


def listar_programados_deposito():
    supabase = get_supabase_client()
    response = (
        supabase.table("ordenes_materiales")
        .select("*")
        .in_("estado", list(ESTADOS_PROGRAMADOS_DEPOSITO))
        .is_("fecha_cierre", "null")
        .execute()
    )
    ordenes = _enriquecer_ordenes(response.data or [], incluir_materiales=True)
    return sorted(
        ordenes,
        key=lambda fila: (
            _limpiar(fila.get("fecha_entrega")),
            fila.get("prioridad_num", 99),
            fila.get("n_orden") or 0,
        ),
    )


def listar_ordenes_por_estados(estados):
    estados_norm = {_limpiar(estado).lower() for estado in estados if _limpiar(estado)}
    if "cerrado" in estados_norm:
        estados_norm.add("entregado")

    supabase = get_supabase_client()
    response = supabase.table("ordenes_materiales").select("*").order("n_orden", desc=True).execute()
    ordenes = response.data or []
    filtradas = [o for o in ordenes if _limpiar(o.get("estado")).lower() in estados_norm]
    resultado = _enriquecer_ordenes(filtradas, incluir_materiales=False)
    for fila in resultado:
        fila["estado_global"] = normalizar_estado_cierre(fila.get("estado"), vista="global")
    return resultado


def obtener_orden_deposito(n_orden):
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
    return _enriquecer_ordenes(response.data, incluir_materiales=True)[0]


def _actualizar_orden(n_orden, payload):
    payload["updated_at"] = datetime.now().isoformat()
    supabase = get_supabase_client()
    response = (
        supabase.table("ordenes_materiales")
        .update(payload)
        .eq("n_orden", n_orden)
        .execute()
    )
    return response.data[0] if response.data else None


def _materiales_faltantes(materiales, seleccionados_idx):
    if not materiales:
        return []
    seleccion = set(seleccionados_idx or [])
    faltantes = []
    for idx, material in enumerate(materiales):
        if idx in seleccion:
            continue
        nombre = _limpiar(material.get("Material"))
        cantidad = _limpiar(material.get("cantidad"))
        if nombre:
            faltantes.append({"Material": nombre, "cantidad": cantidad})
    return faltantes


def _limpiar_materiales_faltantes(materiales_faltantes):
    resultado = []
    for material in materiales_faltantes or []:
        nombre = _limpiar(material.get("Material"))
        cantidad = _limpiar(material.get("cantidad"))
        if nombre and cantidad not in {"", "0", "0.0"}:
            resultado.append({"Material": nombre, "cantidad": cantidad})
    return resultado


def programar_ordenes_deposito(ids_ordenes, fecha_entrega):
    if not ids_ordenes:
        return []

    fecha_visible = datetime.strptime(fecha_entrega, "%Y-%m-%d").strftime("%d/%m/%Y")
    actualizadas = []
    for n_orden in ids_ordenes:
        orden = obtener_orden_deposito(n_orden)
        if not orden:
            continue

        estado_actual = _limpiar(orden.get("estado"))
        if estado_actual == "Pedido retiro":
            nuevo_estado = "Pendiente de retiro"
        elif estado_actual in {"Pedido entrega", "En deposito", "En depósito", "Pedido"}:
            nuevo_estado = "Pendiente de entrega"
        else:
            continue

        mensaje = (
            f"Orden programada desde Deposito. Estado: {nuevo_estado}. "
            f"Fecha estimada: {fecha_visible}."
        )
        actualizadas.append(
            _actualizar_orden(
                n_orden,
                {
                    "estado": nuevo_estado,
                    "fecha_entrega": fecha_entrega,
                    "historial": agregar_historial(orden.get("historial"), mensaje),
                    "fecha_cierre": None,
                },
            )
        )
    return [fila for fila in actualizadas if fila]


def _crear_orden_por_parcialidad(
    orden_original,
    estado_nuevo,
    instrucciones_tarea,
    historial_mensaje,
    materiales_faltantes=None,
    agregar_nota_manual=False,
):
    supabase = get_supabase_client()
    payload = {
        "fecha_emision": _hoy_iso(),
        "id_demanda": orden_original.get("id_demanda"),
        "origen": orden_original.get("origen"),
        "estado": estado_nuevo,
        "fecha_entrega": None,
        "fecha_cierre": None,
        "instrucciones_tarea": instrucciones_tarea,
        "historial": f"{_hoy_ddmmyyyy()} - {historial_mensaje}",
    }
    response = supabase.table("ordenes_materiales").insert(payload).execute()
    if not response.data:
        return None
    nueva = response.data[0]
    n_orden_nueva = nueva.get("n_orden")
    if n_orden_nueva is None:
        return nueva
    nueva = _actualizar_orden(
        n_orden_nueva,
        {
            "estado": estado_nuevo,
            "fecha_entrega": None,
            "fecha_cierre": None,
        },
    )
    if materiales_faltantes:
        crear_materiales_orden(n_orden_nueva, materiales_faltantes)
    elif agregar_nota_manual:
        historial_actual = nueva.get("historial") if nueva else payload.get("historial")
        _actualizar_orden(
            n_orden_nueva,
            {
                "historial": agregar_historial(
                    historial_actual,
                    "No se seleccionaron materiales entregados/retirados. Requiere carga manual de materiales faltantes.",
                )
            },
        )
    return nueva


def marcar_entregado_desde_programados(
    n_orden,
    parcial=False,
    materiales_seleccionados_idx=None,
    materiales_faltantes=None,
):
    orden = obtener_orden_deposito(n_orden)
    if not orden:
        return None, None

    estado_actual = _limpiar(orden.get("estado"))
    n_original = orden.get("n_orden")

    if estado_actual == "Pendiente de entrega":
        if not parcial:
            mensaje = "Entrega completada desde Deposito. Estado: Entregado."
            actualizada = _actualizar_orden(
                n_orden,
                {
                    "estado": "Entregado",
                    "fecha_entrega": _hoy_iso(),
                    "fecha_cierre": _hoy_iso(),
                    "historial": agregar_historial(orden.get("historial"), mensaje),
                },
            )
            return actualizada, None

        mensaje = (
            "Entrega parcial realizada desde Deposito. "
            "Se genera nueva orden para completar pendientes."
        )
        actualizada = _actualizar_orden(
            n_orden,
            {
                "estado": "Entregado parcial",
                "fecha_entrega": _hoy_iso(),
                "fecha_cierre": _hoy_iso(),
                "historial": agregar_historial(orden.get("historial"), mensaje),
            },
        )
        faltantes = _limpiar_materiales_faltantes(materiales_faltantes)
        if not faltantes and materiales_seleccionados_idx:
            faltantes = _materiales_faltantes(orden.get("materiales") or [], materiales_seleccionados_idx)
        nueva = _crear_orden_por_parcialidad(
            orden,
            "Pedido entrega",
            (
                f"Orden generada por entrega parcial de la Orden N° {n_original}. "
                "Cargar manualmente materiales faltantes."
            ),
            (
                f"Orden generada automaticamente por entrega parcial de la Orden N° {n_original}. "
                "Cargar o verificar materiales faltantes."
            ),
            materiales_faltantes=faltantes,
            agregar_nota_manual=not bool(faltantes),
        )
        return actualizada, nueva

    if estado_actual == "Pendiente de retiro":
        if not parcial:
            mensaje = "Retiro completado desde Deposito. Estado: Entregado."
            actualizada = _actualizar_orden(
                n_orden,
                {
                    "estado": "Entregado",
                    "fecha_entrega": _hoy_iso(),
                    "fecha_cierre": _hoy_iso(),
                    "historial": agregar_historial(orden.get("historial"), mensaje),
                },
            )
            return actualizada, None

        mensaje = (
            "Entrega/retiro parcial realizado desde Deposito. "
            "Se genera nueva orden para completar pendientes."
        )
        actualizada = _actualizar_orden(
            n_orden,
            {
                "estado": "Entregado parcial",
                "fecha_entrega": _hoy_iso(),
                "fecha_cierre": _hoy_iso(),
                "historial": agregar_historial(orden.get("historial"), mensaje),
            },
        )
        faltantes = _limpiar_materiales_faltantes(materiales_faltantes)
        if not faltantes and materiales_seleccionados_idx:
            faltantes = _materiales_faltantes(orden.get("materiales") or [], materiales_seleccionados_idx)
        nueva = _crear_orden_por_parcialidad(
            orden,
            "Pedido retiro",
            (
                f"Orden generada por retiro parcial de la Orden N° {n_original}. "
                "Cargar manualmente materiales faltantes."
            ),
            (
                f"Orden generada automaticamente por retiro parcial de la Orden N° {n_original}. "
                "Cargar o verificar materiales faltantes para nuevo retiro."
            ),
            materiales_faltantes=faltantes,
            agregar_nota_manual=not bool(faltantes),
        )
        return actualizada, nueva

    return None, None


def marcar_a_deposito_desde_programados(
    n_orden,
    parcial=False,
    materiales_seleccionados_idx=None,
    materiales_faltantes=None,
):
    orden = obtener_orden_deposito(n_orden)
    if not orden:
        return None, None

    estado_actual = _limpiar(orden.get("estado"))
    if estado_actual != "Pendiente de retiro":
        return None, None

    n_original = orden.get("n_orden")
    if not parcial:
        mensaje = "Retiro completado. Materiales ingresados a deposito. Estado: En deposito."
        actualizada = _actualizar_orden(
            n_orden,
            {
                "estado": "En deposito",
                "fecha_entrega": _hoy_iso(),
                "fecha_cierre": None,
                "historial": agregar_historial(orden.get("historial"), mensaje),
            },
        )
        return actualizada, None

    mensaje = (
        "Retiro parcial a deposito realizado. Estado: En deposito parcial. "
        "Se genera nueva orden para completar pendientes."
    )
    actualizada = _actualizar_orden(
        n_orden,
        {
            "estado": "En deposito parcial",
            "fecha_entrega": _hoy_iso(),
            "fecha_cierre": None,
            "historial": agregar_historial(orden.get("historial"), mensaje),
        },
    )
    faltantes = _limpiar_materiales_faltantes(materiales_faltantes)
    if not faltantes and materiales_seleccionados_idx:
        faltantes = _materiales_faltantes(orden.get("materiales") or [], materiales_seleccionados_idx)
    nueva = _crear_orden_por_parcialidad(
        orden,
        "Pedido retiro",
        (
            f"Orden generada por retiro parcial a deposito de la Orden N° {n_original}. "
            "Cargar manualmente materiales faltantes para nuevo retiro."
        ),
        (
            f"Orden generada automaticamente por retiro parcial a deposito de la Orden N° {n_original}. "
            "Cargar manualmente materiales faltantes para nuevo retiro."
        ),
        materiales_faltantes=faltantes,
        agregar_nota_manual=not bool(faltantes),
    )
    return actualizada, nueva


def marcar_no_realizado(n_orden):
    orden = obtener_orden_deposito(n_orden)
    if not orden:
        return None

    estado_actual = _limpiar(orden.get("estado"))
    if estado_actual == "Pendiente de retiro":
        nuevo_estado = "Pedido retiro"
        mensaje = "No se pudo realizar el retiro programado. La orden vuelve a estado Pedido retiro."
    else:
        nuevo_estado = "En deposito"
        mensaje = "No se pudo realizar la entrega programada. La orden vuelve a estado En deposito."

    return _actualizar_orden(
        n_orden,
        {
            "estado": nuevo_estado,
            "fecha_entrega": None,
            "fecha_cierre": None,
            "historial": agregar_historial(orden.get("historial"), mensaje),
        },
    )
