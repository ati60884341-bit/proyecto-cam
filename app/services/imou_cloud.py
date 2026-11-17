"""Funciones de camaras Imou que NO existen por ONVIF local (sirena, luz,
modo privacidad, seguimiento automatico): van por la nube oficial de Imou
(Imou Open Platform, open.imoulife.com). La Cruiser (IPC-K7F) probada solo
expone ONVIF en el puerto 80 - su API web local (/cgi-bin) esta apagada -,
asi que este es el unico camino para esas funciones.

Credenciales por variables de entorno (igual que la base de datos, ver
config.py), nunca en el codigo:
    CAM_IMOU_APP_ID, CAM_IMOU_APP_SECRET  (consola Imou -> App Information)
    CAM_IMOU_REGION  opcional: sg | eu | na (si falta, se prueban las tres)

El deviceId que pide la nube es el numero de serie de la camara: se lee por
ONVIF local (GetDeviceInformation) con el mismo usuario/clave RTSP que ya
guarda la app, asi que no hay que escribirlo a mano."""
import base64
import hashlib
import hmac
import os
import time
import uuid
from datetime import datetime

from PySide6.QtCore import QThread, Signal

HOSTS_REGION = {
    "sg": "openapi-sg.easy4ip.com",
    "eu": "openapi-fk.easy4ip.com",
    "na": "openapi-or.easy4ip.com",
}
TIMEOUT_SEG = 10

# accion -> (tipo, valor): "flag" usa setDeviceCameraStatus(enableType),
# "servicio" usa la API v2 device.service.invoke(serviceId), "prop" usa la
# API v2 device.property.set({propertyId: valor}). Todo lo de "prop" y
# ptz.aim.reset se confirmo con device.capability.list en la Cruiser IPC-K7F
ACCIONES = {
    "vision_auto": ("prop", ("image.night.mode", 0)),
    "vision_color": ("prop", ("image.night.mode", 1)),
    "vision_ir": ("prop", ("image.night.mode", 2)),
    "vision_off": ("prop", ("image.night.mode", 3)),
    "wdr_on": ("prop", ("image.wdr.mode", 1)),
    "wdr_off": ("prop", ("image.wdr.mode", 0)),
    "ronda_on": ("prop", ("ptz.cruise.smart", 1)),
    "ronda_off": ("prop", ("ptz.cruise.smart", 0)),
    "centrar": ("servicio", "ptz.aim.reset"),
    "voltear_on": ("prop", ("image.orient.enabled", 1)),
    "voltear_off": ("prop", ("image.orient.enabled", 0)),
    "marcar_on": ("prop", ("detection.frame.enabled", 1)),
    "marcar_off": ("prop", ("detection.frame.enabled", 0)),
    "mic_on": ("prop", ("audio.mic.enabled", 1)),
    "mic_off": ("prop", ("audio.mic.enabled", 0)),
    "indicador_on": ("prop", ("light.indicator.enabled", 1)),
    "indicador_off": ("prop", ("light.indicator.enabled", 0)),
    "sirena_on": ("servicio", "detection.siren.start"),
    "sirena_off": ("servicio", "detection.siren.stop"),
    "luz_on": ("flag", ("whiteLight", True)),
    "luz_off": ("flag", ("whiteLight", False)),
    "privacidad_on": ("flag", ("closeCamera", True)),
    "privacidad_off": ("flag", ("closeCamera", False)),
    "seguir_on": ("flag", ("smartTrack", True)),
    "seguir_off": ("flag", ("smartTrack", False)),
}
DESCRIPCION = {
    "sirena_on": "Sirena encendida", "sirena_off": "Sirena apagada",
    "luz_on": "Luz encendida", "luz_off": "Luz apagada",
    "privacidad_on": "Modo privacidad activado", "privacidad_off": "Modo privacidad desactivado",
    "seguir_on": "Seguimiento automatico activado", "seguir_off": "Seguimiento automatico desactivado",
    "vision_auto": "Vision nocturna inteligente", "vision_color": "Vision nocturna a color",
    "vision_ir": "Vision nocturna infrarroja", "vision_off": "Vision nocturna apagada",
    "wdr_on": "Contraluz (WDR) activado", "wdr_off": "Contraluz (WDR) desactivado",
    "ronda_on": "Ronda automatica activada", "ronda_off": "Ronda automatica detenida",
    "centrar": "Camara centrada",
    "voltear_on": "Imagen volteada", "voltear_off": "Imagen normal (sin voltear)",
    "marcar_on": "Recuadro de personas activado", "marcar_off": "Recuadro de personas desactivado",
    "mic_on": "Microfono de la camara encendido", "mic_off": "Microfono de la camara apagado",
    "indicador_on": "Luz indicadora encendida", "indicador_off": "Luz indicadora apagada",
}

# cache por proceso: el token dura 3 dias y la nube limita las llamadas
# (30.000 gratis al mes), asi que no se pide uno por comando
_token = {"valor": None, "vence": 0.0, "host": None}
_serial_por_host = {}


def configurada():
    return bool(os.environ.get("CAM_IMOU_APP_ID") and os.environ.get("CAM_IMOU_APP_SECRET"))


