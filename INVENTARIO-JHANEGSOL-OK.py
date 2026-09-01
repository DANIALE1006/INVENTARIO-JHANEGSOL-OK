import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Jhanegsol - Facturación e Inventarios", layout="wide", page_icon="📦")

# --- CONEXIÓN A SUPABASE ---
SUPABASE_URL = "https://oqafvzwwooxkohkdmatv.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9xYWZ2end3b294a29oa2RtYXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgyNjc5MTcsImV4cCI6MjEwMzg0MzkxN30.t8XQWINbWs0x2FYs2heSCW8wsASLg39_xgYQ__tnUW8"

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# --- ESTADO DE SESIÓN ---
if "carrito" not in st.session_state:
    st.session_state.carrito = []

st.title("📦 Sistema Comercial, Inventarios y Facturación - Jhanesgol")

# --- MENÚ PRINCIPAL ---
menu = st.sidebar.radio(
    "Menú Principal",
    [
        "📋 Catálogo de Productos", 
        "🏢 Proveedores", 
        "👥 Listado y Gestión de Clientes",
        "📥 Ingresos (Compras / Entrada)", 
        "🧾 Ventas y Emisión de Comprobantes", 
        "🔄 Devoluciones", 
        "📊 Histórico de Comprobantes",
        "📈 Estadísticas, Alertas y Reportes"
    ]
)

