"""Manda una alerta con foto al celular: WhatsApp primero y, si no se puede,
Telegram de respaldo, para que ninguna alerta se pierda."""
import threading
import time

from app.services import telegram_service, whatsapp_service


def estado():
    """(tipo, frase) de por donde llegan hoy las alertas; tipo: ok | aviso | error."""
    cfg = whatsapp_service.cargar_config()
    hasta = whatsapp_service.ventana_abierta_hasta(cfg)
    hay_telegram = telegram_service.configurado()
    if cfg["activo"] and whatsapp_service.configurado(cfg) and hasta:
        return "ok", f"Listo: las alertas llegan por WhatsApp hasta el {time.strftime('%d/%m %H:%M', time.localtime(hasta))}."
    if not cfg["activo"] or not whatsapp_service.configurado(cfg):
        motivo = "WhatsApp desactivado" if whatsapp_service.configurado(cfg) else "Falta conectar WhatsApp (paso 1)"
        if hay_telegram:
            return "aviso", f"{motivo}: por ahora las alertas llegan por Telegram."
        return "error", f"{motivo} y Telegram no esta configurado: las alertas NO llegan."
    if hay_telegram:
        return "aviso", "Conversacion de WhatsApp cerrada (paso 2): mientras tanto llegan por Telegram."
    return "error", "Conversacion de WhatsApp cerrada (paso 2) y sin Telegram: las alertas NO llegan."


def enviar_alerta(ruta_foto, texto):
    """Bloquea (usar en un hilo). Devuelve (ok, mensaje para la bitacora)."""
    cfg = whatsapp_service.cargar_config()
    motivo_whatsapp = None
    if cfg["activo"] and whatsapp_service.configurado(cfg):
        if whatsapp_service.ventana_abierta_hasta(cfg):
            try:
                whatsapp_service.enviar_foto(cfg, ruta_foto, texto)
                return True, "Alerta enviada por WhatsApp."
            except whatsapp_service.WhatsAppError as exc:
                motivo_whatsapp = str(exc)
        else:
            motivo_whatsapp = "la conversacion de 24 h esta cerrada (escriba \"inicio turno\" al bot)"

    tg = telegram_service.cargar_config()
    if not (tg["bot_token"] and tg["chat_id"]):
        if motivo_whatsapp:
            return False, f"No se envio la alerta: WhatsApp no disponible ({motivo_whatsapp}) y Telegram no esta configurado."
        return False, "No se envio la alerta: configure WhatsApp o Telegram en la pestana Alertas."
    try:
        telegram_service._enviar_foto_sync(tg["bot_token"], tg["chat_id"], ruta_foto, texto)
    except Exception as exc:
        return False, f"No se pudo enviar la alerta por Telegram: {exc}"
    if motivo_whatsapp:
        return True, f"Alerta enviada por Telegram (WhatsApp no disponible: {motivo_whatsapp})."
    return True, "Alerta enviada por Telegram."


def enviar_alerta_async(ruta_foto, texto, al_terminar=None):
    """Sin bloquear la UI; al_terminar(ok, mensaje) se llama desde el hilo de fondo."""
    def tarea():
        ok, mensaje = enviar_alerta(ruta_foto, texto)
        if al_terminar:
            al_terminar(ok, mensaje)

    threading.Thread(target=tarea, daemon=True).start()
