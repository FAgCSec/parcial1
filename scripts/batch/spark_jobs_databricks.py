# ==========================================================
# HeavyCult — Spark Jobs | Versión Cloud-Ready (Databricks)
# ==========================================================
# Compatibilidad:
#   - Databricks Runtime 13.x / 14.x / 15.x (Spark 3.4 / 3.5)
#   - AWS EMR 6.x / 7.x (Spark 3.x) con ajuste de rutas S3
#   - Databricks Community Edition (gratuito)
#
# Diferencias frente a scripts/batch/spark_jobs.py (versión local Windows):
#   1. NO fija .master("local[*]") ni spark.driver.memory / shuffle.partitions
#      locales. En Databricks el master lo gestiona el clúster.
#   2. NO usa os.environ['PYSPARK_SUBMIT_ARGS'] ni SPARK_LOCAL_HOSTNAME
#      (parches solo necesarios en Windows + winutils.exe).
#   3. NO usa pandas (toPandas() + to_parquet + to_csv locales).
#      Usa escritura nativa distribuida: df.write.parquet("dbfs:/...") y
#      df.write.option("header","true").csv("dbfs:/...").
#   4. NO usa glob + os.path.getctime sobre disco local.
#      Usa rutas DBFS / S3 / ABFS parametrizables vía Widgets.
#   5. Usa display() cuando está disponible (notebooks Databricks).
#
# Uso en Databricks (Notebook Python):
#   1. Suba data_lake/processed/ordenes.json a DBFS:
#      dbfs:/FileStore/heavycult/processed/ordenes.json
#   2. Cree un Notebook nuevo y pegue este archivo por celdas,
#      o impórtelo como %run / import.
#   3. Ejecute celda por celda o "Run All".
# ----------------------------------------------------------

# Databricks ya provee `spark`, `dbutils` y `display` en notebooks.
# Se obtienen vía globals().get() para que el linter local (Pylance/Pyright)
# no reporte "is not defined". Fuera de Databricks valen None y se usan fallbacks.
import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

_spark_global = globals().get("spark")  # existe solo en runtime Databricks
_dbutils_global = globals().get("dbutils")  # existe solo en runtime Databricks
_display_global = globals().get("display")  # existe solo en notebooks Databricks

# Este bloque crea la sesión solo si el script se ejecuta fuera
# de un notebook (p. ej. como Databricks Job con spark-submit o prueba local).
_SPARK_PROVISTO = _spark_global is not None

if _SPARK_PROVISTO:
    spark = _spark_global
else:
    spark = (
        SparkSession.builder
        .appName("HeavyCult_BigData_SparkJobs_Cloud")
        # NO usar .master("local[*]"): el clúster lo define Databricks/EMR.
        .config("spark.sql.shuffle.partitions", "auto")
        .getOrCreate()
    )

# ---------------------------------------------------------
# Parámetros configurables (Widgets de Databricks con fallback)
# ---------------------------------------------------------
DEFAULT_INPUT = "dbfs:/FileStore/heavycult/processed/ordenes.json"
DEFAULT_OUTPUT_BASE = "dbfs:/FileStore/heavycult/curated"

_EN_DATABRICKS = _dbutils_global is not None

if _EN_DATABRICKS:
    dbutils = _dbutils_global
    dbutils.widgets.text("input_path", DEFAULT_INPUT, "Ruta JSON origen (processed)")
    dbutils.widgets.text("output_base", DEFAULT_OUTPUT_BASE, "Ruta base destino (curated)")
    INPUT_PATH = dbutils.widgets.get("input_path")
    OUTPUT_BASE = dbutils.widgets.get("output_base")
else:
    # Ejecución local de prueba o EMR: permite override por variables de entorno.
    INPUT_PATH = os.getenv("INPUT_PATH", DEFAULT_INPUT)
    OUTPUT_BASE = os.getenv("OUTPUT_BASE", DEFAULT_OUTPUT_BASE)

print(f"Origen : {INPUT_PATH}")
print(f"Destino: {OUTPUT_BASE}")


def _mostrar(df, n=10):
    """Muestra resultados tanto en Notebook Databricks como en consola."""
    if _display_global is not None:
        try:
            _display_global(df.limit(n))
            return
        except Exception:
            pass
    df.show(n, truncate=False)


