from datetime import date
import re

import pandas as pd
import streamlit as st

from services.demandas_service import (
    actualizar_demanda,
    cerrar_demanda,
    crear_demanda,
    listar_demandas_pendientes,
)
from services.expedientes_service import buscar_expediente


ORIGENES = [
    "Subdirectora",
    "Area administrativa",
    "Subsecretaria",
    "Secretaria",
    "Secretaria de Gobierno",
    "Intendenta",
    "Noguera",
    "Orden judicial",
    "Defensoria del Pueblo",
    "Vecino / consulta directa",
    "Equipo tecnico",
    "Deposito",
    "Cuadrilla",
    "Otro",
]

PRIORIDADES = [
    "1 - Urgente",
    "2 - Prioritario",
    "3 - Normal",
    "4 - Bajo",
    "5 - En espera",
]

ACCIONES = [
    "Visitar",
    "Hacer nota",
    "Actuacion",
    "Obra",
    "Entregar materiales",
    "Informe",
    "Seguimiento",
    "Emergencia",
    "Otro",
]

RESPONSABLES = ["Facundo", "Pedro", "Guillo", "Bea", "Iris", "Deposito"]

ESTADOS_POR_ACCION = {
    "Visitar": [
        "Para visita",
        "Visita programada",
        "Relevado",
        "Informes pendientes",
        "Con informes completos",
        "En gestion",
        "Pase a obra",
        "Cerrado",
    ],
    "Hacer nota": ["Pendiente", "En elaboracion", "Presentada", "Cerrado"],
    "Actuacion": ["Pendiente", "En elaboracion", "Presentada", "Cerrado"],
    "Obra": [
        "Sin acta",
        "Acta compromiso / inicio firmada",
        "Para iniciar obra",
        "En ejecucion",
        "Suspendida",
        "Ejecutada",
        "Acta de fin pendiente",
        "Fin de obra",
        "Cerrado",
    ],
    "Emergencia": [
        "Ingresada",
        "Visita programada",
        "Relevado",
        "Informe de emergencia",
        "Intervencion",
        "Resuelta",
        "Derivada",
        "Cerrado",
    ],
    "Entregar materiales": [
        "Solicitud recibida",
        "En gestion",
        "Autorizacion recibida",
        "Pendiente de entrega",
        "Entrega programada",
        "Materiales entregados",
        "Firma pendiente",
        "Cerrado",
    ],
    "Informe": ["Solicitado", "En elaboracion", "Presentado", "Cerrado"],
    "Seguimiento": ["Ingresada", "En revision", "Respondida", "Derivada", "Cerrado"],
    "Otro": ["Ingresada", "En gestion", "Resuelta", "Cerrado"],
}


def texto(valor):
    return "" if valor is None else str(valor)


def limpiar(valor):
    return texto(valor).strip()


def parsear_expediente(valor):
    valor = limpiar(valor)
    match = re.search(r"(\d{1,})\s*(?:/\s*[A-Za-z])?\s*/\s*(\d{2,4})", valor)
    if not match:
        return "", "", ""

    numero = match.group(1).lstrip("0") or match.group(1)
    anio = match.group(2)
    if len(anio) == 2:
        anio = f"20{anio}"
    return numero, anio, f"{numero}/{anio}"


def mostrar_error_supabase(error):
    mensaje = str(error)
    if "row-level security" in mensaje:
        st.error(
            "Supabase no permite esta operacion con la anon key. "
            "Revisar las politicas RLS de la tabla demandas."
        )
        return
    st.error(f"No se pudo completar la operacion en Supabase: {mensaje}")


def inicializar_carga():
    defaults = {
        "carga_expediente": "",
        "carga_pedido": "",
    }

    if st.session_state.pop("limpiar_carga_pendiente", False):
        for key in defaults:
            st.session_state[key] = ""
        st.session_state.pop("expediente_carga", None)
        st.session_state.pop("busqueda_carga_realizada", None)

    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    if st.session_state.pop("demanda_guardada", False):
        st.success(st.session_state.pop("mensaje_demanda_guardada", "Demanda guardada correctamente."))


