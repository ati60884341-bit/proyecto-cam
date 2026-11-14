"""API REST chica para la futura app de Android (visor + alertas): corre
adentro del mismo proceso de CAM, en un hilo de fondo - el estado "en linea /
tapada" de cada camara vive en memoria dentro de MonitoreoController y no
hay forma de saberlo solo consultando la base, asi que un servicio aparte
necesitaria duplicar las conexiones RTSP. Esto es v1: solo lectura (estado
de camaras, incidencias, resumen) con login por usuario/clave existente."""
import secrets
import threading
import time

import jwt
import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.models import incidencia_model, usuario_model

PUERTO_API = 8765
ALGORITMO_JWT = "HS256"
HORAS_VALIDEZ_TOKEN = 12
INTERVALO_STREAM_SEG = 0.08  # ~12 fps (antes 0.12/~8 fps: se sentia con atraso)

# un secreto nuevo por arranque: los tokens no sobreviven un reinicio de la
# app, que para un v1 de solo lectura es aceptable (el celular vuelve a
# pedir login) y evita guardar un secreto fijo en el codigo/disco
_secreto_jwt = secrets.token_hex(32)
_monitoreo_controller = None  # lo setea iniciar_api() cuando arranca la app

app = FastAPI(title="CAM API", version="1")


def _crear_token(usuario):
    payload = {
        "sub": usuario["NombreUsuario"],
        "nombre": usuario["NombreCompleto"],
        "rol": usuario["Rol"],
        "exp": int(time.time()) + HORAS_VALIDEZ_TOKEN * 3600,
    }
    return jwt.encode(payload, _secreto_jwt, algorithm=ALGORITMO_JWT)


def _validar_token(authorization):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta el token (Authorization: Bearer <token>).")
    token = authorization.removeprefix("Bearer ")
    try:
        return jwt.decode(token, _secreto_jwt, algorithms=[ALGORITMO_JWT])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El token vencio, inicie sesion de nuevo.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalido.")


@app.post("/login")
def login(datos: dict):
    usuario = usuario_model.autenticar(datos.get("usuario", ""), datos.get("clave", ""))
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario o clave incorrectos.")
    return {
        "token": _crear_token(usuario),
        "nombre": usuario["NombreCompleto"],
        "rol": usuario["Rol"],
    }


@app.get("/camaras")
def camaras(authorization: str = Header(default=None)):
    _validar_token(authorization)
    if _monitoreo_controller is None:
        raise HTTPException(status_code=503, detail="El Centro de Monitoreo todavia no arranco.")
    return _monitoreo_controller.estado_camaras()


@app.get("/camaras/{zona}/stream.mjpg")
def stream_camara(zona: str, authorization: str = Header(default=None)):
    _validar_token(authorization)
    if _monitoreo_controller is None:
        raise HTTPException(status_code=503, detail="El Centro de Monitoreo todavia no arranco.")
    hilo = _monitoreo_controller.hilos_camara.get(zona)
    if hilo is None:
        raise HTTPException(status_code=404, detail="Camara no encontrada.")

    def generar_cuadros():
        anterior = None
        while True:
            jpg = hilo.obtener_ultimo_jpeg()
            if jpg and jpg != anterior:
                anterior = jpg
                yield (b"--cuadro\r\nContent-Type: image/jpeg\r\nContent-Length: "
                       + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
            else:
                # sin cuadro nuevo (camara sin senal, o el mismo frame de siempre):
                # no se reenvia - asi el celular puede notar que dejo de llegar
                # algo nuevo en vez de ver "en vivo" una imagen vieja para siempre.
                # Tambien le da pie al servidor para notar que el cliente se fue.
                yield b""
            time.sleep(INTERVALO_STREAM_SEG)

    return StreamingResponse(generar_cuadros(), media_type="multipart/x-mixed-replace; boundary=cuadro")


@app.get("/incidencias")
def incidencias(limite: int = 20, authorization: str = Header(default=None)):
    _validar_token(authorization)
    return incidencia_model.listar(min(limite, 200))


@app.get("/resumen")
def resumen(authorization: str = Header(default=None)):
    _validar_token(authorization)
    if _monitoreo_controller is None:
        raise HTTPException(status_code=503, detail="El Centro de Monitoreo todavia no arranco.")
    en_linea, total = _monitoreo_controller.resumen_camaras()
    return {
        "camaras_en_linea": en_linea,
        "camaras_total": total,
        "incidencias_hoy": incidencia_model.contar_hoy(),
        "alarma_sonando": _monitoreo_controller._alarma_sonando,
    }


def iniciar_api(monitoreo_controller, puerto=PUERTO_API):
    """Arranca el servidor en un hilo daemon (no Qt: los endpoints solo leen
    atributos simples de MonitoreoController, no tocan widgets)."""
    global _monitoreo_controller
    _monitoreo_controller = monitoreo_controller
    config = uvicorn.Config(app, host="0.0.0.0", port=puerto, log_level="warning")
    servidor = uvicorn.Server(config)
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    return hilo
