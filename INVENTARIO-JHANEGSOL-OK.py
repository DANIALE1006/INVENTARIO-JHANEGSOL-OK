import streamlit as st
from supabase import create_client, Client

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Jhanesgol", layout="wide", page_icon="📦")

# --- CONEXIÓN A SUPABASE ---
# ⚠️ REEMPLAZA ESTOS VALORES CON TUS CLAVES REALES DE SUPABASE:
SUPABASE_URL = "https://oqafvzwwooxkohkdmatv.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9xYWZ2end3b294a29oa2RtYXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgyNjc5MTcsImV4cCI6MjEwMzg0MzkxN30.t8XQWINbWs0x2FYs2heSCW8wsASLg39_xgYQ__tnUW8"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

st.title("📦 Sistema de Gestión: Inventario y Ventas - Jhanesgol")

# --- MENÚ DE NAVEGACIÓN ---
menu = st.sidebar.radio(
    "Menú Principal",
    ["📋 Productos / Catálogo", "🏢 Proveedores", "📥 Ingresos (Compras)", "🔄 Devoluciones", "🧾 Ventas (Facturación)", "📊 Estadísticas"]
)

# -------------------------------------------------------------------
# 1. MÓDULO DE PRODUCTOS / CATÁLOGO
# -------------------------------------------------------------------
if menu == "📋 Productos / Catálogo":
    st.header("📋 Catálogo de Productos")
    
    with st.expander("➕ Registrar Nuevo Producto"):
        with st.form("form_prod", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                codigo = st.text_input("Código Único *")
                marca = st.text_input("Marca")
                descripcion = st.text_area("Descripción *")
            with col2:
                costo = st.number_input("Costo (S/.)", min_value=0.0, step=0.5, format="%.2f")
                precio = st.number_input("Precio de Venta (S/.)", min_value=0.0, step=0.5, format="%.2f")
                stock_min = st.number_input("Stock Mínimo para Alerta", min_value=1, value=5)
            
            btn_guardar = st.form_submit_button("Guardar Producto")
            if btn_guardar:
                if codigo and descripcion:
                    data = {
                        "codigo": codigo, "marca": marca, "descripcion": descripcion,
                        "costo": costo, "precio": precio, "stock_minimo": stock_min
                    }
                    supabase.table("productos").insert(data).execute()
                    st.success("✅ Producto registrado exitosamente.")
                    st.rerun()
                else:
                    st.error("⚠️ El código y la descripción son obligatorios.")

    # Tabla de productos
    st.subheader("Inventario en Tiempo Real")
    prod_data = supabase.table("productos").select("*").execute()
    if prod_data.data:
        st.dataframe(prod_data.data, use_container_width=True)
    else:
        st.info("No hay productos registrados aún.")

# -------------------------------------------------------------------
# 2. MÓDULO DE PROVEEDORES
# -------------------------------------------------------------------
elif menu == "🏢 Proveedores":
    st.header("🏢 Registro de Proveedores")
    
    with st.form("form_prov", clear_on_submit=True):
        nombre = st.text_input("Nombre / Razón Social *")
        col1, col2 = st.columns(2)
        with col1:
            ruc = st.text_input("RUC / DNI")
            telefono = st.text_input("Teléfono")
        with col2:
            email = st.text_input("Email")
        
        if st.form_submit_button("Guardar Proveedor"):
            if nombre:
                supabase.table("proveedores").insert({"nombre": nombre, "ruc_dni": ruc, "telefono": telefono, "email": email}).execute()
                st.success("✅ Proveedor registrado.")
                st.rerun()

    prov_data = supabase.table("proveedores").select("*").execute()
    if prov_data.data:
        st.dataframe(prov_data.data, use_container_width=True)

# -------------------------------------------------------------------
# 3. MÓDULO DE INGRESOS (COMPRAS)
# -------------------------------------------------------------------
elif menu == "📥 Ingresos (Compras)":
    st.header("📥 Registrar Ingreso de Compras")
    
    prods = supabase.table("productos").select("id, codigo, descripcion, costo").execute().data
    provs = supabase.table("proveedores").select("id, nombre").execute().data

    if prods and provs:
        dict_prods = {f"{p['codigo']} - {p['descripcion']}": p for p in prods}
        dict_provs = {pr['nombre']: pr['id'] for pr in provs}

        with st.form("form_compras", clear_on_submit=True):
            nro_boleta = st.text_input("Número de Boleta / Factura de Compra *")
            prod_sel = st.selectbox("Seleccionar Producto", list(dict_prods.keys()))
            prov_sel = st.selectbox("Seleccionar Proveedor", list(dict_provs.keys()))
            
            col1, col2 = st.columns(2)
            with col1:
                cantidad = st.number_input("Cantidad Comprada", min_value=1, value=1)
            with col2:
                costo_unit = st.number_input("Costo Unitario (S/.)", value=float(dict_prods[prod_sel]['costo']))
            
            total_compra = cantidad * costo_unit
            st.markdown(f"**Total Compra:** S/. {total_compra:.2f}")

            if st.form_submit_button("Registrar Ingreso"):
                compra = {
                    "numero_boleta": nro_boleta,
                    "producto_id": dict_prods[prod_sel]['id'],
                    "proveedor_id": dict_provs[prov_sel],
                    "cantidad": cantidad,
                    "costo": costo_unit
                }
                supabase.table("compras").insert(compra).execute()
                st.success("✅ Ingreso registrado. El stock del producto ha aumentado automáticamente.")
                st.rerun()
    else:
        st.warning("⚠️ Debes registrar al menos un producto y un proveedor primero.")

# -------------------------------------------------------------------
# 4. MÓDULO DE DEVOLUCIONES
# -------------------------------------------------------------------
elif menu == "🔄 Devoluciones":
    st.header("🔄 Registro de Devoluciones a Proveedor")
    
    prods = supabase.table("productos").select("id, codigo, descripcion, precio").execute().data
    provs = supabase.table("proveedores").select("id, nombre").execute().data

    if prods and provs:
        dict_prods = {f"{p['codigo']} - {p['descripcion']}": p for p in prods}
        dict_provs = {pr['nombre']: pr['id'] for pr in provs}

        with st.form("form_devolucion", clear_on_submit=True):
            nro_boleta = st.text_input("Número de Boleta de la Compra")
            prod_sel = st.selectbox("Producto a Devolver", list(dict_prods.keys()))
            prov_sel = st.selectbox("Proveedor", list(dict_provs.keys()))
            
            col1, col2 = st.columns(2)
            with col1:
                cantidad = st.number_input("Cantidad a Devolver", min_value=1, value=1)
            with col2:
                precio = st.number_input("Precio Unitario", value=float(dict_prods[prod_sel]['precio']))
            
            motivo = st.text_area("Motivo de la Devolución *")

            if st.form_submit_button("Registrar Devolución"):
                if motivo:
                    dev = {
                        "numero_boleta": nro_boleta,
                        "producto_id": dict_prods[prod_sel]['id'],
                        "proveedor_id": dict_provs[prov_sel],
                        "cantidad": cantidad,
                        "precio": precio,
                        "motivo_devolucion": motivo
                    }
                    supabase.table("devoluciones").insert(dev).execute()
                    st.success("✅ Devolución registrada y ajustada en el inventario.")
                    st.rerun()
                else:
                    st.error("⚠️ Ingrese el motivo de la devolución.")

# -------------------------------------------------------------------
# 5. MÓDULO DE VENTAS (BOLETAS / FACTURAS)
# -------------------------------------------------------------------
elif menu == "🧾 Ventas (Facturación)":
    st.header("🧾 Punto de Venta y Emisión de Comprobantes")
    
    prods = supabase.table("productos").select("id, codigo, descripcion, precio, stock").execute().data
    
    if prods:
        dict_prods = {f"{p['codigo']} - {p['descripcion']} (Stock: {p['stock']})": p for p in prods}
        
        tipo_doc = st.selectbox("Tipo de Comprobante", ["BOLETA", "FACTURA"])
        serie_num = st.text_input("Número de Serie/Comprobante (Ej: B001-000123)")
        cliente = st.text_input("Nombre del Cliente")
        doc_cliente = st.text_input("DNI / RUC del Cliente")
        
        st.divider()
        prod_sel = st.selectbox("Seleccionar Producto a Vender", list(dict_prods.keys()))
        prod_actual = dict_prods[prod_sel]
        
        cant_venta = st.number_input("Cantidad", min_value=1, max_value=max(1, prod_actual['stock']), value=1)
        precio_venta = prod_actual['precio']
        
        subtotal = cant_venta * precio_venta
        igv = subtotal * 0.18
        total = subtotal + igv

        st.metric("Total a Cobrar (inc. IGV)", f"S/. {total:.2f}")

        if st.button("Emitir Comprobante y Descontar Stock"):
            if serie_num and cliente:
                # 1. Crear cabecera comprobante
                comp_data = {
                    "tipo_comprobante": tipo_doc,
                    "serie_numero": serie_num,
                    "cliente_nombre": cliente,
                    "cliente_documento": doc_cliente,
                    "subtotal": subtotal,
                    "igv": igv,
                    "total": total
                }
                res = supabase.table("comprobantes").insert(comp_data).execute()
                comp_id = res.data[0]['id']

                # 2. Registrar detalle (descuenta stock mediante el trigger)
                detalle = {
                    "comprobante_id": comp_id,
                    "producto_id": prod_actual['id'],
                    "cantidad": cant_venta,
                    "precio_unitario": precio_venta
                }
                supabase.table("detalle_comprobante").insert(detalle).execute()

                st.balloons()
                st.success(f"🎉 ¡{tipo_doc} emitida correctamente!")
                st.rerun()

# -------------------------------------------------------------------
# 6. MÓDULO DE ESTADÍSTICAS
# -------------------------------------------------------------------
elif menu == "📊 Estadísticas":
    st.header("📊 Analítica de Ventas y Productos")
    
    st.subheader("Top Productos Más Vendidos")
    top_v = supabase.table("vista_productos_mas_vendidos").select("*").execute()
    if top_v.data:
        st.dataframe(top_v.data, use_container_width=True)
    else:
        st.info("Aún no hay suficientes ventas registradas para generar analíticas.")
