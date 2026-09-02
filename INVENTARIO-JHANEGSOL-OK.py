import base64
from datetime import datetime
import io
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st
import streamlit.components.v1 as components
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
            st.error("⚠️ Ingrese credenciales en .streamlit/secrets.toml")
            st.stop()
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

# --- ESTADOS INDEPENDIENTES ---
if "carrito_ventas" not in st.session_state:
    st.session_state.carrito_ventas = []

if "pdf_generado" not in st.session_state:
    st.session_state.pdf_generado = None

if "num_ultimo_comp" not in st.session_state:
    st.session_state.num_ultimo_comp = ""

# --- GENERADOR DE PDF Y VISOR NATIVO SIN POPPLER ---
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
        desc = item.get("descripcion", "Producto")
        cant = item.get("cantidad", 0)
        pu = item.get("precio_unitario", 0.0)
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
    """Muestra el PDF de forma directa sin requerir Poppler usando Iframe Base64"""
    st.markdown("### 👁️ Previsualización del Comprobante")
    base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
    components.html(pdf_display, height=620)

def comprobante_existe(serie_numero):
    res = supabase.table("comprobantes").select("id").eq("serie_numero", serie_numero).execute()
    return bool(res.data)

# --- EMISIÓN DE VENTAS CORREGIDA ---
def emitir_venta(tipo_doc, serie_num, cliente_nom, cliente_doc, subtotal, igv, total_gen):
    if not st.session_state.carrito_ventas:
        st.error("❌ El carrito está vacío.")
        return

    if comprobante_existe(serie_num):
        st.error(f"❌ El comprobante {serie_num} ya existe.")
        return

    # Validar stocks actualizados
    for item in st.session_state.carrito_ventas:
        res_prod = supabase.table("productos").select("stock, descripcion").eq("id", item["id"]).single().execute()
        if not res_prod.data:
            st.error(f"❌ Producto no encontrado: {item['descripcion']}")
            return
        stock_actual = int(res_prod.data.get("stock") or 0)
        if int(item["cantidad"]) > stock_actual:
            st.error(f"❌ Stock insuficiente para {item['descripcion']}. Disponible real: {stock_actual}")
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
        st.error("❌ No se pudo guardar el comprobante.")
        return

    comp_id = res.data[0]["id"]

    for item in st.session_state.carrito_ventas:
        cant_vendida = int(item["cantidad"])
        p_id = item["id"]

        det = {
            "comprobante_id": comp_id,
            "producto_id": p_id,
            "cantidad": cant_vendida,
            "precio_unitario": float(item["precio_unitario"]),
        }
        ejecutar_consulta("detalle_comprobante", "insert", det)

        # Restar stock exactamente por la cantidad final comprada
        res_p = supabase.table("productos").select("stock").eq("id", p_id).single().execute()
        stock_previo = int(res_p.data.get("stock", 0))
        nuevo_stock = stock_previo - cant_vendida
        ejecutar_consulta("productos", "update", {"stock": nuevo_stock}, eq_col="id", eq_val=p_id)

    st.session_state.pdf_generado = generar_pdf_comprobante(
        tipo_doc, serie_num, cliente_nom, cliente_doc,
        st.session_state.carrito_ventas, subtotal, igv, total_gen
    )
    st.session_state.num_ultimo_comp = serie_num
    st.session_state.carrito_ventas = []
    st.success(f"✅ {tipo_doc} {serie_num} emitido correctamente.")

# --- EMISIÓN DE NOTAS DE CRÉDITO Y DÉBITO CORREGIDA ---
def emitir_nota(tipo_nota, serie_nota, cliente_nom, cliente_doc, subtotal, igv, total_gen, doc_ref, cat_motivo, motivo_nota, lista_items_nc):
    if not lista_items_nc:
        st.error("❌ No hay productos seleccionados para la nota.")
        return

    if comprobante_existe(serie_nota):
        st.error(f"❌ La nota {serie_nota} ya existe.")
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

    for item in lista_items_nc:
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

            # INCREMENTO CORRECTO DEL STOCK
            prod_actual = supabase.table("productos").select("stock").eq("id", p_id).single().execute()
            if prod_actual.data:
                stock_previo = int(prod_actual.data.get("stock") or 0)
                nuevo_stock = stock_previo + cantidad
                ejecutar_consulta("productos", "update", {"stock": nuevo_stock}, eq_col="id", eq_val=p_id)

    st.session_state.pdf_generado = generar_pdf_comprobante(
        tipo_nota, serie_nota, cliente_nom, cliente_doc,
        lista_items_nc, subtotal, igv, total_gen,
        doc_referencia=doc_ref, motivo=motivo_nota
    )
    st.session_state.num_ultimo_comp = serie_nota
    st.success(f"✅ {tipo_nota} {serie_nota} emitida. Se devolvieron las unidades al inventario.")

