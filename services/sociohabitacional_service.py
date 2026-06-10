from datetime import date, datetime
import unicodedata
from services.supabase_client import get_supabase_client

ACCIONES_SOCIO = ["Visitar", "Hacer nota", "Informe", "Actuacion", "Otro", "Seguimiento"]
ESTADOS_REGISTRADOS = ["Para visita", "Programada", "Visitada", "Informe", "Para Hacer", "En elaboración", "Presentado"]

ESTADO_PARA_VISITA = "Para visita"
ESTADO_PROGRAMADA = "Programada"
ESTADO_VISITADA = "Visitada"
ESTADO_INFORMADA = "Informe"

def _limpiar(v):
    return str(v).strip() if v is not None else ""


def _normalizar(v):
    s = _limpiar(v).lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))

def _prioridad_rank(p):
    p = _limpiar(p).lower()
    if p.startswith("1"): return 1
    if p.startswith("2"): return 2
    if p.startswith("3"): return 3
    if p.startswith("4"): return 4
    if p.startswith("5"): return 5
    return 9

def listar_demandas_sociohabitacionales():
    """Trae todas las demandas de tipo sociohabitacional que no estén cerradas."""
    supabase = get_supabase_client()
    response = (
        supabase.table("demandas")
        .select("*, visitas(est_soc, est_tec)")
        .neq("estado", "Cerrado")
        .is_("fecha_cierre", "null")
        .execute()
    )
    data = response.data or []
    acciones_ok = {"visitar", "hacer nota", "informe", "actuacion", "otro", "seguimiento"}
    data = [d for d in data if _normalizar(d.get("accion")) in acciones_ok]
    
    # Aplanamos los datos de la visita si existen para facilitar el acceso en la UI
    for d in data:
        v_list = d.get("visitas", [])
        if v_list and isinstance(v_list, list):
            d["est_soc"] = v_list[0].get("est_soc")
            d["est_tec"] = v_list[0].get("est_tec")
            
    return data

def filtrar_socio_habitacional(demandas, bloque="registradas"):
    """Separa las demandas según si ya fueron validadas o están en estado inicial."""
    if bloque == "registradas":
        filtradas = [d for d in demandas if _limpiar(d.get("estado")) in ESTADOS_REGISTRADOS]
    else:
        # Pendientes: estado Ingresada o Pendiente
        filtradas = [d for d in demandas if _limpiar(d.get("estado")) in ["Ingresada", "Pendiente"]]
    
    # Ordenar por prioridad y luego por ID
    return sorted(filtradas, key=lambda x: (_prioridad_rank(x.get("prioridad")), x.get("id_demanda") or 0))

def estado_sugerido_por_tipo(accion):
    """Mapeo lógico según el tipo de demanda."""
    accion = _limpiar(accion)
    if "Visitar" in accion:
        return "Para visita", "Realizar visita sociohabitacional."
    return "Para Hacer", "Revisar caso y definir acción correspondiente."

def obtener_estados_por_accion(accion):
    """Devuelve la lista de estados posibles para una acción sociohabitacional."""
    accion = _limpiar(accion)
    if "Visitar" in accion: 
        return ["Pendiente", "Para visita", "Visita programada", "Visita Social", "Visita Tecnica", "Visitado", "Informe Social", "Informe Tecnico", "Completo", "Cerrado"]
    if any(x in accion for x in ["Nota", "Actuacion", "Informe", "Otro", "Seguimiento"]):
        return ["Pendiente", "Para Hacer", "En elaboración", "Presentado", "Cerrado"]
    
    # Fallback para otros tipos no sociales
    return ["Ingresada", "En gestion", "Resuelta", "Entregado", "Cerrado"]

def actualizar_estado_demanda_social(id_demanda, nuevo_estado):
    """Actualiza el estado de la demanda y registra el cambio en el historial."""
    supabase = get_supabase_client()
    # Obtener historial previo
    actual_res = supabase.table("demandas").select("observaciones").eq("id_demanda", id_demanda).single().execute()
    obs_previa = _limpiar(actual_res.data.get("observaciones")) if actual_res.data else ""
    hoy = date.today().strftime("%d/%m/%y")
    entrada_historial = f"|| {hoy} - Cambio de estado manual: {nuevo_estado}."
    nuevas_obs = f"{entrada_historial} {obs_previa}".strip()
    payload = {
        "estado": nuevo_estado,
        "observaciones": nuevas_obs,
        "updated_at": datetime.now().isoformat()
    }
    if nuevo_estado in ["Cerrado", "Entregado"]:
        payload["fecha_cierre"] = date.today().isoformat()
    return supabase.table("demandas").update(payload).eq("id_demanda", id_demanda).execute()

