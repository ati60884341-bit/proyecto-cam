import os
import sys

DB_SERVER = os.environ.get("CAM_DB_SERVER", "localhost")
DB_NAME = os.environ.get("CAM_DB_NAME", "bd_cam_seguridad")
DB_DRIVER = os.environ.get("CAM_DB_DRIVER", "ODBC Driver 18 for SQL Server")
DB_USER = os.environ.get("CAM_DB_USER")
DB_PASSWORD = os.environ.get("CAM_DB_PASSWORD")

if DB_USER:
    # autenticacion SQL (usuario/clave): para laptops que se conectan por red
    # a un SQL Server central sin estar en el mismo dominio de Windows que
    # el servidor (Trusted_Connection no funciona entre maquinas de dominios
    # distintos, o sin dominio). Se activa definiendo CAM_DB_USER/CAM_DB_PASSWORD.
    _autenticacion = f"UID={DB_USER};PWD={DB_PASSWORD or ''};"
else:
    # por defecto: autenticacion de Windows (sirve cuando la app y el SQL
    # Server estan en la misma PC, como en desarrollo o en una demo local)
    _autenticacion = "Trusted_Connection=yes;"

CONNECTION_STRING = (
    f"DRIVER={{{DB_DRIVER}}};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_NAME};"
    f"{_autenticacion}"
    "TrustServerCertificate=yes;"
)

if getattr(sys, "frozen", False):
    # empaquetado con PyInstaller: la carpeta del .exe puede estar en
    # Program Files (sin permiso de escritura sin ser administrador), asi
    # que las evidencias se guardan en una carpeta de datos del usuario
    BASE_DIR = os.path.join(os.environ["LOCALAPPDATA"], "ProyectoCAM")
    # recursos estaticos empaquetados (manuales, etc.): van dentro del propio
    # .exe/carpeta de PyInstaller, NO en BASE_DIR (que es de solo escritura
    # de datos del usuario) - sys._MEIPASS apunta ahi tanto en --onefile
    # como en --onedir
    RECURSOS_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    RECURSOS_DIR = BASE_DIR

EVIDENCIAS_DIR = os.path.join(BASE_DIR, "evidencias")
os.makedirs(EVIDENCIAS_DIR, exist_ok=True)

MANUALES_DIR = os.path.join(RECURSOS_DIR, "app", "manuales")

# BUFFER_SEGUNDOS = segundos que guarda la "maquina del tiempo" antes de un sabotaje
BUFFER_SEGUNDOS = 8
CAPTURA_FPS = 10
UMBRAL_SABOTAJE = 35.0
INTERVALO_FATIGA_SEG = 90
TOLERANCIA_FATIGA_SEG = 15