def cargar_datos_expediente(expediente):
    st.session_state["expediente_carga"] = expediente


def valor_personal(expediente, columna_expte):
    if expediente:
        return limpiar(expediente.get(columna_expte)) or None
    return None


def limpiar_carga():
    for key in [
        "carga_expediente",
        "carga_pedido",
    ]:
        st.session_state[key] = ""
    st.session_state.pop("expediente_carga", None)
    st.session_state.pop("busqueda_carga_realizada", None)


def cargar_demanda_tab():
    inicializar_carga()
    st.subheader("Nueva demanda")

    st.text_input("Expediente", key="carga_expediente", placeholder="20373/24")

    st.text_area(
        "Pedido",
        key="carga_pedido",
        height=95,
        placeholder="Texto que llega por mensaje, llamada o resumen breve.",
    )

    col_accion, col_origen, col_responsable = st.columns(3)
    with col_accion:
        accion = st.selectbox("Accion", ACCIONES)
    with col_origen:
        origen = st.selectbox("Origen", ORIGENES, index=0)
    with col_responsable:
        responsable = st.selectbox("Responsable", [""] + RESPONSABLES)

    col_guardar, col_limpiar = st.columns([2, 1])
    with col_guardar:
        guardar = st.button("Guardar demanda", type="primary", use_container_width=True)
    with col_limpiar:
        st.button("Limpiar", use_container_width=True, on_click=limpiar_carga)

    if guardar:
        expte_numero, expte_anio, expediente_texto = parsear_expediente(st.session_state["carga_expediente"])
        pedido = limpiar(st.session_state["carga_pedido"])

        if not expediente_texto:
            st.error("Carga el expediente con formato numero/anio, por ejemplo 20373/24.")
            return

        if not pedido:
            st.error("Completa el pedido antes de guardar.")
            return

        expediente = buscar_expediente(expte_numero, expte_anio)
        datos = {
            "fecha_ingreso": date.today().isoformat(),
            "origen": origen,
            "prioridad": "3 - Normal",
            "expte_numero": expte_numero or None,
            "expte_anio": expte_anio or None,
            "expediente": expediente_texto,
            "apellido": valor_personal(expediente, "apellido"),
            "nombre": valor_personal(expediente, "nombre"),
            "dni": valor_personal(expediente, "dni"),
            "domicilio": valor_personal(expediente, "direccion"),
            "barrio": valor_personal(expediente, "barrio"),
            "contacto": valor_personal(expediente, "contacto"),
            "accion": accion,
            "tipo_intervencion": accion,
            "estado": "Ingresada",
            "responsable": responsable or None,
            "observaciones": pedido,
        }
        try:
            crear_demanda(datos)
        except Exception as error:
            mostrar_error_supabase(error)
            return
        st.session_state["demanda_guardada"] = True
        if expediente:
            st.session_state["mensaje_demanda_guardada"] = "Demanda guardada con datos del expediente."
        else:
            st.session_state["mensaje_demanda_guardada"] = (
                "Demanda guardada. No se encontro el expediente en la base general; "
                "los datos personales quedaron vacios o con la carga manual."
            )
        st.session_state["limpiar_carga_pendiente"] = True
        st.rerun()


def estados_para_demanda(demanda):
    accion = demanda.get("accion")
    if accion in ESTADOS_POR_ACCION:
        return accion, ESTADOS_POR_ACCION[accion]
    return "Otro", ESTADOS_POR_ACCION["Otro"]


def valor_para_historial(valor):
    valor = limpiar(valor)
    return valor if valor else "(vacio)"


def detectar_cambios(demanda, nuevos_valores):
    etiquetas = {
        "estado": "Estado",
        "prioridad": "Prioridad",
        "responsable": "Responsable",
    }
    cambios = []
    for campo, etiqueta in etiquetas.items():
        anterior = limpiar(demanda.get(campo))
        nuevo = limpiar(nuevos_valores.get(campo))
        if anterior != nuevo:
            cambios.append(f"{etiqueta}: {valor_para_historial(anterior)} -> {valor_para_historial(nuevo)}")

    campos_personales = ["apellido", "nombre", "dni", "domicilio", "barrio", "contacto"]
    if any(limpiar(demanda.get(campo)) != limpiar(nuevos_valores.get(campo)) for campo in campos_personales):
        cambios.append("Cambio en datos personales")

    return cambios