# --- MENÚ Y NAVEGACIÓN ---
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
                stock_min = st.number_input("Stock Mínimo (Alerta)", min_value=1, value=5)

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
        st.dataframe(df_prod, use_container_width=True)

# -------------------------------------------------------------------
# 2. PROVEEDORES Y 3. CLIENTES
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
                ejecutar_consulta("proveedores", "insert", {"nombre": nombre, "ruc_dni": ruc, "telefono": telefono, "email": email})
                st.rerun()
    prov_data = ejecutar_consulta("proveedores")
    if prov_data:
        st.dataframe(pd.DataFrame(prov_data), use_container_width=True)

elif menu == "👥 Listado y Gestión de Clientes":
    st.header("👥 Base de Datos y Registro de Clientes")
    with st.form("form_cli", clear_on_submit=True):
        c_nom = st.text_input("Nombre / Razón Social *")
        c_doc = st.text_input("DNI / RUC *")
        c_dir = st.text_input("Dirección")
        if st.form_submit_button("Guardar Cliente"):
            if c_nom and c_doc:
                ejecutar_consulta("clientes", "insert", {"nombre": c_nom.upper(), "ruc_dni": c_doc, "direccion": c_dir})
                st.rerun()
    cli_data = ejecutar_consulta("clientes")
    if cli_data:
        st.dataframe(pd.DataFrame(cli_data), use_container_width=True)

