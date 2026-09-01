import io
import base64
from datetime import datetime
import pandas as pd
import streamlit as st
from supabase import create_client, Client
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

# --- INICIALIZACIÓN SUPABASE ---
def init_supabase() -> Client:
    try:
        if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        else:
            # Reemplaza con tu URL y KEY reales si no usas st.secrets
            url = "https://oqafvzwwooxkohkdmatv.supabase.co"
            key = "TU_SUPABASE_ANON_KEY_COMPLETA_AQUI"

        return create_client(url, key)
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
        return None

supabase = init_supabase()

# --- ESTADO DE SESIÓN ---
if "num_ultimo_comp" not in st.session_state:
    st.session_state.num_ultimo_comp = ""

if "procesando_operacion" not in st.session_state:
    st.session_state.procesando_operacion = False

if "pdf_generado" not in st.session_state:
    st.session_state.pdf_generado = None

if "carrito_ventas" not in st.session_state:
    st.session_state.carrito_ventas = []

if "carrito_nc" not in st.session_state:
    st.session_state.carrito_nc = []

# --- PREVISUALIZACIÓN DE PDF (SIN POPPLER / SIN PDF2IMAGE) ---
def mostrar_previsualizacion_pdf(pdf_bytes):
    """Muestra una vista previa del PDF generado usando un iframe HTML en lugar de pdf2image."""
    if pdf_bytes:
        st.markdown("### 👁️ Previsualización del Comprobante")
        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)

# --- GENERADOR DE PDF ---
def generar_pdf_comprobante(tipo_doc, serie_num, cliente_nom, cliente_doc, items, subtotal, igv, total, **kwargs):
    # Lógica de generación con ReportLab
    buffer = io.BytesIO()
    # ... Tu implementación de ReportLab para armar el 'story' ...
    # doc.build(story)
    return buffer.getvalue()

def comprobante_existe(serie_numero):
    try:
        res = supabase.table("comprobantes").select("id").eq("serie_numero", serie_numero).execute()
        return len(res.data) > 0
    except Exception:
        return False

# --- EMISIÓN DE VENTAS ---
def emitir_venta(tipo_doc, serie_num, cliente_nom, cliente_doc, subtotal, igv, total_gen):
    for item in st.session_state.carrito_ventas:
        det = {
            "comprobante_id": serie_num,
            "producto_id": item["id"],
            "cantidad": item["cantidad"],
            "precio_unitario": item["precio"],
            "subtotal": item["subtotal"]
        }
        ejecutar_consulta("detalle_comprobante", "insert", det)

        # Descontar stock
        res_p = supabase.table("productos").select("stock").eq("id", item["id"]).single().execute()
        st_act = int(res_p.data.get("stock", 0))
        ejecutar_consulta("productos", "update", {"stock": st_act - int(item["cantidad"])}, eq_col="id", eq_val=item["id"])

    st.session_state.pdf_generado = generar_pdf_comprobante(
        tipo_doc, serie_num, cliente_nom, cliente_doc,
        st.session_state.carrito_ventas, subtotal, igv, total_gen
    )

# --- EMISIÓN DE NOTA DE CRÉDITO / DÉBITO ---
def emitir_nota(tipo_nota, serie_nota, cliente_nom, cliente_doc, subtotal, igv, total_gen, **kwargs):
    for item in st.session_state.carrito_nc:
        p_id = item["id"]
        cantidad = int(item["cantidad"])
        
        reg_dev = {
            "nota_id": serie_nota,
            "producto_id": p_id,
            "cantidad": cantidad
        }
        ejecutar_consulta("devoluciones", "insert", reg_dev)

        # Aumento de stock en nota de crédito
        prod_actual = supabase.table("productos").select("stock").eq("id", p_id).single().execute()
        if prod_actual.data:
            stock_previo = int(prod_actual.data.get("stock") or 0)
            nuevo_stock = stock_previo + cantidad
            ejecutar_consulta("productos", "update", data={"stock": nuevo_stock}, eq_col="id", eq_val=p_id)

    st.session_state.pdf_generado = generar_pdf_comprobante(
        tipo_nota, serie_nota, cliente_nom, cliente_doc,
        st.session_state.carrito_nc, subtotal, igv, total_gen
    )

