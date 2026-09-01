import io
from datetime import datetime
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
    except Exception as e:
        st.error(f"⚠️ Error en base de datos (Tabla '{tabla}'): {e}")
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
    buffer.seek(0)
    return buffer

# --- CALLBACK EXCLUSIVO DE VENTAS: DESCUENTA EXACTAMENTE 1 SOLA VEZ ---
def callback_emito_venta(tipo_doc, serie_num, cliente_nom, cliente_doc, subtotal, igv, total_gen):
    if not st.session_state.carrito_ventas:
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

    if res and res.data:
        comp_id = res.data[0]["id"]

        for item in st.session_state.carrito_ventas:
            cant_exacta = int(item["cantidad"])
            p_id = item["id"]

            det = {
                "comprobante_id": comp_id,
                "producto_id": p_id,
                "cantidad": cant_exacta,
                "precio_unitario": item["precio_unitario"],
            }
            ejecutar_consulta("detalle_comprobante", "insert", det)

            # RESTA ÚNICA ATÓMICA DE STOCK
            res_prod = supabase.table("productos").select("stock").eq("id", p_id).execute()
            if res_prod.data:
                stock_actual = int(res_prod.data[0]["stock"] or 0)
                nuevo_stock = stock_actual - cant_exacta
                supabase.table("productos").update({"stock": nuevo_stock}).eq("id", p_id).execute()

        st.session_state.pdf_generado = generar_pdf_comprobante(
            tipo_doc, serie_num, cliente_nom, cliente_doc, st.session_state.carrito_ventas, subtotal, igv, total_gen
        )
        st.session_state.num_ultimo_comp = serie_num
        st.session_state.carrito_ventas = []

# --- CALLBACK EXCLUSIVO DE NOTA DE CRÉDITO: SUMA EXACTAMENTE 1 SOLA VEZ ---
def callback_emito_nota(tipo_nota, serie_nota, cliente_nom, cliente_doc, subtotal, igv, total_gen, doc_ref, cat_motivo, motivo_nota):
    if not st.session_state.carrito_nc:
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

    if res and res.data:
        comp_id = res.data[0]["id"]

        for item in st.session_state.carrito_nc:
            cant_retorno = int(item["cantidad"])
            p_id = item["id"]

            det = {
                "comprobante_id": comp_id,
                "producto_id": p_id,
                "cantidad": cant_retorno,
                "precio_unitario": item["precio_unitario"],
            }
            ejecutar_consulta("detalle_comprobante", "insert", det)

            if tipo_nota == "NOTA DE CRÉDITO":
                # SUMA ÚNICA ATÓMICA DE STOCK (DEVOLUCIÓN)
                res_prod = supabase.table("productos").select("stock").eq("id", p_id).execute()
                if res_prod.data:
                    stock_actual = int(res_prod.data[0]["stock"] or 0)
                    stock_devuelto = stock_actual + cant_retorno
                    supabase.table("productos").update({"stock": stock_devuelto}).eq("id", p_id).execute()

                reg_dev = {
                    "numero_boleta": f"{serie_nota} (Afecta: {doc_ref})",
                    "producto_id": p_id,
                    "cantidad": cant_retorno,
                    "precio": float(item["precio_unitario"]),
                    "motivo_devolucion": f"[{cat_motivo}] {motivo_nota}",
                }
                ejecutar_consulta("devoluciones", "insert", reg_dev)

        st.session_state.pdf_generado = generar_pdf_comprobante(
            tipo_nota, serie_nota, cliente_nom, cliente_doc, st.session_state.carrito_nc, subtotal, igv, total_gen, doc_referencia=doc_ref, motivo=motivo_nota
        )
        st.session_state.num_ultimo_comp = serie_nota
        st.session_state.carrito_nc = []

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
# 5. VENTAS DIRECTAS (BOLETAS Y FACTURAS)
# -------------------------------------------------------------------
elif menu == "🧾 Ventas Directas (Boletas y Facturas)":
    st.header("🧾 Punto de Venta: Boletas, Facturas y Tickets")

    c1, c2 = st.columns(2)
    with c1:
        tipo_doc = st.selectbox("Tipo de Comprobante *", ["BOLETA DE VENTA", "FACTURA", "TICKET DE VENTA"])
        prefijo = "F001" if tipo_doc == "FACTURA" else ("T001" if tipo_doc == "TICKET DE VENTA" else "B001")

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

        serie_num = st.text_input("Serie y Número", value=f"{prefijo}-{siguiente_num:06d}")

    with c2:
        res_clientes_v = ejecutar_consulta("clientes")
        df_cli_v = pd.DataFrame(res_clientes_v) if res_clientes_v else pd.DataFrame()

        opcion_cliente = st.radio(
            "Tipo de Cliente", ["Cliente Genérico (Varios)", "Seleccionar Cliente Registrado"], horizontal=True
        )
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
                            "id": p_info["id"],
                            "codigo": p_info["codigo"],
                            "descripcion": p_info["descripcion"],
                            "cantidad": cant_v,
                            "precio_unitario": p_info["precio"],
                            "subtotal": cant_v * p_info["precio"],
                        })
                    st.success("✅ Agregado")
                    st.rerun()

    if st.session_state.carrito_ventas:
        st.subheader("📋 Detalle de la Venta")
        for idx, item in enumerate(st.session_state.carrito_ventas):
            col_d1, col_d2, col_d3, col_d4 = st.columns([3, 1, 1, 1])
            col_d1.write(f"**{item['codigo']}** - {item['descripcion']}")
            nueva_cant = col_d2.number_input("Cant.", min_value=1, value=int(item["cantidad"]), key=f"v_cant_{idx}")
            col_d3.write(f"P.U: S/. {item['precio_unitario']:.2f}")

            st.session_state.carrito_ventas[idx]["cantidad"] = nueva_cant
            st.session_state.carrito_ventas[idx]["subtotal"] = nueva_cant * item["precio_unitario"]
            col_d4.write(f"Subtotal: S/. {st.session_state.carrito_ventas[idx]['subtotal']:.2f}")

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

        st.button(
            f"🖨️ EMITIR {tipo_doc} Y 🔴 DESCONTAR STOCK",
            type="primary",
            use_container_width=True,
            on_click=callback_emito_venta,
            args=(tipo_doc, serie_num, cliente_nom, cliente_doc, subtotal, igv, total_gen),
        )

    if st.session_state.pdf_generado and st.session_state.num_ultimo_comp == serie_num:
        st.balloons()
        st.success(f"🎉 Comprobante emitido con éxito.")
        st.download_button(
            label="📄 Descargar Comprobante PDF",
            data=st.session_state.pdf_generado,
            file_name=f"{serie_num}.pdf",
            mime="application/pdf",
        )

