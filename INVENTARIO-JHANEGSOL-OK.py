from datetime import datetime
import io
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from supabase import Client, create_client
import streamlit as st

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Sistema Jhanegsol - Facturación e Inventarios",
    layout="wide",
    page_icon="📦",
)

# --- CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    try:
        if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        else:
            url = "https://oqafvzwwooxkohkdmatv.supabase.co"
            key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9xYWZ2end3b294a29oa2RtYXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgyNjc5MTcsImV4cCI6MjEwMzg0MzkxN30.t8XQWINbWs0x2FYs2heSCW8wsASLg39_xgYQ__tnUW8"

        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Error al conectar con Supabase: {e}")
        st.stop()

supabase = init_supabase()

# --- FUNCIÓN DE CONSULTA SEGURA ---
def ejecutar_consulta(
    tabla,
    consulta_type="select",
    data=None,
    eq_col=None,
    eq_val=None,
    like_col=None,
    like_val=None,
    order_col=None,
    desc=False,
    limit=None,
):
    try:
        query = supabase.table(tabla)
        if consulta_type == "select":
            query = query.select("*" if not data else data)
            if eq_col and eq_val:
                query = query.eq(eq_col, eq_val)
            if like_col and like_val:
                query = query.like(like_col, like_val)
            if order_col:
                query = query.order(order_col, desc=desc)
            if limit:
                query = query.limit(limit)
            return query.execute().data
        elif consulta_type == "insert":
            return query.insert(data).execute()
        elif consulta_type == "update":
            return query.update(data).eq(eq_col, eq_val).execute()
    except Exception as e:
        st.error(f"⚠️ Error en base de datos (Tabla '{tabla}'): {e}")
        return None

# --- ESTADO DE SESIÓN ---
if "carrito" not in st.session_state:
    st.session_state.carrito = []

# --- INTERFAZ PRINCIPAL ---
st.title("📦 Sistema Comercial, Inventarios y Facturación - Jhanegsol")

