import io

import qrcode

from app.services import telegram_service


class TelegramController:
    def __init__(self, view):
        self.view = view
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
            al_terminar=lambda ok, msg: self.view.registrar_evento(msg),
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
