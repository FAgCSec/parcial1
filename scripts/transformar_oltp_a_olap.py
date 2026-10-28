import os
import pymongo
from dotenv import load_dotenv
import time

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")


def transformar_datos():

    print("[CLIQUEANDO] Transformando OLTP a OLAP en HeavyCult...\n")

    client = pymongo.MongoClient(MONGO_URI)

    # Base de datos correcta según crear_estructura_heavycult.py
    db = client["bd_erp"]

    inicio = time.time()

    pipeline = [

        # ============================================================
        # 1. Obtener información del cliente
        # ============================================================
        {
            "$lookup": {
                "from": "clientes",
                "localField": "customer_id",
                "foreignField": "_id",
                "as": "cliente_info"
            }
        },

        {
            "$unwind": "$cliente_info"
        },

        # ============================================================
        # 2. Separar los productos de la orden
        # ============================================================
        {
            "$unwind": "$items"
        },

        # ============================================================
        # 3. Obtener información del producto
        # ============================================================
        {
            "$lookup": {
                "from": "productos",
                "localField": "items.product_id",
                "foreignField": "_id",
                "as": "producto_info"
            }
        },

        {
            "$unwind": "$producto_info"
        },

        # ============================================================
        # 4. Construir documento analítico
        # ============================================================
        {
            "$project": {

                "_id": 0,

                "fecha_venta": "$created_at",

                "anio": {
                    "$year": "$created_at"
                },

                "mes": {
                    "$month": "$created_at"
                },

                "dia": {
                    "$dayOfMonth": "$created_at"
                },

                "order_number": 1,

                "cliente": {

                    "id": "$cliente_info._id",

                    "nombre": "$cliente_info.name",

                    "telefono": "$cliente_info.phone",

                    "ciudad": "$cliente_info.city",

                    "departamento": "$cliente_info.department"
                },

                "producto": {

                    "id": "$producto_info._id",

                    "nombre": "$items.product_name",

                    "sku": "$items.sku",

                    "categoria": "$producto_info.category"
                },

                "cantidad": "$items.quantity",

                "precio_unitario": "$items.unit_price",

                "total_venta": "$total_amount",

                "costo_proveedor": "$products_cost_total",

                "costo_flete": "$shipping_cost",

                "ganancia_neta": "$order_profit",

                "metodo_pago": "$payment_method",

                "estado": "$status"
            }
        },

        # ============================================================
        # 5. Guardar los datos transformados en OLAP
        # ============================================================
        {
            "$merge": {
                "into": "ventas_analiticas",
                "whenNotMatched": "insert"
            }
        }
    ]

    print("[ENGRAJE] Ejecutando Aggregation Pipeline ETL...")

    # La colección de origen ahora es "ordenes"
    db.ordenes.aggregate(
        pipeline,
        allowDiskUse=True
    )

    tiempo_total = time.time() - inicio

    total_analitico = db.ventas_analiticas.count_documents({})

    print("=" * 60)
    print("[CELEBRAR] TRANSFORMACION DE DATOS COMPLETA")
    print(f"[CRONOMETRO] Tiempo de procesamiento: {tiempo_total:.2f} segundos")
    print(
        f"[GRAFICO] Registros creados en ventas_analiticas: "
        f"{total_analitico}"
    )
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    transformar_datos()