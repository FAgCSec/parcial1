"""
Catalogo de Datos Automatizado y Diccionario de Datos — HeavyCult Dropshipping
==============================================================================
Conecta a MongoDB Atlas (bd_erp), inspecciona todas las colecciones,
aplana objetos JSON anidados, mapea indices, tipos de datos y metadatos,
y genera un libro Excel en la raiz del proyecto:

    Catalogo_Datos_VentasDB_[YYYYMMDD_HHMMSS].xlsx

Pestanas:
  1. "Resumen Arquitectonico": inventario por coleccion con rol
     (OLTP / OLAP / Data Warehouse) y volumen de datos.
  2. "Diccionario de Datos": tabla tecnica por campo aplanado con
     tipo estandarizado, PK/FK, indexacion y descripcion de negocio.

Uso:
    python scripts/generar_catalogo.py
"""
import os
import sys
from datetime import datetime, date
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = "bd_erp"
SAMPLE_SIZE = 500

# ---------------------------------------------------------------------------
# Clasificacion arquitectonica
# ---------------------------------------------------------------------------
ROL_COLECCIONES = {
    "clientes": "OLTP",
    "productos": "OLTP",
    "ordenes": "OLTP",
    "ventas_analiticas": "OLAP",
    "dim_tiempo": "Data Warehouse",
    "dim_cliente": "Data Warehouse",
    "dim_producto": "Data Warehouse",
    "fact_ventas": "Data Warehouse",
}

DESCRIPCION_ROL = {
    "OLTP": "Transaccional normalizada: operaciones de negocio en tiempo real (CRUD).",
    "OLAP": "Analitica dimensional desnormalizada: consultas agregadas y BI.",
    "Data Warehouse": "Modelo estrella: dimensiones + tabla de hechos para analitica historica.",
}

# (coleccion, campo_aplanado) -> "coleccion_destino.campo_destino"
FK_MAP = {
    ("ordenes", "customer_id"): "clientes._id",
    ("ordenes", "items.product_id"): "productos._id",
    ("ventas_analiticas", "order_number"): "ordenes.order_number",
    ("ventas_analiticas", "cliente.id"): "clientes._id",
    ("ventas_analiticas", "producto.id"): "productos._id",
    ("fact_ventas", "order_number"): "ordenes.order_number",
    ("fact_ventas", "cliente_id"): "dim_cliente.cliente_id",
    ("fact_ventas", "producto_id"): "dim_producto.producto_id",
    ("fact_ventas", "fecha_id"): "dim_tiempo._id",
    ("dim_cliente", "cliente_id"): "clientes._id",
    ("dim_producto", "producto_id"): "productos._id",
}

# Campos con indice unico de negocio -> se reportan como PK (clave candidata)
UNIQUE_BUSINESS_KEYS = {
    ("clientes", "phone"),
    ("productos", "dropi_product_id"),
    ("ordenes", "order_number"),
}

