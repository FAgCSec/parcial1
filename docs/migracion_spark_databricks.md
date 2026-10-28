# Migración de Spark Local a Databricks (Entorno Enterprise)

> Documento técnico y académico del proyecto **HeavyCult Dropshipping — Sistema de Ventas (OLTP + OLAP + Data Lake + Spark)**.
> Complementa al `README.md` principal y al script `scripts/batch/spark_jobs_databricks.py` (versión Cloud-ready).

---

## 1. Resumen ejecutivo

| Aspecto | Entorno local de desarrollo (actual) | Entorno de producción Cloud (propuesto) |
|---|---|---|
| Motor | PySpark 3.5.3 en Windows (`local[*]`) | Databricks Runtime (Spark 3.4/3.5) sobre Linux en clúster real |
| Script | `scripts/batch/spark_jobs.py` | `scripts/batch/spark_jobs_databricks.py` |
| Entrada | `data_lake/processed/*.json` (disco local, `glob + getctime`) | `dbfs:/FileStore/heavycult/processed/ordenes.json` (DBFS / S3 / ADLS) |
| Salida | `toPandas()` + `pandas.to_parquet()` / `.to_csv()` en `data_lake/curated/` | `df.write.parquet("dbfs:/...")` + `df.write.csv("dbfs:/...")` nativo distribuido |
| Dependencias locales | `winutils.exe`, `HADOOP_HOME`, `PYSPARK_SUBMIT_ARGS`, `SPARK_LOCAL_HOSTNAME` | Ninguna. Eliminadas |
| Escalabilidad | 1 máquina, `driver.memory=2g`, `shuffle.partitions=8` fijos | Clúster elástico multi-nodo, auto-scaling, `shuffle.partitions=auto` |
| Costo académico | $0 pero limitado y frágil en Windows | $0 con **Databricks Community Edition** / trial AWS EMR |

**Conclusión:** el código de negocio (los 3 Jobs: agregaciones con `groupBy`, `explode`, `to_date`, segmentación `when/otherwise`) **no cambia**.
Lo que cambia es la **capa de infraestructura**: cómo se crea la `SparkSession`, cómo se parametrizan rutas y cómo se escribe la salida.
Esa es exactamente la evolución Local → Enterprise que se evalúa en el informe final.

---

## 2. Comprensión del proyecto al 100% (base de esta migración)

### 2.1 Arquitectura general

```
MongoDB Atlas (bd_erp: clientes, productos, ordenes, ventas_analiticas,
                 dim_tiempo, dim_cliente, dim_producto, fact_ventas)
        │
        │  scripts/crear_data_lake.py  (Faker es_CO, 5000 clientes / 500 productos / 30000 órdenes)
        ▼
Data Lake local (formato JSON multiline):
  data_lake/raw/        clientes.json, productos.json, ordenes.json
  data_lake/processed/  + items_orden.json (órdenes desanidadas por item, join cliente×producto en Python)
  data_lake/curated/    dimensiones_cliente.json, dimensiones_producto.json, hechos_ventas.json (modelo estrella OLAP)
                        + salidas Spark: job1_*.parquet/csv, job2_*.parquet/csv, job3_*.parquet/csv
        │
        │  scripts/batch/spark_jobs.py  (3 Jobs batch sobre processed/*.json)
        ▼
Data Warehouse MongoDB (scripts/batch/data_warehouse.py, 4 pipelines $group/$merge)
        │
        │  scripts/streaming/{generar_ventas_streaming.py, streaming.py}  (Change Streams ≈ Kafka CDC)
        ▼
Observabilidad: scripts/dashboard_monitoreo.py, generar_catalogo*.py, docs/, terraform/
```

### 2.2 El Data Lake (estado real verificado)

| Capa | Contenido | Tamaño aprox. | Propósito |
|---|---|---|---|
| `raw/` | `clientes.json` (1.04 MB), `productos.json` (0.36 MB), `ordenes.json` (17.35 MB) | ~18.7 MB | Copia fiel de la fuente, sin limpieza |
| `processed/` | `clientes.json`, `productos.json`, `ordenes.json` + `items_orden.json` (20.57 MB, ~30 000 filas desanidadas con 20 columnas planas) | ~39 MB | Datos limpios y desanidados, listos para Spark |
| `curated/` | `dimensiones_cliente.json` (~4 985 filas), `dimensiones_producto.json` (~496 filas), `hechos_ventas.json` (~30 000 hechos, 22.4 MB) + salidas `job1/2/3` en Parquet + CSV | ~23 MB + salidas | Modelo estrella OLAP + resultados analíticos curados |

