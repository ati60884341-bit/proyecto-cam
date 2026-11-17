"""Registro de avistamientos de la IA de personas, para la Busqueda
("persona de rojo cerca de la puerta").

Cada avistamiento = una persona vista por una camara en un momento: recorte
JPG chico + una linea JSON en evidencias/avistamientos/indice.jsonl. Archivo
plano, no tabla de SQL Server: no hace falta tocar el esquema de la base y
se borra simplemente borrando la carpeta.
"""
import json
import os
import re
import threading
import time
import unicodedata

import cv2

from app.config import EVIDENCIAS_DIR
from app.services.ia_personas import NOMBRES_COLOR

CARPETA = os.path.join(EVIDENCIAS_DIR, "avistamientos")
INDICE = os.path.join(CARPETA, "indice.jsonl")
_candado = threading.Lock()


def registrar(camara, personas, t=None, carpeta=None):
    """Guarda las personas de un cuadro (cada una con su "recorte")."""
    carpeta = carpeta or CARPETA
    t = t or time.time()
    dia = time.strftime("%Y%m%d", time.localtime(t))
    os.makedirs(os.path.join(carpeta, dia), exist_ok=True)
    lineas = []
    for i, p in enumerate(personas):
        recorte = p.get("recorte")
        if recorte is None:
            continue
        nombre = f"{time.strftime('%H%M%S', time.localtime(t))}_{int(t * 1000) % 1000:03d}_{i}_" + \
                 re.sub(r"[^\w]+", "_", camara)[:30] + ".jpg"
        ruta = os.path.join(carpeta, dia, nombre)
        cv2.imwrite(ruta, recorte, [cv2.IMWRITE_JPEG_QUALITY, 85])
        lineas.append(json.dumps({
            "t": t, "camara": camara, "arriba": p.get("arriba"), "abajo": p.get("abajo"),
            "relacion": p.get("relacion"), "zona": p.get("zona"), "conf": round(p.get("conf", 0), 2),
            "archivo": os.path.relpath(ruta, carpeta),
        }, ensure_ascii=False))
    if lineas:
        with _candado, open(os.path.join(carpeta, "indice.jsonl"), "a", encoding="utf-8") as f:
            f.write("\n".join(lineas) + "\n")
    return len(lineas)


def _plano(texto):
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


PRENDAS_ARRIBA = ("polo", "camisa", "casaca", "chompa", "polera", "blusa", "saco", "chaleco", "arriba", "camiseta", "buzo")
PRENDAS_ABAJO = ("pantalon", "jean", "falda", "short", "buzo abajo", "abajo", "bermuda", "jogger")


def interpretar_busqueda(texto):
    """'persona de polo rojo y pantalon azul cerca de la puerta' ->
    {"arriba": "rojo", "abajo": "azul", "zona": "puerta"}.
    Un color sin prenda se toma como 'arriba' (lo que mas se ve); un
    segundo color suelto, como 'abajo'."""
    t = _plano(texto)
    # "casaca blanca", "polera roja", "camisas negras" -> forma masculina singular
    t = re.sub(r"\b(blanc|negr|roj|amarill|morad|rosad|oscur)[ao]s\b|\b(blanc|negr|roj|amarill|morad|rosad|oscur)a\b",
               lambda m: (m.group(1) or m.group(2)) + "o", t)
    filtros = {"arriba": None, "abajo": None, "zona": None}
    m = re.search(r"\b(?:en|cerca de|cerca|junto a|por)\s+(?:la |el |los |las )?(.+)$", t)
    if m:
        filtros["zona"] = m.group(1).strip()
        t = t[:m.start()]
    # "azul oscuro" antes que "azul": se buscan primero los nombres largos
    colores = sorted(NOMBRES_COLOR, key=len, reverse=True)
    encontrados = []
    resto = t
    for c in colores:
        for mm in re.finditer(rf"\b{re.escape(c)}s?\b", resto):
            encontrados.append((mm.start(), c))
        resto = re.sub(rf"\b{re.escape(c)}s?\b", lambda x: " " * len(x.group(0)), resto)
    for pos, color in sorted(encontrados):
        antes = t[max(0, pos - 25):pos]
        if any(p in antes.split()[-2:] for p in PRENDAS_ABAJO):
            filtros["abajo"] = color
        elif any(p in antes.split()[-2:] for p in PRENDAS_ARRIBA):
            filtros["arriba"] = color
        elif filtros["arriba"] is None:
            filtros["arriba"] = color
        elif filtros["abajo"] is None:
            filtros["abajo"] = color
    return filtros


def buscar(arriba=None, abajo=None, zona=None, camara=None, carpeta=None, limite=200):
    """Avistamientos que cumplen los filtros, del mas nuevo al mas viejo.
    'zona' se compara sin tildes y por contenido ("puerta" encuentra "Puerta principal")."""
    carpeta = carpeta or CARPETA
    indice = os.path.join(carpeta, "indice.jsonl")
    if not os.path.exists(indice):
        return []
    zona = _plano(zona) if zona else None
    resultados = []
    with open(indice, encoding="utf-8") as f:
        for linea in f:
            try:
                a = json.loads(linea)
            except ValueError:
                continue
            if arriba and a.get("arriba") != arriba:
                continue
            if abajo and a.get("abajo") != abajo:
                continue
            if camara and a.get("camara") != camara:
                continue
            if zona and zona not in _plano(a.get("zona")):
                continue
            a["ruta"] = os.path.join(carpeta, a["archivo"])
            resultados.append(a)
    resultados.reverse()
    return resultados[:limite]
