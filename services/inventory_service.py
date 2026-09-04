"""
Servicio de gestión de inventario, productos y compras (ingresos).
"""
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from core.database import ejecutar_consulta, ajustar_stock_rpc

def obtener_catalogo_productos() -> List[Dict[str, Any]]:
    """Obtiene la lista completa de productos ordenados por código."""
    prods = ejecutar_consulta("productos", consulta_type="select", order_col="codigo", desc=False)
    return prods if prods else []

def crear_producto(
    codigo: str,
    descripcion: str,
    marca: str = "",
    costo: float = 0.0,
    precio: float = 0.0,
    stock: int = 0,
    stock_minimo: int = 5,
    proveedor: str = "",
) -> Tuple[bool, str]:
    """Registra un nuevo producto en la base de datos."""
    codigo_clean = codigo.strip().upper()
    desc_clean = descripcion.strip()
    
    if not codigo_clean or not desc_clean:
        return False, "El código y la descripción son obligatorios."
    
    # Validar duplicados de código
    existente = ejecutar_consulta("productos", eq_col="codigo", eq_val=codigo_clean)
    if existente:
        return False, f"El código '{codigo_clean}' ya está registrado con otro producto."
    
    data = {
        "codigo": codigo_clean,
        "descripcion": desc_clean,
        "marca": marca.strip().upper() if marca else "",
        "costo": round(float(costo), 2),
        "precio": round(float(precio), 2),
        "stock": int(stock),
        "stock_minimo": int(stock_minimo),
        "proveedor": proveedor.strip() if proveedor else "",
    }
    
    res = ejecutar_consulta("productos", consulta_type="insert", data=data)
    if res and getattr(res, "data", None):
        return True, "Producto registrado exitosamente."
    return False, "Error al insertar el producto en la base de datos."

def verificar_disponibilidad_stock(producto_id: str, cantidad_requerida: int) -> Tuple[bool, int, str]:
    """
    Verifica si hay stock suficiente para un producto.
    Retorna (disponible: bool, stock_actual: int, mensaje: str).
    """
    res = ejecutar_consulta("productos", eq_col="id", eq_val=producto_id)
    if not res:
        return False, 0, "Producto no encontrado."
    
    prod = res[0]
    stock_actual = int(prod.get("stock") or 0)
    desc = prod.get("descripcion", "")
    
    if stock_actual <= 0:
        return False, stock_actual, f"El producto '{desc}' no cuenta con stock disponible (Stock: 0)."
    if cantidad_requerida > stock_actual:
        return False, stock_actual, f"Stock insuficiente para '{desc}'. Disponible: {stock_actual}, Solicitado: {cantidad_requerida}."
    
    return True, stock_actual, "Stock disponible."

def registrar_ingreso_compra(
    producto_id: str,
    cantidad: int,
    nuevo_costo: float,
    proveedor_id: Optional[str] = None,
    nro_factura: str = "",
) -> Tuple[bool, str]:
    """
    Registra el ingreso de mercadería por compra:
    - Actualiza el costo unitario del producto.
    - Incrementa el stock de forma atómica mediante RPC.
    """
    if cantidad <= 0:
        return False, "La cantidad a ingresar debe ser mayor a cero."
    
    # 1. Actualizar costo
    update_res = ejecutar_consulta(
        "productos",
        consulta_type="update",
        data={"costo": round(float(nuevo_costo), 2)},
        eq_col="id",
        eq_val=producto_id,
    )
    if not update_res:
        return False, "Error al actualizar el costo del producto."
    
    # 2. Ajustar stock mediante RPC atómico
    nuevo_stock = ajustar_stock_rpc(producto_id, int(cantidad))
    if nuevo_stock is None:
        return False, "Error al actualizar el stock en almacén."
    
    return True, f"Ingreso registrado correctamente. Nuevo stock disponible: {nuevo_stock} unidades."

def obtener_metricas_inventario() -> Dict[str, Any]:
    """Calcula métricas clave del inventario para el dashboard."""
    prods = obtener_catalogo_productos()
    if not prods:
        return {
            "total_items": 0,
            "total_unidades": 0,
            "valor_costo": 0.0,
            "valor_venta": 0.0,
            "items_quiebre": 0,
        }
    
    df = pd.DataFrame(prods)
    df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0)
    df["costo"] = pd.to_numeric(df["costo"], errors="coerce").fillna(0.0)
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0.0)
    df["stock_minimo"] = pd.to_numeric(df["stock_minimo"], errors="coerce").fillna(5)
    
    total_items = len(df)
    total_unidades = int(df["stock"].sum())
    valor_costo = float((df["stock"] * df["costo"]).sum())
    valor_venta = float((df["stock"] * df["precio"]).sum())
    items_quiebre = int((df["stock"] <= df["stock_minimo"]).sum())
    
    return {
        "total_items": total_items,
        "total_unidades": total_unidades,
        "valor_costo": valor_costo,
        "valor_venta": valor_venta,
        "items_quiebre": items_quiebre,
    }
