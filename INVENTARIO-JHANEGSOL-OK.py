from datetime import datetime
import io
from pdf2image import convert_from_bytes
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st
from supabase import Client, create_client

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
        elif consulta_type == "delete":
            return query.delete().eq(eq_col, eq_val).execute()
    except Exception as e:
        st.error(f"⚠️ Error en base de datos (Tabla '{tabla}'): {e}")
        return None

# --- AJUSTE ATÓMICO DE STOCK (NUEVO) ---
# Requiere crear esta función en Supabase (SQL Editor) UNA sola vez:
#
# create or replace function ajustar_stock(p_id bigint, p_delta integer)
# returns integer as $$
# declare
#   nuevo_stock integer;
# begin
#   update productos
#   set stock = stock + p_delta
#   where id = p_id
#   returning stock into nuevo_stock;
#   return nuevo_stock;
# end;
# $$ language plpgsql;
#
# Esta función hace el ajuste directamente en la base de datos (stock = stock + delta),
# evitando el patrón "leer stock -> calcular en Python -> escribir stock" que es propenso
# a condiciones de carrera y a duplicaciones si la función se invoca más de una vez.
def ajustar_stock_producto(producto_id, delta):
    """delta negativo para descontar (ventas), positivo para reponer (notas de crédito, anulaciones, ingresos)."""
    try:
        res = supabase.rpc("ajustar_stock", {"p_id": producto_id, "p_delta": int(delta)}).execute()
        if res.data is None:
            # La función no afectó ninguna fila (posible bloqueo por RLS, id inexistente, etc.)
            st.error(
                f"⚠️ El stock del producto {producto_id} no se actualizó (la función devolvió NULL). "
                "Revisa que la función 'ajustar_stock' esté creada como SECURITY DEFINER y que exista "
                "un producto con ese id."
            )
        return res.data
    except Exception as e:
        st.error(f"⚠️ Error al ajustar stock del producto {producto_id}: {e}")
        return None

# --- ESTADOS INDEPENDIENTES Y PROTEGIDOS ---
if "carrito_ventas" not in st.session_state:
    st.session_state.carrito_ventas = []

if "carrito_nc" not in st.session_state:
    st.session_state.carrito_nc = []

if "pdf_generado" not in st.session_state:
    st.session_state.pdf_generado = None

if "num_ultimo_comp" not in st.session_state:
    st.session_state.num_ultimo_comp = ""

# NUEVO: bandera anti doble-clic para emisión de comprobantes
if "procesando_emision" not in st.session_state:
    st.session_state.procesando_emision = False

