import os
import sys
import pymongo
from dotenv import load_dotenv
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

MONGO_URI = os.getenv("MONGO_URI")

def conectar_bd():
    client = pymongo.MongoClient(MONGO_URI)
    return client, client["bd_erp"]

def construir_data_warehouse():
    print("==================================================")
    print("🏗 CONSTRUYENDO DATA WAREHOUSE (MODELO ESTRELLA)")
    print("==================================================\n")

    client, db = conectar_bd()
    inicio = time.time()

    colecciones_dw = ["dim_tiempo", "dim_cliente", "dim_producto", "fact_ventas"]
    for col in colecciones_dw:
        db[col].drop()

    print("[1/4] Generando dim_tiempo...")
    pipeline_tiempo = [
        {"$group": {
            "_id": {
                "fecha": "$fecha_venta",
                "anio": "$anio",
                "mes": "$mes",
                "dia": "$dia"
            }
        }},
        {"$project": {
            "_id": "$_id.fecha",
            "fecha": "$_id.fecha",
            "anio": "$_id.anio",
            "mes": "$_id.mes",
            "dia": "$_id.dia",
            "trimestre": {"$ceil": {"$divide": ["$_id.mes", 3]}},
            "es_fin_semana": {
                "$cond": [
                    {"$in": [{"$dayOfWeek": "$_id.fecha"}, [1, 7]]},
                    True,
                    False
                ]
            }
        }},
        {"$merge": {"into": "dim_tiempo", "whenNotMatched": "insert"}}
    ]
    db.ventas_analiticas.aggregate(pipeline_tiempo, allowDiskUse=True)

    print("[2/4] Generando dim_cliente...")
    pipeline_cliente = [
        {"$group": {
            "_id": "$cliente.id",
            "nombre": {"$first": "$cliente.nombre"},
            "telefono": {"$first": "$cliente.telefono"},
            "ciudad": {"$first": "$cliente.ciudad"},
            "departamento": {"$first": "$cliente.departamento"},
            "total_compras": {"$sum": 1},
            "gasto_historico": {"$sum": "$total_venta"},
            "ticket_promedio": {"$avg": "$total_venta"}
        }},
        {"$project": {
            "_id": 1,
            "cliente_id": "$_id",
            "nombre": 1,
            "telefono": 1,
            "ciudad": 1,
            "departamento": 1,
            "total_compras": 1,
            "gasto_historico": {"$round": ["$gasto_historico", 2]},
            "ticket_promedio": {"$round": ["$ticket_promedio", 2]}
        }},
        {"$merge": {"into": "dim_cliente", "whenNotMatched": "insert"}}
    ]
    db.ventas_analiticas.aggregate(pipeline_cliente, allowDiskUse=True)

    print("[3/4] Generando dim_producto...")
    pipeline_producto = [
        {"$group": {
            "_id": "$producto.id",
            "nombre_producto": {"$first": "$producto.nombre"},
            "categoria": {"$first": "$producto.categoria"},
            "sku": {"$first": "$producto.sku"},
            "unidades_vendidas": {"$sum": "$cantidad"},
            "ingresos_generados": {"$sum": "$total_venta"}
        }},
        {"$project": {
            "_id": 1,
            "producto_id": "$_id",
            "nombre_producto": 1,
            "categoria": 1,
            "sku": 1,
            "unidades_vendidas": 1,
            "ingresos_generados": {"$round": ["$ingresos_generados", 2]}
        }},
        {"$merge": {"into": "dim_producto", "whenNotMatched": "insert"}}
    ]
    db.ventas_analiticas.aggregate(pipeline_producto, allowDiskUse=True)

    print("[4/4] Generando fact_ventas (Tabla de Hechos)...")
    pipeline_fact = [
        {"$project": {
            "_id": 1,
            "order_number": 1,
            "fecha_id": "$fecha_venta",
            "cliente_id": "$cliente.id",
            "producto_id": "$producto.id",
            "cantidad": 1,
            "precio_unitario": 1,
            "total_venta": 1,
            "costo_proveedor": 1,
            "costo_flete": 1,
            "ganancia_neta": 1,
            "metodo_pago": 1,
            "estado": 1
        }},
        {"$merge": {"into": "fact_ventas", "whenNotMatched": "insert"}}
    ]
    db.ventas_analiticas.aggregate(pipeline_fact, allowDiskUse=True)

    tiempo_total = time.time() - inicio
    print("\n==================================================")
    print(f" DATA WAREHOUSE CONFIGURADO ({tiempo_total:.2f}s)")
    print("==================================================")
    print(f"   dim_tiempo:   {db.dim_tiempo.count_documents({})} registros")
    print(f"   dim_cliente:  {db.dim_cliente.count_documents({})} registros")
    print(f"   dim_producto: {db.dim_producto.count_documents({})} registros")
    print(f"   fact_ventas:  {db.fact_ventas.count_documents({})} registros")
    print("==================================================")
    client.close()

if __name__ == "__main__":
    construir_data_warehouse()
