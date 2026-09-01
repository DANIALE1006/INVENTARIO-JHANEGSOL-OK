import io
from datetime import datetime

import pandas as pd
import streamlit as st

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from supabase import Client, create_client


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="Sistema Jhanegsol - Facturación e Inventarios",
    layout="wide",
    page_icon="📦",
)


# ============================================================
# CONEXIÓN A SUPABASE
# ============================================================

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


# ============================================================
# FUNCIONES DE BASE DE DATOS
# ============================================================

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

            if eq_col is not None and eq_val is not None:
                query = query.eq(eq_col, eq_val)

            if like_col is not None and like_val is not None:
                query = query.like(like_col, like_val)

            if order_col:
                query = query.order(order_col, desc=desc)

            if limit:
                query = query.limit(limit)

            return query.execute().data

        elif consulta_type == "insert":
            return query.insert(data).execute()

        elif consulta_type == "update":

            if eq_col is None or eq_val is None:
                raise ValueError("Para UPDATE se requiere eq_col y eq_val.")

            return (
                query
                .update(data)
                .eq(eq_col, eq_val)
                .execute()
            )

    except Exception as e:

        st.error(
            f"⚠️ Error en base de datos "
            f"(Tabla '{tabla}'): {e}"
        )

        return None


# ============================================================
# SESSION STATE
# ============================================================

if "carrito_ventas" not in st.session_state:
    st.session_state.carrito_ventas = []

if "carrito_nc" not in st.session_state:
    st.session_state.carrito_nc = []

if "pdf_generado" not in st.session_state:
    st.session_state.pdf_generado = None

if "num_ultimo_comp" not in st.session_state:
    st.session_state.num_ultimo_comp = ""

if "procesando_operacion" not in st.session_state:
    st.session_state.procesando_operacion = False


# ============================================================
# CONTROL CENTRALIZADO DE STOCK
# ============================================================

def modificar_stock(producto_id, cantidad):
    """
    Modifica el stock de un producto.

    cantidad positiva  -> aumenta stock
    cantidad negativa  -> disminuye stock
    """

    try:

        producto = (
            supabase
            .table("productos")
            .select("id, stock, descripcion")
            .eq("id", producto_id)
            .single()
            .execute()
        )

        if not producto.data:
            st.error("❌ No se encontró el producto.")
            return False

        stock_actual = int(producto.data.get("stock") or 0)

        nuevo_stock = stock_actual + int(cantidad)

        if nuevo_stock < 0:

            st.error(
                f"❌ Stock insuficiente para "
                f"{producto.data.get('descripcion', 'producto')}."
            )

            return False

        resultado = (
            supabase
            .table("productos")
            .update({"stock": nuevo_stock})
            .eq("id", producto_id)
            .execute()
        )

        if not resultado.data:
            st.error("❌ No se pudo actualizar el stock.")
            return False

        return True

    except Exception as e:

        st.error(
            f"❌ Error modificando stock: {e}"
        )

        return False