### 2.3 Los 3 Spark Jobs (lógica de negocio que se migra intacta)

| Job | Función en `spark_jobs.py` | Transformación Spark | Salida |
|---|---|---|---|
| Job 1 | `job1_ventas_por_metodo_pago` | `explode("items")` si existe + `groupBy("payment_method").agg(count, sum, avg).orderBy(ingresos desc)` | `job1_metodos_pago.parquet/csv` |
| Job 2 | `job2_segmentacion_clientes` | `groupBy("customer_id").agg(count, sum, avg)` + columna `segmento` (VIP >1M, Premium >500k, Frecuente >200k, Regular) | `job2_segmentacion_clientes.parquet/csv` |
| Job 3 | `job3_analisis_temporal` | `to_date(created_at, "yyyy-MM-dd HH:mm:ss")` + `year/month` + `groupBy(anio, mes).agg(count, sum, avg).orderBy(anio, mes)` | `job3_tendencias_temporales.parquet/csv` |

Punto de entrada local (`if __name__ == "__main__"`): crea sesión `local[*]`, localiza el JSON más reciente de `processed/` con `glob + getctime` y ejecuta los 3 jobs secuencialmente con `try/except/finally: spark.stop()`.

### 2.4 Patrón híbrido local: Spark + Pandas + Parquet (por qué existe)

En `scripts/batch/spark_jobs.py` cada job termina con:

```python
pd_df = resultado.toPandas()
pd_df.to_parquet(os.path.join(ruta_destino, "job1_....parquet"), index=False)
pd_df.to_csv(os.path.join(ruta_destino, "job1_....csv"), index=False)
```

Esto es un **patrón híbrido deliberado para Windows**:

1. Spark hace el cómputo distribuido (aunque sea en `local[*]`).
2. `toPandas()` trae el **resultado ya agregado** (pocas filas: 3 métodos de pago, ~5 000 clientes, 12 meses) al driver.
3. Pandas escribe Parquet/CSV en disco local sin pasar por el stack nativo Hadoop de escritura.

Ventaja local: evita los errores clásicos de PySpark en Windows (`winutils.exe`, `HADOOP_HOME`, permisos `AccessDenied`, `SPARK_LOCAL_HOSTNAME`, Java gateway) justo en la fase de escritura, que es donde más fallan.
Costo: **no es distribuido de verdad** — el `collect` al driver rompe la escalabilidad y es un anti-patrón en producción con millones de filas.

---

## 3. Justificación técnica del cambio (para el informe)

### 3.1 Limitaciones del entorno local Windows

1. **Sin distribución real.** `.master("local[*]")` usa los cores de una sola laptop. No hay executors remotos, ni tolerancia a fallos, ni shuffle de red.
2. **Dependencia frágil `winutils.exe`.** Spark espera utilidades POSIX/Hadoop (`winutils.exe + HADOOP_HOME + permisos`) que no existen en Windows. Cada máquina del equipo debe configurarla igual.
3. **Parches de sesión.** `PYSPARK_SUBMIT_ARGS='--master local[*] pyspark-shell'` y `SPARK_LOCAL_HOSTNAME='localhost'` son workarounds de desarrollo, no configuración enterprise.
4. **Cuello de botella `toPandas()`.** Con 30 000 órdenes funciona; con 30 millones OOM en el driver de 2 GB.
5. **Rutas locales no portables.** `os.path.join(base_dir, "data_lake", ...)` + `glob + getctime` no existen en un clúster (DBFS/S3 no tienen `ctime` de Windows).
6. **Recursos fijos.** `spark.driver.memory=2g`, `shuffle.partitions=8` están hardcodeados para una laptop, no para carga elástica.

### 3.2 Beneficios del entorno Cloud (Databricks / EMR sobre Linux)

1. **Procesamiento distribuido real.** Múltiples workers Linux ejecutan `groupBy/shuffle` en paralelo; el mismo código escala de 30k a 300M de filas sin reescribir lógica.
2. **Cero `winutils`.** Los runtimes Databricks/EMR ya incluyen Hadoop nativo, Java y Python alineados. Se elimina toda la fricción Windows.
3. **Escalabilidad elástica.** Auto-scaling del clúster + `spark.sql.shuffle.partitions=auto` (Adaptive Query Execution) en lugar de valores fijos.
4. **Escritura nativa distribuida.** `df.write.mode("overwrite").parquet("dbfs:/...")` escribe particiones en paralelo (archivos `part-*.parquet`) con esquema y compresión Snappy, sin pasar por el driver.
5. **Gobernanza y reproducibilidad.** DBFS/S3 + Widgets (`input_path`, `output_base`) + Jobs programados + historial de ejecuciones reemplazan al "último JSON por fecha de creación".
6. **Costo académico $0.** Databricks Community Edition (Single-node mini-clúster gratuito, suficiente para 30k–1M filas) o trial de AWS EMR. Sin tarjeta para CE.

