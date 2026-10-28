import os
import sys
import glob
import pandas as pd
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

os.environ['PYSPARK_SUBMIT_ARGS'] = '--master local[*] pyspark-shell'
os.environ['SPARK_LOCAL_HOSTNAME'] = 'localhost'

MONGO_URI = os.getenv("MONGO_URI")

def obtener_ultimo_archivo_json(ruta_carpeta):
    archivos = glob.glob(os.path.join(ruta_carpeta, "*.json"))
    if not archivos:
        raise FileNotFoundError(f"No se encontraron archivos JSON en {ruta_carpeta}")
    return max(archivos, key=os.path.getctime)

def crear_spark_session():
    return SparkSession.builder \
        .appName("HeavyCult_BigData_SparkJobs") \
        .master("local[*]") \
        .config("spark.sql.shuffle.partitions", "8") \
        .config("spark.driver.memory", "2g") \
        .getOrCreate()

# ---------------------------------------------------------
# SPARK JOB 1: Ventas por Método de Pago
# ---------------------------------------------------------
def job1_ventas_por_metodo_pago(spark, ruta_origen, ruta_destino):
    print("\n⚡ [SPARK JOB 1] Procesando ventas por método de pago...")
    df = spark.read.option("multiline", "true").json(ruta_origen)

    df_items = df.withColumn("item", F.explode("items")) if "items" in df.columns else df

    resultado = df_items.groupBy("payment_method") \
        .agg(
            F.count("order_number").alias("total_ordenes"),
            F.sum("total_amount").alias("ingresos_totales"),
            F.avg("total_amount").alias("ticket_promedio")
        ) \
        .orderBy(F.col("ingresos_totales").desc())

    resultado.show()

    os.makedirs(ruta_destino, exist_ok=True)
    pd_df = resultado.toPandas()
    pd_df.to_parquet(os.path.join(ruta_destino, "job1_metodos_pago.parquet"), index=False)
    pd_df.to_csv(os.path.join(ruta_destino, "job1_metodos_pago.csv"), index=False)
    print("   [OK] Job 1 guardado en curated/")

# ---------------------------------------------------------
# SPARK JOB 2: Segmentación RFM de Clientes
# ---------------------------------------------------------
def job2_segmentacion_clientes(spark, ruta_origen, ruta_destino):
    print("\n⚡ [SPARK JOB 2] Clasificando y segmentando clientes...")
    df = spark.read.option("multiline", "true").json(ruta_origen)

    resultado = df.groupBy("customer_id") \
        .agg(
            F.count("order_number").alias("total_compras"),
            F.sum("total_amount").alias("gasto_total"),
            F.avg("total_amount").alias("ticket_promedio")
        ) \
        .withColumn(
            "segmento",
            F.when(F.col("gasto_total") > 1000000, "VIP")
             .when(F.col("gasto_total") > 500000, "Premium")
             .when(F.col("gasto_total") > 200000, "Frecuente")
             .otherwise("Regular")
        ) \
        .orderBy(F.col("gasto_total").desc())

    resultado.show(10)

    pd_df = resultado.toPandas()
    pd_df.to_parquet(os.path.join(ruta_destino, "job2_segmentacion_clientes.parquet"), index=False)
    pd_df.to_csv(os.path.join(ruta_destino, "job2_segmentacion_clientes.csv"), index=False)
    print("   [OK] Job 2 guardado en curated/")

# ---------------------------------------------------------
# SPARK JOB 3: Análisis Temporal de Tendencias
# ---------------------------------------------------------
def job3_analisis_temporal(spark, ruta_origen, ruta_destino):
    print("\n⚡ [SPARK JOB 3] Calculando series temporales y tendencias...")
    df = spark.read.option("multiline", "true").json(ruta_origen)

    df_fecha = df.withColumn("fecha_parsed", F.to_date(F.col("created_at"), "yyyy-MM-dd HH:mm:ss")) \
                 .withColumn("anio", F.year("fecha_parsed")) \
                 .withColumn("mes", F.month("fecha_parsed"))

    resultado = df_fecha.groupBy("anio", "mes") \
        .agg(
            F.count("order_number").alias("total_ventas"),
            F.sum("total_amount").alias("ingresos_mensuales"),
            F.avg("total_amount").alias("promedio_diario")
        ) \
        .orderBy("anio", "mes")

    resultado.show()

    pd_df = resultado.toPandas()
    pd_df.to_parquet(os.path.join(ruta_destino, "job3_tendencias_temporales.parquet"), index=False)
    pd_df.to_csv(os.path.join(ruta_destino, "job3_tendencias_temporales.csv"), index=False)
    print("   [OK] Job 3 guardado en curated/")

# ---------------------------------------------------------
# EJECUCIÓN PRINCIPAL
# ---------------------------------------------------------
if __name__ == "__main__":
    print("==================================================")
    print("🚀 INICIANDO SPARK ENGINE (PROCESAMIENTO DISTRIBUIDO)")
    print("==================================================")

    spark = crear_spark_session()

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    processed_dir = os.path.join(base_dir, "data_lake", "processed")
    curated_dir = os.path.join(base_dir, "data_lake", "curated")

    try:
        archivo_origen = obtener_ultimo_archivo_json(processed_dir)
        print(f"📄 Procesando datos desde: {archivo_origen}")

        job1_ventas_por_metodo_pago(spark, archivo_origen, curated_dir)
        job2_segmentacion_clientes(spark, archivo_origen, curated_dir)
        job3_analisis_temporal(spark, archivo_origen, curated_dir)

        print("\n==================================================")
        print("✅ ¡LOS 3 SPARK JOBS SE EJECUTARON EXITOSAMENTE!")
        print("==================================================")

    except Exception as e:
        print(f"\n❌ Error durante la ejecución de PySpark: {e}")
        import traceback
        traceback.print_exc()
    finally:
        spark.stop()
        print("🔒 Sesión de Spark finalizada y memoria liberada.")
