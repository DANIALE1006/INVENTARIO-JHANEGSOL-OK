"""
Vista de Registro de Ingresos de Mercadería (Compras / Abastecimiento) y Dashboard Estadístico.
"""
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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

    # Cargar datos solicitando SOLO columnas existentes en tu BD
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

    # Creación de Pestañas
    tab_operacion, tab_analytics = st.tabs(["📝 Registro de Ingresos", "📊 Dashboard & Analytics"])

    # ==========================================
    # PESTAÑA 1: REGISTRO DE INGRESOS (LOTE)
    # ==========================================
    with tab_operacion:
        if "inbound_cart" not in st.session_state:
            st.session_state.inbound_cart = []

        if not prods or not isinstance(prods, list):
            st.warning("⚠️ No hay productos registrados en el catálogo. Por favor registra productos primero.")
            return

        dict_prods = {
            f"{p['codigo']} - {p['descripcion']} (Stock actual: {p.get('stock', 0)})": p
            for p in prods
        }

        dict_provs = {pr["nombre"]: pr["id"] for pr in provs} if provs and isinstance(provs, list) else {}
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

        if not prods or not isinstance(prods, list):
            st.info("No hay datos de productos suficientes para mostrar el dashboard.")
            return

        # ------------------------------------------
        # FILTRO DE FECHAS (GLOBAL PARA DASHBOARD)
        # ------------------------------------------
        st.markdown("#### 📅 Filtro por Rango de Fechas")
        col_f1, col_f2 = st.columns(2)

        # Rango por defecto: últimos 6 meses a la fecha actual
        fecha_fin_default = datetime.now().date()
        fecha_inicio_default = fecha_fin_default - timedelta(days=180)

        with col_f1:
            fecha_inicio = st.date_input("Fecha Inicio", value=fecha_inicio_default)
        with col_f2:
            fecha_fin = st.date_input("Fecha Fin", value=fecha_fin_default)

        st.markdown("---")

        # Cargar movimientos de inventario con join a productos para traer el costo
        movs = ejecutar_consulta("movimientos_inventario", consulta_type="select")
        df_movs = pd.DataFrame()

        if movs and isinstance(movs, list):
            df_movs = pd.DataFrame(movs)
            if "fecha" in df_movs.columns:
                df_movs["fecha"] = pd.to_datetime(df_movs["fecha"])
                # Filtrar el dataframe de movimientos por el rango de fechas seleccionado
                mask = (df_movs["fecha"].dt.date >= fecha_inicio) & (df_movs["fecha"].dt.date <= fecha_fin)
                df_movs = df_movs.loc[mask]

        df_prods = pd.DataFrame(prods)
        df_prods["stock"] = pd.to_numeric(df_prods["stock"], errors="coerce").fillna(0)
        df_prods["costo"] = pd.to_numeric(df_prods["costo"], errors="coerce").fillna(0.0)
        df_prods["stock_minimo"] = 5
        df_prods["inversion_total"] = df_prods["stock"] * df_prods["costo"]

        # ------------------------------------------
        # 1. GRÁFICO COMPARATIVO EN MONTOS (INGRESOS VS SALIDAS S/.)
        # ------------------------------------------
        st.markdown("#### 💵 1. Ingresos vs. Salidas en Montos (S/.)")
        st.caption("Evolución del flujo financiero de inventario en el intervalo seleccionado.")

        if not df_movs.empty and "tipo" in df_movs.columns:
            # Unir con productos para obtener el costo de cada ítem
            df_movs_monto = df_movs.merge(
                df_prods[["id", "costo"]],
                left_on="producto_id",
                right_on="id",
                how="left",
            )
            df_movs_monto["costo"] = df_movs_monto["costo"].fillna(0.0)
            df_movs_monto["monto"] = df_movs_monto["cantidad"] * df_movs_monto["costo"]
            df_movs_monto["mes_año"] = df_movs_monto["fecha"].dt.strftime("%Y-%m")

            df_resumen_montos = (
                df_movs_monto.groupby(["mes_año", "tipo"])["monto"].sum().reset_index()
            )

            fig_montos = px.bar(
                df_resumen_montos,
                x="mes_año",
                y="monto",
                color="tipo",
                barmode="group",
                text_auto=".2f",
                labels={"mes_año": "Período", "monto": "Monto Total (S/.)", "tipo": "Tipo de Movimiento"},
                color_discrete_map={"INGRESO": "#2E7D32", "SALIDA": "#C62828"},
            )
            fig_montos.update_layout(xaxis_title="Mes", yaxis_title="Soles (S/.)")
            st.plotly_chart(fig_montos, use_container_width=True)
        else:
            st.info("💡 No hay registros de movimientos en el rango de fechas seleccionado.")

        st.markdown("---")

        col_c1, col_c2 = st.columns(2)

        # ------------------------------------------
        # 2. MAYOR INVERSIÓN EN STOCK
        # ------------------------------------------
        with col_c1:
            st.markdown("#### 💰 2. Mayor Inversión en Stock (Top Productos)")
            st.caption("Productos con mayor capital inmovilizado actualmente.")

            df_top_inversion = df_prods.sort_values(by="inversion_total", ascending=False).head(8)

            fig_top_inv = px.bar(
                df_top_inversion,
                x="inversion_total",
                y="descripcion",
                orientation="h",
                text_auto=".2f",
                labels={"inversion_total": "Inversión Total (S/.)", "descripcion": "Producto"},
                color="inversion_total",
                color_continuous_scale="Blues",
            )
            fig_top_inv.update_layout(
                yaxis={"categoryorder": "total ascending"},
                showlegend=False,
                xaxis_title="Soles (S/.)",
                yaxis_title="",
            )
            st.plotly_chart(fig_top_inv, use_container_width=True)

        # ------------------------------------------
        # 3. TENDENCIA DE UNIDADES MOVIDAS (UNIDADES)
        # ------------------------------------------
        with col_c2:
            st.markdown("#### 📈 3. Flujo Físico de Salidas (Unidades)")
            st.caption("Volumen de productos retirados en el período seleccionado.")

            if not df_movs.empty and "tipo" in df_movs.columns:
                df_salidas = df_movs[df_movs["tipo"] == "SALIDA"].copy()
                if not df_salidas.empty:
                    df_salidas["mes_año"] = df_salidas["fecha"].dt.strftime("%Y-%m")
                    df_trend = df_salidas.groupby("mes_año")["cantidad"].sum().reset_index()

                    fig_line = px.line(
                        df_trend,
                        x="mes_año",
                        y="cantidad",
                        markers=True,
                        labels={"mes_año": "Mes", "cantidad": "Unidades Salidas"},
                        color_discrete_sequence=["#1565C0"],
                    )
                    fig_line.update_traces(line_width=3, marker_size=8)
                    fig_line.update_layout(xaxis_title="Período", yaxis_title="Unidades")
                    st.plotly_chart(fig_line, use_container_width=True)
                else:
                    st.info("💡 No se registraron salidas en el intervalo de fechas seleccionado.")
            else:
                st.info("💡 No hay datos de movimientos para este rango.")

        st.markdown("---")

        # ------------------------------------------
        # 4. TABLA DE ALERTA CON FORMATO CONDICIONAL
        # ------------------------------------------
        st.markdown("#### 🚨 4. Alerta de Stock Crítico")
        st.caption("Se resaltan en rojo los productos con stock menor o igual al mínimo (5 unidades).")

        def resaltar_bajo_stock(row):
            if row["stock"] <= row["stock_minimo"]:
                return ["background-color: #ffcdd2; color: #b71c1c; font-weight: bold;"] * len(row)
            return [""] * len(row)

        df_alertas = df_prods[["codigo", "descripcion", "stock", "stock_minimo", "costo", "inversion_total"]]

        styler = df_alertas.style.apply(resaltar_bajo_stock, axis=1).format({
            "costo": "S/ {:.2f}",
            "inversion_total": "S/ {:.2f}",
        })

        st.dataframe(styler, use_container_width=True, hide_index=True)