# --- BLOQUE DE VISTA / DESCARGA ---
if st.session_state.get("pdf_generado"):
    st.download_button(
        label="📄 Descargar Comprobante PDF",
        data=st.session_state.pdf_generado,
        file_name=f"{st.session_state.num_ultimo_comp}.pdf",
        mime="application/pdf",
    )
    mostrar_previsualizacion_pdf(st.session_state.pdf_generado)

# --- 8. ESTADÍSTICAS Y MÉTRICAS ---
elif menu == "📈 Estadísticas y Métricas de Negocio":
    st.header("📈 Métricas del Negocio y Análisis de Rendimiento")

    comps = ejecutar_consulta("comprobantes")
    if comps:
        df_comps = pd.DataFrame(comps)
        total_ventas = df_comps["total"].sum()
        cant_ventas = len(df_comps)

        c1, c2 = st.columns(2)
        c1.metric("Ventas Totales Registradas", f"S/. {total_ventas:.2f}")
        c2.metric("Comprobantes Emitidos", cant_ventas)

    st.divider()

    # 1. PRODUCTOS MÁS VENDIDOS
    st.subheader("🔥 Productos Más Vendidos")
    res_detalles = supabase.table("detalle_comprobante").select("cantidad, producto_id, productos(codigo, descripcion)").execute()

    if res_detalles.data:
        items_list = []
        for d in res_detalles.data:
            prod_info = d.get("productos") or {}
            items_list.append({
                "Código": prod_info.get("codigo", "N/A"),
                "Producto": prod_info.get("descripcion", "Sin nombre"),
                "Cantidad Vendida": d.get("cantidad", 0)
            })
        df_vendidos = pd.DataFrame(items_list)
        df_ranking = df_vendidos.groupby(["Código", "Producto"])["Cantidad Vendida"].sum().reset_index()
        df_ranking = df_ranking.sort_values(by="Cantidad Vendida", ascending=False)

        col_tbl, col_chart = st.columns([2, 2])
        with col_tbl:
            st.dataframe(df_ranking, use_container_width=True)
        with col_chart:
            st.bar_chart(data=df_ranking, x="Producto", y="Cantidad Vendida")

    # 2. ALERTAS DE QUIEBRE DE STOCK
    st.subheader("⚠️ Alertas de Quiebre / Stock Crítico")
    prods_stock = ejecutar_consulta("productos")
    if prods_stock:
        df_stock = pd.DataFrame(prods_stock)
        if "stock_minimo" in df_stock.columns:
            df_quiebre = df_stock[df_stock["stock"] <= df_stock["stock_minimo"]]
        else:
            df_quiebre = df_stock[df_stock["stock"] <= 5]

        if not df_quiebre.empty:
            cols_mostrar = [c for c in ["codigo", "descripcion", "stock", "stock_minimo"] if c in df_quiebre.columns]
            st.warning(f"Se encontraron {len(df_quiebre)} productos en nivel crítico de reabastecimiento:")
            st.dataframe(df_quiebre[cols_mostrar], use_container_width=True)
        else:
            st.success("✅ Todos los productos tienen niveles aceptables de stock.")

    # 3. PROVEEDORES Y PRECIOS DE COMPRA
    st.subheader("🏷️ Análisis de Precios por Proveedor")
    df_prods = pd.DataFrame(prods_stock) if prods_stock else pd.DataFrame()
    if not df_prods.empty and "costo" in df_prods.columns:
        df_costos = df_prods[["codigo", "descripcion", "costo", "precio"]].sort_values(by="costo", ascending=True)
        st.dataframe(df_costos, use_container_width=True)