# ============================================================
# GENERADOR PDF
# ============================================================

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
        "Derecha",
        parent=styles["Normal"],
        alignment=2,
    )

    bold_derecha = ParagraphStyle(
        "BoldDerecha",
        parent=styles["Normal"],
        alignment=2,
        fontName="Helvetica-Bold",
    )

    story.append(
        Paragraph(
            "JHANEGSOL S.A.C.",
            titulo_style
        )
    )

    story.append(
        Paragraph(
            "RUC: 20600000001",
            subtitulo_style
        )
    )

    story.append(
        Paragraph(
            "Oficina Principal - Huacho, Lima - Perú",
            subtitulo_style
        )
    )

    story.append(Spacer(1, 15))

    story.append(
        Paragraph(
            f"<b>{tipo_doc}</b>",
            comprobante_style
        )
    )

    story.append(
        Paragraph(
            f"<b>N° {serie_num}</b>",
            comprobante_style
        )
    )

    story.append(Spacer(1, 10))

    datos_cliente = [
        [
            Paragraph(
                f"<b>Cliente:</b> {cliente_nom}",
                normal_style
            )
        ],
        [
            Paragraph(
                f"<b>DNI / RUC:</b> {cliente_doc}",
                normal_style
            )
        ],
        [
            Paragraph(
                f"<b>Fecha de Emisión:</b> "
                f"{datetime.now().strftime('%d/%m/%Y %H:%M')}",
                normal_style
            )
        ],
    ]

    if doc_referencia:
        datos_cliente.append(
            [
                Paragraph(
                    f"<b>Comprobante Afectado:</b> "
                    f"{doc_referencia}",
                    normal_style
                )
            ]
        )

    if motivo:
        datos_cliente.append(
            [
                Paragraph(
                    f"<b>Motivo / Concepto:</b> "
                    f"{motivo}",
                    normal_style
                )
            ]
        )

    story.append(
        Table(
            datos_cliente,
            colWidths=[500]
        )
    )

    story.append(Spacer(1, 15))

    data_tabla = [
        [
            Paragraph("<b>Cant.</b>", normal_style),
            Paragraph("<b>Descripción</b>", normal_style),
            Paragraph(
                "<b>P. Unit (S/.)</b>",
                derecha_style
            ),
            Paragraph(
                "<b>Subtotal (S/.)</b>",
                derecha_style
            ),
        ]
    ]

    for item in items:

        desc = (
            item.get("descripcion")
            or item.get("productos", {}).get(
                "descripcion",
                "Producto"
            )
        )

        cant = int(item.get("cantidad", 0))

        pu = float(
            item.get(
                "precio_unitario",
                item.get("precio", 0.0)
            )
        )

        sub = cant * pu

        data_tabla.append(
            [
                Paragraph(
                    str(cant),
                    normal_style
                ),
                Paragraph(
                    desc,
                    normal_style
                ),
                Paragraph(
                    f"{pu:.2f}",
                    derecha_style
                ),
                Paragraph(
                    f"{sub:.2f}",
                    derecha_style
                ),
            ]
        )

    tabla_prod = Table(
        data_tabla,
        colWidths=[50, 270, 90, 90]
    )

    tabla_prod.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#f0f2f5"),
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "LINEBELOW",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#CCCCCC"),
                ),
                (
                    "LINEABOVE",
                    (0, 0),
                    (-1, 0),
                    1,
                    colors.black,
                ),
                (
                    "LINEBELOW",
                    (0, 0),
                    (-1, 0),
                    1,
                    colors.black,
                ),
            ]
        )
    )

    story.append(tabla_prod)
    story.append(Spacer(1, 15))

    data_totales = [
        [
            Paragraph(
                "Op. Gravada:",
                derecha_style
            ),
            Paragraph(
                f"S/. {subtotal:.2f}",
                derecha_style
            ),
        ],
        [
            Paragraph(
                "IGV (18%):",
                derecha_style
            ),
            Paragraph(
                f"S/. {igv:.2f}",
                derecha_style
            ),
        ],
        [
            Paragraph(
                "<b>TOTAL:</b>",
                bold_derecha
            ),
            Paragraph(
                f"<b>S/. {total_gen:.2f}</b>",
                bold_derecha
            ),
        ],
    ]

    tabla_totales = Table(
        data_totales,
        colWidths=[400, 100]
    )

    tabla_totales.setStyle(
        TableStyle(
            [
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    story.append(tabla_totales)
    story.append(Spacer(1, 20))

    story.append(
        Paragraph(
            "¡Gracias por su preferencia en JHANEGSOL S.A.C.!",
            subtitulo_style
        )
    )

    doc.build(story)

    buffer.seek(0)

    return buffer


# ============================================================
# EMISIÓN DE VENTA
# ============================================================

def callback_emito_venta(
    tipo_doc,
    serie_num,
    cliente_nom,
    cliente_doc,
    subtotal,
    igv,
    total_gen,
):

    if st.session_state.procesando_operacion:
        return

    if not st.session_state.carrito_ventas:
        return

    st.session_state.procesando_operacion = True

    try:

        # ----------------------------------------------------
        # 1. VALIDAR STOCK ANTES DE CREAR DOCUMENTO
        # ----------------------------------------------------

        for item in st.session_state.carrito_ventas:

            producto = (
                supabase
                .table("productos")
                .select("id, stock, descripcion")
                .eq("id", item["id"])
                .single()
                .execute()
            )

            if not producto.data:
                st.error(
                    f"❌ Producto no encontrado: "
                    f"{item['descripcion']}"
                )
                return

            stock_actual = int(
                producto.data.get("stock") or 0
            )

            cantidad = int(item["cantidad"])

            if cantidad > stock_actual:

                st.error(
                    f"❌ Stock insuficiente para "
                    f"{item['descripcion']}. "
                    f"Disponible: {stock_actual}. "
                    f"Solicitado: {cantidad}."
                )

                return

        # ----------------------------------------------------
        # 2. VERIFICAR QUE EL COMPROBANTE NO EXISTA
        # ----------------------------------------------------

        existente = (
            supabase
            .table("comprobantes")
            .select("id")
            .eq("serie_numero", serie_num)
            .execute()
        )

        if existente.data:

            st.error(
                f"❌ El comprobante {serie_num} "
                f"ya existe."
            )

            return

        # ----------------------------------------------------
        # 3. CREAR CABECERA
        # ----------------------------------------------------

        comp_data = {
            "tipo_comprobante": tipo_doc,
            "serie_numero": serie_num,
            "cliente_nombre": cliente_nom,
            "cliente_documento": cliente_doc,
            "subtotal": round(subtotal, 2),
            "igv": round(igv, 2),
            "total": round(total_gen, 2),
        }

        res = ejecutar_consulta(
            "comprobantes",
            "insert",
            comp_data
        )

        if not res or not res.data:

            st.error(
                "❌ No se pudo crear el comprobante."
            )

            return

        comp_id = res.data[0]["id"]

        # ----------------------------------------------------
        # 4. INSERTAR DETALLES Y DESCONTAR STOCK
        # ----------------------------------------------------

        for item in st.session_state.carrito_ventas:

            cantidad = int(item["cantidad"])

            det = {
                "comprobante_id": comp_id,
                "producto_id": item["id"],
                "cantidad": cantidad,
                "precio_unitario": float(
                    item["precio_unitario"]
                ),
            }

            detalle = ejecutar_consulta(
                "detalle_comprobante",
                "insert",
                det
            )

            if not detalle:

                st.error(
                    "❌ Error registrando detalle."
                )

                return

            # ÚNICO LUGAR DONDE LA VENTA DESCUENTA STOCK
            stock_ok = modificar_stock(
                item["id"],
                -cantidad
            )

            if not stock_ok:

                st.error(
                    f"❌ No se pudo descontar stock "
                    f"de {item['descripcion']}."
                )

                return

        # ----------------------------------------------------
        # 5. GENERAR PDF
        # ----------------------------------------------------

        st.session_state.pdf_generado = (
            generar_pdf_comprobante(
                tipo_doc,
                serie_num,
                cliente_nom,
                cliente_doc,
                st.session_state.carrito_ventas,
                subtotal,
                igv,
                total_gen,
            )
        )

        st.session_state.num_ultimo_comp = serie_num

        st.session_state.carrito_ventas = []

        st.success(
            f"✅ {tipo_doc} {serie_num} emitido correctamente."
        )

    except Exception as e:

        st.error(
            f"❌ Error durante la emisión: {e}"
        )

    finally:

        st.session_state.procesando_operacion = False


# ============================================================
# EMISIÓN DE NOTA DE CRÉDITO / DÉBITO
# ============================================================

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

    if st.session_state.procesando_operacion:
        return

    if not st.session_state.carrito_nc:
        return

    st.session_state.procesando_operacion = True

    try:

        # ----------------------------------------------------
        # 1. VERIFICAR QUE LA NOTA NO EXISTA
        # ----------------------------------------------------

        existente = (
            supabase
            .table("comprobantes")
            .select("id")
            .eq("serie_numero", serie_nota)
            .execute()
        )

        if existente.data:

            st.error(
                f"❌ La nota {serie_nota} ya existe."
            )

            return

        # ----------------------------------------------------
        # 2. VALIDAR CANTIDADES PARA NOTA DE CRÉDITO
        # ----------------------------------------------------

        if tipo_nota == "NOTA DE CRÉDITO":

            detalles_origen = (
                supabase
                .table("detalle_comprobante")
                .select(
                    "producto_id, cantidad"
                )
                .eq(
                    "comprobante_id",
                    obtener_id_comprobante(doc_ref)
                )
                .execute()
                .data
            )

            if not detalles_origen:

                st.error(
                    "❌ No se encontraron detalles "
                    "del comprobante original."
                )

                return

            for item in st.session_state.carrito_nc:

                producto_id = item["id"]
                cantidad_devolver = int(
                    item["cantidad"]
                )

                cantidad_original = sum(
                    int(d["cantidad"])
                    for d in detalles_origen
                    if d["producto_id"] == producto_id
                )

                if cantidad_devolver > cantidad_original:

                    st.error(
                        f"❌ No puedes devolver "
                        f"{cantidad_devolver} unidades de "
                        f"{item['descripcion']}. "
                        f"La venta original contiene "
                        f"{cantidad_original}."
                    )

                    return

        # ----------------------------------------------------
        # 3. CREAR CABECERA
        # ----------------------------------------------------

        comp_data = {
            "tipo_comprobante": tipo_nota,
            "serie_numero": serie_nota,
            "cliente_nombre": cliente_nom,
            "cliente_documento": cliente_doc,
            "subtotal": round(subtotal, 2),
            "igv": round(igv, 2),
            "total": round(total_gen, 2),
        }

        res = ejecutar_consulta(
            "comprobantes",
            "insert",
            comp_data
        )

        if not res or not res.data:

            st.error(
                "❌ No se pudo crear la nota."
            )

            return

        comp_id = res.data[0]["id"]

        # ----------------------------------------------------
        # 4. PROCESAR PRODUCTOS
        # ----------------------------------------------------

        for item in st.session_state.carrito_nc:

            cantidad = int(item["cantidad"])

            det = {
                "comprobante_id": comp_id,
                "producto_id": item["id"],
                "cantidad": cantidad,
                "precio_unitario": float(
                    item["precio_unitario"]
                ),
            }

            detalle = ejecutar_consulta(
                "detalle_comprobante",
                "insert",
                det
            )

            if not detalle:

                st.error(
                    "❌ Error registrando detalle "
                    "de la nota."
                )

                return

            # ------------------------------------------------
            # NOTA DE CRÉDITO
            # DEVUELVE PRODUCTO AL INVENTARIO
            # ------------------------------------------------

            if tipo_nota == "NOTA DE CRÉDITO":

                stock_ok = modificar_stock(
                    item["id"],
                    +cantidad
                )

                if not stock_ok:

                    st.error(
                        f"❌ No se pudo devolver stock "
                        f"de {item['descripcion']}."
                    )

                    return

                # --------------------------------------------
                # REGISTRAR DEVOLUCIÓN
                # --------------------------------------------

                reg_dev = {
                    "numero_boleta":
                        f"{serie_nota} "
                        f"(Afecta: {doc_ref})",

                    "producto_id":
                        item["id"],

                    "cantidad":
                        cantidad,

                    "precio":
                        float(item["precio_unitario"]),

                    "motivo_devolucion":
                        f"[{cat_motivo}] {motivo_nota}",
                }

                ejecutar_consulta(
                    "devoluciones",
                    "insert",
                    reg_dev
                )

            # ------------------------------------------------
            # NOTA DE DÉBITO
            # NO MODIFICA STOCK
            # ------------------------------------------------

            elif tipo_nota == "NOTA DE DÉBITO":

                pass

        # ----------------------------------------------------
        # 5. GENERAR PDF
        # ----------------------------------------------------

        st.session_state.pdf_generado = (
            generar_pdf_comprobante(
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
        )

        st.session_state.num_ultimo_comp = serie_nota

        st.session_state.carrito_nc = []

        st.success(
            f"✅ {tipo_nota} {serie_nota} "
            f"procesada correctamente."
        )

    except Exception as e:

        st.error(
            f"❌ Error procesando la nota: {e}"
        )

    finally:

        st.session_state.procesando_operacion = False


# ============================================================
# OBTENER ID DE COMPROBANTE
# ============================================================

def obtener_id_comprobante(serie_numero):

    resultado = (
        supabase
        .table("comprobantes")
        .select("id")
        .eq("serie_numero", serie_numero)
        .single()
        .execute()
    )

    if resultado.data:
        return resultado.data["id"]

    return None
