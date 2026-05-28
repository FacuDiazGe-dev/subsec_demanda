import os

import streamlit as st
from supabase import create_client


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

    return create_client(url, key)
