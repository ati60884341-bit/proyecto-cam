import json
import os
import threading

import requests

from app.config import BASE_DIR

CONFIG_PATH = os.path.join(BASE_DIR, "telegram_config.json")
API_BASE = "https://api.telegram.org/bot{token}/{metodo}"


def cargar_config():
    if not os.path.exists(CONFIG_PATH):
        return {"bot_token": "", "chat_id": "", "bot_username": ""}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"bot_token": "", "chat_id": "", "bot_username": ""}
    return {
        "bot_token": datos.get("bot_token", ""),
        "chat_id": datos.get("chat_id", ""),
        "bot_username": datos.get("bot_username", ""),
    }


def guardar_config(bot_token, chat_id, bot_username):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {"bot_token": bot_token.strip(), "chat_id": chat_id.strip(), "bot_username": bot_username.strip()},
            f, ensure_ascii=False, indent=2,
        )


def configurado():
    cfg = cargar_config()
    return bool(cfg["bot_token"] and cfg["chat_id"])


def _enviar_foto_sync(bot_token, chat_id, ruta_foto, caption):
    url = API_BASE.format(token=bot_token, metodo="sendPhoto")
    with open(ruta_foto, "rb") as f:
        archivos = {"photo": f}
        datos = {"chat_id": chat_id, "caption": caption}
        respuesta = requests.post(url, data=datos, files=archivos, timeout=15)
    respuesta.raise_for_status()
    return respuesta.json()


def _enviar_mensaje_sync(bot_token, chat_id, texto):
    url = API_BASE.format(token=bot_token, metodo="sendMessage")
    respuesta = requests.post(url, data={"chat_id": chat_id, "text": texto}, timeout=10)
    respuesta.raise_for_status()
    return respuesta.json()


def enviar_foto_async(ruta_foto, caption, al_terminar=None):
    """Envia una foto (evidencia de sabotaje/panico) al canal de Telegram de
    la feria, sin bloquear la UI. al_terminar(ok, mensaje) es opcional, se
    llama desde el hilo en segundo plano."""
    cfg = cargar_config()
    if not cfg["bot_token"] or not cfg["chat_id"]:
        if al_terminar:
            al_terminar(False, "Telegram no esta configurado (ver pestana Telegram).")
        return

    def tarea():
        try:
            _enviar_foto_sync(cfg["bot_token"], cfg["chat_id"], ruta_foto, caption)
            if al_terminar:
                al_terminar(True, "Alerta enviada a Telegram.")
        except Exception as exc:
            if al_terminar:
                al_terminar(False, f"No se pudo enviar la alerta a Telegram: {exc}")

    threading.Thread(target=tarea, daemon=True).start()


def enviar_mensaje_async(texto, al_terminar=None):
    cfg = cargar_config()
    if not cfg["bot_token"] or not cfg["chat_id"]:
        if al_terminar:
            al_terminar(False, "Telegram no esta configurado (ver pestana Telegram).")
        return

    def tarea():
        try:
            _enviar_mensaje_sync(cfg["bot_token"], cfg["chat_id"], texto)
            if al_terminar:
                al_terminar(True, "Mensaje de prueba enviado.")
        except Exception as exc:
            if al_terminar:
                al_terminar(False, f"No se pudo enviar el mensaje de prueba: {exc}")

    threading.Thread(target=tarea, daemon=True).start()