# --- GENERADOR DE PDF ---
def generar_pdf_comprobante(
    tipo_doc,
    serie_num,
    cliente_nom,
    cliente_doc,
    items,
    subtotal,
    igv,
    total_gen,
    doc_referencia="",
    motivo="",
):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
    )
    story = []
    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle(
        "Titulo", parent=styles["Heading1"], alignment=1, fontSize=16, leading=20, fontName="Helvetica-Bold"
    )
    subtitulo_style = ParagraphStyle("SubTitulo", parent=styles["Normal"], alignment=1, fontSize=10, leading=12)
    comprobante_style = ParagraphStyle(
        "Comp", parent=styles["Heading2"], alignment=1, fontSize=12, leading=15, fontName="Helvetica-Bold"
    )
    normal_style = styles["Normal"]
    derecha_style = ParagraphStyle("Derecha", parent=styles["Normal"], alignment=2)
    bold_derecha = ParagraphStyle("BoldDerecha", parent=styles["Normal"], alignment=2, fontName="Helvetica-Bold")

    story.append(Paragraph("JHANEGSOL S.A.C.", titulo_style))
    story.append(Paragraph("RUC: 20600000001", subtitulo_style))
    story.append(Paragraph("Oficina Principal - Huacho, Lima - Perú", subtitulo_style))
    story.append(Spacer(1, 15))

    story.append(Paragraph(f"<b>{tipo_doc}</b>", comprobante_style))
    story.append(Paragraph(f"<b>N° {serie_num}</b>", comprobante_style))
    story.append(Spacer(1, 10))

    datos_cliente = [
        [Paragraph(f"<b>Cliente:</b> {cliente_nom}", normal_style)],
        [Paragraph(f"<b>DNI / RUC:</b> {cliente_doc}", normal_style)],
        [Paragraph(f"<b>Fecha de Emisión:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", normal_style)],
    ]

    if doc_referencia:
        datos_cliente.append([Paragraph(f"<b>Comprobante Afectado:</b> {doc_referencia}", normal_style)])
    if motivo:
        datos_cliente.append([Paragraph(f"<b>Motivo / Concepto:</b> {motivo}", normal_style)])

    story.append(Table(datos_cliente, colWidths=[500]))
    story.append(Spacer(1, 15))

    data_tabla = [[
        Paragraph("<b>Cant.</b>", normal_style),
        Paragraph("<b>Descripción</b>", normal_style),
        Paragraph("<b>P. Unit (S/.)</b>", derecha_style),
        Paragraph("<b>Subtotal (S/.)</b>", derecha_style),
    ]]

    for item in items:
        desc = item.get("descripcion") or item.get("productos", {}).get("descripcion", "Producto")
        cant = item.get("cantidad", 0)
        pu = item.get("precio_unitario", item.get("precio", 0.0))
        sub = cant * pu

        data_tabla.append([
            Paragraph(str(cant), normal_style),
            Paragraph(desc, normal_style),
            Paragraph(f"{pu:.2f}", derecha_style),
            Paragraph(f"{sub:.2f}", derecha_style),
        ])

    tabla_prod = Table(data_tabla, colWidths=[50, 270, 90, 90])
    tabla_prod.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f2f5")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ("LINEABOVE", (0, 0), (-1, 0), 1, colors.black),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
        ])
    )
    story.append(tabla_prod)
    story.append(Spacer(1, 15))

    data_totales = [
        [Paragraph("Op. Gravada:", derecha_style), Paragraph(f"S/. {subtotal:.2f}", derecha_style)],
        [Paragraph("IGV (18%):", derecha_style), Paragraph(f"S/. {igv:.2f}", derecha_style)],
        [Paragraph("<b>TOTAL:</b>", bold_derecha), Paragraph(f"<b>S/. {total_gen:.2f}</b>", bold_derecha)],
    ]
    tabla_totales = Table(data_totales, colWidths=[400, 100])
    tabla_totales.setStyle(TableStyle([("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4)]))
    story.append(tabla_totales)
    story.append(Spacer(1, 20))

    story.append(Paragraph("¡Gracias por su preferencia en JHANEGSOL S.A.C.!", subtitulo_style))

    doc.build(story)
    return buffer.getvalue()

def mostrar_previsualizacion_pdf(pdf_bytes):
    try:
        images = convert_from_bytes(pdf_bytes)
        st.markdown("### 👁️ Previsualización del Comprobante")
        for img in images:
            st.image(img, use_column_width=True)
    except Exception:
        st.info("ℹ️ Para habilitar la vista previa visual de PDF, asegúrese de tener instalada la herramienta del sistema `poppler`.")

def comprobante_existe(serie_numero):
    try:
        res = (
            supabase.table("comprobantes")
            .select("id")
            .eq("serie_numero", serie_numero)
            .execute()
        )
        return bool(res.data)
    except Exception as e:
        st.error(f"❌ Error verificando comprobante: {e}")
        return True

# --- EMISIÓN DE VENTAS ---
def emitir_venta(tipo_doc, serie_num, cliente_nom, cliente_doc, subtotal, igv, total_gen):
    # NUEVO: guardia anti doble-clic
    if st.session_state.procesando_emision:
        st.warning("⏳ Ya se está procesando una emisión, por favor espera.")
        return
    st.session_state.procesando_emision = True

    try:
        if not st.session_state.carrito_ventas:
            st.error("❌ El carrito está vacío.")
            return

        if comprobante_existe(serie_num):
            st.error(f"❌ El comprobante {serie_num} ya existe.")
            return

        for item in st.session_state.carrito_ventas:
            res_prod = (
                supabase.table("productos")
                .select("stock, descripcion")
                .eq("id", item["id"])
                .single()
                .execute()
            )
            if not res_prod.data:
                st.error(f"❌ No se encontró el producto {item['descripcion']}.")
                return
            stock_actual = int(res_prod.data.get("stock") or 0)
            cantidad = int(item["cantidad"])
            if cantidad > stock_actual:
                st.error(f"❌ Stock insuficiente para {item['descripcion']}. Disponible: {stock_actual}")
                return

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
        if not res or not res.data:
            st.error("❌ No se pudo crear el comprobante.")
            return

        comp_id = res.data[0]["id"]

        for item in st.session_state.carrito_ventas:
            # --- DIAGNÓSTICO TEMPORAL: lee el stock en 3 momentos para aislar dónde baja ---
            stock_antes = supabase.table("productos").select("stock").eq("id", item["id"]).single().execute().data.get("stock")

            det = {
                "comprobante_id": comp_id,
                "producto_id": item["id"],
                "cantidad": int(item["cantidad"]),
                "precio_unitario": float(item["precio_unitario"]),
            }
            ejecutar_consulta("detalle_comprobante", "insert", det)

            # Si el stock YA cambió aquí, antes de llamar a ajustar_stock_producto,
            # significa que algo (un trigger) reacciona al insert en detalle_comprobante.
            stock_tras_insert = supabase.table("productos").select("stock").eq("id", item["id"]).single().execute().data.get("stock")

            # Descontar stock (AJUSTE ATÓMICO — reemplaza el patrón select+update anterior)
            ajustar_stock_producto(item["id"], -int(item["cantidad"]))

            stock_despues = supabase.table("productos").select("stock").eq("id", item["id"]).single().execute().data.get("stock")

            st.info(
                f"🔎 DIAGNÓSTICO — Producto {item['id']} | cantidad vendida: {item['cantidad']}\n\n"
                f"- Stock ANTES de insertar detalle: **{stock_antes}**\n"
                f"- Stock DESPUÉS de insertar detalle (antes de ajustar_stock): **{stock_tras_insert}**\n"
                f"- Stock DESPUÉS de ajustar_stock: **{stock_despues}**\n\n"
                f"Si 'ANTES' y 'DESPUÉS de insertar detalle' ya son distintos, hay un trigger en "
                f"`detalle_comprobante` descontando stock automáticamente — esa es la causa del doble descuento."
            )

        st.session_state.pdf_generado = generar_pdf_comprobante(
            tipo_doc, serie_num, cliente_nom, cliente_doc,
            st.session_state.carrito_ventas, subtotal, igv, total_gen
        )
        st.session_state.num_ultimo_comp = serie_num
        st.session_state.carrito_ventas = []
        st.success(f"✅ {tipo_doc} {serie_num} emitido correctamente.")
    finally:
        st.session_state.procesando_emision = False

# --- EMISIÓN DE NOTAS DE CRÉDITO Y DÉBITO ---
def emitir_nota(tipo_nota, serie_nota, cliente_nom, cliente_doc, subtotal, igv, total_gen, doc_ref, cat_motivo, motivo_nota):
    # NUEVO: guardia anti doble-clic
    if st.session_state.procesando_emision:
        st.warning("⏳ Ya se está procesando una emisión, por favor espera.")
        return
    st.session_state.procesando_emision = True

    try:
        if not st.session_state.carrito_nc:
            st.error("❌ No hay ítems en la nota.")
            return

        if comprobante_existe(serie_nota):
            st.error(f"❌ La nota {serie_nota} ya existe.")
            return

        origen = (
            supabase.table("comprobantes")
            .select("id, serie_numero")
            .eq("serie_numero", doc_ref)
            .single()
            .execute()
        )

        if not origen.data:
            st.error(f"❌ No se encontró el comprobante original {doc_ref}.")
            return

        comp_data = {
            "tipo_comprobante": tipo_nota,
            "serie_numero": serie_nota,
            "cliente_nombre": cliente_nom,
            "cliente_documento": cliente_doc,
            "subtotal": round(subtotal, 2),
            "igv": round(igv, 2),
            "total": round(total_gen, 2),
        }

        res = ejecutar_consulta("comprobantes", "insert", comp_data)
        if not res or not res.data:
            st.error("❌ No se pudo crear la nota.")
            return

        comp_id = res.data[0]["id"]

        for item in st.session_state.carrito_nc:
            cantidad = int(item["cantidad"])
            p_id = item["id"]

            det = {
                "comprobante_id": comp_id,
                "producto_id": p_id,
                "cantidad": cantidad,
                "precio_unitario": float(item["precio_unitario"]),
            }
            ejecutar_consulta("detalle_comprobante", "insert", det)

            if tipo_nota == "NOTA DE CRÉDITO":
                reg_dev = {
                    "numero_boleta": f"{serie_nota} (Afecta: {doc_ref})",
                    "producto_id": p_id,
                    "cantidad": cantidad,
                    "precio": float(item["precio_unitario"]),
                    "motivo_devolucion": f"[{cat_motivo}] {motivo_nota}",
                }
                ejecutar_consulta("devoluciones", "insert", reg_dev)

                # --- AUMENTO DE STOCK AL INGRESAR NOTA DE CRÉDITO (AJUSTE ATÓMICO) ---
                ajustar_stock_producto(p_id, cantidad)

        st.session_state.pdf_generado = generar_pdf_comprobante(
            tipo_nota, serie_nota, cliente_nom, cliente_doc,
            st.session_state.carrito_nc, subtotal, igv, total_gen,
            doc_referencia=doc_ref, motivo=motivo_nota
        )
        st.session_state.num_ultimo_comp = serie_nota
        st.session_state.carrito_nc = []
        st.success(f"✅ {tipo_nota} {serie_nota} emitida correctamente.")
    finally:
        st.session_state.procesando_emision = False

# --- INTERFAZ PRINCIPAL ---
st.title("📦 Sistema Comercial, Inventarios y Facturación - Jhanegsol")

menu = st.sidebar.radio(
    "Menú Principal",
    [
        "📋 Catálogo de Productos",
        "🏢 Proveedores",
        "👥 Listado y Gestión de Clientes",
        "📥 Ingresos (Compras / Entrada)",
        "🧾 Ventas Directas (Boletas y Facturas)",
        "📝 Notas de Crédito y Débito",
        "📊 Histórico y Anulación de Comprobantes",
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
                        "codigo": codigo, "marca": marca, "descripcion": descripcion,
                        "costo": costo, "precio": precio, "stock": stock, "stock_minimo": stock_min
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

            if st.form_submit_button("📥 Registrar Ingreso y Aumentar Stock"):
                prod_info = dict_prods[prod_sel]
                # Aquí se actualizan stock Y costo a la vez, así que se mantiene el update directo
                # (no se usa ajustar_stock_producto porque también cambia el costo unitario).
                nuevo_stock = prod_info["stock"] + cant_ingreso
                upd = ejecutar_consulta(
                    "productos", "update",
                    data={"stock": nuevo_stock, "costo": nuevo_costo},
                    eq_col="id", eq_val=prod_info["id"],
                )
                if upd:
                    st.success(f"✅ Stock actualizado. Nuevo Stock: {nuevo_stock}")
                    st.rerun()

# -------------------------------------------------------------------
# 5. VENTAS DIRECTAS
# -------------------------------------------------------------------
elif menu == "🧾 Ventas Directas (Boletas y Facturas)":
    st.header("🧾 Punto de Venta: Boletas, Facturas y Tickets")

    c1, c2 = st.columns(2)
    with c1:
        tipo_doc = st.selectbox("Tipo de Comprobante *", ["BOLETA DE VENTA", "FACTURA", "TICKET DE VENTA"])
        prefijo = "F001" if tipo_doc == "FACTURA" else ("T001" if tipo_doc == "TICKET DE VENTA" else "B001")

        ult_comps = ejecutar_consulta(
            "comprobantes", consulta_type="select", data="serie_numero",
            like_col="serie_numero", like_val=f"{prefijo}-%",
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

        serie_num = st.text_input("Serie y Número", value=f"{prefijo}-{siguiente_num:06d}")

    with c2:
        res_clientes_v = ejecutar_consulta("clientes")
        df_cli_v = pd.DataFrame(res_clientes_v) if res_clientes_v else pd.DataFrame()
        opcion_cliente = st.radio("Tipo de Cliente", ["Cliente Genérico (Varios)", "Seleccionar Cliente Registrado"], horizontal=True)
        cliente_nom = "CLIENTE VARIOS"
        cliente_doc = "00000000"

        if opcion_cliente == "Seleccionar Cliente Registrado" and not df_cli_v.empty:
            cliente_sel = st.selectbox("Buscar Cliente Frecuente", df_cli_v["nombre"].tolist())
            datos_c = df_cli_v[df_cli_v["nombre"] == cliente_sel].iloc[0]
            cliente_nom = datos_c["nombre"]
            cliente_doc = datos_c["ruc_dni"]

    st.divider()
    prods = ejecutar_consulta("productos", consulta_type="select", data="id, codigo, descripcion, precio, stock")
    if prods:
        dict_prods = {f"{p['codigo']} | {p['descripcion']} (Stock: {p['stock']})": p for p in prods}
        cp1, cp2, cp3 = st.columns([3, 1, 1])
        with cp1:
            p_sel_key = st.selectbox("Buscar Producto", list(dict_prods.keys()))
        with cp2:
            cant_v = st.number_input("Cantidad", min_value=1, value=1, key="v_input_cant_unica")
        with cp3:
            st.write("")
            st.write("")
            if st.button("➕ Agregar al Carrito"):
                p_info = dict_prods[p_sel_key]
                ya_en_carrito = next((x for x in st.session_state.carrito_ventas if x["id"] == p_info["id"]), None)
                cant_total_req = cant_v + (ya_en_carrito["cantidad"] if ya_en_carrito else 0)

                if p_info["stock"] <= 0:
                    st.error("❌ El producto no tiene stock.")
                elif cant_total_req > p_info["stock"]:
                    st.error(f"⚠️ Cantidad supera el stock disponible ({p_info['stock']}).")
                else:
                    if ya_en_carrito:
                        ya_en_carrito["cantidad"] += cant_v
                        ya_en_carrito["subtotal"] = ya_en_carrito["cantidad"] * ya_en_carrito["precio_unitario"]
                    else:
                        st.session_state.carrito_ventas.append({
                            "id": p_info["id"], "codigo": p_info["codigo"],
                            "descripcion": p_info["descripcion"], "cantidad": cant_v,
                            "precio_unitario": p_info["precio"], "subtotal": cant_v * p_info["precio"],
                        })
                    st.success("✅ Agregado")
                    st.rerun()

    if st.session_state.carrito_ventas:
        st.subheader("📋 Detalle de la Venta")
        for idx, item in enumerate(st.session_state.carrito_ventas):
            col_d1, col_d2, col_d3, col_d4 = st.columns([3, 1, 1, 1])
            col_d1.write(f"**{item['codigo']}** - {item['descripcion']}")
            nueva_cant = col_d2.number_input("Cant.", min_value=1, value=int(item["cantidad"]), key=f"v_cant_{idx}_{item['id']}")
            col_d3.write(f"P.U: S/. {item['precio_unitario']:.2f}")

            if nueva_cant != item["cantidad"]:
                st.session_state.carrito_ventas[idx]["cantidad"] = nueva_cant
                st.session_state.carrito_ventas[idx]["subtotal"] = nueva_cant * item["precio_unitario"]
                st.rerun()

            col_d4.write(f"Subtotal: S/. {item['subtotal']:.2f}")

        if st.button("🗑️ Vaciar Carrito"):
            st.session_state.carrito_ventas = []
            st.rerun()

        total_gen = sum(float(i["subtotal"]) for i in st.session_state.carrito_ventas)
        subtotal = total_gen / 1.18
        igv = total_gen - subtotal

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Subtotal", f"S/. {subtotal:.2f}")
        col_m2.metric("IGV (18%)", f"S/. {igv:.2f}")
        col_m3.metric("TOTAL", f"S/. {total_gen:.2f}")

        st.divider()
        # NUEVO: botón deshabilitado mientras se procesa una emisión, evita doble clic
        if st.button(
            f"🖨️ EMITIR {tipo_doc}",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.procesando_emision,
        ):
            emitir_venta(tipo_doc, serie_num, cliente_nom, cliente_doc, subtotal, igv, total_gen)

    if st.session_state.pdf_generado:
        st.balloons()
        st.success("🎉 Comprobante emitido con éxito.")
        st.download_button(
            label="📄 Descargar Comprobante PDF",
            data=st.session_state.pdf_generado,
            file_name=f"{st.session_state.num_ultimo_comp}.pdf",
            mime="application/pdf",
        )
        mostrar_previsualizacion_pdf(st.session_state.pdf_generado)

# -------------------------------------------------------------------
# 6. NOTAS DE CRÉDITO Y DÉBITO
# -------------------------------------------------------------------
elif menu == "📝 Notas de Crédito y Débito":
    st.header("📝 Emisión de Notas de Crédito y Débito")

    tipo_nota = st.radio("Seleccione el Tipo de Nota", ["NOTA DE CRÉDITO", "NOTA DE DÉBITO"], horizontal=True)

    c1, c2 = st.columns(2)
    with c1:
        prefijo_nc = "NC01" if tipo_nota == "NOTA DE CRÉDITO" else "ND01"
        ult_nc = ejecutar_consulta("comprobantes", consulta_type="select", data="serie_numero", like_col="serie_numero", like_val=f"{prefijo_nc}-%")
        sig_nc = 1
        if ult_nc:
            nums = [int(x["serie_numero"].split("-")[1]) for x in ult_nc if "-" in x.get("serie_numero", "") and x.get("serie_numero", "").split("-")[1].isdigit()]
            if nums:
                sig_nc = max(nums) + 1
        serie_nota = st.text_input("Serie y Número Nota", value=f"{prefijo_nc}-{sig_nc:06d}")

    with c2:
        doc_ref = st.text_input("Número de Comprobante que Afecta (Ej: F001-000001, B001-000001)")

    cat_motivo = st.selectbox("Categoría de Motivo SUNAT", ["Anulación de la operación", "Anulación por error en el RUC", "Devolución total", "Devolución parcial", "Descuento global"])
    motivo_nota = st.text_input("Sustento / Motivo Detallado")

    if doc_ref:
        comp_orig = ejecutar_consulta("comprobantes", eq_col="serie_numero", eq_val=doc_ref)
        if comp_orig:
            c_info = comp_orig[0]
            st.info(f"📌 **Comprobante Encontrado:** {c_info['cliente_nombre']} | Doc: {c_info['cliente_documento']} | Total Original: S/. {c_info['total']}")

            detalles = (
                supabase.table("detalle_comprobante")
                .select("producto_id, cantidad, precio_unitario, productos(codigo, descripcion)")
                .eq("comprobante_id", c_info["id"])
                .execute()
            )

            if detalles.data:
                st.write("### Seleccionar productos a incluir en la nota:")
                for item in detalles.data:
                    p_id = item["producto_id"]
                    desc = item["productos"]["descripcion"]
                    max_cant = item["cantidad"]
                    pu = item["precio_unitario"]

                    c_check, c_cant = st.columns([3, 1])
                    incluir = c_check.checkbox(f"{desc} (Máx. original: {max_cant})", key=f"nc_chk_{p_id}")
                    cant_nc = c_cant.number_input("Cant. Nota", min_value=1, max_value=max_cant, value=max_cant, key=f"nc_cant_{p_id}")

                    if incluir:
                        ya_estaba = next((x for x in st.session_state.carrito_nc if x["id"] == p_id), None)
                        if ya_estaba:
                            ya_estaba["cantidad"] = cant_nc
                            ya_estaba["subtotal"] = cant_nc * pu
                        else:
                            st.session_state.carrito_nc.append({
                                "id": p_id, "descripcion": desc, "cantidad": cant_nc,
                                "precio_unitario": pu, "subtotal": cant_nc * pu
                            })
                    else:
                        st.session_state.carrito_nc = [x for x in st.session_state.carrito_nc if x["id"] != p_id]

            if st.session_state.carrito_nc:
                tot_nc = sum(x["subtotal"] for x in st.session_state.carrito_nc)
                sub_nc = tot_nc / 1.18
                igv_nc = tot_nc - sub_nc

                st.write("---")
                st.metric("Total de la Nota", f"S/. {tot_nc:.2f}")

                # NUEVO: botón deshabilitado mientras se procesa una emisión, evita doble clic
                if st.button(
                    f"🖨️ EMITIR {tipo_nota}",
                    type="primary",
                    disabled=st.session_state.procesando_emision,
                ):
                    emitir_nota(
                        tipo_nota, serie_nota, c_info["cliente_nombre"],
                        c_info["cliente_documento"], sub_nc, igv_nc, tot_nc,
                        doc_ref, cat_motivo, motivo_nota
                    )

            if st.session_state.pdf_generado:
                st.balloons()
                st.download_button(
                    label="📄 Descargar Nota en PDF",
                    data=st.session_state.pdf_generado,
                    file_name=f"{st.session_state.num_ultimo_comp}.pdf",
                    mime="application/pdf",
                )
                mostrar_previsualizacion_pdf(st.session_state.pdf_generado)
        else:
            st.warning("⚠️ No se encontró el comprobante de referencia especificado.")

# -------------------------------------------------------------------
# 7. HISTÓRICO Y ANULACIÓN DE COMPROBANTES
# -------------------------------------------------------------------
elif menu == "📊 Histórico y Anulación de Comprobantes":
    st.header("📊 Histórico General y Anulación de Comprobantes")
    comps = ejecutar_consulta("comprobantes", order_col="id", desc=True)
    if comps:
        df_comps = pd.DataFrame(comps)
        st.dataframe(df_comps, use_container_width=True)

        st.divider()
        st.subheader("❌ Anular / Eliminar Comprobante")

        comp_sel_num = st.selectbox("Seleccione el N° de Comprobante a anular", df_comps["serie_numero"].tolist())
        reponer_stock = st.checkbox("🔄 Reponer stock de productos automáticamente al anular", value=True)

        if st.button("🚫 Anular Comprobante", type="primary"):
            comp_obj = next((c for c in comps if c["serie_numero"] == comp_sel_num), None)
            if comp_obj:
                c_id = comp_obj["id"]

                # Reposición opcional del stock (AJUSTE ATÓMICO)
                if reponer_stock:
                    dets = ejecutar_consulta("detalle_comprobante", eq_col="comprobante_id", eq_val=c_id)
                    if dets:
                        for d in dets:
                            p_id = d["producto_id"]
                            cant = d["cantidad"]
                            ajustar_stock_producto(p_id, cant)

                # Eliminar detalles e registro principal
                ejecutar_consulta("detalle_comprobante", "delete", eq_col="comprobante_id", eq_val=c_id)
                ejecutar_consulta("comprobantes", "delete", eq_col="id", eq_val=c_id)

                st.success(f"✅ Comprobante {comp_sel_num} anulado exitosamente.")
                st.rerun()

# -------------------------------------------------------------------
# 8. ESTADÍSTICAS Y MÉTRICAS
# -------------------------------------------------------------------
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

    # --- 1. PRODUCTOS MÁS VENDIDOS ---
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

    # --- 2. ALERTAS DE QUIEBRE DE STOCK ---
    st.subheader("⚠️ Alertas de Quiebre / Stock Crítico")
    prods_stock = ejecutar_consulta("productos")
    if prods_stock:
        df_stock = pd.DataFrame(prods_stock)
        df_critico = df_stock[df_stock["stock"] <= df_stock["stock_minimo"]]

        if not df_critico.empty:
            st.warning(f"⚠️ Se encontraron {len(df_critico)} productos con stock igual o inferior a su límite mínimo:")
            st.dataframe(df_critico[["codigo", "marca", "descripcion", "stock", "stock_minimo"]], use_container_width=True)
        else:
            st.success("✅ Todos los productos mantienen niveles aceptables de inventario.")
