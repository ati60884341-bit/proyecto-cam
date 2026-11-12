import os
import threading
import time

import cv2
import numpy as np
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from app.config import EVIDENCIAS_DIR
from app.services import telegram_service, whatsapp_service
from app.services.hash_service import firmar_archivo


class _Puente(QObject):
    """El envio de prueba corre en un hilo comun: esta senal vuelve al hilo de la UI."""
    resultado = pyqtSignal(bool, str)


class AlertasController:
    """Pestana "Alertas al celular": guarda los datos de WhatsApp, recuerda
    cuando se abrio la conversacion de 24 h y prueba el envio."""

    def __init__(self, view):
        self.view = view
        self._puente = _Puente()
        self._puente.resultado.connect(self._al_terminar_prueba)
        self.view.guardar_whatsapp_solicitado.connect(self.guardar)
        self.view.ventana_abierta_avisada.connect(self.marcar_ventana_abierta)
        self.view.probar_whatsapp_solicitado.connect(self.probar)
        self.view.whatsapp_activo_cambiado.connect(self.cambiar_activo)
        # TelegramController guarda primero (se conecto antes): aca solo se refresca el aviso
        self.view.telegram_view.guardar_solicitado.connect(lambda _datos: self.actualizar_estado())
        self.view.cargar(whatsapp_service.cargar_config())
        self.actualizar_estado()
        # la ventana de 24 h se va cerrando sola: el aviso se refresca cada minuto
        self._timer = QTimer()
        self._timer.timeout.connect(self.actualizar_estado)
        self._timer.start(60_000)

    def actualizar_estado(self):
        cfg = whatsapp_service.cargar_config()
        hasta = whatsapp_service.ventana_abierta_hasta(cfg)
        hora_cierre = time.strftime("%d/%m %H:%M", time.localtime(hasta)) if hasta else ""
        if hasta:
            self.view.set_ventana(f"Abierta hasta el {hora_cierre}", True)
        else:
            self.view.set_ventana("Cerrada: escribale \"inicio turno\" al bot", False)

        hay_telegram = telegram_service.configurado()
        if cfg["activo"] and whatsapp_service.configurado(cfg) and hasta:
            self.view.set_estado("ok", f"Listo: las alertas llegan por WhatsApp hasta el {hora_cierre}.")
        elif not cfg["activo"] or not whatsapp_service.configurado(cfg):
            motivo = "WhatsApp desactivado" if whatsapp_service.configurado(cfg) else "Falta conectar WhatsApp (paso 1)"
            if hay_telegram:
                self.view.set_estado("aviso", f"{motivo}: por ahora las alertas llegan por Telegram.")
            else:
                self.view.set_estado("error", f"{motivo} y Telegram no esta configurado: las alertas NO llegan.")
        elif hay_telegram:
            self.view.set_estado("aviso", "Conversacion de WhatsApp cerrada (paso 2): mientras tanto llegan por Telegram.")
        else:
            self.view.set_estado("error", "Conversacion de WhatsApp cerrada (paso 2) y sin Telegram: las alertas NO llegan.")

    def guardar(self, datos):
        if not (datos["token"] and datos["phone_id"] and datos["numero"]):
            self.view.registrar_evento("Complete token, ID del numero y su celular.")
            return
        numero = whatsapp_service.limpiar_numero(datos["numero"])
        if len(numero) < 10:
            self.view.registrar_evento("El celular debe ir con codigo de pais, ej: 51987654321.")
            return
        whatsapp_service.guardar_config(token=datos["token"], phone_id=datos["phone_id"], numero=numero)
        self.view.cargar(whatsapp_service.cargar_config())
        self.view.registrar_evento("Datos de WhatsApp guardados.")
        self.actualizar_estado()

    def marcar_ventana_abierta(self):
        whatsapp_service.guardar_config(ventana_desde=time.time())
        self.view.registrar_evento("Conversacion marcada como abierta por 24 horas.")
        self.actualizar_estado()

    def cambiar_activo(self, activo):
        whatsapp_service.guardar_config(activo=activo)
        self.actualizar_estado()

    def probar(self):
        cfg = whatsapp_service.cargar_config()
        if not whatsapp_service.configurado(cfg):
            self.view.set_resultado_prueba(False, "Primero complete y guarde el paso 1.")
            return
        if not whatsapp_service.ventana_abierta_hasta(cfg):
            self.view.set_resultado_prueba(False, "Primero haga el paso 2: escribale \"inicio turno\" al bot.")
            return
        self.view.set_probando(True)
        self.view.set_resultado_prueba(True, "")
        ruta = self._foto_de_prueba()
        texto = (
            "✅ Prueba de alerta - CAM Centro de Monitoreo\n"
            f"Hora: {time.strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"Firma SHA-256: {firmar_archivo(ruta)}\n"
            "Si ve esto, las alertas de camara tapada le llegaran aqui."
        )

        def tarea():
            try:
                whatsapp_service.enviar_foto(cfg, ruta, texto)
                self._puente.resultado.emit(True, (
                    "Meta acepto el envio: deberia llegarle en segundos. Si en 1 minuto no llega, "
                    "repita el paso 2 desde el celular " + cfg["numero"] + "."
                ))
            except whatsapp_service.WhatsAppError as exc:
                self._puente.resultado.emit(False, str(exc))

        threading.Thread(target=tarea, daemon=True).start()

    def _al_terminar_prueba(self, ok, texto):
        self.view.set_probando(False)
        self.view.set_resultado_prueba(ok, ("Enviada. " if ok else "No se envio: ") + texto)
        self.view.registrar_evento(("[PRUEBA OK] " if ok else "[PRUEBA FALLO] ") + texto)

    @staticmethod
    def _foto_de_prueba():
        imagen = np.full((360, 640, 3), (36, 27, 23), np.uint8)
        cv2.putText(imagen, "CAM - prueba de alerta", (40, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (201, 214, 54), 3)
        cv2.putText(imagen, time.strftime("%d/%m/%Y %H:%M:%S"), (40, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (238, 233, 231), 2)
        ruta = os.path.join(EVIDENCIAS_DIR, "prueba_alerta.jpg")
        cv2.imwrite(ruta, imagen)
        return ruta
