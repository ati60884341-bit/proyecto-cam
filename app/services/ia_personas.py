"""IA de personas en la PC (no depende del NVR/DVR): sirve igual para una
Dahua por NVR, una Hikvision analogica por DVR o una camara IP suelta.

- DetectorPersonas: red neuronal NanoDet-Plus (OpenCV Zoo, licencia Apache
  2.0, ~4 MB en app/recursos/modelos) con el modulo DNN que ya trae OpenCV.
  Pre/post-proceso adaptado del demo oficial del OpenCV Zoo.
- color_ropa(): color dominante del torso y de las piernas, con nombre.
- zona_de(): en que zona dibujada esta parada la persona (o la mas cercana).
- Calibracion: 4 puntos del piso en la camara <-> 4 puntos del plano, para
  ubicar a cada persona sobre el Mapa del lugar (homografia).
- AnalizadorIA: hilo por camara que analiza el ULTIMO cuadro disponible
  (~4-5 por segundo) sin frenar la lectura del video.

Solo se describe ropa y donde esta: no se intenta adivinar edad, genero ni
ningun otro rasgo de la persona.
"""
import math
import os
import threading
import time

import cv2
import numpy as np

from app.config import RECURSOS_DIR

RUTA_MODELO = os.path.join(RECURSOS_DIR, "app", "recursos", "modelos", "nanodet.onnx")
TAM_ENTRADA = 416
STRIDES = (8, 16, 32, 64)
REG_MAX = 7
CLASE_PERSONA = 0
MEDIA = np.array([103.53, 116.28, 123.675], dtype=np.float32).reshape(1, 1, 3)
DESVIO = np.array([57.375, 57.12, 58.395], dtype=np.float32).reshape(1, 1, 3)


def _anclas():
    anclas = []
    for s in STRIDES:
        lado = TAM_ENTRADA // s
        xv, yv = np.meshgrid(np.arange(lado) * s, np.arange(lado) * s)
        anclas.append(np.column_stack((xv.flatten() + 0.5 * (s - 1), yv.flatten() + 0.5 * (s - 1))))
    return anclas


