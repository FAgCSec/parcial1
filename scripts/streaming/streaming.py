import os
import sys
import pymongo
import time
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

MONGO_URI = os.getenv("MONGO_URI")

def simular_streaming_kafka():
    print("==================================================")
    print("🚀 Iniciando pipeline de Event Streaming (CDC)...")
    print("🛰️ Escuchando cambios en MongoDB Atlas (Simulación Kafka Consumer)")
    print("==================================================\n")

    client = pymongo.MongoClient(MONGO_URI)
    db = client["bd_erp"]

    with db.ordenes.watch() as stream:
        contador = 0
        try:
            for change in stream:
                contador += 1
                hora_actual = datetime.now().strftime("%H:%M:%S")
                operacion = change["operationType"]

                if operacion == "insert":
                    doc = change["fullDocument"]
                    orden_num = doc.get("order_number", "N/A")
                    total = doc.get("total_amount", 0)

                    print(f"[{hora_actual}] 🟢 INSERT | Órden: {orden_num} | Total: ${total:,.2f}")

                    if total > 200000:
                        print(f"   🚨 ALERT: ¡Venta de alto valor detectada! (${total:,.2f})")

                elif operacion == "update":
                    doc_id = change["documentKey"]["_id"]
                    campos_modificados = change.get("updateDescription", {}).get("updatedFields", {})
                    print(f"[{hora_actual}] 🟡 UPDATE | ID: {doc_id} | Cambios: {campos_modificados}")

                elif operacion == "delete":
                    doc_id = change["documentKey"]["_id"]
                    print(f"[{hora_actual}] 🔴 DELETE | Registro eliminado ID: {doc_id}")

                if contador % 10 == 0:
                    print(f"\n📦 [MICRO-BATCH] Procesados {contador} eventos en tiempo real...\n")

        except KeyboardInterrupt:
            print("\n🛑 Stream detenido manualmente por el usuario.")
            client.close()
            print("🔒 Conexión con MongoDB cerrada correctamente.")

if __name__ == "__main__":
    simular_streaming_kafka()
