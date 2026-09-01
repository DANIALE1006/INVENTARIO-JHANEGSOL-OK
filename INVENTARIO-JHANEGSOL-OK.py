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

# --- CONFIGURACIÓN INICIAL DE SESSION STATE ---
if "carrito_ventas" not in st.session_state:
    st.session_state.carrito_ventas = []

if "carrito_nc" not in st.session_state:
    st.session_state.carrito_nc = []

if "procesando_operacion" not in st.session_state:
    st.session_state.procesando_operacion = False

if "pdf_generado" not in st.session_state:
    st.session_state.pdf_generado = None

if "num_ultimo_comp" not in st.session_state:
    st.session_state.num_ultimo_comp = ""

if "ultimo_pdf_nombre" not in st.session_state:
    st.session_state.ultimo_pdf_nombre = ""

if "datos_ultimo_comprobante" not in st.session_state:
    st.session_state.datos_ultimo_comprobante = None

# --- GENERADOR DE PDF (REPORTLAB) ---
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
    return buffer.getvalue()

# --- FUNCIONES AUXILIARES ---
def comprobante_existe(serie_numero):
    """Evita que una misma operación se procese dos veces."""
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

def mostrar_seccion_descarga_pdf():
    """Muestra la previsualización y el botón de descarga si existe un PDF generado."""
    if st.session_state.pdf_generado:
        st.markdown("---")
        st.subheader("📄 Último Comprobante Generado")
        
        col_desc, col_info = st.columns([1, 2])
        
        with col_desc:
            st.download_button(
                label=f"⬇️ Descargar PDF ({st.session_state.num_ultimo_comp})",
                data=st.session_state.pdf_generado,
                file_name=st.session_state.ultimo_pdf_nombre,
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )

        with col_info:
            if st.session_state.datos_ultimo_comprobante:
                d = st.session_state.datos_ultimo_comprobante
                with st.expander("👁️ Previsualizar Vista Rápida del Documento", expanded=True):
                    st.markdown(f"**{d['tipo']} - N° {d['serie']}**")
                    st.markdown(f"**Cliente:** {d['cliente']} ({d['doc']})")
                    df_det = pd.DataFrame(d['items'])
                    if not df_det.empty:
                        st.dataframe(df_det[['descripcion', 'cantidad', 'precio_unitario']], use_container_width=True)
                    st.markdown(f"**Total Emitido:** S/. {d['total']:.2f}")

# --- CALLBACK EXCLUSIVO DE VENTAS DIRECTAS ---
def callback_emito_venta(tipo_doc, serie_num, cliente_nom, cliente_doc, subtotal, igv, total_gen):
    if st.session_state.procesando_operacion or not st.session_state.carrito_ventas:
        return

    st.session_state.procesando_operacion = True

    try:
        # 1. Evitar doble emisión del mismo comprobante
        if comprobante_existe(serie_num):
            st.error(f"❌ El comprobante {serie_num} ya existe.")
            return

        # 2. Validar y descontar el stock en base de datos
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
                st.error(
                    f"❌ Stock insuficiente para {item['descripcion']}. "
                    f"Disponible: {stock_actual} | Solicitado: {cantidad}"
                )
                return

            # Descontar stock
            nuevo_stock = stock_actual - cantidad
            ejecutar_consulta("productos", "update", {"stock": nuevo_stock}, eq_col="id", eq_val=item["id"])

        # 3. Crear cabecera
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

        # 4. Insertar detalle
        for item in st.session_state.carrito_ventas:
            cant_exacta = int(item["cantidad"])
            p_id = item["id"]

            det = {
                "comprobante_id": comp_id,
                "producto_id": p_id,
                "cantidad": cant_exacta,
                "precio_unitario": float(item["precio_unitario"]),
            }

            detalle = ejecutar_consulta("detalle_comprobante", "insert", det)

            if detalle is None:
                st.error("❌ Error registrando el detalle de la venta.")
                return

        # 5. Generar PDF y Limpieza
        pdf_bytes = generar_pdf_comprobante(
            tipo_doc,
            serie_num,
            cliente_nom,
            cliente_doc,
            st.session_state.carrito_ventas,
            subtotal,
            igv,
            total_gen,
        )

        st.session_state.pdf_generado = pdf_bytes
        st.session_state.num_ultimo_comp = serie_num
        st.session_state.ultimo_pdf_nombre = f"{serie_num}.pdf"
        st.session_state.datos_ultimo_comprobante = {
            "tipo": tipo_doc,
            "serie": serie_num,
            "cliente": cliente_nom,
            "doc": cliente_doc,
            "items": list(st.session_state.carrito_ventas),
            "total": total_gen,
        }

        # Vaciar Carrito
        st.session_state.carrito_ventas = []

        st.success(f"✅ {tipo_doc} {serie_num} emitido correctamente.")

    except Exception as e:
        st.error(f"❌ Error durante la emisión: {e}")
    finally:
        st.session_state.procesando_operacion = False

