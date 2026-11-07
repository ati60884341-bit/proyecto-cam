# -*- mode: python ; coding: utf-8 -*-
# Genera el .exe de ProyectoCAM. Uso: venv\Scripts\pyinstaller.exe CAM.spec
#
# Build en --onedir (una carpeta con el .exe y sus dependencias), no
# --onefile: arranca mas rapido y, si algo falla, es mucho mas facil ver
# que DLL o archivo de datos falta dentro de dist\ProyectoCAM\.

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# mediapipe guarda sus modelos (.tflite, .binarypb, .pbtxt) mezclados con el
# codigo, dentro del propio paquete: no hay hook de pyinstaller-hooks-contrib
# para esto (se descontinuo), asi que se copian a mano. include_py_files=False
# evita duplicar los .py, que ya se empaquetan via el analisis de imports.
datas = collect_data_files("mediapipe", include_py_files=False)

# manuales ilustrados (pestana "Manuales"): se abren con el navegador del
# sistema vía app.config.MANUALES_DIR, que en el .exe apunta a sys._MEIPASS
datas += [("app/manuales/conectar_camaras.html", "app/manuales"),
          ("app/manuales/comandos_voz.html", "app/manuales"),
          ("app/manuales/conectar_red_dvr.html", "app/manuales")]

# fondo nocturno animado (splash, login, sidebar): via app.config.IMAGENES_DIR
# el .png es la version fija (sidebar, quieta por rendimiento) y el .gif es
# la animacion real (splash/login) - ver app/views/UI/fondo_nocturno.py
datas += [
    ("app/recursos/imagenes/fondo_nocturno.png", "app/recursos/imagenes"),
    ("app/recursos/imagenes/fondo_nocturno.gif", "app/recursos/imagenes"),
]

hiddenimports = [
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",
]

a = Analysis(
    ["app/main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ProyectoCAM",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ProyectoCAM",
)
