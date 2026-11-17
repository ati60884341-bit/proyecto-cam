import cv2
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton,
    QVBoxLayout,
)

from app.views.UI.zona_frame import frame_a_pixmap
from app.views.UI.pantalla import tamano_adaptado

TURQUESA = (201, 214, 54)   # BGR
AMARILLO = (40, 200, 255)


def _clic_relativo(etiqueta, pos):
    """Clic en un QLabel con un pixmap centrado -> punto 0..1 dentro de la
    imagen (descontando las franjas negras de los costados o arriba/abajo)."""
    pixmap = etiqueta.pixmap()
    if pixmap is None or pixmap.isNull():
        return None
    ancho = pixmap.width() / pixmap.devicePixelRatio()
    alto = pixmap.height() / pixmap.devicePixelRatio()
    x0 = (etiqueta.width() - ancho) / 2
    y0 = (etiqueta.height() - alto) / 2
    x, y = (pos.x() - x0) / ancho, (pos.y() - y0) / alto
    if not (0 <= x <= 1 and 0 <= y <= 1):
        return None
    return (x, y)


def _marcar_puntos(img, puntos, color, cerrar=False, numerar=False, cursor=None):
    alto, ancho = img.shape[:2]
    g = max(2, ancho // 400)
    pts = [(int(x * ancho), int(y * alto)) for x, y in puntos]
    if cursor and pts:
        pts_linea = pts + [(int(cursor[0] * ancho), int(cursor[1] * alto))]
    else:
        pts_linea = pts
    for a, b in zip(pts_linea, pts_linea[1:]):
        cv2.line(img, a, b, color, g, cv2.LINE_AA)
    if cerrar and len(pts) >= 3:
        cv2.line(img, pts[-1], pts[0], color, g, cv2.LINE_AA)
    for i, p in enumerate(pts):
        cv2.circle(img, p, g * 4, color, -1, cv2.LINE_AA)
        if numerar:
            cv2.circle(img, p, g * 9, color, g, cv2.LINE_AA)
            cv2.putText(img, str(i + 1), (p[0] + g * 8, p[1] - g * 8), cv2.FONT_HERSHEY_SIMPLEX,
                        max(0.6, ancho / 1200), color, g, cv2.LINE_AA)
    return img


class CalibrarPlanoDialog(QDialog):
    """Paso 2 de la calibracion: marcar en el PLANO los mismos 4 puntos del
    piso que se marcaron en la camara, en el mismo orden."""

    def __init__(self, ruta_plano, foto_camara, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibrar camara con el plano - paso 2 de 2")
        self.resize(*tamano_adaptado(1100, 700))
        self.puntos = []
        self._plano = cv2.imread(ruta_plano)
        layout = QVBoxLayout(self)
        ayuda = QLabel("Haga clic en el PLANO en los mismos 4 puntos del piso, en el mismo orden (1, 2, 3, 4) "
                       "que marco en la camara (a la derecha, como referencia).")
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("color: #7fd6e8;")
        layout.addWidget(ayuda)
        fila = QHBoxLayout()
        self.lbl_plano = QLabel()
        self.lbl_plano.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_plano.setMinimumSize(500, 350)
        self.lbl_plano.mousePressEvent = self._clic
        fila.addWidget(self.lbl_plano, stretch=3)
        self.lbl_camara = QLabel()
        self.lbl_camara.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_camara.setMinimumSize(260, 160)
        fila.addWidget(self.lbl_camara, stretch=1)
        layout.addLayout(fila, stretch=1)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.btn_rehacer = botones.addButton("Volver a marcar", QDialogButtonBox.ButtonRole.ResetRole)
        self.btn_rehacer.clicked.connect(self._rehacer)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)
        self._foto_camara = foto_camara

    def showEvent(self, evento):
        super().showEvent(evento)
        self._repintar()

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._repintar()

    def _repintar(self):
        if self._plano is not None:
            img = _marcar_puntos(self._plano.copy(), self.puntos, AMARILLO, cerrar=True, numerar=True)
            self.lbl_plano.setPixmap(frame_a_pixmap(img, self.lbl_plano))
        if self._foto_camara is not None:
            self.lbl_camara.setPixmap(frame_a_pixmap(self._foto_camara, self.lbl_camara))

    def _rehacer(self):
        self.puntos = []
        self._repintar()

    def _clic(self, evento):
        punto = _clic_relativo(self.lbl_plano, evento.position())
        if punto is None or len(self.puntos) >= 4:
            return
        self.puntos.append(punto)
        self._repintar()
        if len(self.puntos) == 4:
            self.accept()


class ZonaAmpliadaDialog(QDialog):
    """Vista en 'pantalla completa' de una zona (comando de voz: 'sistema ampliar <zona>').
    Aqui tambien se configura lo que se dibuja sobre el video: la linea
    virtual, la IA de personas, las zonas con nombre y la calibracion con el plano."""

    linea_definida = Signal(tuple, tuple)   # p1, p2 en 0..1
    linea_quitada = Signal()
    ia_alternada = Signal(bool)
    zona_agregada = Signal(str, list)       # nombre, [(x, y) en 0..1]
    zonas_borradas = Signal()
    calibracion_definida = Signal(list, list)   # 4 puntos camara, 4 puntos plano

    def __init__(self, nombre_zona, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Camara ampliada: {nombre_zona}")
        self.resize(*tamano_adaptado(980, 720))
        layout = QVBoxLayout(self)
        self.video_label = QLabel("Cargando video...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background: black; color: white;")
        self.video_label.setMouseTracking(True)
        self.video_label.mousePressEvent = self._clic_video
        self.video_label.mouseMoveEvent = self._mover_mouse
        layout.addWidget(self.video_label, stretch=1)

        self.lbl_ayuda = QLabel("Linea virtual: cuenta a las personas que la cruzan y avisa en voz alta.")
        self.lbl_ayuda.setWordWrap(True)
        self.lbl_ayuda.setStyleSheet("color: #7fd6e8;")
        layout.addWidget(self.lbl_ayuda)

        fila = QHBoxLayout()
        self.btn_dibujar = QPushButton("Dibujar linea")
        self.btn_dibujar.setToolTip("Haga clic en dos puntos del video: por ejemplo, de un lado al otro de una puerta")
        self.btn_dibujar.clicked.connect(lambda: self._empezar("linea"))
        fila.addWidget(self.btn_dibujar)
        self.btn_quitar = QPushButton("Quitar linea")
        self.btn_quitar.clicked.connect(self._quitar_linea)
        fila.addWidget(self.btn_quitar)
        fila.addSpacing(18)

        self.chk_ia = QCheckBox("IA: detectar personas")
        self.chk_ia.setToolTip("Recuadros verdes por persona, con el color de su ropa y la zona donde esta")
        self.chk_ia.toggled.connect(self.ia_alternada.emit)
        fila.addWidget(self.chk_ia)
        self.btn_zona = QPushButton("Dibujar zona")
        self.btn_zona.setToolTip("Clic en cada esquina de un area (puerta, escritorio...) y luego \"Terminar zona\"")
        self.btn_zona.clicked.connect(self._boton_zona)
        fila.addWidget(self.btn_zona)
        self.btn_borrar_zonas = QPushButton("Borrar zonas")
        self.btn_borrar_zonas.clicked.connect(self._borrar_zonas)
        fila.addWidget(self.btn_borrar_zonas)
        self.btn_calibrar = QPushButton("Calibrar con el plano")
        self.btn_calibrar.setToolTip("Marque 4 puntos del PISO en la camara y los mismos 4 en el plano: "
                                     "asi cada persona aparece en su lugar en el Mapa del lugar")
        self.btn_calibrar.clicked.connect(lambda: self._empezar("calib"))
        fila.addWidget(self.btn_calibrar)
        fila.addStretch()
        layout.addLayout(fila)

        self._modo = None          # None | "linea" | "zona" | "calib"
        self._puntos = []
        self._cursor = None
        self._ultimo_frame = None
        self.ruta_plano = ""
        self.set_tiene_linea(False)
        self.set_estado_ia(False, 0, False)

    # ---- estado que manda el controlador ----
    def set_tiene_linea(self, tiene):
        self.btn_quitar.setEnabled(tiene)
        self.btn_dibujar.setText("Volver a dibujar" if tiene else "Dibujar linea")

    def set_estado_ia(self, activa, cantidad_zonas, calibrada):
        self.chk_ia.blockSignals(True)
        self.chk_ia.setChecked(activa)
        self.chk_ia.blockSignals(False)
        self.btn_borrar_zonas.setEnabled(cantidad_zonas > 0)
        self.btn_borrar_zonas.setText(f"Borrar zonas ({cantidad_zonas})" if cantidad_zonas else "Borrar zonas")
        self.btn_calibrar.setText("Recalibrar con el plano" if calibrada else "Calibrar con el plano")

    # ---- modos de clic ----
    def _empezar(self, modo):
        if modo == "calib" and not self.ruta_plano:
            QMessageBox.information(self, "Falta el plano",
                                    "Primero cargue el plano en la pestana \"Mapa del lugar\".")
            return
        self._modo = modo
        self._puntos = []
        self._cursor = None
        self.video_label.setCursor(Qt.CursorShape.CrossCursor)
        self.lbl_ayuda.setText({
            "linea": "Clic en el PRIMER punto de la linea sobre el video...",
            "zona": "Clic en cada esquina de la zona sobre el video. Cuando termine, pulse \"Terminar zona\".",
            "calib": "Paso 1 de 2: clic en 4 puntos del PISO que tambien pueda ubicar en el plano "
                     "(esquinas de mesas, baldosas, la puerta). Bien separados entre si.",
        }[modo])
        self.btn_zona.setText("Terminar zona" if modo == "zona" else "Dibujar zona")

    def _terminar_modo(self, texto=""):
        self._modo = None
        self._puntos = []
        self._cursor = None
        self.video_label.unsetCursor()
        self.btn_zona.setText("Dibujar zona")
        if texto:
            self.lbl_ayuda.setText(texto)

    def _quitar_linea(self):
        self._terminar_modo("Linea quitada.")
        self.linea_quitada.emit()

    def _boton_zona(self):
        if self._modo != "zona":
            self._empezar("zona")
            return
        if len(self._puntos) < 3:
            self.lbl_ayuda.setText("Una zona necesita al menos 3 esquinas. Siga marcando o pulse de nuevo para cancelar.")
            if not self._puntos:
                self._terminar_modo("Zona cancelada.")
            return
        puntos = list(self._puntos)
        nombre, ok = QInputDialog.getText(self, "Nombre de la zona", "Nombre (ej. Puerta, Escritorio docente):")
        if ok and nombre.strip():
            self.zona_agregada.emit(nombre.strip(), puntos)
            self._terminar_modo(f"Zona \"{nombre.strip()}\" guardada. La IA dira \"en {nombre.strip()}\" o "
                                f"\"cerca de {nombre.strip()}\".")
        else:
            self._terminar_modo("Zona cancelada.")

    def _borrar_zonas(self):
        if QMessageBox.question(self, "Borrar zonas", "Borrar todas las zonas de esta camara?") == \
                QMessageBox.StandardButton.Yes:
            self.zonas_borradas.emit()

    def _clic_video(self, evento):
        if self._modo is None:
            return
        punto = _clic_relativo(self.video_label, evento.position())
        if punto is None:
            return
        self._puntos.append(punto)
        if self._modo == "linea":
            if len(self._puntos) == 1:
                self.lbl_ayuda.setText("Ahora clic en el SEGUNDO punto...")
                return
            p1, p2 = self._puntos
            self._terminar_modo("Linea activa: camine a traves de ella para probar el contador.")
            self.linea_definida.emit(p1, p2)
        elif self._modo == "calib" and len(self._puntos) == 4:
            puntos_camara = list(self._puntos)
            foto = None
            if self._ultimo_frame is not None:
                foto = _marcar_puntos(self._ultimo_frame.copy(), puntos_camara, AMARILLO, cerrar=True, numerar=True)
            self._terminar_modo()
            dialogo = CalibrarPlanoDialog(self.ruta_plano, foto, self)
            if dialogo.exec() and len(dialogo.puntos) == 4:
                self.calibracion_definida.emit(puntos_camara, dialogo.puntos)
                self.lbl_ayuda.setText("Camara calibrada: las personas que detecte la IA aparecen en el Mapa del lugar.")
            else:
                self.lbl_ayuda.setText("Calibracion cancelada.")

    def _mover_mouse(self, evento):
        if self._modo and self._puntos:
            self._cursor = _clic_relativo(self.video_label, evento.position())

    def mostrar_frame(self, frame_bgr):
        self._ultimo_frame = frame_bgr
        if self._modo and self._puntos:
            frame_bgr = _marcar_puntos(
                frame_bgr.copy(), self._puntos,
                AMARILLO if self._modo == "calib" else TURQUESA,
                cerrar=self._modo in ("zona", "calib"), numerar=self._modo == "calib",
                cursor=self._cursor if self._modo != "calib" else None,
            )
        self.video_label.setPixmap(frame_a_pixmap(frame_bgr, self.video_label))