def firmar(marca_tiempo, nonce, app_secret):
    """sign = Base64(HMAC-SHA256("time:T,nonce:N,appSecret:S", hex(SHA256(S))))
    (ver open.imoulife.com -> Signature)."""
    origen = f"time:{marca_tiempo},nonce:{nonce},appSecret:{app_secret}"
    clave = hashlib.sha256(app_secret.encode("utf-8")).hexdigest().lower()
    digest = hmac.new(clave.encode("utf-8"), origen.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def _post(host, ruta, params):
    import requests

    app_id = os.environ["CAM_IMOU_APP_ID"]
    app_secret = os.environ["CAM_IMOU_APP_SECRET"]
    marca_tiempo = int(time.time())
    nonce = str(uuid.uuid4())
    cuerpo = {
        "system": {
            "ver": "1.0", "appId": app_id, "time": marca_tiempo, "nonce": nonce,
            "sign": firmar(marca_tiempo, nonce, app_secret),
        },
        "id": str(uuid.uuid4()),
        "params": params,
    }
    r = requests.post(f"https://{host}{ruta}", json=cuerpo, timeout=TIMEOUT_SEG)
    r.raise_for_status()
    resultado = r.json().get("result", {})
    return resultado.get("code"), resultado.get("msg"), resultado.get("data") or {}


def _obtener_token(forzar=False):
    if not forzar and _token["valor"] and time.time() < _token["vence"]:
        return _token["valor"], _token["host"]
    region = (os.environ.get("CAM_IMOU_REGION") or "").strip().lower()
    hosts = [HOSTS_REGION[region]] if region in HOSTS_REGION else list(HOSTS_REGION.values())
    ultimo_error = "sin respuesta"
    for host in hosts:
        try:
            codigo, msg, data = _post(host, "/openapi/accessToken", {})
        except Exception as exc:
            ultimo_error = str(exc)
            continue
        if codigo == "0" and data.get("accessToken"):
            _token.update(
                valor=data["accessToken"], host=host,
                vence=time.time() + max(60, int(data.get("expireTime", 3600)) - 300),
            )
            return _token["valor"], host
        ultimo_error = f"{codigo}: {msg}"
    raise RuntimeError(f"La nube Imou rechazo el AppId/AppSecret ({ultimo_error}).")


def _serial_onvif(host_camara, puerto, usuario, clave):
    """Numero de serie = deviceId de la nube. Se lee una vez por camara."""
    if host_camara not in _serial_por_host:
        from onvif import ONVIFCamera

        info = ONVIFCamera(host_camara, puerto, usuario, clave).devicemgmt.GetDeviceInformation()
        _serial_por_host[host_camara] = info.SerialNumber
    return _serial_por_host[host_camara]


def ejecutar(accion, host_camara, puerto_onvif, usuario, clave):
    """Ejecuta una accion de ACCIONES. Devuelve (ok, mensaje)."""
    tipo, valor = ACCIONES[accion]
    device_id = _serial_onvif(host_camara, puerto_onvif, usuario, clave)

    for intento in range(2):  # un reintento con token nuevo si vencio (TK1002)
        token, host = _obtener_token(forzar=intento > 0)
        if tipo == "flag":
            enable_type, encender = valor
            codigo, msg, _ = _post(host, "/openapi/setDeviceCameraStatus", {
                "token": token, "deviceId": device_id, "channelId": "0",
                "enableType": enable_type, "enable": encender,
            })
        elif tipo == "prop":
            propiedad, dato = valor
            codigo, msg, _ = _post(host, "/openapi/v2/device.property.set", {
                "token": token, "deviceId": device_id, "channelId": "0",
                "properties": {propiedad: dato},
            })
        else:
            entrada = {"clientLocalTime": datetime.now().strftime("T%H%M%S")} if valor.endswith("start") else {}
            codigo, msg, _ = _post(host, "/openapi/v2/device.service.invoke", {
                "token": token, "deviceId": device_id, "channelId": "0",
                "serviceId": valor, "inputData": entrada,
            })
        if codigo != "TK1002":
            break

    if codigo == "0":
        return True, DESCRIPCION[accion]
    explicacion = {
        "DV1007": "la camara esta desconectada de la nube Imou",
        "DV1019": "este modelo no tiene esa funcion", "DV1026": "este modelo no tiene esa funcion",
        "DV2003": "este modelo no tiene esa funcion",
        "OP1009": "la camara no esta en la cuenta Imou de este AppId",
        "OP1013": "se agoto el cupo de llamadas de la nube Imou",
        "OP1014": "se agoto el cupo diario de llamadas de la nube Imou",
    }.get(codigo, msg or "error desconocido")
    return False, f"{DESCRIPCION[accion]}: fallo ({codigo}, {explicacion})"


class ImouCloudThread(QThread):
    """Las llamadas a la nube tardan 1-2 s: nunca en el hilo de la UI."""

    resultado = Signal(bool, str)

    def __init__(self, accion, host_camara, puerto_onvif, usuario, clave, parent=None):
        super().__init__(parent)
        self.args = (accion, host_camara, puerto_onvif, usuario, clave)

    def run(self):
        try:
            ok, mensaje = ejecutar(*self.args)
        except Exception as exc:
            ok, mensaje = False, f"Nube Imou: {exc}"
        self.resultado.emit(ok, mensaje)
