import streamlit as st
import unicodedata

from services.usuarios_app_service import obtener_usuario_login, verificar_password


ROLES_TODO = {"admin", "tecnico"}
EQUIPOS_TODO = {"administracion", "general"}


def _norm(valor):
    valor = "" if valor is None else str(valor)
    valor = unicodedata.normalize("NFKD", valor.strip().lower())
    return "".join(ch for ch in valor if not unicodedata.combining(ch))


def usuario_actual():
    return st.session_state.get("usuario_app")


def esta_logueado():
    return bool(usuario_actual())


def cerrar_sesion():
    for key in ["usuario_app", "auth_error"]:
        st.session_state.pop(key, None)


def iniciar_sesion(usuario, password):
    data = obtener_usuario_login(usuario)
    if not data or not verificar_password(password, data.get("password_hash")):
        st.session_state["auth_error"] = "Usuario o contraseña incorrectos."
        return False

    st.session_state["usuario_app"] = {
        "id_usuario": data.get("id_usuario"),
        "usuario": data.get("usuario"),
        "equipo": data.get("equipo"),
        "rol": data.get("rol") or "operador",
    }
    st.session_state.pop("auth_error", None)
    return True


def rol_actual():
    user = usuario_actual() or {}
    rol = _norm(user.get("rol"))
    equipo = _norm(user.get("equipo"))
    if rol in ROLES_TODO or equipo in EQUIPOS_TODO:
        return "admin" if rol == "admin" or equipo == "administracion" else "tecnico"
    if rol in {"deposito", "asistencia"}:
        return rol
    if equipo in {"deposito", "asistencia"}:
        return equipo
    return rol or equipo


def tiene_acceso_total():
    return rol_actual() in ROLES_TODO


def puede_ver(roles_permitidos=None):
    user = usuario_actual()
    if not user:
        return False
    rol = rol_actual()
    if rol in ROLES_TODO:
        return True
    if not roles_permitidos:
        return True
    return rol in {_norm(rol_permitido) for rol_permitido in roles_permitidos}


def paginas_habilitadas():
    rol = rol_actual()
    if rol in ROLES_TODO:
        return {
            "Demandas": "pages/1_Demandas.py",
            "Obras": "pages/2_Obras.py",
            "Órdenes": "pages/5_Ordenes.py",
            "Depósito": "pages/3_Deposito.py",
            "Asistencia": "pages/4_Asistencia.py",
            "Notas rápidas": "pages/6_Notas_Rapidas.py",
            "SocioHabitacional": "pages/7_SocioHabitacional.py",
            "Laboratorio UI": "pages/8_Laboratorio_UI.py",
        }
    if rol == "deposito":
        return {"Depósito": "pages/3_Deposito.py"}
    if rol == "asistencia":
        return {"Asistencia": "pages/4_Asistencia.py"}
    return {}


def render_login_card():
    st.markdown(
        """
        <style>
        .auth-wrap {
            max-width: 420px;
            margin: 8vh auto 0;
            background: #ffffff;
            border: 1px solid #dbe7ee;
            border-radius: 16px;
            padding: 20px 22px;
            box-shadow: 0 2px 10px rgba(15, 23, 42, 0.06);
        }
        .auth-title {
            color: #0f2742;
            font-size: 24px;
            font-weight: 850;
            margin-bottom: 2px;
        }
        .auth-subtitle {
            color: #64748b;
            font-size: 13px;
            font-weight: 650;
            margin-bottom: 14px;
        }
        div[class*="st-key-auth_login_form"] input {
            background: #f8fafc !important;
            border-color: #dbe7ee !important;
        }
        div[class*="st-key-auth_login_form"] [data-testid="stFormSubmitButton"] button {
            background: #006b68 !important;
            border-color: #006b68 !important;
            color: #ffffff !important;
            min-height: 38px !important;
            box-shadow: none !important;
        }
        </style>
        <div class="auth-wrap">
            <div class="auth-title">Ingreso</div>
            <div class="auth-subtitle">Acceso operativo al sistema.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("auth_login_form"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        ingresar = st.form_submit_button("Ingresar", type="primary", use_container_width=True)
    if ingresar:
        try:
            ok = iniciar_sesion(usuario, password)
        except Exception as error:
            st.error(f"No se pudo iniciar sesión: {error}")
            return
        if ok:
            st.rerun()
    if st.session_state.get("auth_error"):
        st.error(st.session_state["auth_error"])


def render_usuario_sidebar():
    user = usuario_actual()
    if not user:
        return
    with st.sidebar:
        st.caption(f"Usuario: {user.get('usuario')}")
        st.caption(f"Rol: {user.get('rol')}")
        st.caption(f"Equipo: {user.get('equipo')}")
        if st.button("Cerrar sesión", use_container_width=True):
            cerrar_sesion()
            st.rerun()


def require_login(roles_permitidos=None):
    if not esta_logueado():
        st.warning("Iniciá sesión para acceder a esta sección.")
        render_login_card()
        st.stop()
    if not puede_ver(roles_permitidos):
        user = usuario_actual()
        st.error(f"Tu rol ({user.get('rol')}) no tiene acceso a esta sección.")
        render_usuario_sidebar()
        st.stop()
    render_usuario_sidebar()