def existe_visita_para_demanda(id_demanda):
    """Verifica si ya existe una visita vinculada a la demanda."""
    supabase = get_supabase_client()
    response = supabase.table("visitas").select("id_visit").eq("id_demanda", id_demanda).execute()
    return len(response.data) > 0

def crear_visita_desde_demanda(demanda):
    """Crea un registro en la tabla visitas vinculado a la demanda."""
    id_demanda = demanda.get("id_demanda")
    
    if existe_visita_para_demanda(id_demanda):
        return {"status": "warning", "message": "Esta demanda ya tiene una visita vinculada."}
    
    supabase = get_supabase_client()
    hoy_fmt = date.today().strftime("%d/%m/%y")
    
    # fec_inicio = fecha_ingreso (fallback hoy) en formato YYYY-MM-DD para la base
    fec_inicio_raw = demanda.get("fecha_ingreso")
    fec_inicio = str(fec_inicio_raw)[:10] if fec_inicio_raw else date.today().isoformat()

    obs_visit = f"|| {hoy_fmt} - Se crea visita sociohabitacional desde demanda de origen {id_demanda}. Estado social: Para visita; Estado técnico: Para visita."
    
    payload = {
        "id_demanda": id_demanda,
        "est_soc": "Para visita",
        "est_tec": "Para visita",
        "fec_inicio": fec_inicio,
        "obs_visit": obs_visit,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    supabase.table("visitas").insert(payload).execute()
    return {"status": "success", "message": "Visita creada correctamente."}

def validar_demanda_sociohabitacional(demanda, nuevo_estado, observacion_accion):
    """
    Actualiza el estado de la demanda y registra la validación en las observaciones/historial.
    """
    supabase = get_supabase_client()
    id_demanda = demanda.get("id_demanda")
    accion = _limpiar(demanda.get("accion"))
    
    # 1. Obtener la demanda actual para no perder observaciones previas
    actual_res = supabase.table("demandas").select("observaciones").eq("id_demanda", id_demanda).single().execute()
    obs_previa = _limpiar(actual_res.data.get("observaciones")) if actual_res.data else ""
    
    # 2. Preparar el registro de historial
    hoy = date.today().strftime("%d/%m/%y") # Formato DD/MM/AA
    entrada_historial = f"|| {hoy} - Demanda validada por equipo sociohabitacional. Estado: {nuevo_estado}. Acción: {observacion_accion}"
    
    nuevas_obs = f"{entrada_historial} {obs_previa}".strip()
    
    payload = {
        "estado": nuevo_estado,
        "observaciones": nuevas_obs,
        "updated_at": datetime.now().isoformat()
    }
    
    response = supabase.table("demandas").update(payload).eq("id_demanda", id_demanda).execute()

    # 3. Lógica especial para Visitas
    resultado_visita = None
    if "Visitar" in accion:
        resultado_visita = crear_visita_desde_demanda(demanda)
        
    return {
        "demanda": response.data[0] if response.data else None,
        "visita": resultado_visita
    }

def contar_indicadores_visitas(visitas):
    """Calcula los contadores para las cards superiores."""
    v_para = 0
    v_prog = 0
    v_inf = 0
    v_comp = 0
    
    for v in visitas:
        esoc = _limpiar(v.get("est_soc"))
        etec = _limpiar(v.get("est_tec"))
        fprog = v.get("fec_program")
        
        # 1. Para visita
        if esoc == ESTADO_PARA_VISITA or etec == ESTADO_PARA_VISITA:
            v_para += 1
            
        # 2. Programados
        if esoc == ESTADO_PROGRAMADA or etec == ESTADO_PROGRAMADA:
            v_prog += 1
            
        # 3. Informes pendientes
        if esoc == ESTADO_VISITADA or etec == ESTADO_VISITADA:
            v_inf += 1
            
        # 4. Completados
        if esoc == ESTADO_INFORMADA and etec == ESTADO_INFORMADA:
            v_comp += 1
            
    return v_para, v_prog, v_inf, v_comp

def listar_visitas_detalladas():
    """Trae todas las visitas activas unificadas con los datos de la demanda."""
    supabase = get_supabase_client()
    res_v = supabase.table("visitas").select("*").order("fec_program", desc=False).execute()
    visitas = res_v.data or []
    if not visitas: return []

    ids_dem = [v["id_demanda"] for v in visitas]
    res_d = supabase.table("demandas").select("*").in_("id_demanda", ids_dem).execute()
    mapa_d = {d["id_demanda"]: d for d in res_d.data or []}

    for v in visitas:
        d = mapa_d.get(v["id_demanda"], {})
        for k in ["apellido", "nombre", "expediente", "domicilio", "contacto", "prioridad", "fecha_ingreso", "observaciones", "estado"]:
            v[f"d_{k}"] = d.get(k)
    return visitas

def registrar_programacion_individual(id_visit, fecha_program, observacion=""):
    """Actualiza la programación de una visita específica."""
    supabase = get_supabase_client()
    hoy_fmt = date.today().strftime("%d/%m/%y")
    f_prog_fmt = fecha_program.strftime("%d/%m/%y")
    
    res = supabase.table("visitas").select("*").eq("id_visit", id_visit).single().execute()
    if not res.data: return
    
    # Estados pasan a Programada si estaban en Para visita
    v = res.data
    n_soc = ESTADO_PROGRAMADA if _limpiar(v.get("est_soc")) == ESTADO_PARA_VISITA else v.get("est_soc")
    n_tec = ESTADO_PROGRAMADA if _limpiar(v.get("est_tec")) == ESTADO_PARA_VISITA else v.get("est_tec")
    
    obs_previa = _limpiar(v.get("obs_visit"))
    nueva_obs = f"|| {hoy_fmt} - Visita programada para {f_prog_fmt}"
    if _limpiar(observacion): nueva_obs += f"; {observacion}"
    
    payload = {
        "fec_program": fecha_program.isoformat(),
        "est_soc": n_soc, "est_tec": n_tec,
        "obs_visit": f"{nueva_obs}. {obs_previa}".strip(),
        "updated_at": datetime.now().isoformat()
    }
    supabase.table("visitas").update(payload).eq("id_visit", id_visit).execute()
    _sincronizar_estado_demanda_desde_visita(id_visit)

def _sincronizar_estado_demanda_desde_visita(id_visit):
    """Calcula y actualiza el estado de la demanda basado en los hitos de la visita."""
    supabase = get_supabase_client()
    res = supabase.table("visitas").select("*, demandas(id_demanda)").eq("id_visit", id_visit).single().execute()
    if not res.data: return
    v = res.data
    id_dem = v.get("id_demanda")
    if not id_dem: return

    soc, tec = _limpiar(v.get("est_soc")), _limpiar(v.get("est_tec"))
    fcomp = v.get("fec_comp")
    
    nuevo_estado = "Para visita" # Default
    if fcomp:
        nuevo_estado = "Completo"
    elif soc == ESTADO_INFORMADA and tec == ESTADO_VISITADA:
        nuevo_estado = "Informe Social"
    elif tec == ESTADO_INFORMADA and soc == ESTADO_VISITADA:
        nuevo_estado = "Informe Tecnico"
    elif soc == ESTADO_VISITADA and tec == ESTADO_VISITADA:
        nuevo_estado = "Visitado"
    elif soc == ESTADO_VISITADA and tec == ESTADO_PARA_VISITA:
        nuevo_estado = "Visita Social"
    elif tec == ESTADO_VISITADA and soc == ESTADO_PARA_VISITA:
        nuevo_estado = "Visita Tecnica"
    elif soc == ESTADO_PROGRAMADA or tec == ESTADO_PROGRAMADA:
        nuevo_estado = "Visita programada"

    supabase.table("demandas").update({"estado": nuevo_estado}).eq("id_demanda", id_dem).execute()

def registrar_visita_campo(id_visit, v_soc=False, v_tec=False):
    """
    Procesa la visita desde el cronograma (columna derecha).
    Si el check está activo -> Visitada.
    Si el check está inactivo -> Vuelve a Para visita (reversión).
    """
    supabase = get_supabase_client()
    hoy_iso = date.today().isoformat()
    hoy_fmt = date.today().strftime("%d/%m/%y")
    
    res = supabase.table("visitas").select("*").eq("id_visit", id_visit).single().execute()
    v = res.data
    if not v: return

    cur_soc = _limpiar(v.get("est_soc"))
    cur_tec = _limpiar(v.get("est_tec"))

    payload = {"updated_at": datetime.now().isoformat()}
    hitos = []
    
    # Procesamiento Social: solo si no tiene ya un informe (estado final en esta etapa)
    if cur_soc not in [ESTADO_VISITADA, ESTADO_INFORMADA]:
        if v_soc:
            payload["est_soc"] = ESTADO_VISITADA
            payload["fec_visit_soc"] = hoy_iso
            hitos.append("Visita social realizada")
        elif cur_soc == ESTADO_PROGRAMADA:
            # Si estaba programada y el check es False, retrocedemos
            payload["est_soc"] = ESTADO_PARA_VISITA
            payload["fec_visit_soc"] = None
            hitos.append("Visita social no realizada (reprogramación pendiente)")

    # Procesamiento Técnico: solo si no tiene ya un informe
    if cur_tec not in [ESTADO_VISITADA, ESTADO_INFORMADA]:
        if v_tec:
            payload["est_tec"] = ESTADO_VISITADA
            payload["fec_visit_tec"] = hoy_iso
            hitos.append("Visita técnica realizada")
        elif cur_tec == ESTADO_PROGRAMADA:
            # Si estaba programada y el check es False, retrocedemos
            payload["est_tec"] = ESTADO_PARA_VISITA
            payload["fec_visit_tec"] = None
            hitos.append("Visita técnica no realizada (reprogramación pendiente)")
        
    if hitos:
        # Sincronizamos n_soc y n_tec para evaluar si la card debe seguir en agenda
        n_soc = payload.get("est_soc", cur_soc)
        n_tec = payload.get("est_tec", cur_tec)
        
        # REGLA DE ORO: Si ya no hay estados "Programada", la card desaparece de la derecha
        if n_soc != ESTADO_PROGRAMADA and n_tec != ESTADO_PROGRAMADA:
            payload["fec_program"] = None

        nueva_obs = f"|| {hoy_fmt} - {'; '.join(hitos)}."
        payload["obs_visit"] = f"{nueva_obs} {_limpiar(v.get('obs_visit'))}".strip()
        supabase.table("visitas").update(payload).eq("id_visit", id_visit).execute()
        _sincronizar_estado_demanda_desde_visita(id_visit)

def registrar_informes_hitos(id_visit, i_soc_target=False, i_tec_target=False):
    """Registra o anula la entrega de informes (Bidireccional)."""
    supabase = get_supabase_client()
    hoy_iso = date.today().isoformat()
    hoy_fmt = date.today().strftime("%d/%m/%y")
    
    res = supabase.table("visitas").select("*").eq("id_visit", id_visit).single().execute()
    v = res.data
    if not v: return
    
    cur_soc, cur_tec = _limpiar(v.get("est_soc")), _limpiar(v.get("est_tec"))

    payload = {"updated_at": datetime.now().isoformat()}
    hitos = []
    
    # Lógica Social
    if i_soc_target and cur_soc == ESTADO_VISITADA:
        payload["est_soc"] = ESTADO_INFORMADA
        hitos.append("Informe social registrado")
    elif not i_soc_target and cur_soc == ESTADO_INFORMADA:
        payload["est_soc"] = ESTADO_VISITADA
        hitos.append("Informe social anulado")

    # Lógica Técnica
    if i_tec_target and cur_tec == ESTADO_VISITADA:
        payload["est_tec"] = ESTADO_INFORMADA
        hitos.append("Informe técnico registrado")
    elif not i_tec_target and cur_tec == ESTADO_INFORMADA:
        payload["est_tec"] = ESTADO_VISITADA
        hitos.append("Informe técnico anulado")
        
    if hitos:
        n_soc = payload.get("est_soc", v.get("est_soc"))
        n_tec = payload.get("est_tec", v.get("est_tec"))
        payload["fec_comp"] = hoy_iso if (n_soc == ESTADO_INFORMADA and n_tec == ESTADO_INFORMADA) else None

        nueva_obs = f"|| {hoy_fmt} - {'; '.join(hitos)}."
        payload["obs_visit"] = f"{nueva_obs} {_limpiar(v.get('obs_visit'))}".strip()
        supabase.table("visitas").update(payload).eq("id_visit", id_visit).execute()
        _sincronizar_estado_demanda_desde_visita(id_visit)