class DetectorPersonas:
    def __init__(self, umbral=0.45, umbral_nms=0.5):
        self.umbral = umbral
        self.umbral_nms = umbral_nms
        self._red = cv2.dnn.readNet(RUTA_MODELO)
        self._anclas = _anclas()
        self._proyeccion = np.arange(REG_MAX + 1, dtype=np.float32)

    def detectar(self, frame_bgr):
        """Lista de {"caja": (x0, y0, x1, y1) en pixeles del cuadro, "conf": 0..1}.

        La red ve todo achicado a 416x416: en un cuadro panoramico la gente
        lejana queda de pocos pixeles y se pierde (medido con una foto del
        laboratorio: 1 persona de 3; con recortes, las 3). Por eso, ademas
        del cuadro entero, se analizan dos "mosaicos" cuadrados que se
        solapan (izquierda y derecha) y se unen los resultados."""
        alto, ancho = frame_bgr.shape[:2]
        piezas = [(0, 0, frame_bgr)]
        if ancho > alto * 1.3:
            lado = alto
            piezas += [(0, 0, frame_bgr[:, :lado]), (ancho - lado, 0, frame_bgr[:, ancho - lado:])]
        cajas, confs = [], []
        for dx, dy, pieza in piezas:
            for det in self._detectar_pieza(pieza):
                x0, y0, x1, y1 = det["caja"]
                cajas.append([x0 + dx, y0 + dy, x1 - x0, y1 - y0])
                confs.append(det["conf"])
        if not cajas:
            return []
        indices = cv2.dnn.NMSBoxes(cajas, confs, self.umbral, self.umbral_nms)
        return [{"caja": (cajas[i][0], cajas[i][1], cajas[i][0] + cajas[i][2], cajas[i][1] + cajas[i][3]),
                 "conf": confs[i]} for i in np.array(indices).flatten()]

    def _detectar_pieza(self, frame_bgr):
        alto, ancho = frame_bgr.shape[:2]
        # letterbox: se achica sin deformar y se rellena con negro hasta 416x416
        escala = TAM_ENTRADA / max(alto, ancho)
        nw, nh = int(round(ancho * escala)), int(round(alto * escala))
        izq, arr = (TAM_ENTRADA - nw) // 2, (TAM_ENTRADA - nh) // 2
        lienzo = np.zeros((TAM_ENTRADA, TAM_ENTRADA, 3), np.uint8)
        lienzo[arr:arr + nh, izq:izq + nw] = cv2.resize(frame_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
        entrada = (cv2.cvtColor(lienzo, cv2.COLOR_BGR2RGB).astype(np.float32) - MEDIA) / DESVIO
        self._red.setInput(cv2.dnn.blobFromImage(entrada))
        salidas = self._red.forward(self._red.getUnconnectedOutLayersNames())

        # cada nivel tiene una salida de clases (80 col.) y una de cajas (32 col.);
        # se emparejan por forma, no por el orden de los nombres de las capas
        salidas = [s.reshape(-1, s.shape[-1]) for s in salidas]
        clases = sorted([s for s in salidas if s.shape[1] == 80], key=len, reverse=True)
        cajas_raw = sorted([s for s in salidas if s.shape[1] == 4 * (REG_MAX + 1)], key=len, reverse=True)

        cajas, confs = [], []
        for s, puntaje, reg, anclas in zip(STRIDES, clases, cajas_raw, self._anclas):
            conf = puntaje[:, CLASE_PERSONA]
            # solo donde la clase ganadora es "persona" y supera el umbral
            mask = (conf >= self.umbral) & (puntaje.argmax(axis=1) == CLASE_PERSONA)
            if not mask.any():
                continue
            r = np.exp(reg[mask].reshape(-1, REG_MAX + 1))
            dist = ((r / r.sum(axis=1, keepdims=True)) @ self._proyeccion).reshape(-1, 4) * s
            a = anclas[mask]
            cajas.append(np.column_stack((a[:, 0] - dist[:, 0], a[:, 1] - dist[:, 1],
                                          a[:, 0] + dist[:, 2], a[:, 1] + dist[:, 3])))
            confs.append(conf[mask])
        if not cajas:
            return []
        cajas = np.concatenate(cajas)
        confs = np.concatenate(confs)
        xywh = np.column_stack((cajas[:, :2], cajas[:, 2:] - cajas[:, :2]))
        indices = cv2.dnn.NMSBoxes(xywh.tolist(), confs.tolist(), self.umbral, self.umbral_nms)
        resultado = []
        for i in np.array(indices).flatten():
            x0, y0, x1, y1 = cajas[i]
            # de 416x416 (con relleno) a pixeles del cuadro original
            x0 = max(0, (x0 - izq) / escala)
            x1 = min(ancho, (x1 - izq) / escala)
            y0 = max(0, (y0 - arr) / escala)
            y1 = min(alto, (y1 - arr) / escala)
            if x1 - x0 > 4 and y1 - y0 > 8:
                resultado.append({"caja": (int(x0), int(y0), int(x1), int(y1)), "conf": float(confs[i])})
        return resultado


# ------------------------------------------------------------------ colores
COLORES_RGB = {   # para pintar el punto de la persona en el mapa
    "negro": (30, 30, 30), "blanco": (240, 240, 240), "gris": (140, 140, 140), "rojo": (220, 40, 40),
    "naranja": (240, 140, 30), "amarillo": (240, 220, 40), "verde": (50, 170, 70), "celeste": (90, 200, 230),
    "azul": (40, 90, 220), "azul oscuro": (25, 40, 110), "morado": (140, 60, 190), "rosado": (240, 120, 180),
    "marron": (120, 75, 40), "beige": (215, 195, 150),
}
NOMBRES_COLOR = list(COLORES_RGB)


def nombre_color(h, s, v):
    """HSV de OpenCV (h 0..180, s y v 0..255) -> nombre en espanol."""
    if v < 55:
        return "negro"
    if 8 <= h < 30 and 60 <= s < 110 and v > 140:
        return "beige"
    # con fluorescentes o sol de ventana el blanco sale algo azulado/amarillento:
    # muy claro y poco saturado sigue siendo blanco
    if s < 45 or (v > 165 and s < 80):
        return "blanco" if v > 165 else "gris"
    if 8 <= h < 22 and v < 130:
        return "marron"   # naranja oscuro
    if h < 9 or h >= 170:
        return "rojo"
    if h < 21:
        return "naranja"
    if h < 34:
        return "amarillo"
    if h < 85:
        return "verde"
    if h < 100:
        return "celeste"
    if h < 130:
        return "azul oscuro" if v < 110 else "azul"
    if h < 150:
        return "morado"
    return "rosado"


def _color_dominante(region_bgr):
    if region_bgr.size == 0 or region_bgr.shape[0] < 3 or region_bgr.shape[1] < 3:
        return None
    pix = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
    if len(pix) > 600:
        pix = pix[np.linspace(0, len(pix) - 1, 600).astype(int)]
    # el tono (h) es circular: rojo esta en 0 y en 180; se agrupa en (cos, sin)
    ang = pix[:, 0] * (2 * math.pi / 180)
    datos = np.column_stack((np.cos(ang) * pix[:, 1], np.sin(ang) * pix[:, 1], pix[:, 2])).astype(np.float32)
    k = min(3, len(datos))
    criterio = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 1.0)
    _, etiquetas, _ = cv2.kmeans(datos, k, None, criterio, 2, cv2.KMEANS_PP_CENTERS)
    mayor = np.bincount(etiquetas.flatten()).argmax()
    grupo = pix[etiquetas.flatten() == mayor]
    h = math.degrees(math.atan2(np.sin(grupo[:, 0] * math.pi / 90).mean(),
                                np.cos(grupo[:, 0] * math.pi / 90).mean())) / 2 % 180
    return nombre_color(h, float(np.median(grupo[:, 1])), float(np.median(grupo[:, 2])))