# ---------------------------------------------------------
# SPARK JOB 1: Ventas por Método de Pago
# ---------------------------------------------------------
def job1_ventas_por_metodo_pago(spark, ruta_origen, ruta_base):
    print("\n[SPARK JOB 1] Ventas por método de pago...")
    df = spark.read.option("multiline", "true").json(ruta_origen)

    df_items = df.withColumn("item", F.explode("items")) if "items" in df.columns else df

    resultado = (
        df_items.groupBy("payment_method")
        .agg(
            F.count("order_number").alias("total_ordenes"),
            F.sum("total_amount").alias("ingresos_totales"),
            F.avg("total_amount").alias("ticket_promedio"),
        )
        .orderBy(F.col("ingresos_totales").desc())
    )

    _mostrar(resultado)

    # Escritura NATIVA distribuida (sin pandas, sin disco local Windows).
    destino_parquet = f"{ruta_base}/job1_metodos_pago_parquet"
    destino_csv = f"{ruta_base}/job1_metodos_pago_csv"
    resultado.write.mode("overwrite").parquet(destino_parquet)
    resultado.write.mode("overwrite").option("header", "true").csv(destino_csv)
    print(f"   [OK] Job 1 -> {destino_parquet} + {destino_csv}")
    return resultado


# ---------------------------------------------------------
# SPARK JOB 2: Segmentación RFM de Clientes
# ---------------------------------------------------------
def job2_segmentacion_clientes(spark, ruta_origen, ruta_base):
    print("\n[SPARK JOB 2] Segmentación de clientes...")
    df = spark.read.option("multiline", "true").json(ruta_origen)

    resultado = (
        df.groupBy("customer_id")
        .agg(
            F.count("order_number").alias("total_compras"),
            F.sum("total_amount").alias("gasto_total"),
            F.avg("total_amount").alias("ticket_promedio"),
        )
        .withColumn(
            "segmento",
            F.when(F.col("gasto_total") > 1000000, "VIP")
            .when(F.col("gasto_total") > 500000, "Premium")
            .when(F.col("gasto_total") > 200000, "Frecuente")
            .otherwise("Regular"),
        )
        .orderBy(F.col("gasto_total").desc())
    )

    _mostrar(resultado)

    destino_parquet = f"{ruta_base}/job2_segmentacion_clientes_parquet"
    destino_csv = f"{ruta_base}/job2_segmentacion_clientes_csv"
    resultado.write.mode("overwrite").parquet(destino_parquet)
    resultado.write.mode("overwrite").option("header", "true").csv(destino_csv)
    print(f"   [OK] Job 2 -> {destino_parquet} + {destino_csv}")
    return resultado


# ---------------------------------------------------------
# SPARK JOB 3: Análisis Temporal de Tendencias
# ---------------------------------------------------------
def job3_analisis_temporal(spark, ruta_origen, ruta_base):
    print("\n[SPARK JOB 3] Series temporales y tendencias...")
    df = spark.read.option("multiline", "true").json(ruta_origen)

    df_fecha = (
        df.withColumn("fecha_parsed", F.to_date(F.col("created_at"), "yyyy-MM-dd HH:mm:ss"))
        .withColumn("anio", F.year("fecha_parsed"))
        .withColumn("mes", F.month("fecha_parsed"))
    )

    resultado = (
        df_fecha.groupBy("anio", "mes")
        .agg(
            F.count("order_number").alias("total_ventas"),
            F.sum("total_amount").alias("ingresos_mensuales"),
            F.avg("total_amount").alias("promedio_diario"),
        )
        .orderBy("anio", "mes")
    )

    _mostrar(resultado)

    destino_parquet = f"{ruta_base}/job3_tendencias_temporales_parquet"
    destino_csv = f"{ruta_base}/job3_tendencias_temporales_csv"
    resultado.write.mode("overwrite").parquet(destino_parquet)
    resultado.write.mode("overwrite").option("header", "true").csv(destino_csv)
    print(f"   [OK] Job 3 -> {destino_parquet} + {destino_csv}")
    return resultado


# ---------------------------------------------------------
# EJECUCIÓN PRINCIPAL (compatible Notebook + Job)
# ---------------------------------------------------------
print("=" * 60)
print("INICIANDO SPARK ENGINE — MODO CLOUD (Databricks / EMR)")
print("=" * 60)

job1_ventas_por_metodo_pago(spark, INPUT_PATH, OUTPUT_BASE)
job2_segmentacion_clientes(spark, INPUT_PATH, OUTPUT_BASE)
job3_analisis_temporal(spark, INPUT_PATH, OUTPUT_BASE)

print("\n" + "=" * 60)
print("LOS 3 SPARK JOBS SE EJECUTARON EXITOSAMENTE (CLOUD)")
print("=" * 60)

# NOTA: En notebooks Databricks NO llamar spark.stop().
# El ciclo de vida del clúster lo gestiona la plataforma.
# Solo detener si se ejecutó como script standalone fuera de notebook:
if not _EN_DATABRICKS and not _SPARK_PROVISTO:
    spark.stop()
    print("Sesión Spark standalone finalizada.")
