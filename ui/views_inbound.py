"""
Vista de Registro de Ingresos de Mercadería (Compras / Abastecimiento).
"""
import streamlit as st
from ui.components import render_header
from core.database import ejecutar_consulta
from services.inventory_service import registrar_ingreso_compra

def render_views_inbound() -> None:
    render_header(
        "Ingresos de Mercadería (Compras y Entradas)",
        "Registro de nuevas existencias y actualización de costo unitario por compra a proveedores",
        "📥",
    )

    prods = ejecutar_consulta("productos", consulta_type="select", data="id, codigo, descripcion, stock, costo", order_col="codigo")
    provs = ejecutar_consulta("proveedores", consulta_type="select", data="id, nombre", order_col="nombre")

    if not prods:
        st.warning("⚠️ No hay productos registrados en el catálogo. Por favor registra productos primero en el Catálogo.")
        return

    dict_prods = {
        f"{p['codigo']} - {p['descripcion']} (Stock actual: {p.get('stock', 0)})": p
        for p in prods
    }
    
    dict_provs = {pr["nombre"]: pr["id"] for pr in provs} if provs else {}
    lista_provs = ["(Sin proveedor asignado)"] + list(dict_provs.keys())

    with st.form("form_ingresos_compra", clear_on_submit=True):
        st.markdown("### 📝 Formulario de Entrada de Mercadería")
        c1, c2, c3 = st.columns(3)
        with c1:
            prov_sel = st.selectbox("Proveedor", lista_provs)
            nro_fact_compra = st.text_input("N° Factura / Guía de Compra", placeholder="Ej: F001-000452")
        with c2:
            prod_sel = st.selectbox("Producto a Ingresar *", list(dict_prods.keys()))
            cant_ingreso = st.number_input("Cantidad que Ingresa *", min_value=1, value=1, step=1)
        with c3:
            prod_info = dict_prods[prod_sel]
            costo_def = float(prod_info["costo"]) if prod_info.get("costo") is not None else 0.0
            nuevo_costo = st.number_input("Costo Unitario de Compra (S/.) *", min_value=0.0, value=costo_def, format="%.2f", step=0.50)

        submit_btn = st.form_submit_button("📥 Registrar Ingreso y Aumentar Stock", type="primary", use_container_width=True)

        if submit_btn:
            p_id = prod_info["id"]
            prov_id = dict_provs.get(prov_sel) if prov_sel in dict_provs else None
            
            ok, msg = registrar_ingreso_compra(
                producto_id=p_id,
                cantidad=cant_ingreso,
                nuevo_costo=nuevo_costo,
                proveedor_id=prov_id,
                nro_factura=nro_fact_compra,
            )

            if ok:
                st.success(f"✅ {msg}")
                st.rerun()
            else:
                st.error(f"❌ {msg}")
