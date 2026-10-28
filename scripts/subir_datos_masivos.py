import os
import json
import time
import boto3
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

BUCKET = os.getenv("S3_BUCKET", "abp-data-lake-fabian")
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_PATH = os.path.join(BASE_DIR, "data_lake", "processed")

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=REGION,
)

# --- CONFIGURACION: 7 archivos x ~320 MB = ~2.2 GB ---
NUM_ARCHIVOS = 7
FILAS_POR_ARCHIVO = 2_800_000      # ~320 MB de CSV por archivo
BORRAR_LOCAL_DESPUES = True        # libera tu disco duro tras subir

CIUDADES = ["Bogotá", "Medellín", "Cali", "Barranquilla", "Bucaramanga", "Pasto"]
ESTADOS = ["delivered", "shipped", "novelty", "cancelled"]
PAGOS = ["Pago Contra Entrega", "PSE", "Nequi"]

def cargar_catalogos():
    """Reutiliza los clientes y productos ya generados en el pipeline."""
    with open(os.path.join(PROCESSED_PATH, "clientes.json"), encoding="utf-8") as f:
        clientes = json.load(f)
    with open(os.path.join(PROCESSED_PATH, "productos.json"), encoding="utf-8") as f:
        productos = json.load(f)
    telefonos = np.array([c["phone"] for c in clientes])
    ciudades_cli = np.array([c["city"] for c in clientes])
    ids_prod = np.array([p["dropi_product_id"] for p in productos])
    precios = np.array([p["pricing"]["sale_price"] for p in productos])
    return telefonos, ciudades_cli, ids_prod, precios

def generar_archivo(indice, telefonos, ciudades_cli, ids_prod, precios):
    n = FILAS_POR_ARCHIVO
    rng = np.random.default_rng(seed=indice)

    idx_cli = rng.integers(0, len(telefonos), n)
    idx_prod = rng.integers(0, len(ids_prod), n)
    cantidad = rng.integers(1, 3, n)
    precio = precios[idx_prod]

    # fechas aleatorias del ultimo año
    base = np.datetime64("2025-10-21")
    dias = rng.integers(0, 365, n)
    fechas = (base + dias.astype("timedelta64[D]")).astype(str)

    df = pd.DataFrame({
        "order_number": [f"HC-BULK-{indice}-{i+1000000}" for i in range(n)],
        "customer_id": telefonos[idx_cli],
        "customer_city": ciudades_cli[idx_cli],
        "product_id": ids_prod[idx_prod],
        "quantity": cantidad,
        "unit_price": np.round(precio, 2),
        "total_venta": np.round(precio * cantidad, 2),
        "payment_method": rng.choice(PAGOS, n),
        "status": rng.choice(ESTADOS, n, p=[0.7, 0.15, 0.1, 0.05]),
        "created_at": fechas,
    })

    ruta_local = os.path.join(PROCESSED_PATH, f"ventas_masivas_{indice:02d}.csv")
    df.to_csv(ruta_local, index=False)
    return ruta_local

def subir_a_s3(ruta_local):
    nombre = os.path.basename(ruta_local)
    clave = f"raw/masivo/{nombre}"
    tam_mb = os.path.getsize(ruta_local) / (1024 * 1024)
    print(f"   Subiendo {nombre} ({tam_mb:.0f} MB)...")
    s3.upload_file(ruta_local, BUCKET, clave)
    print(f"   [S3] -> s3://{BUCKET}/{clave}")
    if BORRAR_LOCAL_DESPUES:
        os.remove(ruta_local)
        print(f"   [LOCAL] {nombre} borrado para liberar disco\n")

def main():
    print("[LANZAR] Generando y subiendo datos masivos a S3...\n")
    telefonos, ciudades_cli, ids_prod, precios = cargar_catalogos()
    print(f"Catalogos cargados: {len(telefonos)} clientes, {len(ids_prod)} productos\n")

    inicio = time.time()
    for i in range(NUM_ARCHIVOS):
        t0 = time.time()
        print(f"[{i+1}/{NUM_ARCHIVOS}] Generando archivo...")
        ruta = generar_archivo(i, telefonos, ciudades_cli, ids_prod, precios)
        subir_a_s3(ruta)
        print(f"   ({time.time()-t0:.0f}s)\n")

    print("="*50)
    print(f"[OK] DATOS MASIVOS COMPLETOS en {time.time()-inicio:.0f}s")
    print(f"   Zona S3: s3://{BUCKET}/raw/masivo/")
    print("="*50)

if __name__ == "__main__":
    main()