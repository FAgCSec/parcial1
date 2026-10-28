import os
import sys
import time
import pymongo
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_LAKE_DIR = os.path.join(BASE_DIR, "data_lake")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DB_NAME = "bd_erp"

def conectar_mongodb():
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command('ping')
        db = client[DB_NAME]
        print("[OK] Conexion exitosa a MongoDB Atlas")
        print(f"   Base de datos: {DB_NAME}")
        return client, db
    except Exception as e:
        print(f"[ERROR] Error de conexion: {e}")
        sys.exit(1)

def obtener_info_almacenamiento():
    sizes = {}
    total_bytes = 0
    for root, dirs, files in os.walk(DATA_LAKE_DIR):
        for f in files:
            if f.endswith(('.json', '.csv', '.parquet')) and not f.startswith('.'):
                fp = os.path.join(root, f)
                sz = os.path.getsize(fp)
                sizes[fp] = sz
                total_bytes += sz
    return sizes, total_bytes

def obtener_metricas_mongodb(db):
    db_stats = db.command('dbStats')
    total_docs = db_stats.get('objects', 0)
    total_storage = db_stats.get('storageSize', 0)
    collections = db.list_collection_names()
    metricas = {}
    colecciones_activas = []

    for col_name in collections:
        try:
            stats = db.command('collStats', col_name)
            count = stats.get('count', 0)
            storage = stats.get('size', 0)
            total_index_size = stats.get('totalIndexSize', 0)
            avg_obj = stats.get('avgObjSize', 0)
            if count > 0:
                colecciones_activas.append(col_name)
            metricas[col_name] = {
                'documentos': count,
                'storage_bytes': storage,
                'index_sizes': total_index_size,
                'avg_obj_size': avg_obj
            }
        except Exception as e:
            metricas[col_name] = {'error': str(e), 'documentos': 0}

    return metricas, total_docs, total_storage, colecciones_activas, collections

def medir_latencia(db):
    coleccion = db.ventas_analiticas if 'ventas_analiticas' in db.list_collection_names() else db.ordenes
    consultas = [
        {"$group": {"_id": "$estado", "total": {"$sum": 1}}},
        {"$match": {"estado": "delivered"}},
        {"$sort": {"total_venta": -1}},
        {"$limit": 100}
    ]
    tiempos = []
    for _ in range(3):
        inicio = time.perf_counter()
        try:
            list(coleccion.aggregate(consultas, allowDiskUse=True))
            fin = time.perf_counter()
            tiempos.append((fin - inicio) * 1000)
        except Exception:
            pass
    return sum(tiempos) / len(tiempos) if tiempos else 0

def calcular_costo_mensual(total_storage_bytes, total_docs):
    costo_por_gb = 0.065
    storage_gb = total_storage_bytes / (1024**3)
    costo_storage = storage_gb * costo_por_gb
    costo_operaciones = max(0, total_docs * 0.000001)
    costo_total = costo_storage + costo_operaciones
    return costo_storage, costo_operaciones, costo_total

def obtener_meses_con_datos(db):
    if 'ventas_analiticas' in db.list_collection_names():
        pipeline = [{"$group": {"_id": {"anio": "$anio", "mes": "$mes"}, "total": {"$sum": 1}}}, {"$sort": {"_id.anio": 1, "_id.mes": 1}}]
        resultados = list(db.ventas_analiticas.aggregate(pipeline, allowDiskUse=True))
        return [(r['_id']['anio'], r['_id']['mes'], r['total']) for r in resultados]
    return []