def color_ropa(frame_bgr, caja):
    """(arriba, abajo): torso = 20-50 % del alto de la caja, piernas = 58-85 %,
    tomando el centro (no los bordes, donde suele haber fondo)."""
    x0, y0, x1, y1 = caja
    w, h = x1 - x0, y1 - y0
    cx0, cx1 = int(x0 + w * 0.3), int(x0 + w * 0.7)
    arriba = _color_dominante(frame_bgr[int(y0 + h * 0.2):int(y0 + h * 0.5), cx0:cx1])
    abajo = _color_dominante(frame_bgr[int(y0 + h * 0.58):int(y0 + h * 0.85), int(x0 + w * 0.32):int(x0 + w * 0.68)])
    return arriba, abajo


# ------------------------------------------------------------------ zonas y plano
def pies(caja, ancho, alto):
    """Punto donde la persona pisa (centro del borde inferior), en 0..1."""
    x0, _, x1, y1 = caja
    return ((x0 + x1) / 2 / ancho, y1 / alto)


def _dentro(p, poligono):
    return cv2.pointPolygonTest(np.array(poligono, np.float32), p, False) >= 0


def _distancia(p, poligono):
    return abs(cv2.pointPolygonTest(np.array(poligono, np.float32), p, True))


def zona_de(punto, zonas):
    """zonas: [(nombre, [(x, y)...] en 0..1)]. Devuelve ("en", nombre),
    ("cerca", nombre) o (None, None) si no hay zonas dibujadas."""
    if not zonas:
        return None, None
    for nombre, poligono in zonas:
        if len(poligono) >= 3 and _dentro(punto, poligono):
            return "en", nombre
    validas = [(n, p) for n, p in zonas if len(p) >= 3]
    if not validas:
        return None, None
    nombre, _ = min(validas, key=lambda z: _distancia(punto, z[1]))
    return "cerca", nombre


def calcular_homografia(puntos_camara, puntos_plano):
    """4 pares de puntos (0..1) -> matriz 3x3 camara -> plano."""
    return cv2.getPerspectiveTransform(np.array(puntos_camara, np.float32), np.array(puntos_plano, np.float32))


def a_plano(punto, homografia):
    x, y = cv2.perspectiveTransform(np.array([[punto]], np.float32), homografia)[0][0]
    if not (-0.05 <= x <= 1.05 and -0.05 <= y <= 1.05):
        return None   # fuera del plano: la calibracion no cubre esa parte de la imagen
    return (min(1.0, max(0.0, float(x))), min(1.0, max(0.0, float(y))))


def analizar(detector, frame_bgr, zonas=None, homografia=None):
    """Detecta y describe a cada persona del cuadro."""
    alto, ancho = frame_bgr.shape[:2]
    personas = []
    for det in detector.detectar(frame_bgr):
        arriba, abajo = color_ropa(frame_bgr, det["caja"])
        punto = pies(det["caja"], ancho, alto)
        relacion, zona = zona_de(punto, zonas or [])
        personas.append({
            **det, "arriba": arriba, "abajo": abajo, "relacion": relacion, "zona": zona,
            "plano": a_plano(punto, homografia) if homografia is not None else None,
        })
    return personas


def describir(p):
    partes = []
    if p.get("arriba"):
        partes.append(f"arriba {p['arriba']}")
    if p.get("abajo"):
        partes.append(f"abajo {p['abajo']}")
    texto = ", ".join(partes)
    if p.get("zona"):
        texto += f"  ·  {'en' if p['relacion'] == 'en' else 'cerca de'} {p['zona']}"
    return texto


