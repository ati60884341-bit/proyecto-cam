"""Linea virtual: cuenta lo que se mueve y cruza una linea dibujada sobre la
imagen de una camara FIJA (analogica por DVR o IP, da igual: lo hace la PC).

Deteccion por fondo/primer plano (MOG2 de OpenCV): con la camara quieta, el
fondo se aprende solo y cualquier cosa que se mueva aparece como una mancha.
Cada mancha se sigue cuadro a cuadro por cercania de su centro, y cuando ese
centro pasa de un lado de la linea al otro cuenta como un cruce.

Coordenadas de la linea en 0..1 (relativas al ancho/alto del cuadro), para
que sirvan igual en el video 1080p del DVR o en el sub-stream chico.
"""
import math

import cv2

ANCHO_PROCESO = 320          # se analiza achicado: rapido incluso con varias camaras
AREA_MINIMA = 0.004          # fraccion del cuadro: menos que esto es ruido (hojas, compresion)
DISTANCIA_MAXIMA = 0.15      # fraccion del ancho: mas lejos que esto es "otro objeto"
CUADROS_SIN_VER = 8          # un objeto que no se ve en estos cuadros se olvida
CUADROS_APRENDER = 15        # al principio solo se aprende el fondo, sin contar


def _lado(p, a, b):
    """Positivo de un lado de la recta a->b, negativo del otro."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _cruza_segmento(p, q, a, b):
    """True si el trayecto p->q atraviesa el segmento a-b (no solo la recta)."""
    d1, d2 = _lado(p, a, b), _lado(q, a, b)
    d3, d4 = _lado(a, p, q), _lado(b, p, q)
    return d1 * d2 < 0 and d3 * d4 < 0


class DetectorLinea:
    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2
        self.entradas = 0   # cruces en un sentido ("A -> B")
        self.salidas = 0    # cruces en el otro
        self._fondo = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=32, detectShadows=True)
        self._nucleo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self._objetos = {}   # id -> {"centro": (x, y) en 0..1, "sin_ver": int}
        self._siguiente_id = 0
        self._cuadros = 0
        self._cajas = []     # ultimas cajas detectadas (0..1), para dibujar

    @property
    def total(self):
        return self.entradas + self.salidas

    def procesar(self, frame):
        """Analiza un cuadro BGR. Devuelve la lista de cruces nuevos en este
        cuadro: cada uno es +1 (sentido A->B) o -1 (sentido contrario)."""
        alto, ancho = frame.shape[:2]
        escala = ANCHO_PROCESO / ancho
        chico = cv2.resize(frame, (ANCHO_PROCESO, max(1, int(alto * escala))), interpolation=cv2.INTER_AREA)
        mascara = self._fondo.apply(chico)
        self._cuadros += 1
        if self._cuadros <= CUADROS_APRENDER:
            return []
        # 127 = sombra (MOG2): se descarta para no contar sombras como personas
        _, mascara = cv2.threshold(mascara, 200, 255, cv2.THRESH_BINARY)
        mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, self._nucleo)
        mascara = cv2.dilate(mascara, self._nucleo, iterations=2)
        contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        ach, alc = mascara.shape[1], mascara.shape[0]
        area_minima = AREA_MINIMA * ach * alc
        centros, self._cajas = [], []
        for c in contornos:
            if cv2.contourArea(c) < area_minima:
                continue
            x, y, w, h = cv2.boundingRect(c)
            self._cajas.append((x / ach, y / alc, w / ach, h / alc))
            centros.append(((x + w / 2) / ach, (y + h / 2) / alc))
        return self._seguir(centros)

    def _seguir(self, centros):
        cruces = []
        libres = set(self._objetos)
        for centro in centros:
            mejor, mejor_d = None, DISTANCIA_MAXIMA
            for oid in libres:
                d = math.dist(centro, self._objetos[oid]["centro"])
                if d < mejor_d:
                    mejor, mejor_d = oid, d
            if mejor is None:
                self._objetos[self._siguiente_id] = {"centro": centro, "sin_ver": 0}
                self._siguiente_id += 1
                continue
            libres.discard(mejor)
            anterior = self._objetos[mejor]["centro"]
            if _cruza_segmento(anterior, centro, self.p1, self.p2):
                sentido = 1 if _lado(centro, self.p1, self.p2) > 0 else -1
                if sentido > 0:
                    self.entradas += 1
                else:
                    self.salidas += 1
                cruces.append(sentido)
            self._objetos[mejor] = {"centro": centro, "sin_ver": 0}
        for oid in libres:
            self._objetos[oid]["sin_ver"] += 1
            if self._objetos[oid]["sin_ver"] > CUADROS_SIN_VER:
                del self._objetos[oid]
        return cruces

    def dibujar(self, frame, resaltar=False):
        """Devuelve una COPIA del cuadro con la linea, las cajas y el contador
        (el original queda limpio para evidencias y el buffer)."""
        salida = frame.copy()
        alto, ancho = salida.shape[:2]
        grosor = max(2, ancho // 320)
        a = (int(self.p1[0] * ancho), int(self.p1[1] * alto))
        b = (int(self.p2[0] * ancho), int(self.p2[1] * alto))
        color_linea = (60, 60, 255) if resaltar else (201, 214, 54)  # rojo al cruzar / turquesa de la app
        cv2.line(salida, a, b, color_linea, grosor * 2, cv2.LINE_AA)
        cv2.circle(salida, a, grosor * 3, color_linea, -1, cv2.LINE_AA)
        cv2.circle(salida, b, grosor * 3, color_linea, -1, cv2.LINE_AA)
        for x, y, w, h in self._cajas:
            cv2.rectangle(
                salida, (int(x * ancho), int(y * alto)), (int((x + w) * ancho), int((y + h) * alto)),
                (0, 200, 255), grosor, cv2.LINE_AA,
            )
        texto = f"Entran {self.entradas}  |  Salen {self.salidas}"
        escala = max(0.5, ancho / 900)
        (tw, th), base = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, escala, grosor)
        cv2.rectangle(salida, (8, 8), (8 + tw + 16, 8 + th + base + 16), (20, 20, 20), -1)
        cv2.putText(salida, texto, (16, 16 + th), cv2.FONT_HERSHEY_SIMPLEX, escala, (255, 255, 255), grosor, cv2.LINE_AA)
        return salida