# --- CALLBACK EXCLUSIVO DE NOTAS (CRÉDITO Y DÉBITO) ---
def callback_emito_nota(
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
):
    if st.session_state.procesando_operacion or not st.session_state.carrito_nc:
        return

    st.session_state.procesando_operacion = True

    try:
        # 1. Evitar doble emisión
        if comprobante_existe(serie_nota):
            st.error(f"❌ La nota {serie_nota} ya existe.")
            return

        # 2. Obtener comprobante original
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

        origen_id = origen.data["id"]

        # 3. Validar devoluciones si es Nota de Crédito
        if tipo_nota == "NOTA DE CRÉDITO":
            detalles_orig = (
                supabase.table("detalle_comprobante")
                .select("producto_id, cantidad")
                .eq("comprobante_id", origen_id)
                .execute()
                .data
            )

            if not detalles_orig:
                st.error("❌ El comprobante original no tiene productos.")
                return

            vendidos = {}
            for d in detalles_orig:
                pid = d["producto_id"]
                vendidos[pid] = vendidos.get(pid, 0) + abs(int(d["cantidad"]))

            devoluciones_previas = (
                supabase.table("devoluciones")
                .select("producto_id, cantidad, numero_boleta")
                .like("numero_boleta", f"%Afecta: {doc_ref}%")
                .execute()
                .data
            )

            devueltos = {}
            for d in devoluciones_previas or []:
                pid = d["producto_id"]
                devueltos[pid] = devueltos.get(pid, 0) + abs(int(d["cantidad"]))

            for item in st.session_state.carrito_nc:
                pid = item["id"]
                cantidad_devolver = int(item["cantidad"])
                cantidad_disponible = vendidos.get(pid, 0) - devueltos.get(pid, 0)

                if cantidad_devolver > cantidad_disponible:
                    st.error(
                        f"❌ No puedes devolver {cantidad_devolver} unidades de "
                        f"{item['descripcion']}. Disponible para devolución: {cantidad_disponible}."
                    )
                    return

        # 4. Crear cabecera de la nota
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

        # 5. Procesar productos y REINTEGRAR STOCK si es Nota de Crédito
        for item in st.session_state.carrito_nc:
            cantidad = int(item["cantidad"])
            p_id = item["id"]

            det = {
                "comprobante_id": comp_id,
                "producto_id": p_id,
                "cantidad": cantidad,
                "precio_unitario": float(item["precio_unitario"]),
            }

            detalle = ejecutar_consulta("detalle_comprobante", "insert", det)

            if detalle is None:
                st.error("❌ Error registrando detalle de la nota.")
                return

            if tipo_nota == "NOTA DE CRÉDITO":
                # Reintegrar stock al inventario
                res_prod = (
                    supabase.table("productos")
                    .select("stock")
                    .eq("id", p_id)
                    .single()
                    .execute()
                )
                if res_prod.data:
                    stock_actual = int(res_prod.data.get("stock") or 0)
                    nuevo_stock = stock_actual + cantidad
                    ejecutar_consulta("productos", "update", {"stock": nuevo_stock}, eq_col="id", eq_val=p_id)

                reg_dev = {
                    "numero_boleta": f"{serie_nota} (Afecta: {doc_ref})",
                    "producto_id": p_id,
                    "cantidad": cantidad,
                    "precio": float(item["precio_unitario"]),
                    "motivo_devolucion": f"[{cat_motivo}] {motivo_nota}",
                }
                ejecutar_consulta("devoluciones", "insert", reg_dev)

        # 6. Generar PDF
        st.session_state.pdf_generado = generar_pdf_comprobante(
            tipo_nota,
            serie_nota,
            cliente_nom,
            cliente_doc,
            st.session_state.carrito_nc,
            subtotal,
            igv,
            total_gen,
            doc_referencia=doc_ref,
            motivo=motivo_nota,
        )

        st.session_state.num_ultimo_comp = serie_nota
        st.session_state.ultimo_pdf_nombre = f"{serie_nota}.pdf"
        st.session_state.datos_ultimo_comprobante = {
            "tipo": tipo_nota,
            "serie": serie_nota,
            "cliente": cliente_nom,
            "doc": cliente_doc,
            "items": list(st.session_state.carrito_nc),
            "total": total_gen,
        }

        st.session_state.carrito_nc = []

        st.success(f"✅ {tipo_nota} {serie_nota} procesada correctamente y stock reingresado.")

    except Exception as e:
        st.error(f"❌ Error procesando la nota: {e}")
    finally:
        st.session_state.procesando_operacion = False