# -------------------------------------------------------------------
# 4. INGRESOS
# -------------------------------------------------------------------
elif menu == "📥 Ingresos (Compras / Entrada)":
    st.header("📥 Registro de Ingresos de Mercadería (Compras)")
    prods = ejecutar_consulta("productos", consulta_type="select", data="id, codigo, descripcion, stock, costo")
    if prods:
        dict_prods = {f"{p['codigo']} - {p['descripcion']} (Stock: {p['stock']})": p for p in prods}
        with st.form("form_ingresos", clear_on_submit=True):
            prod_sel = st.selectbox("Producto a Ingresar", list(dict_prods.keys()))
            cant_ingreso = st.number_input("Cantidad que Ingresa", min_value=1, value=1)
            costo_def = float(dict_prods[prod_sel]["costo"] or 0.0)
            nuevo_costo = st.number_input("Costo Unitario Compra (S/.)", min_value=0.0, value=costo_def)

            if st.form_submit_button("📥 Registrar Ingreso y Aumentar Stock"):
                p_info = dict_prods[prod_sel]
                nuevo_stock = p_info["stock"] + cant_ingreso
                ejecutar_consulta("productos", "update", {"stock": nuevo_stock, "costo": nuevo_costo}, eq_col="id", eq_val=p_info["id"])
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
        ult_comps = ejecutar_consulta("comprobantes", consulta_type="select", data="serie_numero", like_col="serie_numero", like_val=f"{prefijo}-%")
        sig_num = 1
        if ult_comps:
            nums = [int(c["serie_numero"].split("-")[1]) for c in ult_comps if "-" in c.get("serie_numero", "") and c.get("serie_numero", "").split("-")[1].isdigit()]
            if nums:
                sig_num = max(nums) + 1
        serie_num = st.text_input("Serie y Número", value=f"{prefijo}-{sig_num:06d}")

    with c2:
        res_cli = ejecutar_consulta("clientes")
        df_cli = pd.DataFrame(res_cli) if res_cli else pd.DataFrame()
        opcion_cliente = st.radio("Tipo de Cliente", ["Cliente Genérico (Varios)", "Seleccionar Cliente Registrado"], horizontal=True)
        cliente_nom, cliente_doc = "CLIENTE VARIOS", "00000000"

        if opcion_cliente == "Seleccionar Cliente Registrado" and not df_cli.empty:
            c_sel = st.selectbox("Buscar Cliente", df_cli["nombre"].tolist())
            d_c = df_cli[df_cli["nombre"] == c_sel].iloc[0]
            cliente_nom, cliente_doc = d_c["nombre"], d_c["ruc_dni"]

    st.divider()
    prods = ejecutar_consulta("productos", consulta_type="select", data="id, codigo, descripcion, precio, stock")
    if prods:
        dict_prods = {f"{p['codigo']} | {p['descripcion']} (Stock: {p['stock']})": p for p in prods}
        cp1, cp2, cp3 = st.columns([3, 1, 1])
        with cp1:
            p_sel_key = st.selectbox("Buscar Producto", list(dict_prods.keys()))
        with cp2:
            cant_v = st.number_input("Cantidad", min_value=1, value=1, key="v_cant_input")
        with cp3:
            st.write("")
            st.write("")
            if st.button("➕ Agregar al Carrito"):
                p_info = dict_prods[p_sel_key]
                index_existente = next((i for i, x in enumerate(st.session_state.carrito_ventas) if x["id"] == p_info["id"]), None)

                cant_existente = st.session_state.carrito_ventas[index_existente]["cantidad"] if index_existente is not None else 0
                cant_total_solicitada = cant_existente + cant_v

                if cant_total_solicitada > p_info["stock"]:
                    st.error(f"⚠️ Stock insuficiente. Solo hay {p_info['stock']} unidades.")
                else:
                    if index_existente is not None:
                        st.session_state.carrito_ventas[index_existente]["cantidad"] = cant_total_solicitada
                        st.session_state.carrito_ventas[index_existente]["subtotal"] = cant_total_solicitada * p_info["precio"]
                    else:
                        st.session_state.carrito_ventas.append({
                            "id": p_info["id"], "codigo": p_info["codigo"],
                            "descripcion": p_info["descripcion"], "cantidad": cant_v,
                            "precio_unitario": p_info["precio"], "subtotal": cant_v * p_info["precio"]
                        })
                    st.success("✅ Agregado correctamente")
                    st.rerun()

    if st.session_state.carrito_ventas:
        st.subheader("📋 Detalle del Carrito")
        items_a_eliminar = []
        for idx, item in enumerate(st.session_state.carrito_ventas):
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            col1.write(f"**{item['codigo']}** - {item['descripcion']}")
            nueva_cant = col2.number_input("Cant.", min_value=1, value=int(item["cantidad"]), key=f"v_cant_{idx}")
            col3.write(f"P.U: S/. {item['precio_unitario']:.2f}")

            if nueva_cant != item["cantidad"]:
                st.session_state.carrito_ventas[idx]["cantidad"] = nueva_cant
                st.session_state.carrito_ventas[idx]["subtotal"] = nueva_cant * item["precio_unitario"]
                st.rerun()

            col4.write(f"Sub: S/. {item['subtotal']:.2f}")

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
        if st.button(f"🖨️ EMITIR {tipo_doc}", type="primary", use_container_width=True):
            emitir_venta(tipo_doc, serie_num, cliente_nom, cliente_doc, subtotal, igv, total_gen)

    if st.session_state.pdf_generado:
        st.balloons()
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
        doc_ref = st.text_input("Número de Comprobante de Origen (Ej: F001-000001)")

    cat_motivo = st.selectbox("Categoría de Motivo SUNAT", ["Anulación de la operación", "Devolución total", "Devolución parcial", "Descuento global"])
    motivo_nota = st.text_input("Sustento / Motivo Detallado")

    if doc_ref:
        comp_orig = ejecutar_consulta("comprobantes", eq_col="serie_numero", eq_val=doc_ref)
        if comp_orig:
            c_info = comp_orig[0]
            st.info(f"📌 Comprobante Encontrado: {c_info['cliente_nombre']} | Doc: {c_info['cliente_documento']} | Total Original: S/. {c_info['total']}")

            detalles = (
                supabase.table("detalle_comprobante")
                .select("producto_id, cantidad, precio_unitario, productos(codigo, descripcion)")
                .eq("comprobante_id", c_info["id"])
                .execute()
            )

            if detalles.data:
                st.write("### Seleccionar productos a devolver:")
                lista_items_nc = []

                for item in detalles.data:
                    p_id = item["producto_id"]
                    desc = item["productos"]["descripcion"]
                    max_cant = item["cantidad"]
                    pu = float(item["precio_unitario"])

                    c_check, c_cant = st.columns([3, 1])
                    incluir = c_check.checkbox(f"{desc} (Comprados: {max_cant})", key=f"nc_chk_{p_id}")
                    cant_nc = c_cant.number_input("Devolver", min_value=1, max_value=max_cant, value=max_cant, key=f"nc_cant_{p_id}")

                    if incluir:
                        lista_items_nc.append({
                            "id": p_id,
                            "descripcion": desc,
                            "cantidad": cant_nc,
                            "precio_unitario": pu,
                            "subtotal": cant_nc * pu
                        })

                if lista_items_nc:
                    tot_nc = sum(x["subtotal"] for x in lista_items_nc)
                    sub_nc = tot_nc / 1.18
                    igv_nc = tot_nc - sub_nc

                    st.write("---")
                    st.metric("Total Devuelto / Afectado", f"S/. {tot_nc:.2f}")

                    if st.button(f"🖨️ EMITIR {tipo_nota}", type="primary"):
                        emitir_nota(
                            tipo_nota, serie_nota, c_info["cliente_nombre"],
                            c_info["cliente_documento"], sub_nc, igv_nc, tot_nc,
                            doc_ref, cat_motivo, motivo_nota, lista_items_nc
                        )

            if st.session_state.pdf_generado:
                st.balloons()
                st.download_button(
                    label="📄 Descargar Nota PDF",
                    data=st.session_state.pdf_generado,
                    file_name=f"{st.session_state.num_ultimo_comp}.pdf",
                    mime="application/pdf",
                )
                mostrar_previsualizacion_pdf(st.session_state.pdf_generado)
        else:
            st.warning("⚠️ No se encontró el comprobante especificado.")