### 3.3 Justificación pedagógica (párrafo listo para el informe)

> *Durante el desarrollo se utilizó PySpark en Windows con el patrón híbrido Spark → Pandas → Parquet como estrategia didáctica: permitió validar la lógica distribuida (explode, groupBy, funciones temporales, segmentación condicional) sin la fricción operativa de winutils en la fase de escritura. Para producción se migró a Databricks Community Edition sobre Linux, donde la misma lógica se ejecuta en un clúster real con lectura/escritura nativa sobre DBFS (`df.write.parquet("dbfs:/...")`), eliminando dependencias locales, habilitando escalabilidad elástica y aplicando buenas prácticas enterprise (parametrización, idempotencia con `mode("overwrite")` y separación storage/compute). Esta transición demuestra la competencia de portar un pipeline Big Data de desarrollo a producción Cloud sin reescribir la lógica de negocio.*

---

## 4. Qué cambió en el código (comparativa exacta)

| # | Versión local (`spark_jobs.py`) | Versión Cloud (`spark_jobs_databricks.py`) | Por qué |
|---|---|---|---|
| 1 | `os.environ['PYSPARK_SUBMIT_ARGS']='--master local[*] pyspark-shell'` | **Eliminado** | Databricks/EMR gestionan el master; el parche solo enmascara el gateway Java en Windows |
| 2 | `os.environ['SPARK_LOCAL_HOSTNAME']='localhost'` | **Eliminado** | Solo necesario para resolución de hostname en Windows |
| 3 | `.master("local[*]").config("spark.driver.memory","2g").config("shuffle.partitions","8")` | `SparkSession.builder.appName(...).config("shuffle.partitions","auto").getOrCreate()`; reutiliza `spark` si ya existe | En Cloud el manager del clúster asigna recursos; AQE ajusta el shuffle |
| 4 | `glob + os.path.getctime` para "último JSON" | Widgets `input_path` / `output_base` (default `dbfs:/FileStore/heavycult/...`), override por `INPUT_PATH`/`OUTPUT_BASE` en EMR | DBFS/S3 no tienen `ctime`; producción exige rutas explícitas y parametrizables |
| 5 | `resultado.toPandas()` → `pandas.to_parquet/to_csv` + `os.makedirs` | `resultado.write.mode("overwrite").parquet(...)` y `.option("header","true").csv(...)` | Escritura distribuida nativa, idempotente, sin OOM del driver, sin `pandas`/`pyarrow` en el clúster |
| 6 | `print` + `resultado.show()` | `display(df.limit(n))` con fallback a `show()` | Experiencia notebook Databricks (tablas interactivas y gráficos) |
| 7 | `spark.stop()` siempre en `finally` | **No** se detiene en notebooks (`_EN_DATABRICKS`); solo `stop()` en standalone | Detener la sesión mata el contexto compartido del notebook y el historial `display` |
| 8 | `import pandas`, `glob`, `dotenv/MONGO_URI` | Sin `pandas/glob/dotenv`; solo `pyspark.sql.functions` | El job batch puro no necesita Mongo ni Pandas en el clúster; menos dependencias = menos fallos de serialización |

La lógica `groupBy/agg/explode/to_date/when` es **idéntica línea por línea** — verificación intencional de portabilidad.

---

## 5. Instrucciones paso a paso (Databricks Community Edition)

### 5.1 Crear cuenta y clúster (5 min, $0)

1. Ir a `https://community.cloud.databricks.com/` → **Sign Up** (email académico).
2. **Compute → Create Cluster**: nombre `heavycult-spark`, Runtime `13.3 LTS (Spark 3.4)` o superior, Node type por defecto, **Terminate after 30 min of inactivity** (ahorra DBUs).
3. Esperar estado **Running** (2–4 min la primera vez).

### 5.2 Subir datos de entrada a DBFS (2 opciones)

**Opción A — UI (recomendada para el parcial):**

