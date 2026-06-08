import hashlib
import hmac
import os

from services.supabase_client import get_supabase_client


HASH_PREFIX = "pbkdf2_sha256"
ITERATIONS = 120_000


def generar_password_hash(password):
    password = (password or "").encode("utf-8")
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password, salt.encode("utf-8"), ITERATIONS).hex()
    return f"{HASH_PREFIX}${ITERATIONS}${salt}${digest}"


def verificar_password(password, password_hash):
    password = (password or "").encode("utf-8")
    partes = (password_hash or "").split("$")
    if len(partes) != 4 or partes[0] != HASH_PREFIX:
        return False
    _, iteraciones, salt, digest_guardado = partes
    try:
        iteraciones = int(iteraciones)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password, salt.encode("utf-8"), iteraciones).hex()
    return hmac.compare_digest(digest, digest_guardado)


def obtener_usuario_login(usuario):
    usuario = (usuario or "").strip()
    if not usuario:
        return None
    supabase = get_supabase_client()
    response = (
        supabase.table("usuarios_app")
        .select("id_usuario,usuario,password_hash,equipo,rol,activo")
        .eq("usuario", usuario)
        .eq("activo", True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None
