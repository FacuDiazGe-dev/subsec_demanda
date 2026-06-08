import streamlit as st

from utils.auth import (
    esta_logueado,
    paginas_habilitadas,
    render_login_card,
    usuario_actual,
)


st.set_page_config(
    page_title="Vivienda y Hábitat",
    layout="wide",
)

if not esta_logueado():
    st.title("Subsecretaría de Vivienda y Hábitat")
    st.caption("Sistema interno de gestión")
    render_login_card()
    st.stop()

paginas = paginas_habilitadas()
if not paginas:
    user = usuario_actual() or {}
    st.title("Sin acceso habilitado")
    st.warning(
        f"El usuario {user.get('usuario')} no tiene un rol habilitado para ver módulos."
    )
    st.stop()

nav = st.navigation(
    [
        st.Page(path, title=title)
        for title, path in paginas.items()
    ]
)
nav.run()
