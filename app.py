import streamlit as st
from supabase import create_client, Client

# Configuración de la página
st.set_page_config(page_title="Mi App con Supabase", page_icon="⚡")

st.title("⚡ Conexión con Supabase")

# -------------------------------------------------------------
# CREDENCIALES DIRECTAS EN EL CÓDIGO BASE
# -------------------------------------------------------------
URL = "https://oqafvzwwooxkohkdmatv.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9xYWZ2end3b294a29oa2RtYXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgyNjc5MTcsImV4cCI6MjEwMzg0MzkxN30.t8XQWINbWs0x2FYs2heSCW8wsASLg39_xgYQ__tnUW8"

# Conectar con Supabase
@st.cache_resource
def init_connection():
    return create_client(URL, KEY)

supabase = init_connection()

st.success("✅ Conectado exitosamente a Supabase")

# -------------------------------------------------------------
# CONSULTA A LA BASE DE DATOS
# -------------------------------------------------------------
st.subheader("Consultar Datos")

# Cambia "mi_tabla" por el nombre real de una tabla en tu Supabase
nombre_tabla = st.text_input("Nombre de la tabla:", value="mi_tabla")

if st.button("Buscar en Supabase"):
    try:
        respuesta = supabase.table(nombre_tabla).select("*").execute()
        
        if respuesta.data:
            st.write("Datos encontrados:")
            st.json(respuesta.data)
        else:
            st.info("La tabla está vacía o no existe.")
            
    except Exception as e:
        st.error(f"Error de consulta: {e}")