menu = st.sidebar.radio(
    "Menú Principal",
    [
        "📋 Catálogo de Productos",
        "🏢 Proveedores",
        "👥 Listado y Gestión de Clientes",
        "📥 Ingresos (Compras / Entrada)",
        "🧾 Ventas y Emisión de Comprobantes",
        "📊 Histórico de Comprobantes",
        "📈 Estadísticas y Métricas de Negocio",
    ],
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
                stock_min = st.number_input("Stock Mínimo (Alerta de Quiebre)", min_value=1, value=5)

            if st.form_submit_button("Guardar Producto"):
                if codigo and descripcion:
                    data = {
                        "codigo": codigo,
                        "marca": marca,
                        "descripcion": descripcion,
                        "costo": costo,
                        "precio": precio,
                        "stock": stock,
                        "stock_minimo": stock_min,
                    }
                    res = ejecutar_consulta("productos", "insert", data)
                    if res:
                        st.success("✅ Producto registrado exitosamente.")
                        st.rerun()

    prod_data = ejecutar_consulta("productos")
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
                data = {"nombre": nombre, "ruc_dni": ruc, "telefono": telefono, "email": email}
                res = ejecutar_consulta("proveedores", "insert", data)
                if res:
                    st.success("✅ Proveedor registrado.")
                    st.rerun()

    prov_data = ejecutar_consulta("proveedores")
    if prov_data:
        st.dataframe(pd.DataFrame(prov_data), use_container_width=True)

# -------------------------------------------------------------------
# 3. CLIENTES
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
                    data = {"nombre": cli_nom.upper(), "ruc_dni": cli_doc, "telefono": cli_tel, "direccion": cli_dir}
                    res = ejecutar_consulta("clientes", "insert", data)
                    if res:
                        st.success(f"✅ Cliente {cli_nom.upper()} registrado.")
                        st.rerun()

    res_clientes = ejecutar_consulta("clientes")
    if res_clientes:
        st.dataframe(pd.DataFrame(res_clientes), use_container_width=True)

# -------------------------------------------------------------------
# 4. INGRESOS (COMPRAS)
# -------------------------------------------------------------------
elif menu == "📥 Ingresos (Compras / Entrada)":
    st.header("📥 Registro de Ingresos de Mercadería (Compras)")

    prods = ejecutar_consulta("productos", consulta_type="select", data="id, codigo, descripcion, stock, costo")
    provs = ejecutar_consulta("proveedores", consulta_type="select", data="id, nombre")

    if prods and provs:
        dict_prods = {f"{p['codigo']} - {p['descripcion']} (Stock: {p['stock']})": p for p in prods}
        dict_provs = {pr["nombre"]: pr["id"] for pr in provs}

        with st.form("form_ingresos", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                prov_sel = st.selectbox("Proveedor", list(dict_provs.keys()))
                nro_fact_compra = st.text_input("N° Factura/Guía Compra", value="F001-0001")
            with c2:
                prod_sel = st.selectbox("Producto a Ingresar", list(dict_prods.keys()))
                cant_ingreso = st.number_input("Cantidad que Ingresa", min_value=1, value=1)
            with c3:
                costo_def = float(dict_prods[prod_sel]["costo"]) if dict_prods[prod_sel]["costo"] is not None else 0.0
                nuevo_costo = st.number_input("Costo Unitario Compra (S/.)", min_value=0.0, value=costo_def)
                fecha_compra = st.date_input("Fecha de Ingreso", datetime.now().date())

            if st.form_submit_button("📥 Registrar Ingreso y Aumentar Stock"):
                prod_info = dict_prods[prod_sel]
                nuevo_stock = prod_info["stock"] + cant_ingreso

                upd = ejecutar_consulta(
                    "productos",
                    "update",
                    data={"stock": nuevo_stock, "costo": nuevo_costo},
                    eq_col="id",
                    eq_val=prod_info["id"],
                )
                if upd:
                    st.success(f"✅ Stock actualizado. Nuevo Stock: {nuevo_stock}")
                    st.rerun()

# -------------------------------------------------------------------
# 5. VENTAS Y EMISIÓN DE COMPROBANTES
# -------------------------------------------------------------------
elif menu == "🧾 Ventas y Emisión de Comprobantes":
    st.header("🧾 Punto de Venta: Emisión de Boletas, Facturas y Notas")

    res_clientes_v = ejecutar_consulta("clientes")
    df_cli_v = pd.DataFrame(res_clientes_v) if res_clientes_v else pd.DataFrame()

    opcion_cliente = st.radio(
        "Tipo de Cliente",
        ["Cliente Genérico (Varios)", "Seleccionar Cliente Registrado"],
        horizontal=True,
    )

    cliente_nom = "CLIENTE VARIOS"
    cliente_doc = "00000000"

    if opcion_cliente == "Seleccionar Cliente Registrado" and not df_cli_v.empty:
        cliente_sel = st.selectbox("Buscar Cliente Frecuente", df_cli_v["nombre"].tolist())
        datos_c = df_cli_v[df_cli_v["nombre"] == cliente_sel].iloc[0]
        cliente_nom = datos_c["nombre"]
        cliente_doc = datos_c["ruc_dni"]

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        tipo_doc = st.selectbox(
            "Tipo de Comprobante *",
            ["BOLETA DE VENTA", "FACTURA", "TICKET DE VENTA", "NOTA DE CRÉDITO", "NOTA DE DÉBITO"],
        )

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

        ult_comps = ejecutar_consulta(
            "comprobantes",
            consulta_type="select",
            data="serie_numero",
            like_col="serie_numero",
            like_val=f"{prefijo}-%",
        )

        siguiente_num = 1
        if ult_comps:
            numeros = [
                int(c["serie_numero"].split("-")[1])
                for c in ult_comps
                if "-" in c.get("serie_numero", "") and c.get("serie_numero", "").split("-")[1].isdigit()
            ]
            if numeros:
                siguiente_num = max(numeros) + 1

        sugerido = f"{prefijo}-{siguiente_num:06d}"
        serie_num = st.text_input("Serie y Número Comprobante", value=sugerido)

    with c2:
        doc_ref = ""
        motivo_nota = ""
        cat_motivo = ""

        if "NOTA DE CRÉDITO" in tipo_doc:
            st.info("ℹ️ Emitida para disminuir, ajustar o anular una factura/boleta previa (reingresa stock por devolución).")
            doc_ref = st.text_input("N° de Factura/Boleta que modifica *", placeholder="Ej: F001-000005")
            cat_motivo = st.selectbox(
                "Motivo de la Nota de Crédito *",
                ["Anulación de la Operación", "Devolución por Defecto de Fábrica", "Devolución por Error en Pedido", "Descuento / Ajuste de Precio"],
            )
            motivo_nota = st.text_area("Detalle / Observaciones de la Devolución *")

        elif "NOTA DE DÉBITO" in tipo_doc:
            st.info("ℹ️ Emitida para aumentar el monto de una factura/boleta previa (intereses, mora o ajuste sin afectar stock).")
            doc_ref = st.text_input("N° de Factura/Boleta que modifica *", placeholder="Ej: F001-000005")
            cat_motivo = st.selectbox(
                "Motivo de la Nota de Débito *",
                ["Intereses por Mora", "Aumento en el Valor / Cambio de Precio", "Penalidades / Gastos Adicionales"],
            )
            motivo_nota = st.text_area("Detalle del Cobro Adicional *")

    prods = ejecutar_consulta("productos", consulta_type="select", data="id, codigo, descripcion, precio, stock")
    if prods:
        dict_prods = {f"{p['codigo']} | {p['descripcion']} (Stock: {p['stock']})": p for p in prods}

        cp1, cp2, cp3 = st.columns([3, 1, 1])
        with cp1:
            p_sel_key = st.selectbox("Buscar Producto / Concepto", list(dict_prods.keys()))
        with cp2:
            cant_v = st.number_input("Cantidad", min_value=1, value=1)
        with cp3:
            st.write("")
            st.write("")
            if st.button("➕ Agregar"):
                p_info = dict_prods[p_sel_key]

                if "NOTA DE CRÉDITO" in tipo_doc or "NOTA DE DÉBITO" in tipo_doc or cant_v <= p_info["stock"]:
                    st.session_state.carrito.append({
                        "id": p_info["id"],
                        "codigo": p_info["codigo"],
                        "descripcion": p_info["descripcion"],
                        "cantidad": cant_v,
                        "precio_unitario": p_info["precio"],
                        "subtotal": cant_v * p_info["precio"],
                    })
                    st.success("✅ Agregado")
                    st.rerun()
                else:
                    st.error("⚠️ La cantidad supera el stock disponible.")

    if st.session_state.carrito:
        st.subheader("📋 Detalle del Comprobante")
        df_car = pd.DataFrame(st.session_state.carrito)
        st.dataframe(
            df_car[["codigo", "descripcion", "cantidad", "precio_unitario", "subtotal"]], use_container_width=True
        )

        total_gen = float(df_car["subtotal"].sum())
        subtotal = total_gen / 1.18
        igv = total_gen - subtotal

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Subtotal", f"S/. {subtotal:.2f}")
        col_m2.metric("IGV (18%)", f"S/. {igv:.2f}")
        col_m3.metric("TOTAL", f"S/. {total_gen:.2f}")

        st.divider()

        valido = True
        if ("NOTA DE CRÉDITO" in tipo_doc or "NOTA DE DÉBITO" in tipo_doc) and (not doc_ref or not motivo_nota):
            st.error("⚠️ El número de comprobante afectado y la justificación son obligatorios para emitir la Nota.")
            valido = False

        if valido:
            if "NOTA DE CRÉDITO" in tipo_doc:
                lbl_btn = f"🖨️ EMITIR {tipo_doc} Y 🟢 AUMENTAR STOCK (+)"
            elif "NOTA DE DÉBITO" in tipo_doc:
                lbl_btn = f"🖨️ EMITIR {tipo_doc} (AUMENTAR MONTO COBRADO)"
            else:
                lbl_btn = f"🖨️ EMITIR {tipo_doc} Y 🔴 DESCONTAR STOCK (-)"

            if st.button(lbl_btn, type="primary", use_container_width=True):
                comp_data = {
                    "tipo_comprobante": tipo_doc,
                    "serie_numero": serie_num,
                    "cliente_nombre": cliente_nom,
                    "cliente_documento": cliente_doc,
                    "subtotal": round(subtotal, 2),
                    "igv": round(igv, 2),
                    "total": round(total_gen, 2),
                }
                res = ejecutar_consulta("comprobantes", "insert", comp_data)

                if res and res.data:
                    comp_id = res.data[0]["id"]

                    for item in st.session_state.carrito:
                        det = {
                            "comprobante_id": comp_id,
                            "producto_id": item["id"],
                            "cantidad": item["cantidad"],
                            "precio_unitario": item["precio_unitario"],
                        }
                        ejecutar_consulta("detalle_comprobante", "insert", det)

                        # LOGICA DE STOCK SEGÚN TIPO DE COMPROBANTE
                        if "NOTA DE CRÉDITO" in tipo_doc:
                            # Aumenta stock por devolución o anulación
                            prod_bd = ejecutar_consulta("productos", consulta_type="select", data="stock", eq_col="id", eq_val=item["id"])
                            if prod_bd:
                                nuevo_stk = prod_bd[0]["stock"] + item["cantidad"]
                                ejecutar_consulta("productos", "update", data={"stock": nuevo_stk}, eq_col="id", eq_val=item["id"])

                            # Registro de devolución para panel estadístico
                            reg_dev = {
                                "numero_boleta": f"{serie_num} (Afecta: {doc_ref})",
                                "producto_id": item["id"],
                                "cantidad": item["cantidad"],
                                "precio": item["precio_unitario"],
                                "motivo_devolucion": f"[{cat_motivo}] {motivo_nota}",
                            }
                            ejecutar_consulta("devoluciones", "insert", reg_dev)

                        elif "NOTA DE DÉBITO" in tipo_doc:
                            # Ajuste de cobro, no altera el stock físico
                            pass

                        else:
                            # Boleta/Factura/Ticket -> Disminuye stock por venta
                            prod_bd = ejecutar_consulta("productos", consulta_type="select", data="stock", eq_col="id", eq_val=item["id"])
                            if prod_bd:
                                nuevo_stk = prod_bd[0]["stock"] - item["cantidad"]
                                ejecutar_consulta("productos", "update", data={"stock": nuevo_stk}, eq_col="id", eq_val=item["id"])

                    st.balloons()
                    st.success(f"🎉 ¡{tipo_doc} {serie_num} emitida correctamente!")
                    st.session_state.carrito = []
                    st.rerun()

# -------------------------------------------------------------------
# 6. HISTÓRICO DE COMPROBANTES
# -------------------------------------------------------------------
elif menu == "📊 Histórico de Comprobantes":
    st.header("📊 Histórico General de Comprobantes Emitidos")
    comps = ejecutar_consulta("comprobantes")
    if comps:
        st.dataframe(pd.DataFrame(comps), use_container_width=True)

# -------------------------------------------------------------------
# 7. ESTADÍSTICAS Y MÉTRICAS DE NEGOCIO (INCLUYE TODAS TUS ESTADÍSTICAS)
# -------------------------------------------------------------------
elif menu == "📈 Estadísticas y Métricas de Negocio":
    st.header("📈 Panel Consolidado de Estadísticas e Inteligencia")

    tab1, tab2, tab3, tab4 = st.tabs([
        "⚠️ Alerta de Quiebre de Stock",
        "🔥 Productos con Más Salida",
        "🏷️ Mejor Proveedor (Menor Precio)",
        "🔄 Cuadro Estadístico de Devoluciones"
    ])

    # --- TAB 1: AVISO / QUIEBRE DE STOCK ---
    with tab1:
        st.subheader("🚨 Control de Agotamiento y Stock Mínimo")
        prods_stk = ejecutar_consulta("productos")

        if prods_stk:
            df_stk = pd.DataFrame(prods_stk)
            # Productos por debajo o igual al stock mínimo
            df_criticos = df_stk[df_stk["stock"] <= df_stk["stock_minimo"]]

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Productos en Catálogo", len(df_stk))
            m2.metric("En Alerta de Stock Mínimo", len(df_criticos), delta_color="inverse")
            m3.metric("Productos Sin Stock (0)", len(df_stk[df_stk["stock"] == 0]))

            if not df_criticos.empty:
                st.error("⚠️ Atención: Los siguientes productos requieren reabastecimiento urgente:")
                st.dataframe(
                    df_criticos[["codigo", "marca", "descripcion", "stock", "stock_minimo"]],
                    use_container_width=True
                )
            else:
                st.success("✅ Todos los productos se encuentran por encima del nivel de stock mínimo.")

    # --- TAB 2: PRODUCTOS CON MÁS SALIDA ---
    with tab2:
        st.subheader("🔥 Top Productos Más Vendidos")
        detalles = ejecutar_consulta("detalle_comprobante")
        prods_ref = ejecutar_consulta("productos")

        if detalles and prods_ref:
            df_det = pd.DataFrame(detalles)
            df_p = pd.DataFrame(prods_ref)

            # Unir para obtener descripción
            df_m = df_det.merge(df_p, left_on="producto_id", right_on="id", suffixes=("_det", "_prod"))
            top_prod = df_m.groupby("descripcion")["cantidad"].sum().reset_index()
            top_prod = top_prod.sort_values(by="cantidad", ascending=False).head(10)

            st.bar_chart(data=top_prod, x="descripcion", y="cantidad")
            st.dataframe(top_prod.rename(columns={"descripcion": "Producto", "cantidad": "Unidades Vendidas"}), use_container_width=True)
        else:
            st.info("Aún no existen ventas registradas para calcular rotación.")

    # --- TAB 3: MEJOR PROVEEDOR POR MENOR PRECIO ---
    with tab3:
        st.subheader("🏷️ Análisis de Proveedores con Menor Costo")
        provs = ejecutar_consulta("proveedores")
        prods_costo = ejecutar_consulta("productos")

        if prods_costo and provs:
            df_pr = pd.DataFrame(prods_costo)
            df_pv = pd.DataFrame(provs)

            # Promedio de costo por marca o proveedor
            st.markdown("**Comparativa de Costo Promedio por Marca/Proveedor Registrado:**")
            costo_marca = df_pr.groupby("marca")["costo"].mean().reset_index()
            costo_marca = costo_marca.sort_values(by="costo", ascending=True)

            st.dataframe(
                costo_marca.rename(columns={"marca": "Marca / Proveedor", "costo": "Costo Promedio (S/.)"}),
                use_container_width=True
            )
        else:
            st.info("Registra proveedores y costos de productos para visualizar esta comparativa.")

    # --- TAB 4: CUADRO ESTADÍSTICO DE DEVOLUCIONES ---
    with tab4:
        st.subheader("📋 Control Estadístico de Devoluciones y Mermas (Notas de Crédito)")
        devs = ejecutar_consulta("devoluciones")

        if devs:
            df_devs = pd.DataFrame(devs)
            st.dataframe(df_devs, use_container_width=True)

            st.divider()
            c_g1, c_g2 = st.columns(2)

            with c_g1:
                st.markdown("**Distribución por Motivo de Devolución**")
                if "motivo_devolucion" in df_devs.columns and "cantidad" in df_devs.columns:
                    chart_data = df_devs.groupby("motivo_devolucion")["cantidad"].sum()
                    st.bar_chart(chart_data)

            with c_g2:
                st.markdown("**Impacto Económico Total**")
                if "precio" in df_devs.columns and "cantidad" in df_devs.columns:
                    df_devs["total_devuelto"] = df_devs["precio"] * df_devs["cantidad"]
                    monto_dev = df_devs["total_devuelto"].sum()
                    st.metric("Total Anulado / Devuelto a Clientes", f"S/. {monto_dev:.2f}")
        else:
            st.info("No hay devoluciones ni Notas de Crédito registradas hasta el momento.")
