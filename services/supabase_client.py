import os

import httpx
import streamlit as st
from supabase import create_client
from supabase.lib.client_options import ClientOptions


@st.cache_resource
def get_supabase_client():
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
    except Exception:
        url = None
        key = None

    url = url or os.getenv("SUPABASE_URL")
    key = key or os.getenv("SUPABASE_KEY")

    if not url or not key:
        st.error("Faltan SUPABASE_URL y SUPABASE_KEY en secrets.toml o variables de entorno.")
        st.stop()

    httpx_client = httpx.Client(trust_env=False)
    options = ClientOptions(httpx_client=httpx_client)
    return create_client(url, key, options=options)
