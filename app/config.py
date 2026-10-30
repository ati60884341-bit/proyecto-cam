import os

DB_SERVER = os.environ.get("CAM_DB_SERVER", "localhost")
DB_NAME = os.environ.get("CAM_DB_NAME", "bd_cam_seguridad")
DB_DRIVER = os.environ.get("CAM_DB_DRIVER", "ODBC Driver 18 for SQL Server")

CONNECTION_STRING = (
    f"DRIVER={{{DB_DRIVER}}};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_NAME};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVIDENCIAS_DIR = os.path.join(BASE_DIR, "evidencias")
os.makedirs(EVIDENCIAS_DIR, exist_ok=True)

# BUFFER_SEGUNDOS = segundos que guarda la "maquina del tiempo" antes de un sabotaje
BUFFER_SEGUNDOS = 8
CAPTURA_FPS = 10
UMBRAL_SABOTAJE = 35.0
INTERVALO_FATIGA_SEG = 90
TOLERANCIA_FATIGA_SEG = 15
