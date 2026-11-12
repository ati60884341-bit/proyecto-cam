import cv2
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QSizePolicy

ESTILO_NORMAL = "QFrame#zonaFrame { border: 3px solid #3a3f44; border-radius: 6px; background: #111; }"
ESTILO_SABOTAJE = "QFrame#zonaFrame { border: 3px solid #e53935; border-radius: 6px; background: #220000; }"
ESTILO_SIN_SENAL = "QFrame#zonaFrame { border: 3px solid #555; border-radius: 6px; background: #1a1a1a; }"


def frame_a_pixmap(frame_bgr, ancho_destino, alto_destino):
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    alto, ancho, _ = rgb.shape
    imagen = QImage(rgb.data, ancho, alto, 3 * ancho, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(imagen).scaled(
        ancho_destino, alto_destino,
        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
    )


class ZonaFrame(QFrame):
    """QFrame que representa una de las 4 zonas de la maqueta: video en vivo +
    estado + boton de captura manual de evidencia."""

    capturar_evidencia = pyqtSignal(str)   # nombre de zona
    ampliar_zona = pyqtSignal(str)
    reconectar_zona = pyqtSignal(str)
    ocultar_zona = pyqtSignal(str)

    def __init__(self, nombre_zona, nombre_camara, parent=None):
        super().__init__(parent)
        self.nombre_zona = nombre_zona
        self.setObjectName("zonaFrame")
        self.setStyleSheet(ESTILO_NORMAL)
        self.setMinimumSize(280, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)

        fila_titulo = QHBoxLayout()
        self.titulo = QLabel(f"{nombre_zona}  —  {nombre_camara}")
        self.titulo.setStyleSheet("color: white; font-weight: bold;")
        fila_titulo.addWidget(self.titulo, stretch=1)
        # suspende la camara (deja de conectarse y de verse) sin borrarla:
        # se vuelve a mostrar desde el menu "Ocultas" de su grupo
        self.btn_ocultar = QPushButton("Ocultar")
        self.btn_ocultar.setToolTip(
            "Suspende esta camara: deja de verse y de conectarse (libera la conexion "
            "con el DVR/NVR). No detecta sabotaje mientras este oculta. Se vuelve a "
            "mostrar desde el boton \"Ocultas\" de su grupo."
        )
        self.btn_ocultar.setFixedWidth(70)
        self.btn_ocultar.clicked.connect(lambda: self.ocultar_zona.emit(self.nombre_zona))
        fila_titulo.addWidget(self.btn_ocultar)
        layout.addLayout(fila_titulo)

        self.video_label = QLabel("Conectando...")
        self.video_label.setStyleSheet("color: #aaa; background: black;")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumHeight(150)
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.video_label)

        self.estado_label = QLabel("Estado: conectando...")
        self.estado_label.setStyleSheet("color: #ccc; font-size: 11px;")
        layout.addWidget(self.estado_label)

        fila_botones = QHBoxLayout()
        self.btn_capturar = QPushButton("Capturar evidencia")
        self.btn_capturar.clicked.connect(lambda: self.capturar_evidencia.emit(self.nombre_zona))
        fila_botones.addWidget(self.btn_capturar)

        self.btn_ampliar = QPushButton("Ampliar")
        self.btn_ampliar.clicked.connect(lambda: self.ampliar_zona.emit(self.nombre_zona))
        fila_botones.addWidget(self.btn_ampliar)

        self.btn_reconectar = QPushButton("Reconectar")
        self.btn_reconectar.setToolTip("Fuerza una reconexion de esta camara (resincroniza el video)")
        self.btn_reconectar.clicked.connect(lambda: self.reconectar_zona.emit(self.nombre_zona))
        fila_botones.addWidget(self.btn_reconectar)
        layout.addLayout(fila_botones)

    def mostrar_frame(self, frame_bgr):
        pixmap = frame_a_pixmap(frame_bgr, self.video_label.width(), self.video_label.height())
        self.video_label.setPixmap(pixmap)

    def actualizar_estado(self, estado):
        if estado == "conectada":
            self.setStyleSheet(ESTILO_NORMAL)
            self.estado_label.setText("Estado: en linea")
            self._set_botones_habilitados(True)
        elif estado == "sabotaje":
            self.setStyleSheet(ESTILO_SABOTAJE)
            self.estado_label.setText("ALERTA: posible sabotaje / camara tapada")
            self._set_botones_habilitados(True)
        elif estado == "reconectando":
            # resincronizacion INTENCIONAL (tras un PTZ, o preventiva cada
            # par de minutos), no una desconexion real: a proposito NO se
            # toca el video (sigue el ultimo fotograma en pantalla, no el
            # aviso "SIN SENAL") para no interrumpir la vista justo cuando
            # mas se nota, como al mover la camara por voz en una demo
            self.estado_label.setText("Estado: resincronizando video...")
            self._set_botones_habilitados(True)
        else:
            self.setStyleSheet(ESTILO_SIN_SENAL)
            self.video_label.setText("SIN SENAL\n(camara simulada / no disponible)")
            self.estado_label.setText("Estado: sin senal")
            self._set_botones_habilitados(True)

    def _set_botones_habilitados(self, habilitados):
        self.btn_capturar.setEnabled(habilitados)
        self.btn_ampliar.setEnabled(habilitados)
        self.btn_reconectar.setEnabled(habilitados)
