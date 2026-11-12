"""Correr con:  python tests/test_alertas.py   (no usa internet: simula a Meta y Telegram)"""
import os
import sys
import tempfile
import time
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import alertas_service, telegram_service, whatsapp_service

carpeta = tempfile.mkdtemp()
whatsapp_service.CONFIG_PATH = os.path.join(carpeta, "wa.json")
telegram_service.CONFIG_PATH = os.path.join(carpeta, "tg.json")
foto = os.path.join(carpeta, "foto.jpg")
with open(foto, "wb") as f:
    f.write(b"\xff\xd8 jpg falso")


class Respuesta:
    def __init__(self, codigo, datos):
        self.status_code, self._datos, self.ok = codigo, datos, codigo < 400

    def json(self):
        return self._datos


assert whatsapp_service.limpiar_numero("+51 987-654 321") == "51987654321"

# --- sin nada configurado: avisa, no revienta ---
ok, msg = alertas_service.enviar_alerta(foto, "x")
assert not ok and "configure" in msg, msg

# --- WhatsApp configurado y conversacion abierta: sube la foto y la manda ---
whatsapp_service.guardar_config(token="EAA", phone_id="123", numero="51987654321", ventana_desde=time.time())
llamadas = []


def post_ok(url, **kw):
    llamadas.append((url, kw))
    return Respuesta(200, {"id": "media-1"} if url.endswith("/media") else {"messages": [{"id": "wamid"}]})


with mock.patch("requests.post", post_ok):
    ok, msg = alertas_service.enviar_alerta(foto, "Camara: Puerta")
assert ok and "WhatsApp" in msg, msg
assert llamadas[0][0].endswith("/123/media") and llamadas[1][0].endswith("/123/messages")
cuerpo = llamadas[1][1]["json"]
assert cuerpo["to"] == "51987654321" and cuerpo["image"] == {"id": "media-1", "caption": "Camara: Puerta"}
assert llamadas[1][1]["headers"]["Authorization"] == "Bearer EAA"

# --- token vencido: mensaje claro y se va por Telegram ---
telegram_service.guardar_config("tg-token", "999", "bot")


def post_token_malo(url, **kw):
    if "api.telegram.org" in url:
        return mock.Mock(raise_for_status=lambda: None, json=lambda: {"ok": True})
    return Respuesta(401, {"error": {"code": 190, "message": "expired"}})


with mock.patch("requests.post", post_token_malo):
    ok, msg = alertas_service.enviar_alerta(foto, "x")
assert ok and "Telegram" in msg and "token" in msg.lower(), msg

# --- conversacion cerrada: ni intenta WhatsApp, va directo a Telegram ---
whatsapp_service.guardar_config(ventana_desde=time.time() - 25 * 3600)
urls = []


def post_registro(url, **kw):
    urls.append(url)
    return mock.Mock(raise_for_status=lambda: None, json=lambda: {"ok": True})


with mock.patch("requests.post", post_registro):
    ok, msg = alertas_service.enviar_alerta(foto, "x")
assert ok and "cerrada" in msg and all("telegram" in u for u in urls), (msg, urls)

# --- WhatsApp desactivado: solo Telegram, sin quejarse de WhatsApp ---
whatsapp_service.guardar_config(activo=False, ventana_desde=time.time())
with mock.patch("requests.post", post_registro):
    ok, msg = alertas_service.enviar_alerta(foto, "x")
assert ok and msg == "Alerta enviada por Telegram.", msg

print("OK alertas: 6 casos")