# ---------------------------------------------------------------------------
# Descripciones de negocio por campo aplanado
# ---------------------------------------------------------------------------
DESCRIPCIONES = {
    "clientes": {
        "_id": "Identificador unico del cliente (PK generada por MongoDB).",
        "phone": "Telefono del cliente en formato colombiano 573XXXXXXXX. Clave de negocio unica (PK candidata).",
        "name": "Nombre completo del cliente.",
        "city": "Ciudad de residencia del cliente (determina el flete).",
        "department": "Departamento de residencia del cliente.",
        "address": "Direccion fisica de entrega del cliente.",
        "created_at": "Fecha y hora de registro del cliente.",
    },
    "productos": {
        "_id": "Identificador unico del producto (PK).",
        "dropi_product_id": "ID del producto en el proveedor Dropi. Clave de negocio unica (PK candidata).",
        "name": "Nombre comercial del producto (marca HeavyCult).",
        "category": "Categoria del catalogo: Calzado Tactico, Ropa Oversize, Accesorios Tacticos, Maletas y Morrales.",
        "pricing": "Objeto con los precios del producto (costo proveedor y precio de venta).",
        "pricing.supplier_cost": "Costo unitario pagado al proveedor Dropi (COP).",
        "pricing.sale_price": "Precio unitario de venta al publico (COP).",
        "variants": "Arreglo de variantes comerciales del producto (talla/color/stock).",
        "variants.sku": "SKU de la variante (indexado para busqueda por inventario).",
        "variants.size": "Talla de la variante (S, M, L, XL o numerica).",
        "variants.color": "Color de la variante.",
        "variants.stock": "Unidades disponibles en inventario por variante.",
        "variants.is_active": "Indica si la variante esta activa para la venta.",
        "is_active": "Indica si el producto esta activo en el catalogo.",
    },
    "ordenes": {
        "_id": "Identificador unico de la orden (PK).",
        "order_number": "Numero de orden unico del sistema formato HC-2026-XXXXX (PK candidata).",
        "customer_id": "FK al cliente que realizo la compra (clientes._id).",
        "dropi_order_id": "ID de la orden en la plataforma logistica Dropi.",
        "items": "Arreglo de items (productos) incluidos en la orden.",
        "items.product_id": "FK al producto vendido (productos._id).",
        "items.product_name": "Nombre del producto al momento de la venta (desnormalizado).",
        "items.sku": "SKU de la variante vendida.",
        "items.quantity": "Cantidad de unidades del item (1-2).",
        "items.unit_price": "Precio unitario de venta aplicado (COP).",
        "items.supplier_cost": "Costo unitario del proveedor al momento de la venta (COP).",
        "total_amount": "Monto total cobrado al cliente (COP).",
        "_cost_total": "Costo total de mercancia pagado al proveedor (COP).",
        "shipping_cost": "Costo de flete segun ciudad del cliente (COP).",
        "order_profit": "Ganancia neta estimada: total - (costo + flete) (COP).",
        "payment_method": "Metodo de pago: Pago Contra Entrega, PSE, Nequi.",
        "status": "Estado logistico: delivered, shipped, novelty, cancelled.",
        "created_at": "Fecha y hora de creacion de la orden.",
    },
    "ventas_analiticas": {
        "_id": "Identificador del documento analitico (PK).",
        "fecha_venta": "Fecha de la transaccion (dimension tiempo).",
        "anio": "Anio de la venta para agregacion temporal.",
        "mes": "Mes de la venta (1-12) para agregacion mensual.",
        "dia": "Dia del mes para analisis diario.",
        "order_number": "FK al numero de orden origen (ordenes.order_number).",
        "cliente": "Dimension cliente embebida (datos demograficos).",
        "cliente.id": "FK al cliente (clientes._id).",
        "cliente.nombre": "Nombre del cliente.",
        "cliente.telefono": "Telefono del cliente.",
        "cliente.ciudad": "Ciudad del cliente (dimension geografica).",
        "cliente.departamento": "Departamento del cliente.",
        "producto": "Dimension producto embebida.",
        "producto.id": "FK al producto (productos._id).",
        "producto.nombre": "Nombre del producto vendido.",
        "producto.sku": "SKU de la variante vendida.",
        "producto.categoria": "Categoria del producto.",
        "cantidad": "Unidades vendidas en la linea.",
        "precio_unitario": "Precio unitario aplicado (COP).",
        "total_venta": "Monto total de la linea/venta (COP).",
        "costo_proveedor": "Costo del proveedor por las unidades (COP).",
        "costo_flete": "Costo de envio asociado (COP).",
        "ganancia_neta": "Ganancia neta estimada de la linea (COP).",
        "metodo_pago": "Metodo de pago utilizado.",
        "estado": "Estado de la orden.",
    },
    "dim_tiempo": {
        "_id": "Fecha como identificador de la dimension (PK).",
        "fecha": "Fecha completa del registro.",
        "anio": "Anio calendario.",
        "mes": "Mes calendario (1-12).",
        "dia": "Dia del mes.",
        "trimestre": "Trimestre fiscal (1-4).",
        "es_fin_semana": "True si la fecha cae en fin de semana.",
    },
    "dim_cliente": {
        "_id": "Identificador del registro de dimension (PK).",
        "cliente_id": "FK al cliente origen (clientes._id).",
        "nombre": "Nombre del cliente.",
        "telefono": "Telefono de contacto.",
        "ciudad": "Ciudad de residencia.",
        "departamento": "Departamento de residencia.",
        "total_compras": "Numero total de compras historicas.",
        "gasto_historico": "Monto total gastado historicamente (COP).",
        "ticket_promedio": "Monto promedio por compra (COP).",
    },
    "dim_producto": {
        "_id": "Identificador del registro de dimension (PK).",
        "producto_id": "FK al producto origen (productos._id).",
        "nombre_producto": "Nombre del producto.",
        "categoria": "Categoria del producto.",
        "sku": "SKU representativo del producto.",
        "unidades_vendidas": "Total historico de unidades vendidas.",
        "ingresos_generados": "Ingresos totales generados (COP).",
    },
    "fact_ventas": {
        "_id": "Identificador de la transaccion de hechos (PK).",
        "order_number": "FK al numero de orden (ordenes.order_number).",
        "fecha_id": "FK a la dimension tiempo (dim_tiempo._id).",
        "cliente_id": "FK a la dimension cliente (dim_cliente.cliente_id).",
        "producto_id": "FK a la dimension producto (dim_producto.producto_id).",
        "cantidad": "Unidades vendidas.",
        "precio_unitario": "Precio unitario (COP).",
        "total_venta": "Monto total de la venta (COP).",
        "costo_proveedor": "Costo del proveedor (COP).",
        "costo_flete": "Costo de flete (COP).",
        "ganancia_neta": "Ganancia neta (COP).",
        "metodo_pago": "Metodo de pago.",
        "estado": "Estado del pedido.",
    },
}


