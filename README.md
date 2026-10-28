# Parcial BD Primer Corte - Arquitectura de Datos con MongoDB Atlas

Sistema de Ventas - Implementación Completa (OLTP + OLAP)

## 📋 Descripción del Proyecto

Este proyecto implementa una arquitectura de datos completa utilizando:
- **MongoDB Atlas** - Base de datos distribuida en la nube
- **MongoDB Compass** - Herramienta visual de administración
- **Python + PyMongo** - Lenguaje de programación y driver
- **VS Code** - Entorno de desarrollo

### Modelo de Datos

**OLTP (Transaccional - Normalizado):**
- `clientes` - Información de clientes
- `productos` - Catálogo de productos
- `ventas` - Transacciones de ventas con items embebidos

**OLAP (Analítico - Dimensional/Desnormalizado):**
- `ventas_analiticas` - Modelo estrella con dimensiones cliente, producto, tiempo y hechos de venta

---

## 🚀 Requisitos Previos

### 1. Cuenta de MongoDB Atlas
1. Regístrate en [MongoDB Atlas](https://www.mongodb.com/atlas)
2. Crea un cluster gratuito (M0) o compartido (M10 para mejor rendimiento)
3. Configura un usuario de base de datos con permisos de **lectura/escritura**
4. En **Network Access**, agrega `0.0.0.0/0` (permitir desde cualquier IP) o tu IP específica
5. Obtén la **Connection String** (mongodb+srv://...)

### 2. Python 3.8+
Verifica tu versión:
```bash
python --version
```

### 3. VS Code (Recomendado)
- Extensión **Python** instalada
- Extensión **MongoDB for VS Code** (opcional)

---

## 📦 Instalación

### 1. Clonar/Descargar el proyecto
```bash
cd "C:\Users\User hp\Documents\ITP\8VO SMESTRE\am\parcial1"
```

### 2. Crear entorno virtual (Recomendado)
```bash
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1

# O en Command Prompt (cmd)
python -m venv venv
venv\Scripts\activate.bat
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
```bash
# Copia el archivo de ejemplo
copy .env.example .env
```

**Edita el archivo `.env`** con tu connection string real:
```env
MONGO_URI=mongodb+srv://TU_USUARIO:TU_PASSWORD@TU_CLUSTER.mongodb.net/?retryWrites=true&w=majority
```

> ⚠️ **IMPORTANTE**: Reemplaza `TU_USUARIO`, `TU_PASSWORD` y `TU_CLUSTER` con tus credenciales reales de MongoDB Atlas.

---

## 🔧 Ejecución Paso a Paso

### Fase 1: Verificar Conexión
```bash
python conexion.py
```
**Salida esperada:**
```
✅ Conexión exitosa a MongoDB Atlas
   Base de datos: ventas_db
🔌 Conexión cerrada correctamente
```

---

### Fase 2: Crear Estructura de Base de Datos
```bash
python scripts/crear_estructura.py
```
**Qué hace:**
- Crea colecciones OLTP: `clientes`, `productos`, `ventas`
- Crea índices únicos en `email` y `sku`
- Crea índices en `fecha_venta` y `cliente_id`
- Inserta datos de prueba (1 cliente, 1 producto, 1 venta)
- Crea colección OLAP: `ventas_analiticas`

**Salida esperada:**
```
📁 1. Creando colecciones OLTP...
   ✅ Colección 'clientes' creada
   ✅ Colección 'productos' creada
   ✅ Colección 'ventas' creada

🔍 2. Creando índices...
   ✅ Índice único en clientes.email
   ✅ Índice único en productos.sku
   ✅ Índice en ventas.fecha_venta (descendente)
   ✅ Índice en ventas.cliente_id

📝 3. Insertando datos de prueba...
   ✅ Cliente insertado con ID: ...
   ✅ Producto insertado con ID: ...
   ✅ Venta insertada con ID: ...

📊 4. Creando colección OLAP...
   ✅ Colección 'ventas_analiticas' creada

✅ ESTRUCTURA CREADA EXITOSAMENTE
```

---

### Fase 3: Generar Datos Masivos
```bash
python scripts/generar_datos_masivos.py
```
**Qué hace:**
- Genera **5,000 clientes** con datos colombianos reales (Faker)
- Genera **1,000 productos** en 6 categorías
- Genera **50,000 ventas** con items aleatorios (1-5 items por venta)
- Usa **Batch Insert** de 1,000 documentos para eficiencia
- Ignora duplicados con `ordered=False`

**Duración estimada:** 2-5 minutos según conexión

**Salida esperada:**
```
👥 1. GENERANDO CLIENTES...
   📦 clientes: 1000/5000 (1000 insertados en este lote)
   ...
   ✅ Total clientes insertados: 5000

📦 2. GENERANDO PRODUCTOS...
   ✅ Total productos insertados: 1000

💰 3. GENERANDO VENTAS...
   📦 ventas (lote): 1000/50000 (1000 insertados en este lote)
   ...
   ✅ Total ventas insertadas: 50000

📈 RESUMEN DE GENERACIÓN
   • Clientes totales en BD: 5,000
   • Productos totales en BD: 1,000
   • Ventas totales en BD: 50,000
   • Tiempo total: 120.45 segundos
```

---

### Fase 4: Transformar OLTP → OLAP
```bash
python scripts/transformar_oltp_a_olap.py
```
**Qué hace:**
- Ejecuta **Aggregation Pipeline** con `$lookup` (JOIN) y `$unwind`
- Une `ventas` → `clientes` → `productos` (por items)
- Crea modelo dimensional con:
  - **Dimensión Tiempo**: año, mes, día
  - **Dimensión Cliente**: nombre, ciudad, segmento (Premium/Frecuente/Regular)
  - **Dimensión Producto**: nombre, categoría, marca
  - **Hechos**: cantidad, precio_unitario, total_venta, ganancia_estimada (15%)
- Guarda en `ventas_analiticas` usando `$merge`
- Usa `allowDiskUse: true` para escalabilidad

**Duración estimada:** 1-3 minutos

**Salida esperada:**
```
📥 Datos de origen: 50,000 ventas en colección OLTP
⚙️  Ejecutando pipeline de agregación...
✅ TRANSFORMACIÓN COMPLETADA
   • Documentos procesados: 127,432
   • Total en ventas_analiticas: 127,432
   • Tiempo de ejecución: 45.32 segundos
```

> Nota: Una venta con 3 items genera 3 documentos en OLAP (uno por item)

---

### Fase 5: Benchmarking y Optimización
```bash
python scripts/benchmarking_consultas.py
```
**Qué hace:**
- Crea 4 índices compuestos optimizados
- Ejecuta 5 consultas analíticas típicas (3 veces cada una, promedia)
- Mide latencia en milisegundos
- Evalúa rendimiento general

**Consultas evaluadas:**
1. Ventas totales mensuales
2. Top 5 Productos por Categoría
3. Rendimiento por Segmento y Ciudad
4. Ticket Promedio por Método de Pago
5. Ventas por Día de la Semana

**Salida esperada:**
```
🔧 1. CREANDO ÍNDICES COMPUESTOS...
   ✅ Índice 'idx_fecha' creado
   ✅ Índice 'idx_categoria_venta' creado
   ✅ Índice 'idx_segmento_ciudad' creado
   ✅ Índice 'idx_estado_segmento_ciudad' creado

📈 2. EJECUTANDO CONSULTAS ANALÍTICAS...
----------------------------------------------------------------------
CONSULTA                                        TIEMPO (ms)  RESULTADOS
----------------------------------------------------------------------
1. Ventas totales mensuales                          45.23         12
2. Top 5 Productos por Categoría                    123.45          6
3. Rendimiento por Segmento y Ciudad                 67.89         18
4. Ticket Promedio por Método de Pago                34.12          6
5. Ventas por Día de la Semana                       28.67          7
----------------------------------------------------------------------

📋 RESUMEN DE RENDIMIENTO
   • Consultas ejecutadas: 5
   • Latencia promedio: 59.87 ms
   • Latencia mínima: 28.67 ms
   • Latencia máxima: 123.45 ms
   • Documentos analizados: 127,432
======================================================================
🟢 EXCELENTE: Latencias < 100ms - Sistema optimizado para tiempo real
======================================================================
```

---

## 📁 Estructura del Proyecto

```
parcial1/
├── .env                      # Variables de entorno (NO subir a git)
├── .env.example              # Plantilla de configuración
├── requirements.txt          # Dependencias Python
├── conexion.py               # Fase 1: Verificación de conexión
├── README.md                 # Esta documentación
└── scripts/
    ├── crear_estructura.py   # Fase 2: Estructura BD + índices
    ├── generar_datos_masivos.py  # Fase 3: Datos sintéticos (50k+ ventas)
    ├── transformar_oltp_a_olap.py # Fase 4: ETL con Aggregation Pipeline
    └── benchmarking_consultas.py  # Fase 5: Índices + Benchmarking
```

---

## ☁️ Migración de Spark Local a Databricks (Entorno Enterprise)

> **Nuevo:** versión Cloud-ready en `scripts/batch/spark_jobs_databricks.py` + guía completa en `docs/migracion_spark_databricks.md`.

| | Local (desarrollo Windows) | Cloud (producción) |
|---|---|---|
| Script | `scripts/batch/spark_jobs.py` | `scripts/batch/spark_jobs_databricks.py` |
| Sesión | `.master("local[*]")` + `winutils.exe` + `PYSPARK_SUBMIT_ARGS` | Sesión del clúster (Linux), sin `local[*]`, sin winutils |
| I/O | `glob` local + `toPandas()` + `pandas.to_parquet/csv` (patrón híbrido) | `spark.read.json("dbfs:/...")` + `df.write.parquet("dbfs:/...")` / `.csv("dbfs:/...")` nativo distribuido |
| Rutas | `data_lake/processed/*.json` → `data_lake/curated/` | `dbfs:/FileStore/heavycult/processed/ordenes.json` → `dbfs:/FileStore/heavycult/curated/` (o `s3://` en EMR) |

**Ejecución local (actual):**
```bash
python scripts/batch/spark_jobs.py
```

**Ejecución Cloud (Databricks Community Edition, $0):**
1. Subir `data_lake/processed/ordenes.json` a `dbfs:/FileStore/heavycult/processed/ordenes.json`.
2. Crear Notebook Python, pegar `scripts/batch/spark_jobs_databricks.py` por celdas (usa Widgets `input_path` / `output_base`).
3. `Run All` → verificar `job1/2/3_*_parquet/` y `*_csv/` en `dbfs:/FileStore/heavycult/curated/` con `spark.read.parquet("dbfs:/...")` + `display()`.

Justificación técnica, comparativa de código, paso a paso con capturas esperadas y guía para el informe final: ver **`docs/migracion_spark_databricks.md`**.

---

## 🐛 Troubleshooting Común

| Error | Causa | Solución |
|-------|-------|----------|
| `bad auth: authentication failed` | Contraseña incorrecta en .env | Verifica usuario/contraseña en Atlas |
| `connection timeout` | IP no permitida / Firewall | Agrega `0.0.0.0/0` en Network Access |
| `E11000 duplicate key error` | Valor único duplicado | Usa `insert_many(datos, ordered=False)` |
| `Expression $cond takes exactly 3 arguments` | $cond mal anidado | Anida `$cond` dentro de otro `$cond` |
| `The field must specify one accumulator` | $slice en $group | Mueve `$slice` a `$project` posterior |
| Consultas lentas (> 1s) | Falta de índices | Crea índices compuestos que cubran `$match` y `$sort` |

---

## 📝 Entregables Esperados

Al completar todas las fases, tendrás:

- [x] Conexión a MongoDB Atlas verificada
- [x] Colecciones OLTP creadas (`clientes`, `productos`, `ventas`)
- [x] Índices únicos creados (`email`, `sku`)
- [x] Datos masivos generados (50,000+ ventas → ~127k items OLAP)
- [x] Transformación ETL completada (OLTP → OLAP)
- [x] Índices compuestos creados en colección OLAP
- [x] Benchmarking ejecutado con latencias < 500ms
- [x] Documentación técnica completada

---

## 💡 Conceptos Clave Implementados

### Ingesta por Lotes (Batch Insert)
> "Se implementó el patrón de Batch Insert con tamaño de chunk de 1,000 documentos. Esta decisión arquitectónica reduce la sobrecarga de red y el consumo de memoria RAM, alineándose con las mejores prácticas de procesamiento de datos a escala."

### Transformación ETL con Aggregation Pipeline
> "Se utilizó el Aggregation Pipeline nativo de MongoDB con las etapas `$lookup` (JOIN) y `$unwind` para transformar datos normalizados (OLTP) en un modelo dimensional desnormalizado (OLAP). Se habilitó `allowDiskUse: true` para garantizar escalabilidad en operaciones que superan los 100MB de RAM."

### Indexación Compuesta
> "Se implementó una estrategia de índices Compuestos (`idx_fecha`, `idx_categoria_venta`, `idx_estado_segmento_ciudad`) que permite resolver operaciones de filtrado y ordenamiento sin escaneos completos de colección, reduciendo la complejidad de O(N) a O(log N)."

---

## 📞 Soporte

Si encuentras problemas:
1. Revisa la sección **Troubleshooting** arriba
2. Verifica que tu `.env` tenga la URI correcta
3. Confirma que el cluster Atlas esté **activo** (no en pausa)
4. Ejecuta `python conexion.py` para diagnosticar conexión

---

**¡Éxitos con tu parcial!** 🎓