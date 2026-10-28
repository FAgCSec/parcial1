import os
import json
import random
import boto3
from faker import Faker
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

fake = Faker('es_CO')

NUM_CLIENTES = 5000
NUM_PRODUCTOS = 500
NUM_VENTAS = 30000
BATCH_SIZE = 1000

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PATH = os.path.join(BASE_DIR, "data_lake", "raw")
PROCESSED_PATH = os.path.join(BASE_DIR, "data_lake", "processed")
CURATED_PATH = os.path.join(BASE_DIR, "data_lake", "curated")

# --- CONFIGURACION AWS S3 ---
BUCKET = os.getenv("S3_BUCKET", "abp-data-lake-fabian")
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=REGION,
)

def preparar_bucket():
    """Verifica que el bucket exista y crea las 'carpetas' (prefijos) si no existen."""
    try:
        s3.head_bucket(Bucket=BUCKET)
        print(f"[S3] Bucket '{BUCKET}' ya existe\n")
    except Exception:
        try:
            s3.create_bucket(Bucket=BUCKET)
            print(f"[S3] Bucket '{BUCKET}' creado en {REGION}\n")
        except Exception as e:
            print(f"[S3] Error creando bucket: {e}\n")
            raise

    for zona in ["raw", "processed", "curated"]:
        s3.put_object(Bucket=BUCKET, Key=f"{zona}/")
    print(f"[S3] Carpetas raw/, processed/, curated/ listas\n")

CIUDADES_COLOMBIA = [
    {"ciudad": "Bogotá", "depto": "Cundinamarca", "flete": 14000},
    {"ciudad": "Medellín", "depto": "Antioquia", "flete": 15000},
    {"ciudad": "Cali", "depto": "Valle del Cauca", "flete": 16000},
    {"ciudad": "Barranquilla", "depto": "Atlántico", "flete": 18000},
    {"ciudad": "Bucaramanga", "depto": "Santander", "flete": 15000},
    {"ciudad": "Pasto", "depto": "Nariño", "flete": 19000}
]

CATEGORIAS = ["Calzado Táctico", "Ropa Oversize", "Accesorios Tácticos", "Maletas y Morrales"]

def subir_a_s3(ruta_local, zona):
    """Sube un archivo local a s3://BUCKET/zona/nombre_archivo"""
    nombre = os.path.basename(ruta_local)
    clave = f"{zona}/{nombre}"
    try:
        s3.upload_file(ruta_local, BUCKET, clave)
        print(f"   [S3] -> s3://{BUCKET}/{clave}")
    except Exception as e:
        print(f"   [S3 ERROR] subiendo {clave}: {e}")

def escribir_json(ruta, datos, zona):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, default=str)
    subir_a_s3(ruta, zona)
    return datos