# ---------------------------------------------------------------------------
# Utilidades de inferencia
# ---------------------------------------------------------------------------
def tipo_estandarizado(valor):
    """Mapea un valor BSON/Python a un tipo de dato estandarizado."""
    import datetime as _dt
    from bson import ObjectId as _Oid

    if valor is None:
        return "Null"
    if isinstance(valor, bool):
        return "Boolean"
    if isinstance(valor, int):
        return "Integer"
    if isinstance(valor, float):
        return "Float"
    if isinstance(valor, str):
        return "String"
    if isinstance(valor, (_dt.datetime, _dt.date)):
        return "Timestamp"
    if isinstance(valor, _Oid):
        return "ObjectId"
    if isinstance(valor, list):
        return "Array"
    if isinstance(valor, dict):
        return "Object"
    return type(valor).__name__


def aplanar(doc, padre="", sep=".", resultado=None):
    """Aplana un documento: {'cliente': {'ciudad': 'X'}} -> {'cliente.ciudad': 'X'}.

    Los arreglos se registran como Array y, si contienen objetos, se aplanan
    las claves del primer elemento no nulo (p. ej. items.sku).
    """
    if resultado is None:
        resultado = {}
    if isinstance(doc, dict):
        for k, v in doc.items():
            clave = f"{padre}{sep}{k}" if padre else str(k)
            if isinstance(v, dict):
                resultado[clave] = v  # conserva el objeto padre
                aplanar(v, clave, sep, resultado)
            elif isinstance(v, list):
                resultado[clave] = v
                for elem in v:
                    if isinstance(elem, dict):
                        aplanar(elem, clave, sep, resultado)
                        break
            else:
                resultado[clave] = v
    return resultado


def es_objeto_intermedio(coleccion, campo, muestra_tipos):
    """True si el campo siempre es dict/list contenedor (tiene hijos aplanados)."""
    tipos = muestra_tipos.get(campo, set())
    if tipos <= {"Object", "Array"}:
        prefijo = campo + "."
        return any(c.startswith(prefijo) for c in muestra_tipos)
    return False


