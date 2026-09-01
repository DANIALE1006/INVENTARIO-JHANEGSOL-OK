import io
import pandas as pd
import streamlit as st
from fpdf import FPDF

# -------------------------------------------------------------------
# CONFIGURACIÓN INICIAL DE SESSION STATE
# -------------------------------------------------------------------
if "carrito_ventas" not in st.session_state:
    st.session_state.carrito_ventas = []

if "procesando_operacion" not in st.session_state:
    st.session_state.procesando_operacion = False

if "pdf_generado" not in st.session_state:
    st.session_state.pdf_generado = None

if "ultimo_pdf_nombre" not in st.session_state:
    st.session_state.ultimo_pdf_nombre = ""

if "datos_ultimo_comprobante" not in st.session_state:
    st.session_state.datos_ultimo_comprobante = None


# -------------------------------------------------------------------
# FUNCIONES AUXILIARES DE BASE DE DATOS (REEMPLAZAR CON TU LÓGICA DE SUPABASE)
# -------------------------------------------------------------------
def ejecutar_consulta(tabla, consulta_type="select", data=None, where_col=None, where_val=None, like_col=None, like_val=None):
    """
    Función adaptadora para Supabase o base de datos local.
    Ajusta esta función según tu integración real con Supabase Client.
    """
    # NOTA: Reemplazar este bloque condicional con tus llamadas reales a supabase.table(tabla)
    return []