# -------------------------------------------------------------------
# 6. NOTAS DE CRÉDITO Y DÉBITO (CON SUMA GARANTIZADA DE STOCK)
# -------------------------------------------------------------------
elif menu == "📝 Notas de Crédito y Débito":
    st.header("📝 Gestión Exclusiva de Notas de Crédito y Débito")

    c1, c2 = st.columns(2)
    with c1:
        tipo_nota = st.selectbox("Tipo de Ajuste *", ["NOTA DE CRÉDITO", "NOTA DE DÉBITO"])
        prefijo_nc = "NC01" if tipo_nota == "NOTA DE CRÉDITO" else "ND01"

        ult_notes = ejecutar_consulta(
            "comprobantes",
            consulta_type="select",
            data="serie_numero",
            like_col="serie_numero",
            like_val=f"{prefijo_nc}-%",
        )
        sig_num = 1
        if ult_notes:
            nums = [
                int(c["serie_numero"].split("-")[1])
                for c in ult_notes
                if "-" in c.get("serie_numero", "") and c.get("serie_numero", "").split("-")[1].isdigit()
            ]
            if nums:
                sig_num = max(nums) + 1

        serie_nota = st.text_input("Número de Nota", value=f"{prefijo_nc}-{sig_num:06d}")

    comps_origen = ejecutar_consulta("comprobantes", order_col="id", desc=True)

    if comps_origen:
        dict_comps_orig = {
            f"{c['serie_numero']} - {c['cliente_nombre']} (S/. {c['total']})": c for c in comps_origen
        }

        with c2:
            comp_afectado_sel = st.selectbox("Comprobante Afectado *", list(dict_comps_orig.keys()))
            obj_orig = dict_comps_orig[comp_afectado_sel]

            doc_ref = obj_orig["serie_numero"]
            cliente_nom = obj_orig["cliente_nombre"]
            cliente_doc = obj_orig["cliente_documento"]

            if tipo_nota == "NOTA DE CRÉDITO":
                cat_motivo = st.selectbox(
                    "Motivo de Devolución / Anulación *",
                    [
                        "Anulación de la Operación",
                        "Devolución por Defecto de Fábrica",
                        "Devolución por Error en Pedido",
                        "Descuento / Ajuste de Precio",
                    ],
                )
            else:
                cat_motivo = st.selectbox(
                    "Motivo de Débito *",
                    ["Intereses por Mora", "Aumento en el Valor / Cambio de Precio", "Penalidades"],
                )

            motivo_nota = st.text_area("Detalle explicativo *")

        if st.button("📥 Importar Productos del Comprobante"):
            detalles_orig = (
                supabase.table("detalle_comprobante")
                .select("producto_id, cantidad, precio_unitario, productos(id, codigo, descripcion)")
                .eq("comprobante_id", obj_orig["id"])
                .execute()
                .data
            )

            if detalles_orig:
                st.session_state.carrito_nc = []
                for d in detalles_orig:
                    p = d.get("productos") or {}
                    st.session_state.carrito_nc.append({
                        "id": d["producto_id"],
                        "codigo": p.get("codigo", "N/A"),
                        "descripcion": p.get("descripcion", "Producto"),
                        "cantidad": abs(int(d["cantidad"])),
                        "precio_unitario": float(d["precio_unitario"]),
                        "subtotal": float(abs(int(d["cantidad"])) * float(d["precio_unitario"])),
                    })
                st.success("✅ Productos importados al formulario de devolución.")
                st.rerun()

        if st.session_state.carrito_nc:
            st.subheader("📋 Productos a Modificar por la Nota")

            for idx, item in enumerate(st.session_state.carrito_nc):
                cd1, cd2, cd3, cd4 = st.columns([3, 1, 1, 1])
                cd1.write(f"**{item['codigo']}** - {item['descripcion']}")
                cant_devolver = cd2.number_input(
                    "Cant. Devuelta", min_value=1, value=int(item["cantidad"]), key=f"nc_cant_{idx}"
                )
                cd3.write(f"P.U: S/. {item['precio_unitario']:.2f}")

                st.session_state.carrito_nc[idx]["cantidad"] = cant_devolver
                st.session_state.carrito_nc[idx]["subtotal"] = cant_devolver * item["precio_unitario"]
                cd4.write(f"Subtotal: S/. {st.session_state.carrito_nc[idx]['subtotal']:.2f}")

            total_gen = sum(float(i["subtotal"]) for i in st.session_state.carrito_nc)
            subtotal = total_gen / 1.18
            igv = total_gen - subtotal

            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Subtotal Ajuste", f"S/. {subtotal:.2f}")
            col_m2.metric("IGV Ajuste", f"S/. {igv:.2f}")
            col_m3.metric("TOTAL AJUSTE", f"S/. {total_gen:.2f}")

            st.divider()

            if motivo_nota != "":
                lbl_btn_nc = (
                    f"🟢 EMITIR NOTA DE CRÉDITO Y AUMENTAR STOCK (+{sum(i['cantidad'] for i in st.session_state.carrito_nc)})"
                    if tipo_nota == "NOTA DE CRÉDITO"
                    else "🟡 EMITIR NOTA DE DÉBITO"
                )

                st.button(
                    lbl_btn_nc,
                    type="primary",
                    use_container_width=True,
                    on_click=callback_emito_nota,
                    args=(
                        tipo_nota,
                        serie_nota,
                        cliente_nom,
                        cliente_doc,
                        subtotal,
                        igv,
                        total_gen,
                        doc_ref,
                        cat_motivo,
                        motivo_nota,
                    ),
                )
            else:
                st.warning("⚠️ Ingresa un motivo explicativo para activar la emisión.")

    if st.session_state.pdf_generado and st.session_state.num_ultimo_comp == serie_nota:
        st.balloons()
        st.success(f"✅ {tipo_nota} procesada correctamente. Stock restituido.")
        st.download_button(
            label="📄 Descargar PDF de la Nota",
            data=st.session_state.pdf_generado,
            file_name=f"{serie_nota}.pdf",
            mime="application/pdf",
        )