def clasificar_pk_fk(coleccion, campo):
    """Devuelve (marca, referencia): marca en {PK, FK, PK/FK, ''}."""
    es_pk = campo == "_id" or (coleccion, campo) in UNIQUE_BUSINESS_KEYS
    referencia = FK_MAP.get((coleccion, campo), "")
    # dropi_order_id es un identificador externo del proveedor logistico,
    # no una clave foranea hacia otra coleccion del modelo.
    NO_FK = {"dropi_order_id"}
    if campo in NO_FK or campo.split(".")[-1] in NO_FK:
        return ("PK" if es_pk else ""), ""
    if not referencia:
        # Heuristica generica de FK
        base = campo.split(".")[-1]
        if campo != "_id" and (base.endswith("_id") or base == "id" or base in ("customer_id", "cliente_id", "producto_id", "fecha_id")):
            es_fk = True
        elif campo in ("order_number", "dropi_order_id") and coleccion in ("ventas_analiticas", "fact_ventas"):
            es_fk = True
            referencia = "ordenes.order_number"
        else:
            es_fk = False
    else:
        es_fk = True
    if es_pk and (es_fk or campo in ("cliente_id", "producto_id")) and campo != "_id":
        # cliente_id/producto_id en dimensiones son PK logica y FK a la vez
        if campo != "_id" and es_fk:
            return "PK/FK", referencia
        return "PK", referencia
    if es_pk:
        return "PK", referencia
    if es_fk:
        return "FK", referencia
    return "", referencia


def descripcion_negocio(coleccion, campo):
    desc = DESCRIPCIONES.get(coleccion, {}).get(campo)
    if desc:
        return desc
    base = campo.split(".")[-1]
    for col_desc in DESCRIPCIONES.get(coleccion, {}).values():
        pass
    if campo == "_id":
        return "Identificador unico generado por MongoDB (PK)."
    return f"Campo '{campo}' de la coleccion '{coleccion}'."


def conectar():
    import pymongo

    if not MONGO_URI:
        print("[ERROR] MONGO_URI no definida en el archivo .env")
        sys.exit(1)
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    return client, client[DB_NAME]


def inspeccionar_coleccion(db, nombre):
    """Inspecciona una coleccion: volumen, muestra, esquema aplanado e indices."""
    col = db[nombre]
    total = col.estimated_document_count()
    try:
        exacto = col.count_documents({})
    except Exception:
        exacto = total

    # Indices reales
    try:
        raw_indexes = col.index_information()
    except Exception:
        raw_indexes = {}
    indice_detalle = []
    campos_indexados = defaultdict(list)  # campo -> [nombres de indice]
    unicos = set()
    for idx_name, spec in raw_indexes.items():
        keys = spec.get("key", [])
        unique = bool(spec.get("unique", False))
        key_str = ", ".join([f"{k}({d})" for k, d in keys])
        indice_detalle.append(f"{idx_name} [{key_str}]{' UNIQUE' if unique else ''}")
        for k, _ in keys:
            campos_indexados[k].append(idx_name)
            if unique:
                unicos.add(k)

    # Muestra para inferencia de esquema
    docs = list(col.find().limit(SAMPLE_SIZE))
    campos_tipos = defaultdict(set)      # campo -> {tipos estandarizados}
    campos_ejemplo = {}                  # campo -> valor ejemplo serializable
    campos_nulos = defaultdict(int)      # campo -> conteos de None/missing
    for doc in docs:
        plano = aplanar(doc)
        for campo in set(list(campos_tipos.keys()) + list(plano.keys())):
            if campo not in plano:
                campos_nulos[campo] += 1
        for campo, valor in plano.items():
            t = tipo_estandarizado(valor)
            campos_tipos[campo].add(t)
            if valor is None:
                campos_nulos[campo] += 1
            if campo not in campos_ejemplo and valor is not None and not isinstance(valor, (dict, list)):
                s = str(valor)
                campos_ejemplo[campo] = s[:80]

    # Tamano de almacenamiento (si el rol lo permite)
    storage_bytes = None
    avg_obj = None
    try:
        stats = db.command("collStats", nombre)
        storage_bytes = stats.get("size")
        avg_obj = stats.get("avgObjSize")
    except Exception:
        pass

    return {
        "nombre": nombre,
        "rol": ROL_COLECCIONES.get(nombre, "Otro"),
        "total": exacto,
        "indices": indice_detalle,
        "campos_indexados": dict(campos_indexados),
        "unicos": unicos,
        "campos_tipos": dict(campos_tipos),
        "campos_ejemplo": campos_ejemplo,
        "campos_nulos": dict(campos_nulos),
        "n_muestra": len(docs),
        "storage_bytes": storage_bytes,
        "avg_obj": avg_obj,
    }


