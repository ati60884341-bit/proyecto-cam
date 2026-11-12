"""Alertas por WhatsApp con la API oficial de Meta (WhatsApp Cloud API).

Gratis asi: numero de prueba de Meta, SIN metodo de pago, y solo mensajes
"de servicio" (los que se mandan dentro de las 24 h siguientes a que el
usuario le escribe al bot). Nunca se usan plantillas, que son las que Meta
cobra.

Limitacion de fondo: si pasaron las 24 h, Meta igual ACEPTA el envio y el
rechazo llega despues a un webhook (un servidor publico, que esta PC no
tiene). Por eso la app guarda cuando el usuario dijo "ya le escribi" y, con
la ventana cerrada, ni intenta WhatsApp (ver alertas_service)."""
import json
import os
import re
import time

import requests

from app.config import BASE_DIR

CONFIG_PATH = os.path.join(BASE_DIR, "whatsapp_config.json")
API = "https://graph.facebook.com/v23.0/{phone_id}/{recurso}"
# Meta da 24 h; se deja margen para no mandar justo cuando se cierra
DURACION_VENTANA_SEG = 23.5 * 3600

CONFIG_VACIA = {"token": "", "phone_id": "", "numero": "", "activo": True, "ventana_desde": 0}

# codigos de error de Meta -> explicacion para alguien que no es tecnico
MENSAJES_ERROR = {
    190: "El token vencio o esta mal copiado. Use el token PERMANENTE (usuario del sistema), no el de 24 h.",
    131030: "Su numero no esta en la lista de destinatarios del numero de prueba. Agreguelo en Meta "
            "(WhatsApp > Configuracion de la API > campo \"Para\").",
    131047: "Pasaron mas de 24 h sin escribirle al bot. Escribale \"inicio turno\" desde su WhatsApp.",
    131026: "Meta no pudo entregar el mensaje a ese numero (¿tiene WhatsApp? ¿esta bien el codigo de pais?).",
    131042: "Meta pide un metodo de pago. NO lo agregue: use el numero de prueba gratuito.",
    131056: "Demasiados mensajes seguidos al mismo numero: espere un minuto.",
    100: "Algun dato no es valido (revise el ID del numero de telefono).",
}


class WhatsAppError(Exception):
    pass


def cargar_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, json.JSONDecodeError):
        datos = {}
    return {clave: datos.get(clave, valor) for clave, valor in CONFIG_VACIA.items()}


def guardar_config(**cambios):
    cfg = cargar_config()
    cfg.update(cambios)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


def limpiar_numero(numero):
    """'+51 987 654 321' -> '51987654321' (Meta lo quiere solo con digitos)."""
    return re.sub(r"\D", "", numero or "")


def configurado(cfg):
    return bool(cfg["token"] and cfg["phone_id"] and cfg["numero"])


def ventana_abierta_hasta(cfg):
    """Hora (epoch) en que se cierra la conversacion, o 0 si ya esta cerrada."""
    hasta = cfg.get("ventana_desde", 0) + DURACION_VENTANA_SEG
    return hasta if hasta > time.time() else 0


def _error_de_meta(respuesta):
    try:
        error = respuesta.json().get("error", {})
    except ValueError:
        return WhatsAppError(f"Meta respondio un error ({respuesta.status_code}).")
    codigo = error.get("code")
    return WhatsAppError(MENSAJES_ERROR.get(codigo) or f"Meta respondio: {error.get('message')} (codigo {codigo}).")


def enviar_foto(cfg, ruta_foto, texto):
    """Sube la foto a Meta y la manda con su texto. Bloquea (usar en un hilo).
    Lanza WhatsAppError con un mensaje entendible si algo falla."""
    cabecera = {"Authorization": f"Bearer {cfg['token'].strip()}"}
    phone_id = cfg["phone_id"].strip()
    try:
        with open(ruta_foto, "rb") as f:
            subida = requests.post(
                API.format(phone_id=phone_id, recurso="media"), headers=cabecera, timeout=20,
                data={"messaging_product": "whatsapp", "type": "image/jpeg"},
                files={"file": (os.path.basename(ruta_foto), f, "image/jpeg")},
            )
        if not subida.ok:
            raise _error_de_meta(subida)
        envio = requests.post(
            API.format(phone_id=phone_id, recurso="messages"), headers=cabecera, timeout=20,
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": limpiar_numero(cfg["numero"]),
                "type": "image",
                "image": {"id": subida.json()["id"], "caption": texto[:1024]},
            },
        )
    except requests.RequestException:
        raise WhatsAppError("Sin internet, o Meta no responde.") from None
    if not envio.ok:
        raise _error_de_meta(envio)