# -------------------------------------------------------------------
# GENERADOR DE PDF CON FPDF2
# -------------------------------------------------------------------
def generar_pdf_comprobante(tipo_doc, serie_num, cliente_nom, cliente_doc, items, subtotal, igv, total_gen, motivo=""):
    """
    Genera un comprobante en PDF con formato Ticket (80mm de ancho).
    Devuelve los bytes del PDF.
    """
    pdf = FPDF(format=(80, 200), unit="mm")
    pdf.set_margins(4, 4, 4)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=5)

    # Encabezado
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 5, "MI EMPRESA S.A.C.", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, "RUC: 20123456789", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 4, "Av. Principal 123 - Lima", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, f"{tipo_doc}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 4, f"N°: {serie_num}", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    pdf.line(4, pdf.get_y(), 76, pdf.get_y())
    pdf.ln(2)

    # Datos del Cliente
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, f"Cliente: {cliente_nom[:28]}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 4, f"Doc/RUC/DNI: {cliente_doc}", new_x="LMARGIN", new_y="NEXT")
    if motivo:
        pdf.cell(0, 4, f"Motivo: {motivo[:28]}", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    pdf.line(4, pdf.get_y(), 76, pdf.get_y())
    pdf.ln(2)

    # Tabla de Items
    pdf.set_font("Helvetica", "B", 7)
    pdf.cell(32, 4, "Cant / Descripción", align="L")
    pdf.cell(18, 4, "P.Unit", align="R")
    pdf.cell(22, 4, "Importe", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 7)
    for it in items:
        desc = it["descripcion"][:20]
        cant = it["cantidad"]
        pu = it["precio_unitario"]
        sub = it["subtotal"]

        pdf.cell(32, 4, f"{cant}x {desc}", align="L")
        pdf.cell(18, 4, f"{pu:.2f}", align="R")
        pdf.cell(22, 4, f"{sub:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    pdf.line(4, pdf.get_y(), 76, pdf.get_y())
    pdf.ln(2)

    # Totales
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(50, 4, "OP. GRAVADA:", align="R")
    pdf.cell(22, 4, f"S/ {subtotal:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(50, 4, "I.G.V. (18%):", align="R")
    pdf.cell(22, 4, f"S/ {igv:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(50, 5, "TOTAL:", align="R")
    pdf.cell(22, 5, f"S/ {total_gen:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 7)
    pdf.cell(0, 4, "¡Gracias por su compra!", align="C", new_x="LMARGIN", new_y="NEXT")

    # Retornar Bytes
    return bytes(pdf.output())


# -------------------------------------------------------------------
# CALLBACK: EMISIÓN DE VENTAS DIRECTAS (DESCUENTA STOCK)
# -------------------------------------------------------------------
def callback_emito_venta(tipo_doc, serie_num, cliente_nom, cliente_doc, subtotal, igv, total_gen):
    try:
        st.session_state.procesando_operacion = True

        if not st.session_state.carrito_ventas:
            st.error("El carrito está vacío.")
            return

        items = [dict(i) for i in st.session_state.carrito_ventas]

        # 1. Registrar Comprobante
        datos_comp = {
            "tipo_documento": tipo_doc,
            "serie_numero": serie_num,
            "cliente_nombre": cliente_nom,
            "cliente_doc": cliente_doc,
            "subtotal": subtotal,
            "igv": igv,
            "total": total_gen,
        }
        ejecutar_consulta("comprobantes", consulta_type="insert", data=datos_comp)

        # 2. Descontar Stock
        for item in items:
            p_actual = ejecutar_consulta("productos", consulta_type="select", data="stock", where_col="id", where_val=item["id"])
            if p_actual:
                nuevo_stock = max(0, p_actual[0]["stock"] - item["cantidad"])
                ejecutar_consulta("productos", consulta_type="update", data={"stock": nuevo_stock}, where_col="id", where_val=item["id"])

        # 3. Generar PDF y Almacenar en Session State
        pdf_bytes = generar_pdf_comprobante(tipo_doc, serie_num, cliente_nom, cliente_doc, items, subtotal, igv, total_gen)

        st.session_state.pdf_generado = pdf_bytes
        st.session_state.ultimo_pdf_nombre = f"{serie_num}.pdf"
        st.session_state.datos_ultimo_comprobante = {
            "tipo": tipo_doc,
            "serie": serie_num,
            "cliente": cliente_nom,
            "doc": cliente_doc,
            "items": items,
            "total": total_gen,
        }

        # Vaciar Carrito
        st.session_state.carrito_ventas = []

    except Exception as e:
        st.error(f"Error procesando la venta: {e}")
    finally:
        st.session_state.procesando_operacion = False


# -------------------------------------------------------------------
# CALLBACK: EMISIÓN DE NOTA DE CRÉDITO (REINSERTA / AUMENTA STOCK)
# -------------------------------------------------------------------
def callback_emitir_nota_credito(serie_nc, comp_ref_serie, cliente_nom, cliente_doc, motivo, items_nc):
    try:
        st.session_state.procesando_operacion = True

        if not items_nc:
            st.error("No hay ítems para procesar en la Nota de Crédito.")
            return

        total_gen = sum(float(i["subtotal"]) for i in items_nc)
        subtotal = total_gen / 1.18
        igv = total_gen - subtotal

        # 1. Registrar Nota de Crédito en BD
        datos_nc = {
            "tipo_documento": "NOTA DE CREDITO",
            "serie_numero": serie_nc,
            "comprobante_referencia": comp_ref_serie,
            "cliente_nombre": cliente_nom,
            "cliente_doc": cliente_doc,
            "motivo": motivo,
            "subtotal": subtotal,
            "igv": igv,
            "total": total_gen,
        }
        ejecutar_consulta("comprobantes", consulta_type="insert", data=datos_nc)

        # 2. INCREMENTAR STOCK (DEVOLUCIÓN)
        for item in items_nc:
            prod_id = item["id"]
            cant_devueltas = item["cantidad"]

            p_actual = ejecutar_consulta("productos", consulta_type="select", data="stock", where_col="id", where_val=prod_id)
            if p_actual:
                stock_restaurado = p_actual[0]["stock"] + cant_devueltas
                ejecutar_consulta("productos", consulta_type="update", data={"stock": stock_restaurado}, where_col="id", where_val=prod_id)

        # 3. Generar PDF
        pdf_bytes = generar_pdf_comprobante("NOTA DE CREDITO", serie_nc, cliente_nom, cliente_doc, items_nc, subtotal, igv, total_gen, motivo=motivo)

        st.session_state.pdf_generado = pdf_bytes
        st.session_state.ultimo_pdf_nombre = f"{serie_nc}.pdf"
        st.session_state.datos_ultimo_comprobante = {
            "tipo": "NOTA DE CREDITO",
            "serie": serie_nc,
            "cliente": cliente_nom,
            "doc": cliente_doc,
            "items": items_nc,
            "total": total_gen,
            "motivo": motivo,
        }

    except Exception as e:
        st.error(f"Error al emitir Nota de Crédito: {e}")
    finally:
        st.session_state.procesando_operacion = False


# -------------------------------------------------------------------
# MENÚ Y NAVEGACIÓN PRINCIPAL DE STREAMLIT
# -------------------------------------------------------------------
menu = st.sidebar.radio(
    "Navegación",
    ["🧾 Ventas Directas (Boletas y Facturas)", "🔄 Nota de Crédito (Devolución)"],
)

# -------------------------------------------------------------------
# 1. VENTAS DIRECTAS (BOLETAS Y FACTURAS)
# -------------------------------------------------------------------
if menu == "🧾 Ventas Directas (Boletas y Facturas)":
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
                        st.session_state.carrito_ventas.append(
                            {
                                "id": p_info["id"],
                                "codigo": p_info["codigo"],
                                "descripcion": p_info["descripcion"],
                                "cantidad": int(cant_v),
                                "precio_unitario": float(p_info["precio"]),
                                "subtotal": float(cant_v * p_info["precio"]),
                            }
                        )
                    st.success("✅ Agregado")
                    st.rerun()

    if st.session_state.carrito_ventas:
        st.subheader("📋 Detalle de la Venta")

        def actualizar_cant_carrito(index):
            nueva_c = st.session_state[f"v_cant_{index}"]
            st.session_state.carrito_ventas[index]["cantidad"] = int(nueva_c)
            st.session_state.carrito_ventas[index]["subtotal"] = float(
                nueva_c * st.session_state.carrito_ventas[index]["precio_unitario"]
            )

        for idx, item in enumerate(st.session_state.carrito_ventas):
            col_d1, col_d2, col_d3, col_d4 = st.columns([3, 1, 1, 1])
            col_d1.write(f"**{item['codigo']}** - {item['descripcion']}")
            col_d2.number_input(
                "Cant.",
                min_value=1,
                value=int(item["cantidad"]),
                key=f"v_cant_{idx}",
                on_change=actualizar_cant_carrito,
                args=(idx,),
            )
            col_d3.write(f"P.U: S/. {item['precio_unitario']:.2f}")
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

        st.button(
            f"🖨️ EMITIR {tipo_doc} Y 🔴 DESCONTAR STOCK",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.procesando_operacion,
            on_click=callback_emito_venta,
            args=(tipo_doc, serie_num, cliente_nom, cliente_doc, subtotal, igv, total_gen),
        )


# -------------------------------------------------------------------
# 2. NOTA DE CRÉDITO (AUMENTA STOCK)
# -------------------------------------------------------------------
elif menu == "🔄 Nota de Crédito (Devolución)":
    st.header("🔄 Emisión de Nota de Crédito (Devolución de Stock)")

    nc_c1, nc_c2 = st.columns(2)
    with nc_c1:
        num_comp_ref = st.text_input("Serie/Número de Comprobante de Origen", placeholder="Ej. B001-000005")
        motivo_nc = st.selectbox(
            "Motivo de Devolución",
            ["Anulación de la operación", "Devolución total", "Devolución parcial", "Error en el valor o descripción"],
        )

    with nc_c2:
        ult_ncs = ejecutar_consulta(
            "comprobantes",
            consulta_type="select",
            data="serie_numero",
            like_col="serie_numero",
            like_val="FC01-%",
        )
        sig_num_nc = 1
        if ult_ncs:
            nums_nc = [
                int(c["serie_numero"].split("-")[1])
                for c in ult_ncs
                if "-" in c.get("serie_numero", "") and c.get("serie_numero", "").split("-")[1].isdigit()
            ]
            if nums_nc:
                sig_num_nc = max(nums_nc) + 1

        serie_nc = st.text_input("Serie Nota de Crédito", value=f"FC01-{sig_num_nc:06d}")

    st.divider()
    st.subheader("📦 Ítems a Devolver a Inventario")

    # Selección de productos para la devolución
    prods_nc = ejecutar_consulta("productos", consulta_type="select", data="id, codigo, descripcion, precio, stock")
    if prods_nc:
        dict_nc = {f"{p['codigo']} | {p['descripcion']}": p for p in prods_nc}
        nc_p1, nc_p2, nc_p3 = st.columns([3, 1, 1])

        with nc_p1:
            p_sel_nc = st.selectbox("Seleccionar Producto devuelto", list(dict_nc.keys()), key="nc_prod_select")
        with nc_p2:
            cant_nc = st.number_input("Cantidad a Devolver", min_value=1, value=1, key="nc_cant_input")
        with nc_p3:
            st.write("")
            st.write("")
            if st.button("➕ Añadir a Devolución"):
                if "carrito_nc" not in st.session_state:
                    st.session_state.carrito_nc = []

                p_data = dict_nc[p_sel_nc]
                st.session_state.carrito_nc.append(
                    {
                        "id": p_data["id"],
                        "codigo": p_data["codigo"],
                        "descripcion": p_data["descripcion"],
                        "cantidad": int(cant_nc),
                        "precio_unitario": float(p_data["precio"]),
                        "subtotal": float(cant_nc * p_data["precio"]),
                    }
                )
                st.success("Añadido a lista de devolución")
                st.rerun()

    if "carrito_nc" in st.session_state and st.session_state.carrito_nc:
        st.write("---")
        for i_nc in st.session_state.carrito_nc:
            st.write(
                f"• **{i_nc['codigo']}** - {i_nc['descripcion']} | Cantidad: **{i_nc['cantidad']}** | Subtotal: S/. {i_nc['subtotal']:.2f}"
            )

        if st.button("🗑️ Limpiar Ítems de NC"):
            st.session_state.carrito_nc = []
            st.rerun()

        st.divider()

        cliente_nc_nom = st.text_input("Cliente", value="CLIENTE VARIOS", key="nc_cli_nom")
        cliente_nc_doc = st.text_input("DNI / RUC Cliente", value="00000000", key="nc_cli_doc")

        st.button(
            "🟢 EMITIR NOTA DE CRÉDITO Y AUMENTAR STOCK",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.procesando_operacion,
            on_click=callback_emitir_nota_credito,
            args=(
                serie_nc,
                num_comp_ref,
                cliente_nc_nom,
                cliente_nc_doc,
                motivo_nc,
                st.session_state.get("carrito_nc", []),
            ),
        )


# -------------------------------------------------------------------
# SECCIÓN GLOBAL: PREVISUALIZACIÓN Y DESCARGA DE PDF PERSISTENTE
# -------------------------------------------------------------------
if st.session_state.pdf_generado is not None and st.session_state.datos_ultimo_comprobante:
    st.divider()
    st.balloons()
    st.success(f"🎉 Operación finalizada exitosamente: {st.session_state.ultimo_pdf_nombre}")

    col_prev1, col_prev2 = st.columns([1, 1])

    with col_prev1:
        st.subheader("👁️ Previsualización del Comprobante")

        info = st.session_state.datos_ultimo_comprobante
        items_html = "".join(
            [
                f"<tr><td>{it['cantidad']}x {it['descripcion'][:15]}</td><td style='text-align:right;'>S/ {it['subtotal']:.2f}</td></tr>"
                for it in info["items"]
            ]
        )

        html_ticket = f"""
        <div style="background-color: #ffffff; color: #000000; padding: 15px; border-radius: 5px; border: 1px solid #ddd; font-family: monospace; width: 280px; margin: auto;">
            <h4 style="text-align: center; margin: 0;">MI EMPRESA S.A.C.</h4>
            <p style="text-align: center; margin: 2px; font-size: 11px;">RUC: 20123456789</p>
            <hr style="border-top: 1px dashed #000;">
            <p style="margin: 2px; font-size: 12px;"><b>{info['tipo']}</b></p>
            <p style="margin: 2px; font-size: 11px;">N°: {info['serie']}</p>
            <p style="margin: 2px; font-size: 11px;">Cliente: {info['cliente']}</p>
            <p style="margin: 2px; font-size: 11px;">Doc: {info['doc']}</p>
            <hr style="border-top: 1px dashed #000;">
            <table style="width: 100%; font-size: 11px;">
                {items_html}
            </table>
            <hr style="border-top: 1px dashed #000;">
            <p style="text-align: right; font-size: 13px; margin: 2px;"><b>TOTAL: S/ {info['total']:.2f}</b></p>
        </div>
        """
        st.markdown(html_ticket, unsafe_allow_html=True)

    with col_prev2:
        st.subheader("📥 DESCARGA DE COMPROBANTE")
        st.write("Haz clic en el siguiente botón para obtener el PDF generado:")

        st.download_button(
            label="📄 Descargar PDF Oficial",
            data=st.session_state.pdf_generado,
            file_name=st.session_state.ultimo_pdf_nombre,
            mime="application/pdf",
            type="primary",
            use_container_width=True,
            key="btn_download_pdf_persistente",
        )

        if st.button("❌ Cerrar Vista Previa", use_container_width=True):
            st.session_state.pdf_generado = None
            st.session_state.datos_ultimo_comprobante = None
            st.rerun()