def generar_raw():
    print("[1/3] GENERANDO RAW DATA\n")
    inicio = time.time()

    os.makedirs(RAW_PATH, exist_ok=True)

    print("CLIENTES...")
    clientes = []
    for _ in range(NUM_CLIENTES):
        ubicacion = random.choice(CIUDADES_COLOMBIA)
        clientes.append({
            "phone": f"573{random.randint(10000000, 99999999)}",
            "name": fake.name(),
            "city": ubicacion["ciudad"],
            "department": ubicacion["depto"],
            "address": fake.street_address(),
            "created_at": str(fake.date_time_between(start_date='-1y', end_date='now'))
        })
    escribir_json(os.path.join(RAW_PATH, "clientes.json"), clientes, "raw")
    print(f"   -> {len(clientes)} clientes\n")

    print("PRODUCTOS...")
    productos = []
    for i in range(NUM_PRODUCTOS):
        costo_prov = round(random.uniform(30000, 90000), 2)
        precio_venta = round(costo_prov + random.uniform(40000, 80000), 2)
        productos.append({
            "dropi_product_id": f"DROPI_{random.randint(10000, 99999)}",
            "name": f"{random.choice(['Botas', 'Camiseta', 'Chaquetón', 'Morral'])} {fake.word().capitalize()} HeavyCult",
            "category": random.choice(CATEGORIAS),
            "pricing": {"supplier_cost": costo_prov, "sale_price": precio_venta},
            "variants": [
                {"sku": f"SKU-{i}-{tam}", "size": str(tam), "stock": random.randint(10, 100), "is_active": True}
                for tam in ["S", "M", "L", "XL"]
            ],
            "is_active": True
        })
    escribir_json(os.path.join(RAW_PATH, "productos.json"), productos, "raw")
    print(f"   -> {len(productos)} productos\n")

    print("ORDENES...")
    estados_dropshipping = ["delivered", "delivered", "delivered", "shipped", "novelty", "cancelled"]
    metodos_pago = ["Pago Contra Entrega", "Pago Contra Entrega", "PSE", "Nequi"]
    ordenes = []
    for idx in range(NUM_VENTAS):
        cliente = random.choice(clientes)
        producto = random.choice(productos)
        variante = random.choice(producto["variants"])
        cantidad = random.randint(1, 2)
        costo_productos = producto["pricing"]["supplier_cost"] * cantidad
        precio_productos = producto["pricing"]["sale_price"] * cantidad
        flete = next((item["flete"] for item in CIUDADES_COLOMBIA if item["ciudad"] == cliente["city"]), 15000)
        total_orden = precio_productos
        ganancia_neta = total_orden - (costo_productos + flete)
        ordenes.append({
            "order_number": f"HC-2026-{idx+10000}",
            "customer_id": cliente["phone"],
            "dropi_order_id": f"DP-{random.randint(100000, 999999)}",
            "items": [{
                "product_id": producto["dropi_product_id"],
                "product_name": producto["name"],
                "sku": variante["sku"],
                "quantity": cantidad,
                "unit_price": producto["pricing"]["sale_price"],
                "supplier_cost": producto["pricing"]["supplier_cost"]
            }],
            "total_amount": round(total_orden, 2),
            "_cost_total": round(costo_productos, 2),
            "shipping_cost": float(flete),
            "order_profit": round(ganancia_neta, 2),
            "payment_method": random.choice(metodos_pago),
            "status": random.choice(estados_dropshipping),
            "created_at": str(fake.date_time_between(start_date='-1y', end_date='now'))
        })
    escribir_json(os.path.join(RAW_PATH, "ordenes.json"), ordenes, "raw")
    print(f"   -> {len(ordenes)} ordenes\n")
    print(f"   [OK] RAW listo en {time.time()-inicio:.2f}s\n")
    return clientes, productos, ordenes

def generar_processed(clientes, productos, ordenes):
    print("[2/3] GENERANDO PROCESSED DATA\n")
    inicio = time.time()
    os.makedirs(PROCESSED_PATH, exist_ok=True)

    clientes_map = {c["phone"]: c for c in clientes}
    productos_map = {p["dropi_product_id"]: p for p in productos}

    print("Desanidando ordenes por item...")
    items_orden = []
    for orden in ordenes:
        for item in orden["items"]:
            cliente = clientes_map.get(orden["customer_id"], {})
            producto = productos_map.get(item["product_id"], {})
            items_orden.append({
                "order_number": orden["order_number"],
                "customer_id": orden["customer_id"],
                "customer_name": cliente.get("name", ""),
                "customer_city": cliente.get("city", ""),
                "customer_department": cliente.get("department", ""),
                "customer_phone": cliente.get("phone", ""),
                "dropi_order_id": orden["dropi_order_id"],
                "product_id": item["product_id"],
                "product_name": item["product_name"],
                "product_category": producto.get("category", ""),
                "sku": item["sku"],
                "quantity": item["quantity"],
                "unit_price": item["unit_price"],
                "supplier_cost": item["supplier_cost"],
                "total_amount": orden["total_amount"],
                "shipping_cost": orden["shipping_cost"],
                "order_profit": orden["order_profit"],
                "payment_method": orden["payment_method"],
                "status": orden["status"],
                "created_at": orden["created_at"]
            })
    escribir_json(os.path.join(PROCESSED_PATH, "items_orden.json"), items_orden, "processed")
    print(f"   -> {len(items_orden)} items de orden\n")

    print("Limpiando clientes...")
    clientes_limpios = [{k: v for k, v in c.items()} for c in clientes]
    escribir_json(os.path.join(PROCESSED_PATH, "clientes.json"), clientes_limpios, "processed")
    print(f"   -> {len(clientes_limpios)} clientes\n")

    print("Limpiando productos...")
    productos_limpios = [{k: v for k, v in p.items()} for p in productos]
    escribir_json(os.path.join(PROCESSED_PATH, "productos.json"), productos_limpios, "processed")
    print(f"   -> {len(productos_limpios)} productos\n")

    print("Limpiando ordenes...")
    ordenes_limpias = [{k: v for k, v in o.items()} for o in ordenes]
    escribir_json(os.path.join(PROCESSED_PATH, "ordenes.json"), ordenes_limpias, "processed")
    print(f"   -> {len(ordenes_limpias)} ordenes\n")

    print(f"   [OK] PROCESSED listo en {time.time()-inicio:.2f}s\n")
    return items_orden