def tipo_final(tipos):
    """Consolida el set de tipos observados en un tipo estandarizado unico."""
    reales = {t for t in tipos if t != "Null"}
    if not reales:
        return "Null"
    if len(reales) == 1:
        return next(iter(reales))
    # Mezclas numericas comunes
    if reales <= {"Integer", "Float"}:
        return "Float"
    return "Mixed (" + "/".join(sorted(reales)) + ")"


def construir_dataframes(inspecciones):
    import pandas as pd

    total_docs = sum(i["total"] for i in inspecciones) or 1

    # ---- Pestana 1: Resumen Arquitectonico ----
    filas_resumen = []
    for info in sorted(inspecciones, key=lambda x: x["nombre"]):
        n_campos = len(info["campos_tipos"])
        mb = round((info["storage_bytes"] or 0) / (1024 * 1024), 2) if info["storage_bytes"] else 0
        filas_resumen.append({
            "Coleccion": info["nombre"],
            "Rol": info["rol"],
            "Descripcion del Rol": DESCRIPCION_ROL.get(info["rol"], "Coleccion auxiliar del sistema."),
            "Volumen (documentos)": info["total"],
            "% del Total": round(info["total"] / total_docs * 100, 2),
            "Campos Detectados": n_campos,
            "N. Indices": len(info["indices"]),
            "Detalle de Indices": "; ".join(info["indices"]) if info["indices"] else "Solo _id_",
            "Tamano Aprox (MB)": mb,
        })
    df_resumen = pd.DataFrame(filas_resumen, columns=[
        "Coleccion", "Rol", "Descripcion del Rol", "Volumen (documentos)",
        "% del Total", "Campos Detectados", "N. Indices",
        "Detalle de Indices", "Tamano Aprox (MB)",
    ])

    # ---- Pestana 2: Diccionario de Datos ----
    filas_dic = []
    for info in sorted(inspecciones, key=lambda x: x["nombre"]):
        for campo in sorted(info["campos_tipos"].keys()):
            tipos = info["campos_tipos"][campo]
            t_final = tipo_final(tipos)
            marca, referencia = clasificar_pk_fk(info["nombre"], campo)
            idxs = info["campos_indexados"].get(campo, [])
            # Un campo objeto/array intermedio no se marca como indexado salvo indice exacto
            indexado = "Si (" + ", ".join(idxs) + ")" if idxs else "No"
            unico = "Si" if (campo in info["unicos"] or campo == "_id") else "No"
            ejemplo = info["campos_ejemplo"].get(campo, "")
            nulos = info["campos_nulos"].get(campo, 0)
            pct_nulos = round(nulos / max(info["n_muestra"], 1) * 100, 1) if info["n_muestra"] else 0
            filas_dic.append({
                "Coleccion": info["nombre"],
                "Rol": info["rol"],
                "Campo": campo,
                "Tipo Estandarizado": t_final,
                "Tipos Observados": "/".join(sorted(tipos)),
                "PK / FK": marca,
                "Referencia (FK)": referencia,
                "Indexado": indexado,
                "Unico": unico,
                "Ejemplo": ejemplo,
                "% Nulos (muestra)": pct_nulos,
                "Descripcion de Negocio": descripcion_negocio(info["nombre"], campo),
            })
    df_dic = pd.DataFrame(filas_dic, columns=[
        "Coleccion", "Rol", "Campo", "Tipo Estandarizado", "Tipos Observados",
        "PK / FK", "Referencia (FK)", "Indexado", "Unico", "Ejemplo",
        "% Nulos (muestra)", "Descripcion de Negocio",
    ])
    return df_resumen, df_dic


