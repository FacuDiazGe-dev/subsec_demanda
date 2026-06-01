from datetime import datetime

import pandas as pd
import streamlit as st

from services.demandas_service import listar_demandas_abiertas
from services.materiales_base_service import listar_materiales_base_activos
from services.materiales_orden_service import (
    crear_materiales_orden,
    eliminar_materiales_por_orden,
    listar_materiales_por_orden,
)
from services.ordenes_service import (
    actualizar_orden_material,
    crear_orden_material,
    eliminar_orden_material,
    listar_ordenes_con_demanda,
    obtener_datos_pdf_orden,
)
from services.pdf_orden_service import generar_pdf_orden


ESTADOS_ORDEN = [
    "Pedido entrega",
    "Pedido retiro",
    "Pendiente de retiro",
    "Pendiente de entrega",
    "En deposito",
    "Entrega parcial",
    "Entregado",
    "Cancelado",
]
TIPOS_STOCK = {
    "gestion de stock",
    "compra para emergencias",
    "reposicion de deposito",
    "insumos internos",
    "herramientas / equipamiento",
}


def texto(valor):
    return "" if valor is None else str(valor)


def limpiar(valor):
    return texto(valor).strip()


def fecha_visible(valor):
    valor = limpiar(valor)
    if not valor:
        return "-"
    partes = valor[:10].split("-")
    if len(partes) == 3 and all(partes):
        return f"{partes[2]}/{partes[1]}/{partes[0]}"
    return valor


def parsear_fecha_ddmmaa(valor):
    valor = limpiar(valor)
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%d/%m/%y").date().isoformat()
    except ValueError:
        return None


def formatear_cantidad(valor):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return ""
    if numero.is_integer():
        return str(int(numero))
    return f"{numero:.2f}".rstrip("0").rstrip(".")


def mostrar_error_supabase(error):
    mensaje = str(error)
    if "row-level security" in mensaje:
        st.error("Supabase bloqueo la operacion por RLS. Revisa policies de la tabla.")
        return
    st.error(f"No se pudo completar la operacion en Supabase: {mensaje}")


def tipo_materiales_desde_obs(demanda):
    obs = limpiar(demanda.get("observaciones"))
    prefijo = "tipo materiales:"
    if obs.lower().startswith(prefijo):
        resto = obs[len(prefijo) :].strip()
        return resto.split(".")[0].strip()
    return ""


def es_demanda_stock(demanda):
    accion = limpiar(demanda.get("accion")).lower()
    if accion != "entregar materiales":
        return False
    tipo = tipo_materiales_desde_obs(demanda).lower()
    return tipo in TIPOS_STOCK


def etiqueta_demanda(d):
    return (
        f"ID {d.get('id_demanda')} | Expte {texto(d.get('expediente'))} | "
        f"{texto(d.get('apellido'))}, {texto(d.get('nombre'))} | {texto(d.get('barrio'))} | "
        f"{texto(d.get('accion'))} | {texto(d.get('estado'))}"
    )


@st.cache_data(ttl=300)
def opciones_materiales_base():
    materiales = listar_materiales_base_activos()
    opciones = []
    mapa = {}
    for item in materiales:
        material = limpiar(item.get("material"))
        if not material:
            continue
        tipo = limpiar(item.get("tipo"))
        unidad = limpiar(item.get("unidad"))
        etiqueta = " - ".join([x for x in [material, tipo, unidad] if x])
        opciones.append(etiqueta)
        mapa[etiqueta] = material
    return opciones, mapa


def key_tmp(prefijo):
    return f"{prefijo}_materiales_tmp"


def init_tmp(prefijo):
    if key_tmp(prefijo) not in st.session_state:
        st.session_state[key_tmp(prefijo)] = []


def editor_materiales(prefijo):
    init_tmp(prefijo)
    opciones, mapa = opciones_materiales_base()
    c1, c2 = st.columns([3, 1])
    with c1:
        seleccion = st.selectbox(
            "Material",
            options=opciones,
            index=None,
            key=f"{prefijo}_material",
            placeholder="Escriba para sugerir o cargue manual",
            accept_new_options=True,
            filter_mode="contains",
        )
    with c2:
        cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0, format="%.2f", key=f"{prefijo}_cantidad")
    if st.button("Agregar material", key=f"{prefijo}_add", use_container_width=True):
        material = limpiar(mapa.get(seleccion, seleccion))
        if material:
            st.session_state[key_tmp(prefijo)].append(
                {"Material": material, "cantidad": formatear_cantidad(cantidad)}
            )
            st.rerun()

    tmp = st.session_state.get(key_tmp(prefijo), [])
    if not tmp:
        st.caption("Sin materiales cargados.")
        return []
    st.dataframe(pd.DataFrame(tmp), hide_index=True, use_container_width=True, height=180)
    if st.button("Limpiar lista", key=f"{prefijo}_clear", use_container_width=True):
        st.session_state[key_tmp(prefijo)] = []
        st.rerun()
    return tmp