def generar_curated(items_orden):
    print("[3/3] GENERANDO CURATED DATA (MODELO ESTRELLA OLAP)\n")
    inicio = time.time()
    os.makedirs(CURATED_PATH, exist_ok=True)

    print("Construyendo dimensiones y hechos...")
    dimensiones_cliente = {}
    dimensiones_producto = {}
    hechos = []

    for item in items_orden:
        dt = datetime.strptime(item["created_at"][:19], "%Y-%m-%d %H:%M:%S") if isinstance(item["created_at"], str) else item["created_at"]

        key_cliente = str(item["customer_id"])
        if key_cliente not in dimensiones_cliente:
            dimensiones_cliente[key_cliente] = {
                "cliente_id": key_cliente,
                "nombre": item["customer_name"],
                "telefono": item["customer_phone"],
                "ciudad": item["customer_city"],
                "departamento": item["customer_department"]
            }

        key_producto = str(item["product_id"])
        if key_producto not in dimensiones_producto:
            dimensiones_producto[key_producto] = {
                "producto_id": key_producto,
                "nombre": item["product_name"],
                "sku": item["sku"],
                "categoria": item["product_category"]
            }

        hechos.append({
            "_id": None,
            "fecha_venta": item["created_at"],
            "anio": dt.year,
            "mes": dt.month,
            "dia": dt.day,
            "order_number": item["order_number"],
            "cliente": dimensiones_cliente[key_cliente],
            "producto": dimensiones_producto[key_producto],
            "cantidad": item["quantity"],
            "precio_unitario": item["unit_price"],
            "total_venta": item["total_amount"],
            "costo_proveedor": round(item["supplier_cost"] * item["quantity"], 2),
            "costo_flete": item["shipping_cost"],
            "ganancia_neta": item["order_profit"],
            "metodo_pago": item["payment_method"],
            "estado": item["status"]
        })

    escribir_json(os.path.join(CURATED_PATH, "dimensiones_cliente.json"), list(dimensiones_cliente.values()), "curated")
    print(f"   -> {len(dimensiones_cliente)} clientes en dimensión")

    escribir_json(os.path.join(CURATED_PATH, "dimensiones_producto.json"), list(dimensiones_producto.values()), "curated")
    print(f"   -> {len(dimensiones_producto)} productos en dimensión")

    escribir_json(os.path.join(CURATED_PATH, "hechos_ventas.json"), hechos, "curated")
    print(f"   -> {len(hechos)} hechos de venta\n")

    tiempo = time.time() - inicio
    print("="*50)
    print(f"[CELEBRAR] DATA LAKE COMPLETO EN {tiempo:.2f} SEGUNDOS")
    print(f"   LOCAL: data_lake/raw|processed|curated/ -> respaldo")
    print(f"   S3:    s3://{BUCKET}/raw|processed|curated/ -> data lake en la nube")
    print(f"   Total documentos OLAP: {len(hechos)}")
    print("="*50)

def main():
    print("[LANZAR] Generando Data Lake completo de HeavyCult Dropshipping...\n")

    preparar_bucket()

    total_inicio = time.time()

    clientes, productos, ordenes = generar_raw()
    items_orden = generar_processed(clientes, productos, ordenes)
    generar_curated(items_orden)

    print(f"\n[OK] Pipeline completo en {time.time()-total_inicio:.2f}s")

if __name__ == "__main__":
    main()