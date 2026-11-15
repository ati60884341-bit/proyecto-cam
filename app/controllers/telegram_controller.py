import io

import qrcode
from PySide6.QtCore import QObject, Signal

from app.services import telegram_service


class _PuenteResultado(QObject):
    """enviar_mensaje_async llama a al_terminar desde un hilo Python comun
    (threading.Thread, no QThread): tocar un widget de ahi directo es
    inseguro. Esta senal Qt vuelve al hilo de la UI antes de escribir en
    el registro, igual que _PuenteAlertas en monitoreo_controller.py."""
    resultado = Signal(str)


class TelegramController:
    def __init__(self, view):
        self.view = view
        self._puente = _PuenteResultado()
        self._puente.resultado.connect(self.view.registrar_evento)
        self.view.guardar_solicitado.connect(self.guardar)
        self.view.probar_solicitado.connect(self.probar)
        self.view.generar_qr_solicitado.connect(self.generar_qr)
        self.view.cargar_config(telegram_service.cargar_config())

    def guardar(self, datos):
        telegram_service.guardar_config(datos["bot_token"], datos["chat_id"], datos["bot_username"])
        self.view.registrar_evento("Configuracion guardada.")

    def probar(self):
        self.view.registrar_evento("Enviando mensaje de prueba...")
        telegram_service.enviar_mensaje_async(
            "Prueba desde CAM - Centro de Monitoreo Inteligente. Si ve este mensaje, las alertas "
            "de sabotaje y panico llegaran aqui durante la demo.",
            al_terminar=lambda ok, msg: self._puente.resultado.emit(msg),
        )

    def generar_qr(self, bot_username):
        if not bot_username:
            self.view.registrar_evento("Indique el usuario del bot antes de generar el QR.")
            return
        link = f"https://t.me/{bot_username}"
        imagen = qrcode.make(link)
        buffer = io.BytesIO()
        imagen.save(buffer, format="PNG")
        self.view.mostrar_qr(buffer.getvalue(), link)
        self.view.registrar_evento(f"QR generado para {link}")
