import os
import pymongo
from dotenv import load_dotenv
from pymongo.errors import ConnectionFailure, ConfigurationError, OperationFailure

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError("MONGO_URI no está definida en el archivo .env")

def conectar_mongodb():
    try:
        client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')

        db = client["heavycult"]
        print("✅ Conexión exitosa a MongoDB Atlas")
        print(f"   Base de datos: heavycult")
        return client, db

    except ConnectionFailure:
        print("❌ Error de conexión: No se pudo conectar al servidor MongoDB")
        print("   Verifica tu MONGO_URI en el archivo .env")
    except ConfigurationError as e:
        print(f"❌ Error de configuración: {e}")
    except OperationFailure as e:
        print(f"❌ Error de autenticación/operación: {e}")
        print("   Verifica usuario/contraseña en MongoDB Atlas")

    return None, None

if __name__ == "__main__":
    client, db = conectar_mongodb()
    if client:
        client.close()
        print("🔌 Conexión cerrada correctamente")