def agregar_al_historial(historial_actual, nueva_accion, cambios):
    historial_actual = limpiar(historial_actual)
    partes = []

    nueva_accion = limpiar(nueva_accion)
    if nueva_accion:
        partes.append(f"Actualizacion: {nueva_accion}")
    partes.extend(cambios)

    if not partes:
        return historial_actual or None

    entrada = f"{date.today().strftime('%d/%m/%Y')}: {'; '.join(partes)}"
    if historial_actual:
        return f"{entrada} || {historial_actual}"
    return entrada


def opciones_filtro(df, columna):
    if columna not in df.columns:
        return []
    valores = [limpiar(valor) for valor in df[columna].dropna().tolist()]
    return sorted({valor for valor in valores if valor})


def aplicar_filtros_demandas(df):
    if df.empty:
        return df

    with st.expander("Filtros", expanded=True):
        busqueda = st.text_input(
            "Buscar",
            placeholder="Expediente, apellido, nombre, barrio, pedido...",
        )

        col_1, col_2, col_3 = st.columns(3)
        with col_1:
            filtro_prioridad = st.multiselect("Prioridad", opciones_filtro(df, "prioridad"))
            filtro_estado = st.multiselect("Estado", opciones_filtro(df, "estado"))
        with col_2:
            filtro_responsable = st.multiselect("Responsable", opciones_filtro(df, "responsable"))
            filtro_accion = st.multiselect("Accion", opciones_filtro(df, "accion"))
        with col_3:
            filtro_origen = st.multiselect("Origen", opciones_filtro(df, "origen"))
            filtro_barrio = st.multiselect("Barrio", opciones_filtro(df, "barrio"))

    filtrado = df.copy()
    filtros = {
        "prioridad": filtro_prioridad,
        "estado": filtro_estado,
        "responsable": filtro_responsable,
        "accion": filtro_accion,
        "origen": filtro_origen,
        "barrio": filtro_barrio,
    }

    for columna, valores in filtros.items():
        if valores and columna in filtrado.columns:
            filtrado = filtrado[filtrado[columna].fillna("").astype(str).isin(valores)]

    busqueda = limpiar(busqueda).lower()
    if busqueda:
        columnas_busqueda = [
            "id_demanda",
            "expediente",
            "apellido",
            "nombre",
            "dni",
            "barrio",
            "domicilio",
            "contacto",
            "observaciones",
            "accion",
            "estado",
            "responsable",
            "origen",
            "prioridad",
        ]
        columnas_busqueda = [col for col in columnas_busqueda if col in filtrado.columns]
        mascara = (
            filtrado[columnas_busqueda]
            .fillna("")
            .astype(str)
            .agg(" ".join, axis=1)
            .str.lower()
            .str.contains(busqueda, regex=False)
        )
        filtrado = filtrado[mascara]

    return filtrado