# --- INTERFAZ PRINCIPAL DE STREAMLIT ---
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
            prov_sel = st.selectbox("Seleccionar Proveedor", list(dict_provs.keys()))
            prod_sel = st.selectbox("Seleccionar Producto", list(dict_prods.keys()))
            c1, c2 = st.columns(2)
            with c1:
                cant_ing = st.number_input("Cantidad Ingresada", min_value=1, value=1)
            with c2:
                costo_ing = st.number_input("Costo Unitario (S/.)", min_value=0.0, format="%.2f")

            if st.form_submit_button("Registrar Ingreso"):
                p_selected = dict_prods[prod_sel]
                nuevo_stock = p_selected["stock"] + cant_ing

                ejecutar_consulta("productos", "update", {"stock": nuevo_stock, "costo": costo_ing}, eq_col="id", eq_val=p_selected["id"])
                
                data_ingreso = {
                    "proveedor_id": dict_provs[prov_sel],
                    "producto_id": p_selected["id"],
                    "cantidad": cant_ing,
                    "costo_unitario": costo_ing,
                    "fecha": datetime.now().isoformat()
                }
                ejecutar_consulta("ingresos", "insert", data_ingreso)

                st.success(f"✅ Ingreso registrado. Stock actualizado de {p_selected['stock']} a {nuevo_stock}.")
                st.rerun()
    else:
        st.warning("⚠️ Debes registrar productos y proveedores antes de ingresar compras.")

# -------------------------------------------------------------------
# 5. VENTAS DIRECTAS (BOLETAS Y FACTURAS)
# -------------------------------------------------------------------
elif menu == "🧾 Ventas Directas (Boletas y Facturas)":
    st.header("🧾 Punto de Venta - Emisión de Boletas y Facturas")

    prods = ejecutar_consulta("productos", consulta_type="select", data="id, codigo, descripcion, stock, precio")
    
    if prods:
        dict_prods = {f"{p['codigo']} - {p['descripcion']} (S/. {p['precio']:.2f} | Stock: {p['stock']})": p for p in prods}

        st.subheader("1. Agregar Productos")
        col_p, col_c, col_b = st.columns([3, 1, 1])
        with col_p:
            p_sel = st.selectbox("Producto", list(dict_prods.keys()))
        with col_c:
            cant_v = st.number_input("Cantidad", min_value=1, value=1)
        with col_b:
            st.write("")
            st.write("")
            if st.button("➕ Agregar"):
                prod = dict_prods[p_sel]
                if cant_v <= prod["stock"]:
                    st.session_state.carrito_ventas.append({
                        "id": prod["id"],
                        "descripcion": prod["descripcion"],
                        "cantidad": cant_v,
                        "precio_unitario": prod["precio"],
                        "subtotal": cant_v * prod["precio"]
                    })
                    st.success("Agregado al carrito.")
                else:
                    st.error("Stock insuficiente.")

        if st.session_state.carrito_ventas:
            st.subheader("2. Detalle de la Venta")
            df_cart = pd.DataFrame(st.session_state.carrito_ventas)
            st.dataframe(df_cart[["descripcion", "cantidad", "precio_unitario", "subtotal"]], use_container_width=True)

            if st.button("🗑️ Vaciar Carrito"):
                st.session_state.carrito_ventas = []
                st.rerun()

            total_gen = sum(i["subtotal"] for i in st.session_state.carrito_ventas)
            subtotal = total_gen / 1.18
            igv = total_gen - subtotal

            st.markdown(f"**Subtotal:** S/. {subtotal:.2f} | **IGV (18%):** S/. {igv:.2f} | **TOTAL:** S/. {total_gen:.2f}")

            st.subheader("3. Datos del Comprobante")
            c_doc, c_serie, c_cli, c_num = st.columns(4)
            with c_doc:
                tipo_doc = st.selectbox("Tipo Documento", ["BOLETA", "FACTURA"])
            with c_serie:
                serie = st.text_input("Serie", value="B001" if tipo_doc == "BOLETA" else "F001")
            with c_num:
                correlativo = st.text_input("Número Correlativo", value="000001")
            with c_cli:
                cliente_nom = st.text_input("Cliente", value="CLIENTES VARIOS")
            
            cliente_doc = st.text_input("DNI / RUC Cliente", value="00000000")
            serie_num = f"{serie}-{correlativo}"

            if st.button("🚀 Emitir Comprobante", type="primary"):
                callback_emito_venta(tipo_doc, serie_num, cliente_nom, cliente_doc, subtotal, igv, total_gen)

    mostrar_seccion_descarga_pdf()