def dibujar(frame_bgr, personas, zonas=None):
    """Copia del cuadro con zonas (tenues) y recuadros verdes con su descripcion."""
    salida = frame_bgr.copy()
    alto, ancho = salida.shape[:2]
    g = max(1, ancho // 700)
    escala = max(0.4, ancho / 2300)
    for nombre, poligono in zonas or []:
        if len(poligono) < 3:
            continue
        pts = np.array([(int(x * ancho), int(y * alto)) for x, y in poligono], np.int32)
        capa = salida.copy()
        cv2.fillPoly(capa, [pts], (201, 214, 54))
        cv2.addWeighted(capa, 0.12, salida, 0.88, 0, salida)
        cv2.polylines(salida, [pts], True, (201, 214, 54), g, cv2.LINE_AA)
        cv2.putText(salida, nombre, tuple(pts.min(axis=0) + [6, int(22 * escala * 1.6)]),
                    cv2.FONT_HERSHEY_SIMPLEX, escala, (201, 214, 54), g, cv2.LINE_AA)
    verde = (60, 220, 60)
    for p in personas:
        x0, y0, x1, y1 = p["caja"]
        cv2.rectangle(salida, (x0, y0), (x1, y1), verde, g, cv2.LINE_AA)
        lineas = [f"Persona {p['conf'] * 100:.0f}%"]
        desc = describir(p)
        if desc:
            lineas += desc.split("  ·  ")
        alto_linea = int(26 * escala * 1.4)
        y = max(alto_linea * len(lineas) + 4, y0)
        tw = max(cv2.getTextSize(l, cv2.FONT_HERSHEY_SIMPLEX, escala, g)[0][0] for l in lineas)
        cv2.rectangle(salida, (x0, y - alto_linea * len(lineas) - 4), (x0 + tw + 12, y), verde, -1)
        for i, linea in enumerate(lineas):
            cv2.putText(salida, linea, (x0 + 6, y - alto_linea * (len(lineas) - 1 - i) - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, escala, (10, 30, 10), g, cv2.LINE_AA)
    if personas:
        texto = f"Personas en vista: {len(personas)}"
        cv2.putText(salida, texto, (12, alto - 14), cv2.FONT_HERSHEY_SIMPLEX, escala * 1.1, (0, 0, 0), g + 3, cv2.LINE_AA)
        cv2.putText(salida, texto, (12, alto - 14), cv2.FONT_HERSHEY_SIMPLEX, escala * 1.1, verde, g, cv2.LINE_AA)
    return salida


class AnalizadorIA:
    """Hilo por camara: toma el ULTIMO cuadro que le dejan y lo analiza. Si
    la red tarda mas que el video, los cuadros intermedios se saltan solos
    (no se encolan), asi nunca atrasa la camara."""

    INTERVALO_SEG = 0.2

    def __init__(self, al_resultado):
        self.al_resultado = al_resultado   # funcion(personas), se llama desde este hilo
        self.zonas = []
        self.homografia = None
        self.personas = []                 # ultimo resultado (lo dibuja el hilo de la camara)
        self._cuadro = None
        self._hay = threading.Event()
        self._activo = True
        self._hilo = threading.Thread(target=self._bucle, daemon=True)
        self._hilo.start()

    def entregar(self, frame_bgr):
        self._cuadro = frame_bgr
        self._hay.set()

    def detener(self):
        self._activo = False
        self._hay.set()

    def _bucle(self):
        detector = DetectorPersonas()   # una red por hilo: cv2.dnn no es seguro entre hilos
        while self._activo:
            self._hay.wait()
            self._hay.clear()
            frame = self._cuadro
            if not self._activo or frame is None:
                continue
            inicio = time.time()
            try:
                personas = analizar(detector, frame, self.zonas, self.homografia)
                for p in personas:   # recorte chico para la Busqueda (no la imagen entera)
                    x0, y0, x1, y1 = p["caja"]
                    recorte = frame[y0:y1, x0:x1]
                    if recorte.size:
                        alto = 180
                        p["recorte"] = cv2.resize(recorte, (max(1, int(recorte.shape[1] * alto / recorte.shape[0])), alto))
                self.personas = personas
                self.al_resultado(personas)
            except Exception as e:  # una falla puntual no debe matar la IA de la camara
                print(f"[IA] error analizando cuadro: {e}", flush=True)
            espera = self.INTERVALO_SEG - (time.time() - inicio)
            if espera > 0:
                time.sleep(espera)
