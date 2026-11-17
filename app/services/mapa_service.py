"""Mapa del lugar: cuanto movimiento ve cada camara y como "pasa" la gente
de una camara a otra.

- MedidorMovimiento: fraccion de la imagen que se esta moviendo (0..1), con
  fondo/primer plano de OpenCV sobre un cuadro chiquito. Corre siempre en el
  hilo de cada camara; con 160 px de ancho cuesta menos de 1 ms por cuadro.
- RecorridoMapa: logica pura (sin Qt, se prueba sola). Con el nivel de
  movimiento de cada camara decide cuales estan "activas", acumula el
  calor (segundos con movimiento) y detecta los pasos A -> B: cuando una
  camara empieza a ver movimiento poco despues de que otra lo vio, se toma
  como la misma persona caminando de una zona a la otra. Es una estimacion
  (no reconoce caras ni ropa), suficiente para dibujar el recorrido.
"""
import cv2

ANCHO_MEDICION = 160
UMBRAL_ACTIVA = 0.012       # fraccion de pixeles en movimiento para decir "hay alguien"
SEG_PARA_APAGAR = 1.5       # sin movimiento este tiempo -> la camara deja de estar activa
VENTANA_PASO_SEG = 20.0     # una camara que se activa hasta 20 s despues de otra = paso A -> B


class MedidorMovimiento:
    def __init__(self):
        self._fondo = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=32, detectShadows=False)
        self._cuadros = 0

    def medir(self, frame):
        alto, ancho = frame.shape[:2]
        chico = cv2.resize(frame, (ANCHO_MEDICION, max(1, int(alto * ANCHO_MEDICION / ancho))),
                           interpolation=cv2.INTER_AREA)
        mascara = self._fondo.apply(chico)
        self._cuadros += 1
        if self._cuadros < 15:
            return 0.0  # todavia aprendiendo el fondo
        mascara = cv2.medianBlur(mascara, 5)
        return cv2.countNonZero(mascara) / mascara.size


class RecorridoMapa:
    def __init__(self):
        self.calor = {}          # clave -> segundos con movimiento
        self.flujos = {}         # (origen, destino) -> cantidad de pasos
        self.pasos = []          # [(t, origen, destino)] en orden
        self._ultimo_mov = {}    # clave -> ultimo instante con movimiento
        self._activas = set()
        self._ultima_actualizacion = {}
        self._ultima_activacion = None   # (clave, t) de la ultima camara que se "encendio"

    def activas(self):
        return set(self._activas)

    def reiniciar(self):
        self.__init__()

    def actualizar(self, clave, nivel, t):
        """Nuevo nivel de movimiento de una camara en el instante t.
        Devuelve (origen, destino) si esto fue un paso entre camaras, o None."""
        anterior = self._ultima_actualizacion.get(clave)
        self._ultima_actualizacion[clave] = t
        if clave in self._activas and anterior is not None:
            self.calor[clave] = self.calor.get(clave, 0.0) + min(t - anterior, 2.0)

        if nivel < UMBRAL_ACTIVA:
            if clave in self._activas and t - self._ultimo_mov.get(clave, t) > SEG_PARA_APAGAR:
                self._activas.discard(clave)
            return None

        self._ultimo_mov[clave] = t
        if clave in self._activas:
            return None
        self._activas.add(clave)
        paso = None
        previa = self._ultima_activacion
        if previa and previa[0] != clave:
            origen = previa[0]
            # la referencia es cuando la otra camara vio movimiento por ULTIMA
            # vez (no cuando empezo): alguien que se quedo un rato en el patio
            # y despues paso al pasillo igual cuenta como paso
            if t - self._ultimo_mov.get(origen, previa[1]) <= VENTANA_PASO_SEG:
                paso = (origen, clave)
                self.flujos[paso] = self.flujos.get(paso, 0) + 1
                self.pasos.append((t, origen, clave))
        self._ultima_activacion = (clave, t)
        return paso
