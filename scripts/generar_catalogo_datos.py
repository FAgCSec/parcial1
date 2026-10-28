import os
import sys
import json
import pymongo
from datetime import datetime
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_LAKE_DIR = os.path.join(BASE_DIR, "data_lake")
DOCS_DIR = os.path.join(BASE_DIR, "docs")
DB_NAME = "bd_erp"

def conectar_mongodb():
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command('ping')
        return client, client[DB_NAME]
    except Exception as e:
        print(f"Error de conexion: {e}")
        sys.exit(1)

def obtener_schema_mongodb(db):
    collections = db.list_collection_names()
    schema_data = {}

    for col_name in collections:
        try:
            col = db[col_name]
            count = col.estimated_document_count()
            sample = col.find().limit(1)

            campos = {}
            if count > 0:
                for doc in sample:
                    for key, value in doc.items():
                        if isinstance(value, dict):
                            sub_campos = {}
                            for sk, sv in value.items():
                                sub_campos[sk] = {
                                    "tipo": type(sv).__name__,
                                    "descripcion": obtener_descripcion_semantica(col_name, key, sk)
                                }
                            campos[key] = {
                                "tipo": "objecto anidado",
                                "campos": sub_campos,
                                "descripcion": obtener_descripcion_semantica(col_name, key)
                            }
                        elif isinstance(value, list) and len(value) > 0:
                            first_item = value[0]
                            if isinstance(first_item, dict):
                                sub_campos = {}
                                for sk, sv in first_item.items():
                                    sub_campos[sk] = {
                                        "tipo": type(sv).__name__,
                                        "descripcion": obtener_descripcion_semantica(col_name, key, sk)
                                    }
                                campos[key] = {
                                    "tipo": "arreglo de objetos",
                                    "campos": sub_campos,
                                    "descripcion": obtener_descripcion_semantica(col_name, key)
                                }
                            else:
                                campos[key] = {
                                    "tipo": f"arreglo de {type(first_item).__name__}",
                                    "descripcion": obtener_descripcion_semantica(col_name, key)
                                }
                        else:
                            campos[key] = {
                                "tipo": type(value).__name__,
                                "descripcion": obtener_descripcion_semantica(col_name, key)
                            }

            schema_data[col_name] = {
                "documentos": count,
                "campos": campos
            }
        except Exception as e:
            schema_data[col_name] = {"error": str(e)}

    return schema_data