def estilizar_excel(ruta, df_resumen, df_dic):
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl import load_workbook

    wb = load_workbook(ruta)
    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    thin = Side(style="thin", color="B0B0B0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for ws in wb.worksheets:
        # Encabezado
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        # Anchos
        anchos = {
            "Resumen Arquitectonico": [22, 16, 55, 20, 12, 17, 12, 70, 18],
            "Diccionario de Datos": [20, 16, 28, 18, 20, 10, 28, 30, 10, 28, 15, 70],
        }
        for i, w in enumerate(anchos.get(ws.title, []), start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        # Bordes + zebra en el cuerpo
        fill_zebra = PatternFill("solid", fgColor="DDEBF7")
        for r in range(2, ws.max_row + 1):
            for c in range(1, ws.max_column + 1):
                cell = ws.cell(row=r, column=c)
                cell.border = border
                cell.alignment = Alignment(vertical="center", wrap_text=True, horizontal="left" if c > 1 else "center")
            if r % 2 == 0:
                for c in range(1, ws.max_column + 1):
                    ws.cell(row=r, column=c).fill = fill_zebra
    # Metadatos de proveniencia (no contaminan el rango de datos: van a
    # propiedades del libro, no a filas dentro de las tablas)
    wb.properties.creator = "Catalogo Automatizado HeavyCult (scripts/generar_catalogo.py)"
    wb.properties.created = datetime.now()
    wb.properties.description = (
        f"BD: {DB_NAME} | Muestra por coleccion: {SAMPLE_SIZE} docs | "
        f"Colecciones: {df_resumen.shape[0]} | Campos: {df_dic.shape[0]}"
    )

    wb.save(ruta)


def main():
    print("=" * 70)
    print("CATALOGO DE DATOS AUTOMATIZADO — HeavyCult Dropshipping")
    print("=" * 70)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        import pandas  # noqa: F401
        import openpyxl  # noqa: F401
    except ImportError as e:
        print(f"[ERROR] Falta dependencia: {e}. Ejecute: pip install -r requirements.txt")
        sys.exit(1)

    client, db = conectar()
    print(f"[OK] Conexion exitosa a MongoDB Atlas | BD: {DB_NAME}")

    colecciones = sorted(db.list_collection_names())
    print(f"[INFO] Colecciones detectadas ({len(colecciones)}): {', '.join(colecciones)}")

    inspecciones = []
    for nombre in colecciones:
        print(f"[SCAN] Inspeccionando '{nombre}' ...")
        info = inspeccionar_coleccion(db, nombre)
        print(f"       docs={info['total']:,} | campos={len(info['campos_tipos'])} | indices={len(info['indices'])}")
        inspecciones.append(info)

    import pandas as pd

    df_resumen, df_dic = construir_dataframes(inspecciones)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    salida = os.path.join(BASE_DIR, f"Catalogo_Datos_VentasDB_{timestamp}.xlsx")
    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        df_resumen.to_excel(writer, sheet_name="Resumen Arquitectonico", index=False)
        df_dic.to_excel(writer, sheet_name="Diccionario de Datos", index=False)
    estilizar_excel(salida, df_resumen, df_dic)

    size_kb = os.path.getsize(salida) / 1024
    print("\n" + "=" * 70)
    print("[OK] Catalogo generado exitosamente")
    print(f"     Archivo: {salida}")
    print(f"     Tamano: {size_kb:.1f} KB | Colecciones: {len(inspecciones)} | "
          f"Campos: {len(df_dic)} | Docs totales: {sum(i['total'] for i in inspecciones):,}")
    print("     Hojas: 'Resumen Arquitectonico', 'Diccionario de Datos'")
    print("=" * 70)

    client.close()


if __name__ == "__main__":
    main()
