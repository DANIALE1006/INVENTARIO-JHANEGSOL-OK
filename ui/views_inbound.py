"""
Vista de Registro de Ingresos de Mercadería (Compras / Abastecimiento).
Permite añadir múltiples productos a una lista antes de procesar la entrada masiva.
"""
import pandas as pd
import streamlit as st
from ui.components import render_header
from core.database import ejecutar_consulta
from services.inventory_service import registrar_ingreso_compra_lote


def render_views_inbound() -> None:
    render_header(
        "Ingresos de Mercadería (Compras y Entradas)",
        "Registro de nuevas existencias y actualización de costo unitario por compra a proveedores",
        "📥",
    )

    # 1. Inicializar el carrito/lote de compras en Session State
    if "inbound_cart" not in st.session_state:
        st.session_state.inbound_cart = []

    # 2. Cargar catalogos
    prods = ejecutar_consulta(
        "productos",
        consulta_type="select",
        data="id, codigo, descripcion, stock, costo",
        order_col="codigo",
    )
    provs = ejecutar_consulta(
        "proveedores",
        consulta_type="select",
        data="id, nombre",
        order_col="nombre",
    )

    if not prods:
        st.warning("⚠️ No hay productos registrados en el catálogo. Por favor registra productos primero en el Catálogo.")
        return

    dict_prods = {
        f"{p['codigo']} - {p['descripcion']} (Stock actual: {p.get('stock', 0)})": p
        for p in prods
    }

    dict_provs = {pr["nombre"]: pr["id"] for pr in provs} if provs else {}
    lista_provs = ["(Sin proveedor asignado)"] + list(dict_provs.keys())

    # 3. Cabecera del Documento (Proveedor y Factura/Guía)
    st.markdown("### 📄 Datos del Comprobante")
    col_prov, col_fact = st.columns(2)
    with col_prov:
        prov_sel = st.selectbox("Proveedor", lista_provs)
    with col_fact:
        nro_fact_compra = st.text_input("N° Factura / Guía de Compra", placeholder="Ej: F001-000452")

    st.markdown("---")

    # 4. Selector e Ingreso Individual al Carrito
    st.markdown("### ➕ Agregar Productos al Lote")
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])

    with c1:
        prod_sel = st.selectbox("Producto a Ingresar *", list(dict_prods.keys()))
        prod_info = dict_prods[prod_sel]

    with c2:
        cant_ingreso = st.number_input("Cantidad *", min_value=1, value=1, step=1)

    with c3:
        costo_def = float(prod_info["costo"]) if prod_info.get("costo") is not None else 0.0
        nuevo_costo = st.number_input("Costo Unitario (S/.) *", min_value=0.0, value=costo_def, format="%.2f", step=0.50)

    with c4:
        st.write("") # Espaciador para alinear con el input
        st.write("")
        if st.button("➕ Añadir", use_container_width=True, type="secondary"):
            # Verificar si el producto ya está en el lote para no duplicar filas
            p_id = prod_info["id"]
            existente = next((item for item in st.session_state.inbound_cart if item["producto_id"] == p_id), None)

            if existente:
                existente["cantidad"] += cant_ingreso
                existente["nuevo_costo"] = nuevo_costo
                existente["subtotal"] = round(existente["cantidad"] * nuevo_costo, 2)
            else:
                st.session_state.inbound_cart.append({
                    "producto_id": p_id,
                    "codigo": prod_info["codigo"],
                    "descripcion": prod_info["descripcion"],
                    "cantidad": cant_ingreso,
                    "nuevo_costo": nuevo_costo,
                    "subtotal": round(cant_ingreso * nuevo_costo, 2),
                })
            st.rerun()

    # 5. Visualización del Lote y Botón de Procesamiento
    if st.session_state.inbound_cart:
        st.markdown("### 📋 Detalle de la Compra a Procesar")
        df_cart = pd.DataFrame(st.session_state.inbound_cart)

        st.dataframe(
            df_cart[["codigo", "descripcion", "cantidad", "nuevo_costo", "subtotal"]],
            column_config={
                "codigo": "Código",
                "descripcion": "Descripción",
                "cantidad": "Cant.",
                "nuevo_costo": st.column_config.NumberColumn("Costo Unit. (S/.)", format="S/ %.2f"),
                "subtotal": st.column_config.NumberColumn("Subtotal (S/.)", format="S/ %.2f"),
            },
            hide_index=True,
            use_container_width=True,
        )

        col_tot, col_del, col_send = st.columns([2, 1, 1])

        with col_tot:
            total_lote = sum(item["subtotal"] for item in st.session_state.inbound_cart)
            st.metric("Total Inversión Lote", f"S/ {total_lote:.2f}")

        with col_del:
            if st.button("🗑️ Vaciar Lote", use_container_width=True):
                st.session_state.inbound_cart = []
                st.rerun()

        with col_send:
            if st.button("📥 Guardar e Ingresar Stock", type="primary", use_container_width=True):
                prov_id = dict_provs.get(prov_sel) if prov_sel in dict_provs else None

                ok, msg = registrar_ingreso_compra_lote(
                    items=st.session_state.inbound_cart,
                    proveedor_id=prov_id,
                    nro_factura=nro_fact_compra,
                )

                if ok:
                    st.success(f"✅ {msg}")
                    st.session_state.inbound_cart = []
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
    else:
        st.info("💡 El lote de compra está vacío. Selecciona un producto y presiona 'Añadir'.")