# -------------------------------------------------------------------
# 7. HISTÓRICO Y ANULACIÓN
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
                if reponer_stock:
                    dets = ejecutar_consulta("detalle_comprobante", eq_col="comprobante_id", eq_val=c_id)
                    if dets:
                        for d in dets:
                            p_id = d["producto_id"]
                            cant = d["cantidad"]
                            p_act = supabase.table("productos").select("stock").eq("id", p_id).single().execute()
                            if p_act.data:
                                stock_actual = int(p_act.data.get("stock") or 0)
                                ejecutar_consulta("productos", "update", {"stock": stock_actual + cant}, eq_col="id", eq_val=p_id)

                ejecutar_consulta("detalle_comprobante", "delete", eq_col="comprobante_id", eq_val=c_id)
                ejecutar_consulta("comprobantes", "delete", eq_col="id", eq_val=c_id)
                st.success(f"✅ Comprobante {comp_sel_num} anulado exitosamente.")
                st.rerun()

# -------------------------------------------------------------------
# 8. ESTADÍSTICAS Y MÉTRICAS
# -------------------------------------------------------------------
elif menu == "📈 Estadísticas y Métricas de Negocio":
    st.header("📈 Métricas del Negocio")
    comps = ejecutar_consulta("comprobantes")
    if comps:
        df_comps = pd.DataFrame(comps)
        c1, c2 = st.columns(2)
        c1.metric("Ventas Totales Registradas", f"S/. {df_comps['total'].sum():.2f}")
        c2.metric("Comprobantes Emitidos", len(df_comps))

    st.subheader("⚠️ Alertas de Quiebre / Stock Crítico")
    prods_stock = ejecutar_consulta("productos")
    if prods_stock:
        df_stock = pd.DataFrame(prods_stock)
        df_critico = df_stock[df_stock["stock"] <= df_stock["stock_minimo"]]
        if not df_critico.empty:
            st.warning(f"⚠️ Se encontraron {len(df_critico)} productos con stock en nivel crítico:")
            st.dataframe(df_critico[["codigo", "marca", "descripcion", "stock", "stock_minimo"]], use_container_width=True)
        else:
            st.success("✅ Todos los productos mantienen niveles aceptables de inventario.")
