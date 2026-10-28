import os
import time
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import pandas as pd
from google.cloud import bigquery

load_dotenv()

# --- CONFIGURACION ---
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = "bd_erp"  # Base de datos correcta vista en Compass
BQ_PROJECT = "abp-data-warehouse"  # El ID del proyecto de Google Cloud
BQ_DATASET = "ventas_dw"

# Colecciones de MongoDB -> tablas de BigQuery
TABLAS = {
    "fact_ventas": "fact_ventas",
    "dim_cliente": "dim_clientes",
    "dim_producto": "dim_productos",
    "dim_tiempo": "dim_fechas",
}

cliente_mongo = MongoClient(MONGO_URI)
db = cliente_mongo[MONGO_DB]

bq = bigquery.Client(project=BQ_PROJECT)
dataset_ref = f"{BQ_PROJECT}.{BQ_DATASET}"

def migrar_tabla(coleccion_mongo, tabla_bq):
    print(f"\n[MIGRANDO] {coleccion_mongo} -> {dataset_ref}.{tabla_bq}")
    inicio = time.time()

    docs = list(db[coleccion_mongo].find({}, {"_id": 0}))   # excluimos el _id principal
    if not docs:
        print(f"   [AVISO] La coleccion '{coleccion_mongo}' esta vacia, se omite")
        return

    # Convertir recursivamente cualquier ObjectId restante a string
    for doc in docs:
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                doc[k] = str(v)

    df = pd.DataFrame(docs)
    print(f"   -> {len(df)} filas leidas de MongoDB")

    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",   # si la tabla existe, la reemplaza
        autodetect=True,                    # BigQuery infiere el esquema
    )

    job = bq.load_table_from_dataframe(df, f"{dataset_ref}.{tabla_bq}", job_config=job_config)
    job.result()   # espera a que termine el job

    tabla = bq.get_table(f"{dataset_ref}.{tabla_bq}")
    print(f"   [OK] {tabla.num_rows} filas en BigQuery ({time.time()-inicio:.1f}s)")

def main():
    print("[LANZAR] Pipeline ETL: MongoDB Atlas -> Google BigQuery\n")
    total = time.time()

    for coleccion, tabla in TABLAS.items():
        migrar_tabla(coleccion, tabla)

    print("\n" + "="*50)
    print(f"[OK] MIGRACION COMPLETA en {time.time()-total:.1f}s")
    print(f"   Verifica en: console.cloud.google.com -> BigQuery -> {BQ_DATASET}")
    print("="*50)

if __name__ == "__main__":
    main()