# -------------------------------------------------------------------
# 1. CATÁLOGO DE PRODUCTOS
# -------------------------------------------------------------------
if menu == "📋 Catálogo de Productos":
    st.header("📋 Catálogo de Productos e Inventario")
    
    with st.expander("➕ Registrar Nuevo Producto", expanded=False):
        with st.form("form_prod", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                codigo = st.text_input("Código *")
                marca = st.text_input("Marca")
                descripcion = st.text_area("Descripción *")
            with col2:
                costo = st.number_input("Costo (S/.)", min_value=0.0, format="%.2f")
                precio = st.number_input("Precio Venta (S/.)", min_value=0.0, format="%.2f")
                stock = st.number_input("Stock Inicial", min_value=0, value=0)
                stock_min = st.number_input("Stock Mínimo Alerta", min_value=1, value=5)
            
            if st.form_submit_button("Guardar Producto"):
                if codigo and descripcion:
                    data = {
                        "codigo": codigo, "marca": marca, "descripcion": descripcion,
                        "costo": costo, "precio": precio, "stock": stock, "stock_minimo": stock_min
                    }
                    supabase.table("productos").insert(data).execute()
                    st.success("✅ Producto registrado exitosamente.")
                    st.rerun()
                else:
                    st.error("⚠️ El código y la descripción son requeridos.")

    # Búsqueda interactiva
    prod_data = supabase.table("productos").select("*").execute().data
    if prod_data:
        df_prod = pd.DataFrame(prod_data)
        busqueda = st.text_input("🔍 Buscar por código, marca o descripción:")
        if busqueda:
            df_prod = df_prod[df_prod.apply(lambda r: busqueda.lower() in str(r).lower(), axis=1)]
        st.dataframe(df_prod, use_container_width=True)

# -------------------------------------------------------------------
# 2. PROVEEDORES
# -------------------------------------------------------------------
elif menu == "🏢 Proveedores":
    st.header("🏢 Registro y Directorio de Proveedores")
    
    with st.form("form_prov", clear_on_submit=True):
        nombre = st.text_input("Nombre / Razón Social *")
        c1, c2 = st.columns(2)
        with c1:
            ruc = st.text_input("RUC / DNI")
            telefono = st.text_input("Teléfono")
        with c2:
            email = st.text_input("Email")
        
        if st.form_submit_button("Guardar Proveedor"):
            if nombre:
                supabase.table("proveedores").insert({"nombre": nombre, "ruc_dni": ruc, "telefono": telefono, "email": email}).execute()
                st.success("✅ Proveedor registrado.")
                st.rerun()

    prov_data = supabase.table("proveedores").select("*").execute().data
    if prov_data:
        st.dataframe(pd.DataFrame(prov_data), use_container_width=True)

# -------------------------------------------------------------------
# 3. LISTADO Y GESTIÓN DE CLIENTES
# -------------------------------------------------------------------
elif menu == "👥 Listado y Gestión de Clientes":
    st.header("👥 Base de Datos y Registro de Clientes")
    
    with st.expander("➕ Registrar Nuevo Cliente", expanded=False):
        with st.form("form_cli_dir", clear_on_submit=True):
            cli_nom = st.text_input("Nombre o Razón Social del Cliente *")
            c1, c2 = st.columns(2)
            with c1:
                cli_doc = st.text_input("DNI / RUC *")
                cli_tel = st.text_input("Teléfono")
            with c2:
                cli_dir = st.text_input("Dirección")
            
            if st.form_submit_button("Guardar Cliente"):
                if cli_nom and cli_doc:
                    supabase.table("clientes").insert({
                        "nombre": cli_nom.upper(),
                        "ruc_dni": cli_doc,
                        "telefono": cli_tel,
                        "direccion": cli_dir
                    }).execute()
                    st.success(f"✅ Cliente {cli_nom.upper()} registrado con éxito.")
                    st.rerun()
                else:
                    st.error("⚠️ El Nombre y el DNI/RUC son campos obligatorios.")

    res_clientes = supabase.table("clientes").select("*").execute().data
    if res_clientes:
        df_clientes = pd.DataFrame(res_clientes)
        busqueda_c = st.text_input("🔍 Buscar cliente por Nombre o DNI/RUC:")
        if busqueda_c:
            df_clientes = df_clientes[df_clientes.apply(lambda r: busqueda_c.lower() in str(r).lower(), axis=1)]
        st.dataframe(df_clientes[["id", "nombre", "ruc_dni", "telefono", "direccion"]], use_container_width=True)
    else:
        st.info("No hay clientes registrados en la base de datos.")

# -------------------------------------------------------------------
# 4. INGRESOS (COMPRAS / ENTRADA DE STOCK)
# -------------------------------------------------------------------
elif menu == "📥 Ingresos (Compras / Entrada)":
    st.header("📥 Registro de Ingresos de Mercadería (Compras)")
    st.info("Registra las guías de compra de proveedores para aumentar el stock de tu inventario automáticamente.")

    prods = supabase.table("productos").select("id, codigo, descripcion, stock, costo").execute().data
    provs = supabase.table("proveedores").select("id, nombre").execute().data

    if prods and provs:
        dict_prods = {f"{p['codigo']} - {p['descripcion']} (Stock actual: {p['stock']})": p for p in prods}
        dict_provs = {pr['nombre']: pr['id'] for pr in provs}

        with st.form("form_ingresos", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                prov_sel = st.selectbox("Proveedor", list(dict_provs.keys()))
                nro_fact_compra = st.text_input("N° Factura/Guía de Compra", value="F001-0001")
            with c2:
                prod_sel = st.selectbox("Producto a Ingresar", list(dict_prods.keys()))
                cant_ingreso = st.number_input("Cantidad que Ingresa", min_value=1, value=1)
            with c3:
                nuevo_costo = st.number_input("Costo Unitario Compra (S/.)", min_value=0.0, value=float(dict_prods[prod_sel]['costo']))
                fecha_compra = st.date_input("Fecha de Ingreso", datetime.now())

            if st.form_submit_button("📥 Registrar Ingreso y Aumentar Stock"):
                prod_info = dict_prods[prod_sel]
                nuevo_stock = prod_info['stock'] + cant_ingreso
                
                # Actualizar stock en BD
                supabase.table("productos").update({"stock": nuevo_stock, "costo": nuevo_costo}).eq("id", prod_info['id']).execute()
                st.success(f"✅ Stock actualizado. Nuevo Stock de '{prod_info['descripcion']}': {nuevo_stock}")
                st.rerun()
    else:
        st.warning("⚠️ Asegúrate de tener al menos 1 producto y 1 proveedor registrados.")

import io

# -------------------------------------------------------------------
# 5. VENTAS Y EMISIÓN DE COMPROBANTES
# -------------------------------------------------------------------
elif menu == "🧾 Ventas y Emisión de Comprobantes":
    st.header("🧾 Punto de Venta: Emisión de Boletas, Facturas y Tickets")

    # Inicializar carrito si no existe
    if "carrito" not in st.session_state:
        st.session_state.carrito = []

    # 1. Selección o Creación de Cliente
    st.subheader("👤 Seleccionar o Registrar Cliente")
    res_clientes_v = supabase.table("clientes").select("*").execute().data
    df_cli_v = pd.DataFrame(res_clientes_v) if res_clientes_v else pd.DataFrame()

    opcion_cliente = st.radio(
        "Tipo de Cliente", 
        ["Cliente Genérico (Varios)", "Seleccionar Cliente Registrado", "➕ Registrar Nuevo Cliente"],
        horizontal=True
    )

    cliente_nom = "CLIENTE VARIOS"
    cliente_doc = "00000000"

    if opcion_cliente == "Cliente Genérico (Varios)":
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.text_input("Nombre / Razón Social", value=cliente_nom, disabled=True)
        with col_c2:
            st.text_input("DNI / RUC", value=cliente_doc, disabled=True)

    elif opcion_cliente == "Seleccionar Cliente Registrado":
        if not df_cli_v.empty:
            df_frec = df_cli_v[df_cli_v["ruc_dni"] != "00000000"]
            lista_nombres = df_frec["nombre"].tolist() if not df_frec.empty else df_cli_v["nombre"].tolist()
            
            cliente_sel = st.selectbox("Buscar Cliente Frecuente", lista_nombres)
            datos_c = df_cli_v[df_cli_v["nombre"] == cliente_sel].iloc[0]
            cliente_nom = datos_c["nombre"]
            cliente_doc = datos_c["ruc_dni"]

            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.text_input("Nombre / Razón Social", value=cliente_nom, disabled=True)
            with col_c2:
                st.text_input("DNI / RUC", value=cliente_doc, disabled=True)
        else:
            st.warning("No hay clientes registrados en la BD. Usa la opción 'Registrar Nuevo Cliente'.")

    elif opcion_cliente == "➕ Registrar Nuevo Cliente":
        st.info("Ingresa los datos para registrarlo y usarlo en este comprobante:")
        with st.form("form_cli_rapido_venta"):
            col1, col2 = st.columns(2)
            with col1:
                nuevo_nom = st.text_input("Nombre / Razón Social *")
                nuevo_tel = st.text_input("Teléfono")
            with col2:
                nuevo_doc = st.text_input("DNI / RUC *")
                nueva_dir = st.text_input("Dirección")
            
            if st.form_submit_button("Guardar y Aplicar Cliente"):
                if nuevo_nom and nuevo_doc:
                    supabase.table("clientes").insert({
                        "nombre": nuevo_nom.upper(),
                        "ruc_dni": nuevo_doc,
                        "telefono": nuevo_tel,
                        "direccion": nueva_dir
                    }).execute()
                    st.success(f"✅ Cliente {nuevo_nom.upper()} registrado.")
                    cliente_nom = nuevo_nom.upper()
                    cliente_doc = nuevo_doc
                    st.rerun()
                else:
                    st.error("⚠️ Nombre y DNI/RUC obligatorios.")

    st.divider()

    # 2. Configuración del Comprobante
    c1, c2, c3 = st.columns(3)
    with c1:
        tipo_doc = st.selectbox("Tipo de Comprobante *", ["BOLETA DE VENTA", "FACTURA", "TICKET DE VENTA", "NOTA DE CRÉDITO", "NOTA DE DÉBITO"])
        
        # Generación de correlativo automático
        if "FACTURA" in tipo_doc:
            prefijo = "F001"
        elif "TICKET" in tipo_doc:
            prefijo = "T001"
        elif "NOTA DE CRÉDITO" in tipo_doc:
            prefijo = "NC01"
        elif "NOTA DE DÉBITO" in tipo_doc:
            prefijo = "ND01"
        else:
            prefijo = "B001"

        try:
            ult_comp = supabase.table("comprobantes")\
                .select("serie_numero")\
                .like("serie_numero", f"{prefijo}-%")\
                .order("id", desc=True)\
                .limit(1)\
                .execute().data
            
            if ult_comp:
                ultimo_num = int(ult_comp[0]["serie_numero"].split("-")[1])
                siguiente_num = ultimo_num + 1
            else:
                siguiente_num = 1
                
            sugerido = f"{prefijo}-{siguiente_num:06d}"
        except Exception:
            sugerido = f"{prefijo}-000001"

        serie_num = st.text_input("Serie y Número Comprobante", value=sugerido)

    # 3. Selección e Inclusión de Productos al Carrito
    prods = supabase.table("productos").select("id, codigo, descripcion, precio, stock").execute().data
    if prods:
        dict_prods = {f"{p['codigo']} | {p['descripcion']} (Stock: {p['stock']})": p for p in prods}
        
        cp1, cp2, cp3 = st.columns([3, 1, 1])
        with cp1:
            p_sel_key = st.selectbox("Buscar Producto para Salida / Venta", list(dict_prods.keys()))
        with cp2:
            cant_v = st.number_input("Cantidad", min_value=1, value=1)
        with cp3:
            st.write("")
            st.write("")
            if st.button("➕ Agregar al Comprobante"):
                p_info = dict_prods[p_sel_key]
                if cant_v <= p_info['stock']:
                    st.session_state.carrito.append({
                        "id": p_info['id'],
                        "codigo": p_info['codigo'],
                        "descripcion": p_info['descripcion'],
                        "cantidad": cant_v,
                        "precio_unitario": p_info['precio'],
                        "subtotal": cant_v * p_info['precio']
                    })
                    st.success("✅ Producto agregado")
                    st.rerun()
                else:
                    st.error("⚠️ La cantidad supera el stock disponible.")

    # 4. Detalle y Vista Previa del Comprobante
    if st.session_state.carrito:
        st.subheader("📋 Detalle de la Venta")
        df_car = pd.DataFrame(st.session_state.carrito)
        st.dataframe(df_car[["codigo", "descripcion", "cantidad", "precio_unitario", "subtotal"]], use_container_width=True)

        total_gen = float(df_car["subtotal"].sum())
        subtotal = total_gen / 1.18
        igv = total_gen - subtotal

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Op. Gravada (Subtotal)", f"S/. {subtotal:.2f}")
        col_m2.metric("IGV (18%)", f"S/. {igv:.2f}")
        col_m3.metric("TOTAL GENERAL", f"S/. {total_gen:.2f}")

        # --- SECCIÓN VISTA PREVIA Y EMISIÓN ---
        st.divider()
        st.subheader("👁️ Vista Previa del Comprobante")

        # Construir tabla HTML de productos para la vista previa
        filas_html = ""
        for item in st.session_state.carrito:
            filas_html += f"""
            <tr>
                <td style="padding: 6px; border-bottom: 1px dashed #ccc; text-align: center;">{item['cantidad']}</td>
                <td style="padding: 6px; border-bottom: 1px dashed #ccc;">{item['descripcion']}</td>
                <td style="padding: 6px; border-bottom: 1px dashed #ccc; text-align: right;">S/. {item['precio_unitario']:.2f}</td>
                <td style="padding: 6px; border-bottom: 1px dashed #ccc; text-align: right;">S/. {item['subtotal']:.2f}</td>
            </tr>
            """

        html_preview = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{tipo_doc} {serie_num}</title>
</head>
<body style="background-color: #f0f2f5; font-family: 'Courier New', Courier, monospace; margin: 0; padding: 10px;">
    <div id="ticket-print" style="max-width: 380px; margin: 0 auto; padding: 20px; border: 2px dashed #333; background-color: #ffffff; color: #000000; font-size: 13px;">
        <div style="text-align: center; margin-bottom: 10px;">
            <h3 style="margin: 0; font-size: 18px; color: #000;">JHANEGSOL S.A.C.</h3>
            <p style="margin: 2px 0;">RUC: 20600000001</p>
            <p style="margin: 2px 0;">Oficina Principal - Huacho, Lima - Perú</p>
            <hr style="border-top: 1px dashed #000; margin: 8px 0;">
            <h4 style="margin: 5px 0; font-size: 15px; color: #000;">{tipo_doc}</h4>
            <p style="margin: 2px 0; font-weight: bold; font-size: 14px;">N° {serie_num}</p>
        </div>
        <div style="margin-bottom: 10px;">
            <p style="margin: 2px 0;"><strong>Cliente:</strong> {cliente_nom}</p>
            <p style="margin: 2px 0;"><strong>DNI/RUC:</strong> {cliente_doc}</p>
        </div>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 10px; font-size: 12px;">
            <thead>
                <tr style="border-bottom: 1px solid #000; border-top: 1px solid #000;">
                    <th style="text-align: center; padding: 4px;">CANT</th>
                    <th style="text-align: left; padding: 4px;">DESCRIPCIÓN</th>
                    <th style="text-align: right; padding: 4px;">P.U.</th>
                    <th style="text-align: right; padding: 4px;">TOTAL</th>
                </tr>
            </thead>
            <tbody>
                {filas_html}
            </tbody>
        </table>
        <div style="text-align: right; margin-top: 10px; border-top: 1px solid #000; padding-top: 5px;">
            <p style="margin: 2px 0;"><strong>OP. GRAVADA:</strong> S/. {subtotal:.2f}</p>
            <p style="margin: 2px 0;"><strong>IGV (18%):</strong> S/. {igv:.2f}</p>
            <p style="margin: 4px 0; font-size: 15px;"><strong>TOTAL A PAGAR: S/. {total_gen:.2f}</strong></p>
        </div>
        <div style="text-align: center; margin-top: 15px; font-size: 11px;">
            <p style="margin: 2px 0;">¡Gracias por su compra en JHANEGSOL S.A.C.!</p>
        </div>
    </div>
</body>
</html>
"""

        # Renderizar la vista previa visual
        st.components.v1.html(html_preview, height=450, scrolling=True)

        # Botones de Acción
        b_col1, b_col2, b_col3 = st.columns(3)
        
        with b_col1:
            if st.button("🔴 Vaciar Selección", use_container_width=True):
                st.session_state.carrito = []
                st.rerun()

        with b_col2:
            # Botón para descargar el Comprobante/Ticket en formato HTML (para imprimir o guardar)
            st.download_button(
                label="📥 DESCARGAR COMPROBANTE (HTML)",
                data=html_preview,
                file_name=f"Comprobante_{tipo_doc.replace(' ', '_')}_{serie_num}.html",
                mime="text/html",
                use_container_width=True
            )

        with b_col3:
            if st.button(f"🖨️ EMITIR {tipo_doc} Y DESCONTAR STOCK", type="primary", use_container_width=True):
                try:
                    # Validar e incrementar automáticamente si la serie y número ya existen
                    correlativo_final = serie_num
                    existe = supabase.table("comprobantes").select("id").eq("serie_numero", correlativo_final).execute().data
                    
                    if existe:
                        prefix = correlativo_final.split("-")[0]
                        ult_reg = supabase.table("comprobantes")\
                            .select("serie_numero")\
                            .like("serie_numero", f"{prefix}-%")\
                            .order("id", desc=True)\
                            .limit(1)\
                            .execute().data
                        
                        if ult_reg:
                            num_act = int(ult_reg[0]["serie_numero"].split("-")[1]) + 1
                        else:
                            num_act = 1
                        correlativo_final = f"{prefix}-{num_act:06d}"

                    # 1. Guardar la cabecera del comprobante
                    comp_data = {
                        "tipo_comprobante": tipo_doc,
                        "serie_numero": correlativo_final,
                        "cliente_nombre": cliente_nom,
                        "cliente_documento": cliente_doc,
                        "subtotal": round(subtotal, 2),
                        "igv": round(igv, 2),
                        "total": round(total_gen, 2)
                    }
                    
                    res = supabase.table("comprobantes").insert(comp_data).execute()
                    
                    if res.data:
                        comp_id = res.data[0]['id']

                        # 2. Guardar el detalle de items y descontar stock
                        for item in st.session_state.carrito:
                            det = {
                                "comprobante_id": comp_id,
                                "producto_id": item['id'],
                                "cantidad": item['cantidad'],
                                "precio_unitario": item['precio_unitario']
                            }
                            supabase.table("detalle_comprobante").insert(det).execute()

                            # Descontar del inventario
                            prod_bd = supabase.table("productos").select("stock").eq("id", item['id']).execute().data[0]
                            nuevo_stk = prod_bd['stock'] - item['cantidad']
                            supabase.table("productos").update({"stock": nuevo_stk}).eq("id", item['id']).execute()

                        st.balloons()
                        st.success(f"🎉 ¡{tipo_doc} {correlativo_final} emitida con éxito para JHANEGSOL S.A.C.!")
                        st.session_state.carrito = []
                        st.rerun()
                    else:
                        st.error("⚠️ La base de datos no devolvió respuesta al guardar el comprobante.")
                        
                except Exception as e:
                    st.error(f"❌ Error al procesar la venta: {str(e)}")
# -------------------------------------------------------------------
# 6. DEVOLUCIONES
# -------------------------------------------------------------------
elif menu == "🔄 Devoluciones":
    st.header("🔄 Registro de Devoluciones de Clientes / Proveedores")
    
    col1, col2 = st.columns(2)
    with col1:
        tipo_doc = st.selectbox("Tipo Comprobante", ["BOLETA", "FACTURA", "TICKET", "NOTA DE CRÉDITO"])
        nro_doc = st.text_input("Número Comprobante")
        tipo_op = st.selectbox("Tipo de Operación", ["DEVOLUCIÓN POR DEFECTO", "DEVOLUCIÓN POR STOCK", "AJUSTE DE INVENTARIO"])
    with col2:
        fecha_emision = st.date_input("Fecha", datetime.now())
        motivo = st.text_area("Motivo de Devolución *")

    prods = supabase.table("productos").select("id, codigo, descripcion, precio").execute().data
    provs = supabase.table("proveedores").select("id, nombre").execute().data

    if prods and provs:
        dict_prods = {f"{p['codigo']} - {p['descripcion']}": p for p in prods}
        dict_provs = {pr['nombre']: pr['id'] for pr in provs}

        prod_sel = st.selectbox("Seleccionar Producto", list(dict_prods.keys()))
        prov_sel = st.selectbox("Proveedor", list(dict_provs.keys()))
        cant_dev = st.number_input("Cantidad a Devolver", min_value=1, value=1)

        if st.button("Registrar Devolución"):
            if motivo and nro_doc:
                dev_data = {
                    "numero_boleta": nro_doc,
                    "producto_id": dict_prods[prod_sel]["id"],
                    "proveedor_id": dict_provs[prov_sel],
                    "cantidad": cant_dev,
                    "precio": dict_prods[prod_sel]["precio"],
                    "motivo_devolucion": f"[{tipo_doc} - {tipo_op}] | {motivo}"
                }
                supabase.table("devoluciones").insert(dev_data).execute()
                st.success("✅ Devolución procesada.")
                st.rerun()

# -------------------------------------------------------------------
# 7. HISTÓRICO DE COMPROBANTES Y SALIDAS
# -------------------------------------------------------------------
elif menu == "📊 Histórico de Comprobantes":
    st.header("📊 Histórico de Ventas y Comprobantes Emitidos")
    comps = supabase.table("comprobantes").select("*").execute().data
    if comps:
        st.dataframe(pd.DataFrame(comps), use_container_width=True)
    else:
        st.info("Aún no se han emitido comprobantes de venta.")

# -------------------------------------------------------------------
# 8. ESTADÍSTICAS, ALERTAS Y REPORTES
# -------------------------------------------------------------------
elif menu == "📈 Estadísticas, Alertas y Reportes":
    st.header("📈 Panel de Inteligencia Comercial y Alertas")

    # A. ALERTAS DE REABASTECIMIENTO
    st.subheader("⚠️ Alertas de Stock Bajo (Para Comprar)")
    try:
        alertas_res = supabase.table("vista_alerta_stock").select("*").execute().data
        df_alertas = pd.DataFrame(alertas_res) if alertas_res else pd.DataFrame()
        
        if not df_alertas.empty:
            st.error(f"¡Atención! Hay {len(df_alertas)} productos con stock crítico (mínimo alcanzado).")
            st.dataframe(df_alertas[["codigo", "descripcion", "stock", "proveedor", "costo_actual"]], use_container_width=True)
        else:
            st.success("El inventario se encuentra en niveles óptimos.")
    except Exception as e:
        st.warning("Verifica que las vistas SQL estén creadas correctamente en Supabase.")

    st.divider()

    # B. REPORTES Y PRODUCTOS MÁS VENDIDOS
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Top Productos Más Vendidos**")
        try:
            top_prod_res = supabase.table("vista_productos_mas_vendidos").select("*").execute().data
            df_top_prod = pd.DataFrame(top_prod_res) if top_prod_res else pd.DataFrame()
            if not df_top_prod.empty:
                st.bar_chart(df_top_prod.set_index("descripcion")["total_unidades_vendidas"])
                st.dataframe(df_top_prod[["codigo", "descripcion", "total_unidades_vendidas", "total_recaudado"]])
        except Exception as e:
            st.warning("No se pudieron cargar los datos de productos más vendidos.")

    with col2:
        st.markdown("**Clientes Frecuentes (Top Compradores)**")
        try:
            top_cli_res = supabase.table("vista_clientes_frecuentes").select("*").execute().data
            df_top_cli = pd.DataFrame(top_cli_res) if top_cli_res else pd.DataFrame()
            if not df_top_cli.empty:
                st.dataframe(df_top_cli[["nombre", "ruc_dni", "cantidad_compras", "total_gastado"]])
        except Exception as e:
            st.warning("No se pudieron cargar los datos de clientes frecuentes.")

    st.divider()

    # C. COMPARATIVO DE PRECIOS POR PROVEEDOR
    st.subheader("🏷️ Proveedores con Mejor Precio Registrado")
    try:
        precios_res = supabase.table("vista_mejor_precio_proveedor").select("*").execute().data
        df_precios = pd.DataFrame(precios_res) if precios_res else pd.DataFrame()
        if not df_precios.empty:
            st.dataframe(df_precios, use_container_width=True)
    except Exception as e:
        st.warning("No se pudieron cargar las alertas de mejores precios.")


