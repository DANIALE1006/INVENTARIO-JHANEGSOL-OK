"""
Vista de Registro de Ingresos de Mercadería (Compras / Abastecimiento) y Dashboard Estadístico.
"""
import pandas as pd
import plotly.express as px
import streamlit as st
from ui.components import render_header
from core.database import ejecutar_consulta
from services.inventory_service import registrar_ingreso_compra_lote


def render_views_inbound() -> None:
    render_header(
        "Ingresos de Mercadería (Compras y Entradas)",
        "Registro de nuevas existencias y análisis gráfico de inventario e inversión",
        "📥",
    )

    # Cargar catálogos iniciales
    prods = ejecutar_consulta(
        "productos",
        consulta_type="select",
        data="id, codigo, descripcion, stock, costo, categoria, stock_minimo",
        order_col="codigo",
    )
    provs = ejecutar_consulta(
        "proveedores",
        consulta_type="select",
        data="id, nombre",
        order_col="nombre",
    )

    # Creación de Pestañas
    tab_operacion, tab_analytics = st.tabs(["📝 Registro de Ingresos", "📊 Dashboard & Analytics"])

    # ==========================================
    # PESTAÑA 1: REGISTRO DE INGRESOS (LOTE)
    # ==========================================
    with tab_operacion:
        if "inbound_cart" not in st.session_state:
            st.session_state.inbound_cart = []

        if not prods:
            st.warning("⚠️ No hay productos registrados en el catálogo. Por favor registra productos primero.")
            return

        dict_prods = {
            f"{p['codigo']} - {p['descripcion']} (Stock actual: {p.get('stock', 0)})": p
            for p in prods
        }

        dict_provs = {pr["nombre"]: pr["id"] for pr in provs} if provs else {}
        lista_provs = ["(Sin proveedor asignado)"] + list(dict_provs.keys())

        st.markdown("### 📄 Datos del Comprobante")
        col_prov, col_fact = st.columns(2)
        with col_prov:
            prov_sel = st.selectbox("Proveedor", lista_provs)
        with col_fact:
            nro_fact_compra = st.text_input("N° Factura / Guía de Compra", placeholder="Ej: F001-000452")

        st.markdown("---")

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
            st.write("")
            st.write("")
            if st.button("➕ Añadir", use_container_width=True, type="secondary"):
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

    # ==========================================
    # PESTAÑA 2: DASHBOARD Y ANALÍTICA
    # ==========================================
    with tab_analytics:
        st.markdown("### 📈 Control Visual e Indicadores de Inventario")

        if not prods:
            st.info("No hay datos de productos suficientes para mostrar el dashboard.")
            return

        df_prods = pd.DataFrame(prods)
        df_prods["stock"] = pd.to_numeric(df_prods["stock"], errors="coerce").fillna(0)
        df_prods["costo"] = pd.to_numeric(df_prods["costo"], errors="coerce").fillna(0.0)
        df_prods["stock_minimo"] = pd.to_numeric(df_prods.get("stock_minimo", 5), errors="coerce").fillna(5)
        df_prods["categoria"] = df_prods.get("categoria", "General").fillna("General")
        df_prods["inversion_total"] = df_prods["stock"] * df_prods["costo"]

        # 1. GRÁFICO DE BARRAS (Stock Actual)
        st.markdown("#### 📊 1. Nivel de Stock Actual por Producto")
        st.caption("Visión general para detectar excesos o desabastecimiento inmediato.")
        
        fig_stock = px.bar(
            df_prods,
            x="descripcion",
            y="stock",
            color="stock",
            color_continuous_scale="Viridis",
            text_auto=True,
            labels={"descripcion": "Producto", "stock": "Stock Actual"},
        )
        fig_stock.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_stock, use_container_width=True)

        st.markdown("---")

        col_c1, col_c2 = st.columns(2)

        # 2. GRÁFICO CIRCULAR / ANILLO (Composición por Categorías)
        with col_c1:
            st.markdown("#### 🍩 2. Valor del Inventario por Categoria")
            st.caption("Porcentaje de inversión total según el grupo o categoría.")
            
            fig_pie = px.pie(
                df_prods,
                names="categoria",
                values="inversion_total",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3,
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_pie, use_container_width=True)

        # 3. GRÁFICO DE LÍNEAS (Tendencia de Movimientos / Salidas)
        with col_c2:
            st.markdown("#### 📈 3. Tendencia de Salidas / Flujo de Stock")
            st.caption("Comportamiento mensual para proyección de reabastecimiento.")
            
            movs = ejecutar_consulta("movimientos_inventario", consulta_type="select")
            if movs:
                df_movs = pd.DataFrame(movs)
                if "fecha" in df_movs.columns:
                    df_movs["fecha"] = pd.to_datetime(df_movs["fecha"])
                    df_trend = df_movs.groupby(df_movs["fecha"].dt.to_period("M"))["cantidad"].sum().reset_index()
                    df_trend["fecha"] = df_trend["fecha"].astype(str)

                    fig_line = px.line(
                        df_trend,
                        x="fecha",
                        y="cantidad",
                        markers=True,
                        labels={"fecha": "Mes", "cantidad": "Unidades Moviéndose"},
                    )
                    st.plotly_chart(fig_line, use_container_width=True)
                else:
                    st.info("💡 La tabla de movimientos no registra columna de fecha aún.")
            else:
                st.info("💡 Sin registros históricos en movimientos para trazar la tendencia.")

        st.markdown("---")

        # 4. TABLA DE ALERTA CON FORMATO CONDICIONAL
        st.markdown("#### 🚨 4. Alerta de Stock Crítico")
        st.caption("Se resaltan automáticamente en rojo las filas cuyo stock es menor o igual al mínimo permitido.")

        def resaltar_bajo_stock(row):
            if row["stock"] <= row["stock_minimo"]:
                return ["background-color: #ffcdd2; color: #b71c1c; font-weight: bold;"] * len(row)
            return [""] * len(row)

        df_alertas = df_prods[["codigo", "descripcion", "stock", "stock_minimo", "costo", "inversion_total"]]
        
        styler = df_alertas.style.apply(resaltar_bajo_stock, axis=1).format({
            "costo": "S/ {:.2f}",
            "inversion_total": "S/ {:.2f}"
        })

        st.dataframe(styler, use_container_width=True, hide_index=True)