def obtener_descripcion_semantica(collection_name, field_name, sub_field=None):
    descripciones = {
        "clientes": {
            "_id": "Identificador único del cliente generado por MongoDB",
            "phone": "Número de teléfono del cliente (formato colombiano 573XXXXXXXX)",
            "name": "Nombre completo del cliente",
            "city": "Ciudad de residencia del cliente",
            "department": "Departamento de residencia del cliente",
            "address": "Dirección física del cliente"
        },
        "productos": {
            "_id": "Identificador único del producto",
            "dropi_product_id": "Identificador único del producto en el sistema Dropi",
            "name": "Nombre del producto con marca HeavyCult",
            "category": "Categoría del producto (Calzado Táctico, Ropa Oversize, etc.)",
            "pricing": "Información de precios del producto",
            "variants": "Variantes del producto (tallas, colores, stock)",
            "variants.sku": "Stock Keeping Unit único de la variante",
            "variants.size": "Talla del producto",
            "variants.stock": "Cantidad disponible en inventario",
            "variants.is_active": "Indica si la variante está activa para venta",
            "is_active": "Indica si el producto está activo en el catálogo"
        },
        "ordenes": {
            "_id": "Identificador único de la orden",
            "order_number": "Número de orden único del sistema",
            "customer_id": "Referencia al cliente que realizó la compra",
            "dropi_order_id": "Identificador de orden en el sistema Dropi",
            "items": "Lista de productos incluidos en la orden",
            "total_amount": "Monto total de la orden en pesos colombianos",
            "shipping_cost": "Costo de envío fijo según ciudad del cliente",
            "order_profit": "Ganancia neta estimada de la orden",
            "payment_method": "Método de pago utilizado (Pago Contra Entrega, PSE, Nequi)",
            "status": "Estado actual de la orden (delivered, shipped, novelty, cancelled)",
            "created_at": "Fecha y hora de creación de la orden"
        },
        "ventas_analiticas": {
            "_id": "Identificador del documento analítico",
            "fecha_venta": "Fecha de la transacción de venta",
            "anio": "Año de la venta para análisis temporal",
            "mes": "Mes de la venta para agrupación mensual",
            "dia": "Día del mes para análisis diario",
            "order_number": "Referencia al número de orden original",
            "cliente": "Dimensión del cliente con datos demográficos",
            "producto": "Dimensión del producto con categoría y SKU",
            "cantidad": "Cantidad de unidades vendidas",
            "precio_unitario": "Precio unitario de venta del producto",
            "total_venta": "Monto total de la transacción",
            "costo_proveedor": "Costo total del proveedor por las unidades vendidas",
            "costo_flete": "Costo de envío asociado a la transacción",
            "ganancia_neta": "Ganancia neta estimada (15% margen)",
            "metodo_pago": "Método de pago utilizado",
            "estado": "Estado de la orden"
        },
        "dim_tiempo": {
            "_id": "Fecha como identificador",
            "fecha": "Fecha completa del registro",
            "anio": "Año",
            "mes": "Mes",
            "dia": "Día del mes",
            "trimestre": "Trimestre fiscal del año",
            "es_fin_semana": "Indica si la fecha cae en fin de semana"
        },
        "dim_cliente": {
            "cliente_id": "Identificador único del cliente",
            "nombre": "Nombre del cliente",
            "telefono": "Teléfono de contacto",
            "ciudad": "Ciudad de residencia",
            "departamento": "Departamento de residencia",
            "total_compras": "Número total de compras realizadas",
            "gasto_historico": "Monto total gastado históricamente",
            "ticket_promedio": "Monto promedio por compra"
        },
        "dim_producto": {
            "producto_id": "Identificador único del producto",
            "nombre_producto": "Nombre del producto",
            "categoria": "Categoría del producto",
            "sku": "Código SKU del producto",
            "unidades_vendidas": "Total de unidades vendidas",
            "ingresos_generados": "Ingresos totales generados por el producto"
        },
        "fact_ventas": {
            "_id": "Identificador de la transacción",
            "order_number": "Número de orden",
            "fecha_id": "Referencia a la dimensión de tiempo",
            "cliente_id": "Referencia a la dimensión de cliente",
            "producto_id": "Referencia a la dimensión de producto",
            "cantidad": "Cantidad de unidades",
            "precio_unitario": "Precio unitario",
            "total_venta": "Monto total de venta",
            "costo_proveedor": "Costo del proveedor",
            "costo_flete": "Costo de flete",
            "ganancia_neta": "Ganancia neta",
            "metodo_pago": "Método de pago",
            "estado": "Estado del pedido"
        }
    }

    if collection_name in descripciones:
        col_desc = descripciones[collection_name]
        if sub_field and sub_field in col_desc:
            return col_desc[sub_field]["descripcion"]
        if field_name in col_desc:
            return col_desc[field_name]

    if field_name == "_id":
        return "Identificador único generado por MongoDB"

    return f"Campo {field_name} en colección {collection_name}"

def obtener_info_archivos_data_lake():
    archivos_info = []
    for root, dirs, files in os.walk(DATA_LAKE_DIR):
        for f in files:
            if f.endswith(('.json', '.csv', '.parquet')) and not f.startswith('.'):
                filepath = os.path.join(root, f)
                size = os.path.getsize(filepath)
                relpath = os.path.relpath(filepath, DATA_LAKE_DIR)
                capas = relpath.split(os.sep)[0] if os.sep in relpath else relpath
                archivos_info.append({
                    "archivo": f,
                    "ruta": relpath,
                    "capa": capas,
                    "tamano_bytes": size,
                    "tamano_mb": round(size / (1024**2), 2),
                    "extension": os.path.splitext(f)[1].lower()
                })
    return archivos_info

