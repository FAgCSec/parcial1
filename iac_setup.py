import argparse
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
ENV_FILE = BASE_DIR / ".env"
REQUIREMENTS_FILE = BASE_DIR / "requirements.txt"
VENV_DIR = BASE_DIR / "venv"


def check_python_version():
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"Python {version.major}.{version.minor} detectado.")
        print("Se requiere Python 3.8 o superior.")
        return False
    print(f"Python {version.major}.{version.minor}.{version.micro} - OK")
    return True


def ensure_venv():
    if VENV_DIR.exists():
        print(f"Entorno virtual ya existe en {VENV_DIR}")
        return VENV_DIR
    print(f"Creando entorno virtual en {VENV_DIR}...")
    subprocess.run(
        [sys.executable, "-m", "venv", str(VENV_DIR)],
        check=True,
        capture_output=True,
        text=True,
    )
    print("Entorno virtual creado exitosamente")
    return VENV_DIR


def get_python_executable():
    if sys.platform.startswith("win"):
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def install_dependencies():
    python_exec = get_python_executable()
    if not python_exec.exists():
        print("Ejecutable de Python del venv no encontrado")
        return False
    if not REQUIREMENTS_FILE.exists():
        print(f"Archivo {REQUIREMENTS_FILE} no encontrado")
        return False
    print(f"Instalando dependencias desde {REQUIREMENTS_FILE}...")
    subprocess.run(
        [str(python_exec), "-m", "pip", "install", "--upgrade", "pip"],
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        [str(python_exec), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Error instalando dependencias")
        print(result.stderr)
        return False
    print("Dependencias instaladas exitosamente")
    return True


def provision_data_lake():
    folders = [
        BASE_DIR / "data_lake" / "raw",
        BASE_DIR / "data_lake" / "processed",
        BASE_DIR / "data_lake" / "curated",
    ]
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
        print(f"Carpeta asegurada: {folder}")
    print("Estructura del Data Lake lista")
    return True


def health_check():
    if not ENV_FILE.exists():
        print(f"Archivo {ENV_FILE} no encontrado")
        print("Copia .env.example y configura tu MONGO_URI")
        return False
    print("Archivo .env encontrado")
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=ENV_FILE)
    except Exception:
        pass
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        print("MONGO_URI no definida en .env")
        return False
    print("Realizando ping a MongoDB Atlas...")
    try:
        import pymongo
        client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        result = client.admin.command("ping")
        print("Conexion exitosa a MongoDB Atlas")
        client.close()
        return True
    except ImportError:
        print("pymongo no instalado aun")
        return False
    except Exception as e:
        print(f"Error conectando a MongoDB Atlas: {e}")
        return False


def simulate_launch():
    print("\n" + "="*60)
    print("SIMULACION: Levantando entorno de trabajo")
    print("="*60)
    steps = [
        ("Verificar Python", check_python_version),
        ("Crear/Validar venv", lambda: ensure_venv().exists()),
        ("Instalar dependencias", install_dependencies),
        ("Provisionar Data Lake", provision_data_lake),
        ("Health Check", health_check),
    ]
    all_passed = True
    for step_name, step_func in steps:
        print(f"  {step_name}...")
        try:
            result = step_func()
            if result is False:
                all_passed = False
                print(f"  Fallo: {step_name}")
        except Exception as e:
            all_passed = False
            print(f"  Error: {step_name} - {e}")
    print("="*60 + "\n")
    return all_passed


def main():
    parser = argparse.ArgumentParser(
        description="Setup infraestructura y orquestacion como codigo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--auto-approve", action="store_true")
    parser.add_argument("--simulate", action="store_true")
    args = parser.parse_args()
    if args.simulate:
        print("mode: Simulacion activa - no se realizaran cambios")
        success = simulate_launch()
        sys.exit(0 if success else 1)
    print("="*60)
    print("IAC Setup - Infraestructura y Orquestacion como codigo")
    print("="*60)
    if not check_python_version():
        sys.exit(1)
    venv_path = ensure_venv()
    if not install_dependencies():
        sys.exit(1)
    provision_data_lake()
    if not health_check():
        print("Health Check con advertencias")
    print("="*60)
    print("Configuracion completada exitosamente")
    print("="*60)
    print("\nProximos pasos:")
    print("  1. Ejecuta: python conexion.py")
    print("  2. Ejecuta: python scripts/crear_estructura.py")
    print("  3. Ejecuta: python scripts/generar_datos_masivos.py")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()