"""Manda una alerta con foto al celular: WhatsApp primero y, si no se puede,
Telegram de respaldo, para que ninguna alerta se pierda."""
import threading

from app.services import telegram_service, whatsapp_service


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