# -------------------------------------------------------------------
# 6. NOTAS DE CRÉDITO Y DÉBITO
# -------------------------------------------------------------------
elif menu == "📝 Notas de Crédito y Débito":
    st.header("📝 Emisión de Notas de Crédito y Débito")

    doc_ref = st.text_input("Comprobante Afectado (Ejemplo: B001-000001)").upper()

    if doc_ref:
        comp_orig = (
            supabase.table("comprobantes")
            .select("*")
            .eq("serie_numero", doc_ref)
            .execute()
            .data
        )

        if comp_orig:
            c = comp_orig[0]
            st.info(f"📄 Comprobante Encontrado: {c['tipo_comprobante']} {c['serie_numero']} - Cliente: {c['cliente_nombre']}")

            detalles = (
                supabase.table("detalle_comprobante")
                .select("*, productos(descripcion)")
                .eq("comprobante_id", c["id"])
                .execute()
                .data
            )

            if detalles:
                prods_dict = {f"{d['productos']['descripcion']} (Comprado: {d['cantidad']})": d for d in detalles}
                
                col_p, col_c, col_b = st.columns([3, 1, 1])
                with col_p:
                    p_sel = st.selectbox("Producto a Devolver / Modificar", list(prods_dict.keys()))
                with col_c:
                    cant_nc = st.number_input("Cantidad", min_value=1, value=1)
                with col_b:
                    st.write("")
                    st.write("")
                    if st.button("➕ Agregar a Nota"):
                        item_d = prods_dict[p_sel]
                        st.session_state.carrito_nc.append({
                            "id": item_d["producto_id"],
                            "descripcion": item_d["productos"]["descripcion"],
                            "cantidad": cant_nc,
                            "precio_unitario": item_d["precio_unitario"],
                            "subtotal": cant_nc * item_d["precio_unitario"]
                        })
                        st.success("Agregado a la nota.")

                if st.session_state.carrito_nc:
                    st.dataframe(pd.DataFrame(st.session_state.carrito_nc), use_container_width=True)

                    total_gen = sum(i["subtotal"] for i in st.session_state.carrito_nc)
                    subtotal = total_gen / 1.18
                    igv = total_gen - subtotal

                    c_tipo, c_serie, c_mot, c_cat = st.columns(4)
                    with c_tipo:
                        tipo_nota = st.selectbox("Tipo de Nota", ["NOTA DE CRÉDITO", "NOTA DE DÉBITO"])
                    with c_serie:
                        serie_nota = st.text_input("Serie/Número", value="FC01-000001" if tipo_nota == "NOTA DE CRÉDITO" else "FD01-000001")
                    with c_cat:
                        cat_motivo = st.selectbox("Categoría Motivo", ["Anulación de la operación", "Devolución total", "Devolución parcial", "Descuento global"])
                    with c_mot:
                        motivo_nota = st.text_input("Sustento/Motivo", value="Devolución de mercadería")

                    if st.button("🚀 Emitir Nota", type="primary"):
                        callback_emito_nota(
                            tipo_nota,
                            serie_nota,
                            c["cliente_nombre"],
                            c["cliente_documento"],
                            subtotal,
                            igv,
                            total_gen,
                            doc_ref,
                            cat_motivo,
                            motivo_nota,
                        )
        else:
            st.warning("⚠️ No se encontró el comprobante referenciado.")

    mostrar_seccion_descarga_pdf()

# -------------------------------------------------------------------
# 7. HISTÓRICO DE COMPROBANTES
# -------------------------------------------------------------------
elif menu == "📊 Histórico de Comprobantes":
    st.header("📊 Histórico de Comprobantes Emitidos")

    comps = ejecutar_consulta("comprobantes", order_col="created_at", desc=True)

    if comps:
        df_comps = pd.DataFrame(comps)
        st.dataframe(df_comps, use_container_width=True)

# -------------------------------------------------------------------
# 8. ESTADÍSTICAS Y MÉTRICAS
# -------------------------------------------------------------------
elif menu == "📈 Estadísticas y Métricas de Negocio":
    st.header("📈 Indicadores y Métricas del Negocio")

    comps = ejecutar_consulta("comprobantes")
    prods = ejecutar_consulta("productos")

    if comps and prods:
        df_c = pd.DataFrame(comps)
        df_p = pd.DataFrame(prods)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total Ventas (S/.)", f"S/. {df_c['total'].sum():.2f}")
        with c2:
            st.metric("Comprobantes Emitidos", len(df_c))
        with c3:
            st.metric("Productos Registrados", len(df_p))