def ficha_demanda(d):
    if es_demanda_stock(d):
        st.info(
            f"Destino: Deposito / Stock | Tipo: {tipo_materiales_desde_obs(d) or 'Gestion de stock'} | "
            f"Origen: {texto(d.get('origen'))} | Prioridad: {texto(d.get('prioridad'))}"
        )
    else:
        st.caption(
            f"Expte: {texto(d.get('expediente'))} | Persona: {texto(d.get('apellido'))}, {texto(d.get('nombre'))} | "
            f"DNI: {texto(d.get('dni'))} | Domicilio: {texto(d.get('domicilio'))} - {texto(d.get('barrio'))} | "
            f"Contacto: {texto(d.get('contacto'))}"
        )


def tab_nueva():
    demandas = listar_demandas_abiertas()
    demandas = [d for d in demandas if limpiar(d.get("accion")).lower() in {"obra", "emergencia", "emerencia"} or es_demanda_stock(d)]
    if not demandas:
        st.info("No hay demandas abiertas elegibles para generar orden.")
        return
    opciones = {etiqueta_demanda(d): d for d in demandas}
    sel = st.selectbox("Demanda vinculada", list(opciones.keys()))
    d = opciones[sel]
    ficha_demanda(d)

    instrucciones = st.text_area("Instrucciones / tarea", height=120)
    estado_default = "Pedido retiro" if es_demanda_stock(d) else "Pedido entrega"
    estado = st.selectbox("Estado inicial", ESTADOS_ORDEN, index=ESTADOS_ORDEN.index(estado_default))
    agregar_materiales = st.checkbox("Agregar materiales asociados (opcional)")
    materiales = []
    if agregar_materiales:
        materiales = editor_materiales("orden_nueva")

    if st.button("Crear orden", type="primary", use_container_width=True):
        if not limpiar(instrucciones):
            st.warning("Completa la instruccion antes de crear.")
            return
        try:
            orden = crear_orden_material(
                {
                    "id_demanda": d.get("id_demanda"),
                    "origen": d.get("origen"),
                    "estado": estado,
                    "instrucciones_tarea": instrucciones,
                }
            )
            if orden and materiales:
                crear_materiales_orden(orden.get("n_orden"), materiales)
                st.session_state[key_tmp("orden_nueva")] = []
        except Exception as error:
            mostrar_error_supabase(error)
            return
        st.success(f"Orden creada. N° {texto(orden.get('n_orden'))}")
        st.rerun()


def nombre_pdf(orden, demanda):
    expte = limpiar(demanda.get("expediente")).replace("/", "-").replace("\\", "-") or "sin-expediente"
    return f"orden_N{orden.get('n_orden')}_expte_{expte}.pdf"