1. **Catalog → DBFS / Browse DBFS** (o `Data → DBFS → Upload` según UI vigente).
2. Crear carpeta `FileStore/heavycult/processed/` y subir `data_lake/processed/ordenes.json` local.
3. Verificar ruta: `dbfs:/FileStore/heavycult/processed/ordenes.json`.

**Opción B — CLI/API (para el informe como evidencia DevOps):**

```bash
# Desde tu laptop con Databricks CLI configurado
databricks fs mkdirs dbfs:/FileStore/heavycult/processed
databricks fs mkdirs dbfs:/FileStore/heavycult/curated
databricks fs cp data_lake/processed/ordenes.json dbfs:/FileStore/heavycult/processed/ordenes.json
databricks fs ls dbfs:/FileStore/heavycult/processed/
```

> Alternativa AWS EMR/S3: sustituya `dbfs:/...` por `s3://mi-bucket-heavycult/processed/ordenes.json` y `s3://mi-bucket-heavycult/curated/`. El script acepta cualquier esquema Hadoop (`dbfs:/`, `s3://`, `s3a://`, `abfss://`) sin cambios porque usa `spark.read.json` / `df.write.parquet` genéricos.

### 5.3 Crear el Notebook y pegar el script (5 min)

1. **Workspace → Create → Notebook**, nombre `heavycult_spark_jobs_cloud`, lenguaje **Python**, adjuntar al clúster creado.
2. Dividir `scripts/batch/spark_jobs_databricks.py` en celdas en este orden:
   - **Celda 1:** bloque de sesión `spark` + imports + Widgets (`input_path`, `output_base`).
   - **Celda 2:** `job1_ventas_por_metodo_pago` + llamada.
   - **Celda 3:** `job2_segmentacion_clientes` + llamada.
   - **Celda 4:** `job3_analisis_temporal` + llamada.
   - Tip: el archivo ya está estructurado secuencialmente; basta copiar cada bloque de función como una celda.
3. **Run All**. Resultado esperado por celda: tabla `display()` + línea `[OK] Job N -> dbfs:/...`.
4. Capturas para el informe: (a) clúster Running, (b) `display()` del Job 2 con segmentos VIP/Premium, (c) listado DBFS con `job1/2/3_*_parquet/`.

### 5.4 Verificar y consumir la salida nativa

```python
# Celda de verificación (pegar en el mismo Notebook)
df1 = spark.read.parquet("dbfs:/FileStore/heavycult/curated/job1_metodos_pago_parquet")
df2 = spark.read.parquet("dbfs:/FileStore/heavycult/curated/job2_segmentacion_clientes_parquet")
df3 = spark.read.parquet("dbfs:/FileStore/heavycult/curated/job3_tendencias_temporales_parquet")

display(df1)  # 3-4 filas: Pago Contra Entrega / PSE / Nequi
print(f"Clientes segmentados: {df2.count()}")
display(df3.orderBy("anio", "mes"))

# Descargar a laptop si el docente lo exige:
# DBFS -> FileStore -> botón Download, o:
# dbutils.fs.cp("dbfs:/FileStore/heavycult/curated/job1_metodos_pago_csv/", "file:/tmp/job1_csv/", recurse=True)
```

Detalles a destacar en clase:

- Cada destino `*_parquet/` contiene múltiples `part-*.parquet` + `_SUCCESS`: **prueba visible de escritura distribuida** (vs. 1 archivo local del modo Pandas).
- `mode("overwrite")` hace el job **idempotente**: re-ejecutar no duplica datos (vs. `to_parquet` local que sobrescribe silenciosamente 1 archivo).
- El CSV Cloud también es un **directorio** de `part-*.csv`: se lee con `spark.read.option("header","true").csv("dbfs:/.../job1_metodos_pago_csv")`, no como archivo único.

### 5.5 (Opcional) Programarlo como Databricks Job

1. **Workflows → Create Job**, tarea Notebook = `heavycult_spark_jobs_cloud`, clúster = el mismo o **New Job Cluster** (más barato, se auto-termina).
2. Parámetros: `input_path=dbfs:/FileStore/heavycult/processed/ordenes.json`, `output_base=dbfs:/FileStore/heavycult/curated`.
3. Schedule (ej. diario 02:00) → evidencia de **orquestación enterprise** para el informe.

---

## 6. Cómo documentar esta evolución en el informe final

Estructura sugerida (1.5–2 páginas + anexos):