def pendientes_tab():
    st.subheader("Demandas pendientes")

    demandas = listar_demandas_pendientes()
    if not demandas:
        st.info("No hay demandas pendientes.")
        return

    df = pd.DataFrame(demandas)
    columnas = [
        "id_demanda",
        "fecha_ingreso",
        "origen",
        "prioridad",
        "expediente",
        "apellido",
        "nombre",
        "barrio",
        "domicilio",
        "contacto",
        "observaciones",
        "accion",
        "estado",
        "responsable",
    ]

    df_filtrado = aplicar_filtros_demandas(df)
    if df_filtrado.empty:
        st.info("No hay demandas pendientes que coincidan con los filtros.")
        return

    columnas_visibles = [col for col in columnas if col in df.columns]
    df_visible = df_filtrado[columnas_visibles].rename(columns={"observaciones": "historial"})
    seleccion_tabla = st.dataframe(
        df_visible,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="tabla_demandas_pendientes",
    )

    filas_seleccionadas = seleccion_tabla.selection.rows
    if not filas_seleccionadas:
        st.info("Selecciona una demanda desde la tabla para editarla.")
        return

    demanda = df_filtrado.iloc[filas_seleccionadas[0]].to_dict()
    categoria, estados = estados_para_demanda(demanda)

    with st.form("actualizar_demanda_form"):
        st.caption(f"Editando demanda #{demanda.get('id_demanda')} - {texto(demanda.get('expediente'))}")
        col_estado, col_prioridad, col_responsable = st.columns(3)
        estado_actual = demanda.get("estado") if demanda.get("estado") in estados else estados[0]
        prioridad_actual = demanda.get("prioridad") if demanda.get("prioridad") in PRIORIDADES else "3 - Normal"
        responsable_actual = demanda.get("responsable") if demanda.get("responsable") in RESPONSABLES else ""

        with col_estado:
            estado = st.selectbox("Estado", estados, index=estados.index(estado_actual))
        with col_prioridad:
            prioridad = st.selectbox("Prioridad", PRIORIDADES, index=PRIORIDADES.index(prioridad_actual))
        with col_responsable:
            responsable = st.selectbox(
                "Responsable",
                [""] + RESPONSABLES,
                index=([""] + RESPONSABLES).index(responsable_actual),
            )

        st.text_area(
            "Historial",
            value=texto(demanda.get("observaciones")),
            height=120,
            disabled=True,
        )
        nueva_accion = st.text_area(
            "Nueva accion / actualizacion",
            height=90,
            placeholder="Opcional. Los cambios de campos se agregan automaticamente.",
        )

        with st.expander("Datos personales"):
            col_apellido, col_nombre, col_dni = st.columns(3)
            with col_apellido:
                apellido = st.text_input("Apellido", value=texto(demanda.get("apellido")))
            with col_nombre:
                nombre = st.text_input("Nombre", value=texto(demanda.get("nombre")))
            with col_dni:
                dni = st.text_input("DNI", value=texto(demanda.get("dni")))

            col_domicilio, col_barrio, col_contacto = st.columns(3)
            with col_domicilio:
                domicilio = st.text_input("Domicilio", value=texto(demanda.get("domicilio")))
            with col_barrio:
                barrio = st.text_input("Barrio", value=texto(demanda.get("barrio")))
            with col_contacto:
                contacto = st.text_input("Contacto", value=texto(demanda.get("contacto")))

        col_guardar, col_cerrar = st.columns(2)
        with col_guardar:
            actualizar = st.form_submit_button("Actualizar", type="primary", use_container_width=True)
        with col_cerrar:
            cerrar = st.form_submit_button("Cerrar demanda", use_container_width=True)

    if actualizar:
        nuevos_valores = {
            "estado": estado,
            "prioridad": prioridad,
            "responsable": responsable or None,
            "apellido": apellido.strip() or None,
            "nombre": nombre.strip() or None,
            "dni": dni.strip() or None,
            "domicilio": domicilio.strip() or None,
            "barrio": barrio.strip() or None,
            "contacto": contacto.strip() or None,
        }
        cambios = detectar_cambios(demanda, nuevos_valores)
        try:
            actualizar_demanda(
                demanda["id_demanda"],
                {
                    **nuevos_valores,
                    "observaciones": agregar_al_historial(demanda.get("observaciones"), nueva_accion, cambios),
                },
            )
        except Exception as error:
            mostrar_error_supabase(error)
            return
        st.success("Demanda actualizada.")
        st.rerun()

    if cerrar:
        try:
            cerrar_demanda(demanda["id_demanda"])
        except Exception as error:
            mostrar_error_supabase(error)
            return
        st.success("Demanda cerrada.")
        st.rerun()


st.set_page_config(page_title="Demandas", layout="wide")
st.title("Demandas")

tab_cargar, tab_pendientes = st.tabs(["Cargar demanda", "Pendientes"])
with tab_cargar:
    cargar_demanda_tab()
with tab_pendientes:
    pendientes_tab()