# -------------------------------------------------------------------
# 7. HISTÓRICO DE COMPROBANTES
# -------------------------------------------------------------------
elif menu == "📊 Histórico de Comprobantes":
    st.header("📊 Histórico General de Comprobantes Emitidos")
    comps = ejecutar_consulta("comprobantes", order_col="id", desc=True)

    if comps:
        df_comps = pd.DataFrame(comps)
        st.dataframe(df_comps, use_container_width=True)

        st.divider()
        st.subheader("🔍 Detalle de Productos y Previsualización de Comprobante")

        lista_num = [f"{c['serie_numero']} - {c['cliente_nombre']} (S/. {c['total']})" for c in comps]
        comp_sel = st.selectbox("Seleccione Comprobante para Inspeccionar / Descargar PDF", lista_num)

        if comp_sel:
            serie_sel = comp_sel.split(" - ")[0]
            datos_comp = next((c for c in comps if c["serie_numero"] == serie_sel), None)

            if datos_comp:
                st.write(
                    f"**Tipo:** {datos_comp.get('tipo_comprobante')} | **Cliente:** {datos_comp.get('cliente_nombre')} | **Doc:** {datos_comp.get('cliente_documento')}"
                )

                detalles = (
                    supabase.table("detalle_comprobante")
                    .select("cantidad, precio_unitario, productos(codigo, descripcion)")
                    .eq("comprobante_id", datos_comp["id"])
                    .execute()
                    .data
                )

                if detalles:
                    items_render = []
                    for d in detalles:
                        prod_info = d.get("productos") or {}
                        items_render.append({
                            "Código": prod_info.get("codigo", "N/A"),
                            "Descripción": prod_info.get("descripcion", "Producto"),
                            "Cantidad": d["cantidad"],
                            "Precio Unit.": f"S/. {d['precio_unitario']:.2f}",
                            "Subtotal": f"S/. {d['cantidad'] * d['precio_unitario']:.2f}",
                        })

                    st.table(pd.DataFrame(items_render))

                    pdf_hist = generar_pdf_comprobante(
                        datos_comp.get("tipo_comprobante", "COMPROBANTE"),
                        datos_comp.get("serie_numero", "000"),
                        datos_comp.get("cliente_nombre", "CLIENTE"),
                        datos_comp.get("cliente_documento", "000"),
                        detalles,
                        float(datos_comp.get("subtotal", 0)),
                        float(datos_comp.get("igv", 0)),
                        float(datos_comp.get("total", 0)),
                    )

                    st.download_button(
                        label=f"📥 Descargar PDF {datos_comp['serie_numero']}",
                        data=pdf_hist,
                        file_name=f"{datos_comp['serie_numero']}.pdf",
                        mime="application/pdf",
                    )