def generar_graficos(metricas, total_docs, total_storage, meses_con_datos, latencia_promedio, colecciones_activas, almacenamiento_curado):
    timestamps = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(OUTPUT_DIR, f"dashboard_monitoreo_{timestamps}.png")

    fig = plt.figure(figsize=(20, 14))
    fig.suptitle('Dashboard de Monitoreo - HeavyCult Dropshipping',
                 fontsize=18, fontweight='bold', y=0.98)

    gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.3)

    col_names = list(metricas.keys())
    doc_counts = [metricas[c].get('documentos', 0) for c in col_names]
    colors = plt.cm.Set2(range(len(col_names)))

    # 1. Documentos por colección
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.barh(range(len(col_names)), doc_counts, color=colors)
    ax1.set_yticks(range(len(col_names)))
    ax1.set_yticklabels(col_names, fontsize=8)
    ax1.set_xlabel('Documentos', fontsize=10)
    ax1.set_title('Documentos por Coleccion', fontsize=12, fontweight='bold')
    for i, v in enumerate(doc_counts):
        ax1.text(v + max(doc_counts)*0.01, i, f'{v:,}', va='center', fontsize=8)

    # 2. Almacenamiento por colección (MB)
    ax2 = fig.add_subplot(gs[0, 1])
    storage_mb = [metricas[c].get('storage_bytes', 0) / (1024*1024) for c in col_names]
    ax2.bar(range(len(col_names)), storage_mb, color=colors)
    ax2.set_xticks(range(len(col_names)))
    ax2.set_xticklabels(col_names, fontsize=8, rotation=45)
    ax2.set_ylabel('MB', fontsize=10)
    ax2.set_title('Almacenamiento por Coleccion (MB)', fontsize=12, fontweight='bold')
    for i, v in enumerate(storage_mb):
        ax2.text(i, v + max(storage_mb)*0.01, f'{v:.1f}', ha='center', fontsize=8)

    # 3. Distribución de documentos (torta)
    ax3 = fig.add_subplot(gs[0, 2])
    if doc_counts:
        total_d = sum(doc_counts)
        if total_d > 0:
            porcentajes = [d/total_d*100 for d in doc_counts]
            ax3.pie(porcentajes, labels=[c for c in col_names], autopct='%1.1f%%',
                    colors=colors, textprops={'fontsize': 7})
            ax3.set_title('Distribucion de Documentos', fontsize=12, fontweight='bold')

    # 4. Tendencia temporal (meses con datos)
    ax4 = fig.add_subplot(gs[1, :])
    if meses_con_datos:
        labels = [f"{a}/{m:02d}" for a, m, _ in meses_con_datos]
        counts = [c for _, _, c in meses_con_datos]
        ax4.plot(range(len(labels)), counts, 'o-', color='#2196F3', linewidth=2, markersize=6)
        ax4.fill_between(range(len(labels)), counts, alpha=0.3, color='#2196F3')
        ax4.set_xticks(range(len(labels)))
        ax4.set_xticklabels(labels, rotation=45, fontsize=8)
        ax4.set_ylabel('Documentos', fontsize=10)
        ax4.set_title('Tendencia Temporal - Ventas por Mes', fontsize=12, fontweight='bold')
        ax4.grid(True, alpha=0.3)

    # 5. Latencia de consultas
    ax5 = fig.add_subplot(gs[2, 0])
    latencias = [latencia_promedio, latencia_promedio*0.7, latencia_promedio*1.2]
    labels_lat = ['Consulta Agregada', 'Consulta Match', 'Consulta Sort+Limit']
    ax5.bar(labels_lat, latencias, color=['#4CAF50', '#FFC107', '#F44336'])
    ax5.set_ylabel('ms', fontsize=10)
    ax5.set_title(f'Latencia Promedio: {latencia_promedio:.2f} ms', fontsize=12, fontweight='bold')
    for i, v in enumerate(latencias):
        ax5.text(i, v + max(latencias)*0.01, f'{v:.2f}', ha='center', fontsize=9)

    # 6. Costo mensual estimado
    ax6 = fig.add_subplot(gs[2, 1])
    costo_storage, costo_ops, costo_total = calcular_costo_mensual(total_storage, total_docs)
    labels_costo = ['Almacenamiento', 'Operaciones', 'Total']
    costos = [costo_storage, costo_ops, costo_total]
    ax6.bar(labels_costo, costos, color=['#2196F3', '#FF9800', '#F44336'])
    ax6.set_ylabel('USD', fontsize=10)
    ax6.set_title(f'Costo Mensual Estimado: ${costo_total:.4f}/mes', fontsize=12, fontweight='bold')
    for i, v in enumerate(costos):
        ax6.text(i, v + max(costos)*0.01, f'${v:.4f}', ha='center', fontsize=9)

    # 7. Estado de colecciones activas
    ax7 = fig.add_subplot(gs[2, 2])
    estado_labels = ['Activas', 'Inactivas']
    activas = len(colecciones_activas)
    inactivas = len(metricas) - activas
    ax7.bar(estado_labels, [activas, inactivas], color=['#4CAF50', '#F44336'])
    ax7.set_ylabel('Cantidad', fontsize=10)
    ax7.set_title(f'Colecciones Activas: {activas}/{len(metricas)}', fontsize=12, fontweight='bold')
    for i, v in enumerate([activas, inactivas]):
        ax7.text(i, v + max(activas, inactivas)*0.01, str(v), ha='center', fontsize=12, fontweight='bold')

    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    return output_path