def obtener_schema_archivos():
    import json
    archivos_schema = []
    for root, dirs, files in os.walk(DATA_LAKE_DIR):
        for f in files:
            if f.endswith('.json') and not f.startswith('.'):
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                        if isinstance(data, list) and len(data) > 0:
                            campos = {}
                            for key in data[0].keys():
                                val = data[0][key]
                                if isinstance(val, dict):
                                    campos[key] = "objecto"
                                elif isinstance(val, list):
                                    campos[key] = "arreglo"
                                else:
                                    campos[key] = type(val).__name__
                            archivos_schema.append({
                                "archivo": f,
                                "ruta": os.path.relpath(filepath, DATA_LAKE_DIR),
                                "registros": len(data),
                                "campos": campos
                            })
                except Exception:
                    pass
    return archivos_schema

def generar_markdown(schema_mongodb, archivos_info, archivos_schema):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_docs_mongo = sum(
        v.get("documentos", 0) for v in schema_mongodb.values()
        if isinstance(v, dict) and "documentos" in v
    )
    total_lake_bytes = sum(f["tamano_bytes"] for f in archivos_info)

    md = f"""# Diccionario de Datos — HeavyCult Dropshipping

## Información General

| Parámetro | Valor |
|-----------|-------|
| **Fecha de generación** | {timestamp} |
| **Base de datos** | `{DB_NAME}` |
| **Total documentos MongoDB** | {total_docs_mongo:,} |
| **Total archivos Data Lake** | {len(archivos_info)} |
| **Tamaño total Data Lake** | {total_lake_bytes/(1024**3):.4f} GB |
| **Capas Data Lake** | raw, processed, curated |

---

## 1. Colecciones MongoDB

"""

    for col_name, info in schema_mongodb.items():
        if "error" in info:
            md += f"### {col_name}\n- **Error:** {info['error']}\n\n"
            continue

        md += f"### `{col_name}`\n"
        md += f"- **Documentos:** {info['documentos']:,}\n"
        md += f"- **Campos:**\n"

        for field_name, field_info in info.get("campos", {}).items():
            if isinstance(field_info, dict) and "campos" in field_info:
                md += f"  - **{field_name}** (*{field_info['tipo']}*) — {field_info['descripcion']}\n"
                for sub_name, sub_info in field_info.get("campos", {}).items():
                    md += f"    - `{sub_name}` (*{sub_info['tipo']}*) — {sub_info['descripcion']}\n"
            else:
                md += f"  - **{field_name}** (*{field_info['tipo']}*) — {field_info['descripcion']}\n"

        md += "\n"

    md += "---\n\n## 2. Archivos del Data Lake\n\n"
    md += f"Total: {len(archivos_info)} archivos, {total_lake_bytes/(1024**3):.4f} GB\n\n"

    for capas in ["raw", "processed", "curated"]:
        archivos_capa = [f for f in archivos_info if f["capa"] == capas]
        if archivos_capa:
            md += f"### Capa: {capas.upper()}\n\n"
            for arch in archivos_capa:
                md += f"- **{arch['archivo']}** ({arch['extension']}) — {arch['tamano_mb']:.2f} MB, {arch['registros'] if 'registros' in arch else 'N/A'} registros\n"
            md += "\n"

    md += "---\n\n## 3. Schema de Archivos JSON (Data Lake)\n\n"
    for arch_info in archivos_schema:
        md += f"### {arch_info['archivo']}\n"
        md += f"- **Ruta:** `{arch_info['ruta']}`\n"
        md += f"- **Registros:** {arch_info['registros']:,}\n"
        md += f"- **Campos:** {len(arch_info['campos'])}\n"
        for campo, tipo in arch_info['campos'].items():
            md += f"  - `{campo}`: {tipo}\n"
        md += "\n"

    md += "---\n\n## 4. Índices MongoDB\n\n"
    md += "Los índices principales del proyecto son:\n\n"
    md += "| Colección | Índice | Tipo |\n"
    md += "|-----------|--------|------|\n"
    md += "| clientes | phone_1 | Único |\n"
    md += "| productos | dropi_product_id_1 | Único |\n"
    md += "| productos | variants.sku_1 | Normal |\n"
    md += "| ordenes | order_number_1 | Único |\n"
    md += "| ordenes | customer_id_1 | Normal |\n"
    md += "| ordenes | created_at_-1 | Normal |\n"
    md += "| ventas_analiticas | anio_1_mes_1 | Compuesto |\n"
    md += "| ventas_analiticas | producto.categoria_1_ganancia_neta_-1 | Compuesto |\n"
    md += "| ventas_analiticas | estado_1_cliente.ciudad_1 | Compuesto |\n"
    md += "| ventas_analiticas | cliente.id_1_total_venta_-1 | Compuesto |\n"
    md += "| ventas_analiticas | metodo_pago_1_total_venta_-1 | Compuesto |\n"
    md += "| ventas_analiticas | cliente.ciudad_1_costo_flete_-1 | Compuesto |\n\n"

    md += "---\n\n## 5. Relaciones Entre Entidades\n\n"
    md += """```
clientes ──┐
           ├──> ordenes ──> items ──> productos
           │
           └──> ventas_analiticas (modelo dimensional)
                          │
                          ├──> dim_tiempo
                          ├──> dim_cliente
                          ├──> dim_producto
                          └──> fact_ventas
```

---

*Diccionario de datos generado automáticamente por el script generar_catalogo_datos.py*
"""

    return md