# -------------------------------------------------------------------
# 8. ESTADÍSTICAS Y MÉTRICAS DE NEGOCIO
# -------------------------------------------------------------------
elif menu == "📈 Estadísticas y Métricas de Negocio":
    st.header("📈 Panel Consolidado de Estadísticas e Inteligencia")

    tab1, tab2, tab3, tab4 = st.tabs([
        "⚠️ Alerta de Quiebre de Stock",
        "🔥 Productos con Más Salida",
        "🏷️ Mejor Proveedor (Menor Precio)",
        "🔄 Cuadro Estadístico de Devoluciones",
    ])

    with tab1:
        st.subheader("🚨 Control de Agotamiento y Stock Mínimo")
        prods_stk = ejecutar_consulta("productos")

        if prods_stk:
            df_stk = pd.DataFrame(prods_stk)
            df_criticos = df_stk[df_stk["stock"] <= df_stk["stock_minimo"]]

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Productos en Catálogo", len(df_stk))
            m2.metric("En Alerta de Stock Mínimo", len(df_criticos), delta_color="inverse")
            m3.metric("Productos Sin Stock (0)", len(df_stk[df_stk["stock"] == 0]))

            if not df_criticos.empty:
                st.error("⚠️ Atención: Los siguientes productos requieren reabastecimiento urgente:")
                st.dataframe(
                    df_criticos[["codigo", "marca", "descripcion", "stock", "stock_minimo"]],
                    use_container_width=True,
                )
            else:
                st.success("✅ Todos los productos se encuentran por encima del nivel de stock mínimo.")

    with tab2:
        st.subheader("🔥 Top Productos Más Vendidos")
        detalles = ejecutar_consulta("detalle_comprobante")
        if detalles:
            df_det = pd.DataFrame(detalles)
            df_top = df_det.groupby("producto_id")["cantidad"].sum().reset_index()
            st.dataframe(df_top, use_container_width=True)

    with tab3:
        st.subheader("🏷️ Comparativa de Precios por Proveedor")
        st.info("Visualización de costos y cotizaciones.")

    with tab4:
        st.subheader("🔄 Historial y Registro de Devoluciones")
        devs = ejecutar_consulta("devoluciones")
        if devs:
            st.dataframe(pd.DataFrame(devs), use_container_width=True)