1. **3.4.1 Entorno de desarrollo (p. ej. §3.4).** Describa PySpark Windows + patrón híbrido con snippet de `toPandas().to_parquet()` y justifique por qué se eligió (rapidez didáctica, evasión de winutils). Incluya captura de consola local `LOS 3 SPARK JOBS SE EJECUTARON EXITOSAMENTE`.
2. **3.4.2 Entorno de producción Cloud.** Tabla comparativa §1 + diagrama: `laptop (local[*]) → DBFS → Databricks Cluster (workers Linux) → curated parquet`. Cite eliminación de `winutils`, `local[*]`, `toPandas`.
3. **3.4.3 Evidencias de migración.** Mínimo 3 capturas: (a) Notebook ejecutado con `display()`, (b) `dbfs ls` con carpetas `job*_parquet` y archivos `part-*`, (c) re-lectura `spark.read.parquet("dbfs:/...")` exitosa. Añada enlace/commit del archivo `spark_jobs_databricks.py`.
4. **Conclusiones.** Frase evaluable: *"La lógica de negocio no se reescribió; se portó la capa de I/O y sesión a estándares Cloud, demostrando separación entre cómputo y almacenamiento y preparación para escalar de 30k a N millones de registros sin cambio de código."*
5. **Anexos.** Diff resumido (§4 de este doc) + comandos `databricks fs cp/ls` + spec del clúster (Runtime, workers, auto-terminate).

Rúbrica típica que cubre este documento: arquitectura distribuida (Data Lake 3 capas), justificación tecnológica, evidencias reproducibles, buenas prácticas Cloud (parametrización, idempotencia, AQE) y proyección a producción.

---

## 7. Checklist de entrega

- [ ] `scripts/batch/spark_jobs.py` intacto (evidencia entorno local).
- [ ] `scripts/batch/spark_jobs_databricks.py` creado (versión Cloud-ready, sin pandas/winutils, con `dbfs:/`).
- [ ] Datos subidos a `dbfs:/FileStore/heavycult/processed/ordenes.json`.
- [ ] Notebook Databricks ejecutado `Run All` con 3× `[OK]`.
- [ ] Salidas verificadas: `job1/2/3_*_parquet/` + `*_csv/` en `dbfs:/FileStore/heavycult/curated/`.
- [ ] Capturas para informe (clúster, display, DBFS ls, re-lectura parquet).
- [ ] Sección "Migración Spark → Databricks" en README + referencia a este documento.

---

## 8. Troubleshooting Cloud

| Error | Causa | Solución |
|---|---|---|
| `Path does not exist: dbfs:/FileStore/...` | JSON no subido o ruta con mayúsculas | Verificar con `dbutils.fs.ls("dbfs:/FileStore/heavycult/processed/")`; respetar `input_path` del Widget |
| `AnalysisException: Unable to infer schema` | JSON vacío o single-line sin `multiline` | El script ya usa `.option("multiline","true")`; validar que el archivo subido sea el `ordenes.json` completo (~18 MB) |
| `dbutils is not defined` al probar local | Ejecución fuera de Databricks | Esperado: el script hace fallback a `os.getenv("INPUT_PATH")`; definirla o usar defaults |
| CSV Cloud es una carpeta, no un archivo | Comportamiento nativo Spark | Leer como directorio: `spark.read.option("header","true").csv("dbfs:/.../job1_metodos_pago_csv")`; descargar con `recurse=True` |
| Clúster tarda en iniciar | Cold start Community Edition | Esperar 3–5 min; no recrear el clúster; activar auto-terminate 30 min |
| `SparkContext should only be created once` | Llamar `SparkSession.builder...getOrCreate()` tras usar `spark` del notebook | El script reutiliza `spark` si existe (`_SPARK_PROVISTO`); no crear segunda sesión manualmente |

---

## 9. Referencias del repo

- Local: `scripts/batch/spark_jobs.py` — `crear_spark_session()` (`local[*]`, 2g, partitions 8), `obtener_ultimo_archivo_json()`, `toPandas → to_parquet/csv`.
- Cloud: `scripts/batch/spark_jobs_databricks.py` — sesión reutilizada, Widgets `input_path/output_base`, `df.write.parquet/csv("dbfs:/...")`, `display()` con fallback.
- Data Lake: `scripts/crear_data_lake.py`, `data_lake/{raw,processed,curated}/`.
- Orquestación/IaC: `terraform/`, `scripts/batch/data_warehouse.py`, `scripts/streaming/`.

*Generado para migración Local → Databricks. Última revisión: octubre 2026.*