def tab_seguimiento():
    try:
        ordenes = listar_ordenes_con_demanda(incluir_cerradas=True)
    except Exception as error:
        mostrar_error_supabase(error)
        return
    if not ordenes:
        st.info("No hay ordenes cargadas.")
        return
    df = pd.DataFrame(ordenes)
    with st.expander("Filtros", expanded=False):
        q = st.text_input("Buscar", placeholder="N orden, expte, apellido, nombre...")
        c1, c2 = st.columns(2)
        with c1:
            f_estado = st.multiselect("Estado", sorted({limpiar(x) for x in df["estado"].dropna()}))
        with c2:
            f_origen = st.multiselect("Origen", sorted({limpiar(x) for x in df["origen"].dropna()}))

    filtrado = df.copy()
    if f_estado:
        filtrado = filtrado[filtrado["estado"].fillna("").astype(str).isin(f_estado)]
    if f_origen:
        filtrado = filtrado[filtrado["origen"].fillna("").astype(str).isin(f_origen)]
    q = limpiar(q).lower()
    if q:
        cols = [c for c in ["n_orden", "id_demanda", "expediente", "apellido", "nombre", "instrucciones_tarea"] if c in filtrado.columns]
        mask = filtrado[cols].fillna("").astype(str).apply(lambda row: any(q in v.lower() for v in row), axis=1)
        filtrado = filtrado[mask]
    if filtrado.empty:
        st.info("Sin resultados con esos filtros.")
        return

    vista = filtrado[["n_orden", "fecha_emision", "estado", "id_demanda", "expediente", "apellido", "nombre", "origen"]].copy()
    st.dataframe(vista, hide_index=True, use_container_width=True, height=280)
    ids = [int(x) for x in vista["n_orden"].tolist()]
    n_sel = st.selectbox("Seleccionar orden", ids)
    orden = next((o for o in ordenes if o.get("n_orden") == n_sel), None)
    if not orden:
        return
    demanda = orden.get("demanda") or {}

    st.divider()
    st.markdown(f"### Orden seleccionada N° {n_sel}")
    with st.container(border=True):
        st.write(f"Estado: {texto(orden.get('estado'))} | Emision: {fecha_visible(orden.get('fecha_emision'))} | Entrega: {fecha_visible(orden.get('fecha_entrega'))}")
        st.write(f"Expte: {texto(demanda.get('expediente'))} | Beneficiario: {texto(demanda.get('apellido'))}, {texto(demanda.get('nombre'))}")
        st.write(f"Domicilio: {texto(demanda.get('domicilio'))} - {texto(demanda.get('barrio'))} | Contacto: {texto(demanda.get('contacto'))}")
        st.write(f"Origen: {texto(orden.get('origen'))} | Prioridad: {texto(demanda.get('prioridad'))} | Accion: {texto(demanda.get('accion'))}")
        st.caption(f"Tarea: {texto(orden.get('instrucciones_tarea'))}")

    st.markdown("#### Materiales asociados")
    try:
        mats = listar_materiales_por_orden(n_sel)
    except Exception as error:
        mostrar_error_supabase(error)
        mats = []
    if mats:
        st.dataframe(pd.DataFrame(mats)[["Material", "cantidad"]], hide_index=True, use_container_width=True, height=200)
    else:
        st.info("Esta orden no tiene materiales asociados.")
    with st.expander("Agregar materiales", expanded=False):
        nuevos = editor_materiales(f"orden_{n_sel}")
        if st.button("Guardar materiales nuevos", key=f"save_mats_{n_sel}", use_container_width=True):
            if not nuevos:
                st.warning("No hay materiales para guardar.")
            else:
                try:
                    crear_materiales_orden(n_sel, nuevos)
                    st.session_state[key_tmp(f"orden_{n_sel}")] = []
                except Exception as error:
                    mostrar_error_supabase(error)
                else:
                    st.success("Materiales agregados.")
                    st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        nuevo_estado = st.selectbox("Estado", ESTADOS_ORDEN, index=ESTADOS_ORDEN.index(orden.get("estado")) if orden.get("estado") in ESTADOS_ORDEN else 0)
        fecha_txt = st.text_input("Fecha entrega (DD/MM/AA)", value=fecha_visible(orden.get("fecha_entrega"))[:8] if fecha_visible(orden.get("fecha_entrega")) != "-" else "")
    with c2:
        comentario = st.text_area("Comentario para historial", height=90)

    if st.button("Actualizar orden", type="primary", use_container_width=True):
        fecha_iso = parsear_fecha_ddmmaa(fecha_txt) if limpiar(fecha_txt) else None
        if limpiar(fecha_txt) and not fecha_iso:
            st.warning("Fecha invalida. Usa DD/MM/AA.")
            return
        try:
            actualizar_orden_material(n_sel, nuevo_estado, comentario, fecha_entrega=fecha_iso)
        except Exception as error:
            mostrar_error_supabase(error)
            return
        st.success("Orden actualizada.")
        st.rerun()

    try:
        datos_pdf = obtener_datos_pdf_orden(n_sel)
        if datos_pdf:
            pdf = generar_pdf_orden(datos_pdf["orden"], datos_pdf["demanda"], datos_pdf["materiales"])
            st.download_button(
                "Descargar orden PDF",
                data=pdf,
                file_name=nombre_pdf(datos_pdf["orden"], datos_pdf["demanda"]),
                mime="application/pdf",
                use_container_width=True,
            )
    except Exception as error:
        mostrar_error_supabase(error)

    st.divider()
    st.markdown("#### Zona de peligro")
    check = st.checkbox(f"Confirmo eliminar la orden {n_sel}")
    if st.button("Eliminar orden", disabled=not check, use_container_width=True):
        try:
            eliminar_materiales_por_orden(n_sel)
            eliminar_orden_material(n_sel)
        except Exception as error:
            mostrar_error_supabase(error)
            return
        st.success("Orden eliminada.")
        st.rerun()


st.set_page_config(page_title="Ordenes", layout="wide")
st.title("Ordenes")

tab1, tab2 = st.tabs(["Nueva orden", "Seguimiento de ordenes"])
with tab1:
    tab_nueva()
with tab2:
    tab_seguimiento()
