import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def test_documentacion_existe():
    """Los documentos clave del parcial deben existir."""
    docs = [
        "docs/diccionario_datos.md",
        "docs/justificacion_volumen_datos.md",
        "docs/migracion_spark_databricks.md",
    ]
    for doc in docs:
        assert os.path.exists(os.path.join(BASE_DIR, doc)), f"Falta {doc}"

def test_estructura_data_lake():
    """Las tres zonas del data lake deben existir localmente."""
    for zona in ["raw", "processed", "curated"]:
        assert os.path.isdir(os.path.join(BASE_DIR, "data_lake", zona)), f"Falta data_lake/{zona}"

def test_scripts_existen():
    """Los scripts del pipeline deben existir."""
    scripts = [
        "scripts/crear_data_lake.py",
        "scripts/migrar_a_bigquery.py",
    ]
    for s in scripts:
        assert os.path.exists(os.path.join(BASE_DIR, s)), f"Falta {s}"

def test_no_credenciales_en_git():
    """Seguridad: el .env no debe estar trackeado por git."""
    assert not os.path.exists(os.path.join(BASE_DIR, ".git", "index.lock"))
    with open(os.path.join(BASE_DIR, ".gitignore"), encoding="utf-8") as f:
        contenido = f.read()
    assert ".env" in contenido
    assert "google-credentials.json" in contenido