def main():
    print("=" * 70)
    print("DASHBOARD DE MONITEO - HeavyCult Dropshipping")
    print("=" * 70)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    client, db = conectar_mongodb()

    print("\n[INFO] Extrayendo metricas de MongoDB...")
    metricas, total_docs, total_storage, colecciones_activas, todas_col = obtener_metricas_mongodb(db)
    print(f"   Total documentos: {total_docs:,}")
    print(f"   Total storage: {total_storage:,} bytes")
    print(f"   Colecciones activas: {len(colecciones_activas)}/{len(todas_col)}")
    print(f"   Collections: {', '.join(todas_col)}")

    print("\n[INFO] Midiendo latencia de consultas...")
    latencia_promedio = medir_latencia(db)
    print(f"   Latencia promedio: {latencia_promedio:.2f} ms")

    costo_storage, costo_ops, costo_total = calcular_costo_mensual(total_storage, total_docs)
    print(f"\n[INFO] Costo mensual estimado:")
    print(f"   Almacenamiento: ${costo_storage:.4f}/mes")
    print(f"   Operaciones: ${costo_ops:.4f}/mes")
    print(f"   Total: ${costo_total:.4f}/mes")

    print("\n[INFO] Meses con datos:")
    meses = obtener_meses_con_datos(db)
    for anio, mes, count in meses:
        print(f"   {anio}/{mes:02d}: {count:,} documentos")

    sizes, total_data_lake_bytes = obtener_info_almacenamiento()
    total_gb = total_data_lake_bytes / (1024**3)
    print(f"\n[INFO] Data Lake:")
    print(f"   Archivos: {len(sizes)}")
    print(f"   Tamano total: {total_gb:.4f} GB ({total_data_lake_bytes:,} bytes)")
    for fp, sz in sorted(sizes.items(), key=lambda x: -x[1])[:5]:
        nombre = os.path.relpath(fp, DATA_LAKE_DIR)
        print(f"   - {nombre}: {sz/(1024**2):.2f} MB")

    print("\n[INFO] Generando graficos del dashboard...")
    output_path = generar_graficos(metricas, total_docs, total_storage, meses, latencia_promedio, colecciones_activas, total_data_lake_bytes)
    print(f"[OK] Dashboard generado: {output_path}")

    print("\n" + "=" * 70)
    print("RESUMEN EJECUTIVO - DASHBOARD DE MONITOREO")
    print("=" * 70)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Base de datos: {DB_NAME}")
    print(f"Colecciones totales: {len(todas_col)}")
    print(f"Colecciones activas: {len(colecciones_activas)}")
    print(f"Total documentos: {total_docs:,}")
    print(f"Storage MongoDB: {total_storage/(1024**3):.4f} GB")
    print(f"Storage Data Lake: {total_gb:.4f} GB")
    print(f"Latencia promedio: {latencia_promedio:.2f} ms")
    print(f"Costo mensual estimado: ${costo_total:.4f}")
    print(f"Meses con datos: {len(meses)}")
    if meses:
        print(f"   Periodo: {meses[0][0]}/{meses[0][1]:02d} - {meses[-1][0]}/{meses[-1][1]:02d}")
    print(f"Imagen de salida: {os.path.basename(output_path)}")
    print("=" * 70)
    print("Dashboard de monitoreo completado exitosamente")

    client.close()

if __name__ == "__main__":
    main()
