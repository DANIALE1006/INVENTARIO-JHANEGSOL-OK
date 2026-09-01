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
        # Se prioriza leer desde st.secrets (.streamlit/secrets.toml)
        if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        else:
            # Reemplaza estos valores por tu URL y Anon Key válidas de Supabase
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


# --- FUNCIÓN GENERADORA DE PDF (REPORTLAB) ---
def generar_pdf_comprobante(
    tipo_doc,
    serie_num,
    cliente_nom,
    cliente_doc,
    carrito,
    subtotal,
    igv,
    total_gen,
):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )
    story = []
    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle(
        "Titulo",
        parent=styles["Heading1"],
        alignment=1,
        fontSize=16,
        leading=20,
        fontName="Helvetica-Bold",
    )
    subtitulo_style = ParagraphStyle(
        "SubTitulo",
        parent=styles["Normal"],
        alignment=1,
        fontSize=10,
        leading=12,
    )
    comprobante_style = ParagraphStyle(
        "Comp",
        parent=styles["Heading2"],
        alignment=1,
        fontSize=12,
        leading=15,
        fontName="Helvetica-Bold",
    )
    normal_style = styles["Normal"]
    derecha_style = ParagraphStyle(
        "Derecha", parent=styles["Normal"], alignment=2
    )
    bold_derecha = ParagraphStyle(
        "BoldDerecha", parent=styles["Normal"], alignment=2, fontName="Helvetica-Bold"
    )

    story.append(Paragraph("JHANEGSOL S.A.C.", titulo_style))
    story.append(Paragraph("RUC: 20600000001", subtitulo_style))
    story.append(
        Paragraph("Oficina Principal - Huacho, Lima - Perú", subtitulo_style)
    )
    story.append(Spacer(1, 15))

    story.append(Paragraph(f"<b>{tipo_doc}</b>", comprobante_style))
    story.append(Paragraph(f"<b>N° {serie_num}</b>", comprobante_style))
    story.append(Spacer(1, 10))

    datos_cliente = [
        [Paragraph(f"<b>Cliente:</b> {cliente_nom}", normal_style)],
        [Paragraph(f"<b>DNI / RUC:</b> {cliente_doc}", normal_style)],
        [
            Paragraph(
                f"<b>Fecha de Emisión:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                normal_style,
            )
        ],
    ]
    story.append(Table(datos_cliente, colWidths=[500]))
    story.append(Spacer(1, 15))

    data_tabla = [[
        Paragraph("<b>Cant.</b>", normal_style),
        Paragraph("<b>Descripción</b>", normal_style),
        Paragraph("<b>P. Unit (S/.)</b>", derecha_style),
        Paragraph("<b>Subtotal (S/.)</b>", derecha_style),
    ]]

    for item in carrito:
        data_tabla.append([
            Paragraph(str(item["cantidad"]), normal_style),
            Paragraph(item["descripcion"], normal_style),
            Paragraph(f"{item['precio_unitario']:.2f}", derecha_style),
            Paragraph(f"{item['subtotal']:.2f}", derecha_style),
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
        [
            Paragraph("Op. Gravada:", derecha_style),
            Paragraph(f"S/. {subtotal:.2f}", derecha_style),
        ],
        [
            Paragraph("IGV (18%):", derecha_style),
            Paragraph(f"S/. {igv:.2f}", derecha_style),
        ],
        [
            Paragraph("<b>TOTAL A PAGAR:</b>", bold_derecha),
            Paragraph(f"<b>S/. {total_gen:.2f}</b>", bold_derecha),
        ],
    ]
    tabla_totales = Table(data_totales, colWidths=[400, 100])
    tabla_totales.setStyle(
        TableStyle([
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(tabla_totales)
    story.append(Spacer(1, 20))

    story.append(
        Paragraph(
            "¡Gracias por su preferencia en JHANEGSOL S.A.C.!", subtitulo_style
        )
    )

    doc.build(story)
    buffer.seek(0)
    return buffer


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
        "🔄 Devoluciones",
        "📊 Histórico de Comprobantes",
        "📈 Estadísticas, Alertas y Reportes",
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
                costo = st.number_input(
                    "Costo (S/.)", min_value=0.0, format="%.2f"
                )
                precio = st.number_input(
                    "Precio Venta (S/.)", min_value=0.0, format="%.2f"
                )
                stock = st.number_input("Stock Inicial", min_value=0, value=0)
                stock_min = st.number_input(
                    "Stock Mínimo Alerta", min_value=1, value=5
                )

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
                else:
                    st.error("⚠️ El código y la descripción son requeridos.")

    prod_data = ejecutar_consulta("productos")
    if prod_data:
        df_prod = pd.DataFrame(prod_data)
        busqueda = st.text_input("🔍 Buscar por código, marca o descripción:")
        if busqueda:
            df_prod = df_prod[
                df_prod.apply(
                    lambda r: busqueda.lower() in str(r).lower(), axis=1
                )
            ]
        st.dataframe(df_prod, use_container_width=True)
    else:
        st.info("No hay productos registrados o no se pudo cargar la tabla.")

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
                data = {
                    "nombre": nombre,
                    "ruc_dni": ruc,
                    "telefono": telefono,
                    "email": email,
                }
                res = ejecutar_consulta("proveedores", "insert", data)
                if res:
                    st.success("✅ Proveedor registrado.")
                    st.rerun()

    prov_data = ejecutar_consulta("proveedores")
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
                    data = {
                        "nombre": cli_nom.upper(),
                        "ruc_dni": cli_doc,
                        "telefono": cli_tel,
                        "direccion": cli_dir,
                    }
                    res = ejecutar_consulta("clientes", "insert", data)
                    if res:
                        st.success(
                            f"✅ Cliente {cli_nom.upper()} registrado con éxito."
                        )
                        st.rerun()
                else:
                    st.error(
                        "⚠️ El Nombre y el DNI/RUC son campos obligatorios."
                    )

    res_clientes = ejecutar_consulta("clientes")
    if res_clientes:
        df_clientes = pd.DataFrame(res_clientes)
        busqueda_c = st.text_input("🔍 Buscar cliente por Nombre o DNI/RUC:")
        if busqueda_c:
            df_clientes = df_clientes[
                df_clientes.apply(
                    lambda r: busqueda_c.lower() in str(r).lower(), axis=1
                )
            ]
        st.dataframe(df_clientes, use_container_width=True)
    else:
        st.info("No hay clientes registrados en la base de datos.")

# -------------------------------------------------------------------
# 4. INGRESOS (COMPRAS / ENTRADA DE STOCK)
# -------------------------------------------------------------------
elif menu == "📥 Ingresos (Compras / Entrada)":
    st.header("📥 Registro de Ingresos de Mercadería (Compras)")
    st.info(
        "Registra las guías de compra de proveedores para aumentar el stock"
        " de tu inventario automáticamente."
    )

    prods = ejecutar_consulta(
        "productos", consulta_type="select", data="id, codigo, descripcion, stock, costo"
    )
    provs = ejecutar_consulta("proveedores", consulta_type="select", data="id, nombre")

    if prods and provs:
        dict_prods = {
            f"{p['codigo']} - {p['descripcion']} (Stock actual: {p['stock']})": p
            for p in prods
        }
        dict_provs = {pr["nombre"]: pr["id"] for pr in provs}

        with st.form("form_ingresos", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                prov_sel = st.selectbox("Proveedor", list(dict_provs.keys()))
                nro_fact_compra = st.text_input(
                    "N° Factura/Guía de Compra", value="F001-0001"
                )
            with c2:
                prod_sel = st.selectbox(
                    "Producto a Ingresar", list(dict_prods.keys())
                )
                cant_ingreso = st.number_input(
                    "Cantidad que Ingresa", min_value=1, value=1
                )
            with c3:
                nuevo_costo = st.number_input(
                    "Costo Unitario Compra (S/.)",
                    min_value=0.0,
                    value=float(dict_prods[prod_sel]["costo"] or 0.0),
                )
                fecha_compra = st.date_input("Fecha de Ingreso", datetime.now())

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
                    st.success(
                        "✅ Stock actualizado. Nuevo Stock de"
                        f" '{prod_info['descripcion']}': {nuevo_stock}"
                    )
                    st.rerun()
    else:
        st.warning(
            "⚠️ Asegúrate de tener al menos 1 producto y 1 proveedor"
            " registrados en el sistema."
        )
# -------------------------------------------------------------------
# 5. VENTAS Y EMISIÓN DE COMPROBANTES
# -------------------------------------------------------------------
elif menu == "🧾 Ventas y Emisión de Comprobantes":
    st.header("🧾 Punto de Venta: Emisión de Boletas, Facturas y Tickets")

    st.subheader("👤 Seleccionar o Registrar Cliente")
    res_clientes_v = ejecutar_consulta("clientes")
    df_cli_v = pd.DataFrame(res_clientes_v) if res_clientes_v else pd.DataFrame()

    opcion_cliente = st.radio(
        "Tipo de Cliente",
        [
            "Cliente Genérico (Varios)",
            "Seleccionar Cliente Registrado",
            "➕ Registrar Nuevo Cliente",
        ],
        horizontal=True,
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
            lista_nombres = df_cli_v["nombre"].tolist()
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
            st.warning("No hay clientes registrados en la BD.")

    elif opcion_cliente == "➕ Registrar Nuevo Cliente":
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
                    data = {
                        "nombre": nuevo_nom.upper(),
                        "ruc_dni": nuevo_doc,
                        "telefono": nuevo_tel,
                        "direccion": nueva_dir,
                    }
                    ejecutar_consulta("clientes", "insert", data)
                    st.success(f"✅ Cliente {nuevo_nom.upper()} registrado.")
                    cliente_nom = nuevo_nom.upper()
                    cliente_doc = nuevo_doc
                    st.rerun()

    st.divider()

    c1, c2, c3 = st.columns(3)
    with c1:
        tipo_doc = st.selectbox(
            "Tipo de Comprobante *",
            [
                "BOLETA DE VENTA",
                "FACTURA",
                "TICKET DE VENTA",
                "NOTA DE CRÉDITO",
                "NOTA DE DÉBITO",
            ],
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

        # --- LÓGICA CORREGIDA PARA CÁLCULO DE CORRELATIVO ---
        ult_comps = ejecutar_consulta(
            "comprobantes",
            consulta_type="select",
            data="serie_numero",
            like_col="serie_numero",
            like_val=f"{prefijo}-%",
        )

        siguiente_num = 1
        if ult_comps:
            numeros = []
            for c in ult_comps:
                val = c.get("serie_numero", "")
                if "-" in val:
                    try:
                        # Extrae la parte numérica tras el guión (ej: "B001-000003" -> 3)
                        num = int(val.split("-")[1])
                        numeros.append(num)
                    except ValueError:
                        pass
            if numeros:
                siguiente_num = max(numeros) + 1

        sugerido = f"{prefijo}-{siguiente_num:06d}"
        serie_num = st.text_input("Serie y Número Comprobante", value=sugerido)

    prods = ejecutar_consulta(
        "productos",
        consulta_type="select",
        data="id, codigo, descripcion, precio, stock",
    )
    if prods:
        dict_prods = {
            f"{p['codigo']} | {p['descripcion']} (Stock: {p['stock']})": p
            for p in prods
        }

        cp1, cp2, cp3 = st.columns([3, 1, 1])
        with cp1:
            p_sel_key = st.selectbox(
                "Buscar Producto para Salida / Venta", list(dict_prods.keys())
            )
        with cp2:
            cant_v = st.number_input("Cantidad", min_value=1, value=1)
        with cp3:
            st.write("")
            st.write("")
            if st.button("➕ Agregar al Comprobante"):
                p_info = dict_prods[p_sel_key]
                if "NOTA DE CRÉDITO" in tipo_doc or cant_v <= p_info["stock"]:
                    st.session_state.carrito.append({
                        "id": p_info["id"],
                        "codigo": p_info["codigo"],
                        "descripcion": p_info["descripcion"],
                        "cantidad": cant_v,
                        "precio_unitario": p_info["precio"],
                        "subtotal": cant_v * p_info["precio"],
                    })
                    st.success("✅ Producto agregado")
                    st.rerun()
                else:
                    st.error("⚠️ La cantidad supera el stock disponible.")

    if st.session_state.carrito:
        st.subheader("📋 Detalle de la Venta")
        df_car = pd.DataFrame(st.session_state.carrito)
        st.dataframe(
            df_car[
                ["codigo", "descripcion", "cantidad", "precio_unitario", "subtotal"]
            ],
            use_container_width=True,
        )

        total_gen = float(df_car["subtotal"].sum())
        subtotal = total_gen / 1.18
        igv = total_gen - subtotal

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Op. Gravada (Subtotal)", f"S/. {subtotal:.2f}")
        col_m2.metric("IGV (18%)", f"S/. {igv:.2f}")
        col_m3.metric("TOTAL GENERAL", f"S/. {total_gen:.2f}")

        st.divider()
        archivo_pdf = generar_pdf_comprobante(
            tipo_doc,
            serie_num,
            cliente_nom,
            cliente_doc,
            st.session_state.carrito,
            subtotal,
            igv,
            total_gen,
        )

        st.download_button(
            label=f"📄 DESCARGAR PDF ({tipo_doc} {serie_num})",
            data=archivo_pdf,
            file_name=f"{tipo_doc.replace(' ', '_')}_{serie_num}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

        b_col1, b_col2 = st.columns(2)
        with b_col1:
            if st.button("🔴 Vaciar Selección", use_container_width=True):
                st.session_state.carrito = []
                st.rerun()

        with b_col2:
            accion_texto = (
                "SUMAR AL STOCK"
                if "NOTA DE CRÉDITO" in tipo_doc
                else "DESCONTAR STOCK"
            )
            if st.button(
                f"🖨️ EMITIR {tipo_doc} Y {accion_texto}",
                type="primary",
                use_container_width=True,
            ):
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

                        prod_bd = ejecutar_consulta(
                            "productos",
                            consulta_type="select",
                            data="stock",
                            eq_col="id",
                            eq_val=item["id"],
                        )
                        if prod_bd:
                            stock_actual = prod_bd[0]["stock"]
                            nuevo_stk = (
                                stock_actual + item["cantidad"]
                                if "NOTA DE CRÉDITO" in tipo_doc
                                else stock_actual - item["cantidad"]
                            )
                            ejecutar_consulta(
                                "productos",
                                "update",
                                data={"stock": nuevo_stk},
                                eq_col="id",
                                eq_val=item["id"],
                            )

                    st.balloons()
                    st.success(f"🎉 ¡{tipo_doc} {serie_num} emitida con éxito!")
                    st.session_state.carrito = []
                    st.rerun()
# -------------------------------------------------------------------
# 6. DEVOLUCIONES
# -------------------------------------------------------------------
elif menu == "🔄 Devoluciones":
    st.header("🔄 Registro de Devoluciones de Clientes / Proveedores")

    col1, col2 = st.columns(2)
    with col1:
        tipo_doc = st.selectbox(
            "Tipo Comprobante", ["BOLETA", "FACTURA", "TICKET", "NOTA DE CRÉDITO"]
        )
        nro_doc = st.text_input("Número Comprobante")
        tipo_op = st.selectbox(
            "Tipo de Operación",
            [
                "DEVOLUCIÓN POR DEFECTO",
                "DEVOLUCIÓN POR STOCK",
                "AJUSTE DE INVENTARIO",
            ],
        )
    with col2:
        fecha_emision = st.date_input("Fecha", datetime.now())
        motivo = st.text_area("Motivo de Devolución *")

    prods = ejecutar_consulta(
        "productos", consulta_type="select", data="id, codigo, descripcion, precio"
    )
    provs = ejecutar_consulta("proveedores", consulta_type="select", data="id, nombre")

    if prods and provs:
        dict_prods = {f"{p['codigo']} - {p['descripcion']}": p for p in prods}
        dict_provs = {pr["nombre"]: pr["id"] for pr in provs}

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
                    "motivo_devolucion": f"[{tipo_doc} - {tipo_op}] | {motivo}",
                }
                res = ejecutar_consulta("devoluciones", "insert", dev_data)
                if res:
                    st.success("✅ Devolución procesada.")
                    st.rerun()

# -------------------------------------------------------------------
# 7. HISTÓRICO DE COMPROBANTES
# -------------------------------------------------------------------
elif menu == "📊 Histórico de Comprobantes":
    st.header("📊 Histórico de Ventas y Comprobantes Emitidos")
    comps = ejecutar_consulta("comprobantes")
    if comps:
        st.dataframe(pd.DataFrame(comps), use_container_width=True)
    else:
        st.info("Aún no se han emitido comprobantes de venta.")

# -------------------------------------------------------------------
# 8. ESTADÍSTICAS Y REPORTES
# -------------------------------------------------------------------
elif menu == "📈 Estadísticas, Alertas y Reportes":
    st.header("📈 Panel de Inteligencia Comercial y Alertas")

    st.subheader("⚠️ Alertas de Stock Bajo (Para Comprar)")
    alertas_res = ejecutar_consulta("vista_alerta_stock")
    if alertas_res:
        df_alertas = pd.DataFrame(alertas_res)
        st.error(f"¡Atención! Hay {len(df_alertas)} productos con stock crítico.")
        st.dataframe(df_alertas, use_container_width=True)
    else:
        st.info(
            "No hay alertas de stock bajo o la vista SQL 'vista_alerta_stock' no"
            " está creada."
        )

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Top Productos Más Vendidos**")
        top_prod_res = ejecutar_consulta("vista_productos_mas_vendidos")
        if top_prod_res:
            df_top_prod = pd.DataFrame(top_prod_res)
            if "descripcion" in df_top_prod.columns:
                st.bar_chart(
                    df_top_prod.set_index("descripcion")["total_unidades_vendidas"]
                )
            st.dataframe(df_top_prod, use_container_width=True)
        else:
            st.info("Sin datos de productos más vendidos.")

    with col2:
        st.markdown("**Clientes Frecuentes (Top Compradores)**")
        top_cli_res = ejecutar_consulta("vista_clientes_frecuentes")
        if top_cli_res:
            st.dataframe(pd.DataFrame(top_cli_res), use_container_width=True)
        else:
            st.info("Sin datos de clientes frecuentes.")