def main():
    print("=" * 70)
    print("CATÁLOGO DE DATOS / DICCIONARIO DE DATOS")
    print("=" * 70)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    client, db = conectar_mongodb()
    print("\n[INFO] Escaneando colecciones MongoDB...")
    schema_mongodb = obtener_schema_mongodb(db)
    print(f"   Colecciones escaneadas: {len(schema_mongodb)}")

    print("\n[INFO] Escaneando Data Lake (archivos)...")
    archivos_info = obtener_info_archivos_data_lake()
    print(f"   Archivos encontrados: {len(archivos_info)}")

    print("\n[INFO] Analizando schema de archivos JSON...")
    archivos_schema = obtener_schema_archivos()
    print(f"   Archivos JSON analizados: {len(archivos_schema)}")

    print("\n[INFO] Generando diccionario de datos (Markdown)...")
    md_content = generar_markdown(schema_mongodb, archivos_info, archivos_schema)

    output_path = os.path.join(DOCS_DIR, "diccionario_datos.md")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f"\n[OK] Diccionario de datos generado: {output_path}")
    print(f"   Tamaño: {len(md_content):,} caracteres")
    print(f"   Colecciones: {len(schema_mongodb)}")
    print(f"   Archivos Data Lake: {len(archivos_info)}")
    print(f"   Documentos MongoDB: {sum(v.get('documentos', 0) for v in schema_mongodb.values() if isinstance(v, dict) and 'documentos' in v):,}")

    print("\n" + "=" * 70)
    print("RESUMEN EJECUTIVO - CATÁLOGO DE DATOS")
    print("=" * 70)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Archivo generado: docs/diccionario_datos.md")
    print(f"Total colecciones MongoDB: {len(schema_mongodb)}")
    print(f"Total archivos Data Lake: {len(archivos_info)}")
    print("=" * 70)

    client.close()

if __name__ == "__main__":
    main()
