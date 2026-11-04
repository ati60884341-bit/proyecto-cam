"""Deteccion automatica de camaras/grabadores en la red local ("radar de
camaras"): es el mismo mecanismo que usan las herramientas propias de cada
fabricante (SADP de Hikvision, ConfigTool de Dahua, etc.) para "buscar"
dispositivos sin que el usuario tenga que saber su IP de antemano.

Dos metodos, usados en orden:
1. WS-Discovery (estandar ONVIF): una sonda multicast UDP a la que
   responden los dispositivos con ONVIF habilitado, dando su IP. De ahi se
   consulta ONVIF directo al dispositivo para sacar marca/modelo reales
   (el propio equipo se identifica) y una estimacion de si es una camara
   suelta o un grabador con varios canales.
2. Barrido del puerto 554 (RTSP) en toda la subred: respaldo para equipos
   que no respondieron al WS-Discovery (ONVIF apagado, o firmware que no
   lo implementa bien - pasa seguido con equipos economicos). Estos quedan
   con marca/modelo "Desconocidos" salvo que un reintento de ONVIF directo
   contra esa IP si funcione.

Honestidad: esto es deteccion "de buena fe", no infalible. La cantidad de
canales (VideoSources de ONVIF) es una buena pista de si es un grabador,
pero no una garantia en todas las marcas/firmwares; el usuario confirma o
corrige al agregar el equipo desde las pestanas "Camaras" o "NVR / DVR".
"""

import ipaddress
import socket
import time
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from PyQt6.QtCore import QThread, pyqtSignal

GRUPO_WS_DISCOVERY = "239.255.255.250"
PUERTO_WS_DISCOVERY = 3702
TIEMPO_ESCUCHA_WS_DISCOVERY_SEG = 4.0

# puertos ONVIF conocidos por marca/modelo: 2020 es el que usa TP-Link Tapo
# (no el 80 "estandar" de la mayoria del resto); se prueban todos en orden
PUERTOS_ONVIF_COMUNES = (80, 8080, 2020, 8899, 8000)

_PROBE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
            xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
            xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
  <e:Header>
    <w:MessageID>uuid:{msgid}</w:MessageID>
    <w:To e:mustUnderstand="1">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
    <w:Action e:mustUnderstand="1">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
  </e:Header>
  <e:Body>
    <d:Probe>
      <d:Types>dn:NetworkVideoTransmitter</d:Types>
    </d:Probe>
  </e:Body>
</e:Envelope>"""


def _extraer_ip_de_probematch(datos_xml):
    """Saca el host del primer XAddr de una respuesta ProbeMatch. Si el XML
    no se puede interpretar (pasa con firmware que no sigue bien el
    estandar), se devuelve None y el llamador usa la IP de origen del
    paquete UDP como respaldo."""
    try:
        texto = datos_xml.decode("utf-8", errors="ignore")
        raiz = ET.fromstring(texto)
        for elem in raiz.iter():
            if elem.tag.endswith("XAddrs") and elem.text:
                primera_url = elem.text.strip().split()[0]
                return urlparse(primera_url).hostname
    except Exception:
        pass
    return None


def enviar_probe_ws_discovery(tiempo_escucha=TIEMPO_ESCUCHA_WS_DISCOVERY_SEG):
    """Manda la sonda WS-Discovery estandar de ONVIF por multicast UDP y
    escucha las respuestas (ProbeMatch) durante tiempo_escucha segundos.
    Devuelve un set de IPs distintas que respondieron."""
    mensaje = _PROBE_XML.format(msgid=uuid.uuid4()).encode("utf-8")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
    except OSError:
        pass

    ips = set()
    try:
        sock.sendto(mensaje, (GRUPO_WS_DISCOVERY, PUERTO_WS_DISCOVERY))
        fin = time.time() + tiempo_escucha
        while True:
            restante = fin - time.time()
            if restante <= 0:
                break
            sock.settimeout(restante)
            try:
                datos, direccion = sock.recvfrom(65535)
            except socket.timeout:
                break
            except OSError:
                break
            ip_respuesta = _extraer_ip_de_probematch(datos) or direccion[0]
            if ip_respuesta:
                ips.add(ip_respuesta)
    except OSError:
        pass  # sin red, o multicast bloqueado: se devuelve lo que se tenga (nada)
    finally:
        sock.close()
    return ips


# palabras clave para reconocer el texto LIBRE que cada fabricante pone en
# su propio campo ONVIF "Manufacturer" (ej. "Hangzhou Hikvision Digital
# Technology Co.,Ltd.", "TP-LINK") y llevarlo a la marca que usan los
# desplegables de "Camaras"/"NVR-DVR" en esta app
_PALABRAS_CLAVE_MARCA = {
    "hikvision": "Hikvision",
    "dahua": "Dahua",
    "tp-link": "Tapo",
    "tplink": "Tapo",
    "tapo": "Tapo",
}


def normalizar_marca(fabricante_onvif):
    """"Hangzhou Hikvision Digital Technology Co.,Ltd." -> "Hikvision"
    (la marca tal como aparece en los desplegables de la app). "Generico"
    si no se reconoce ninguna palabra clave - el usuario la ajusta a mano."""
    texto = (fabricante_onvif or "").lower()
    for clave, marca_app in _PALABRAS_CLAVE_MARCA.items():
        if clave in texto:
            return marca_app
    return "Generico"


def consultar_onvif(ip, usuario="admin", clave="", puertos=PUERTOS_ONVIF_COMUNES, timeout=2.5):
    """Prueba los puertos ONVIF mas comunes contra una IP. Si alguno
    responde, devuelve un dict con marca/modelo REALES (el dispositivo se
    identifica solo via GetDeviceInformation) y una estimacion de si es
    una camara suelta o un grabador, contando sus fuentes de video
    (GetVideoSources: una por canal fisico). None si ninguno respondio."""
    try:
        from onvif import ONVIFCamera
    except ImportError:
        return None

    for puerto in puertos:
        try:
            camara = ONVIFCamera(ip, puerto, usuario, clave)
            dispositivo = camara.create_devicemgmt_service()
            info = dispositivo.GetDeviceInformation()
        except Exception:
            continue

        canales = 1
        try:
            media = camara.create_media_service()
            fuentes = media.GetVideoSources()
            if fuentes:
                canales = len(fuentes)
        except Exception:
            pass  # algunos firmwares no exponen GetVideoSources: se asume 1

        marca_cruda = getattr(info, "Manufacturer", None) or "Desconocida"
        return {
            "ip": ip,
            "puerto_onvif": puerto,
            "marca": marca_cruda,
            "marca_app": normalizar_marca(marca_cruda),
            "modelo": getattr(info, "Model", None) or "Desconocido",
            "firmware": getattr(info, "FirmwareVersion", None) or "",
            "numero_serie": getattr(info, "SerialNumber", None) or "",
            "canales_detectados": canales,
            "tipo_estimado": "Grabador DVR/NVR" if canales > 1 else "Camara individual",
            "metodo": "ONVIF",
        }
    return None


def red_local_cidr():
    """Subred /24 de esta PC (ej. 192.168.1.0/24) para el barrido de
    respaldo, sin que el usuario tenga que escribir nada. No abre ninguna
    conexion de verdad (UDP "connect" solo elige la interfaz de salida)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip_local = s.getsockname()[0]
    except OSError:
        ip_local = "127.0.0.1"
    finally:
        s.close()
    partes = ip_local.split(".")
    return f"{'.'.join(partes[:3])}.0/24"


def escanear_puerto_554(red_cidr, timeout=0.3, hilos=60):
    """Barrido del puerto RTSP (554) en toda la subred: encuentra equipos
    que transmiten video pero no respondieron al WS-Discovery. Concurrente
    (ThreadPoolExecutor) para que revisar 254 direcciones tome segundos, no
    minutos."""
    red = ipaddress.ip_network(red_cidr, strict=False)
    encontrados = []

    def probar(ip):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((str(ip), 554))
            return str(ip)
        except OSError:
            return None
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=hilos) as pool:
        futuros = [pool.submit(probar, ip) for ip in red.hosts()]
        for futuro in as_completed(futuros):
            resultado = futuro.result()
            if resultado:
                encontrados.append(resultado)
    return encontrados


class RadarEscaneoThread(QThread):
    """Orquesta WS-Discovery + (opcional) barrido de puerto 554, emitiendo
    cada hallazgo apenas se identifica (no espera a terminar todo), para
    que la tabla del "Radar de camaras" se vaya llenando en vivo."""

    progreso = pyqtSignal(str)
    dispositivo_encontrado = pyqtSignal(dict)
    terminado = pyqtSignal(int)  # total de dispositivos encontrados

    def __init__(self, escaneo_completo=False, usuario="admin", clave="", parent=None):
        super().__init__(parent)
        self.escaneo_completo = escaneo_completo
        # algunas marcas (ej. Tapo) exigen usuario/clave incluso para
        # identificarse por ONVIF (GetDeviceInformation) - sin esto
        # quedaban siempre como "Desconocida/Desconocido" aunque
        # respondieran. Es la "Cuenta de camara" de cada marca, no la de
        # la app del celular - el usuario la escribe si hace falta.
        self.usuario = usuario
        self.clave = clave
        self._total = 0

    def _emitir(self, info):
        self._total += 1
        self.dispositivo_encontrado.emit(info)

    def run(self):
        self.progreso.emit("Enviando sonda ONVIF (WS-Discovery) por la red local...")
        ips_onvif = enviar_probe_ws_discovery()

        ips_ya_reportadas = set()
        for ip in sorted(ips_onvif, key=lambda s: tuple(int(p) for p in s.split("."))):
            self.progreso.emit(f"Identificando {ip}...")
            info = consultar_onvif(ip, usuario=self.usuario, clave=self.clave)
            if not info:
                info = {
                    "ip": ip, "puerto_onvif": None, "marca": "Desconocida", "marca_app": "Generico", "modelo": "Desconocido",
                    "firmware": "", "numero_serie": "", "canales_detectados": 1,
                    "tipo_estimado": "Dispositivo ONVIF (pide usuario/clave - complete los campos y reintente esta fila)",
                    "metodo": "WS-Discovery",
                }
            self._emitir(info)
            ips_ya_reportadas.add(ip)

        if self.escaneo_completo:
            red = red_local_cidr()
            self.progreso.emit(f"Revisando toda la red {red} por el puerto 554 (RTSP)... puede tardar un minuto.")
            for ip in escanear_puerto_554(red):
                if ip in ips_ya_reportadas:
                    continue
                info = consultar_onvif(ip, usuario=self.usuario, clave=self.clave) or {
                    "ip": ip, "puerto_onvif": None, "marca": "Desconocida", "marca_app": "Generico", "modelo": "Desconocido",
                    "firmware": "", "numero_serie": "", "canales_detectados": 1,
                    "tipo_estimado": "Transmite RTSP (pide usuario/clave, o no tiene ONVIF)",
                    "metodo": "Puerto 554 abierto",
                }
                self._emitir(info)

        self.progreso.emit(
            f"Escaneo terminado: {self._total} dispositivo(s) encontrado(s)." if self._total
            else "Escaneo terminado: no se encontro ningun dispositivo."
        )
        self.terminado.emit(self._total)


class ReintentoCredencialesThread(QThread):
    """Reintenta UNA sola IP con usuario/clave, sin repetir todo el
    escaneo: para cuando una fila quedo "Desconocida" porque la camara
    (ej. Tapo) exige autenticacion hasta para GetDeviceInformation."""

    resultado = pyqtSignal(dict)

    def __init__(self, ip, usuario="admin", clave="", parent=None):
        super().__init__(parent)
        self.ip = ip
        self.usuario = usuario
        self.clave = clave

    def run(self):
        info = consultar_onvif(self.ip, usuario=self.usuario, clave=self.clave)
        if not info:
            info = {
                "ip": self.ip, "puerto_onvif": None, "marca": "Desconocida", "marca_app": "Generico",
                "modelo": "Desconocido", "firmware": "", "numero_serie": "", "canales_detectados": 1,
                "tipo_estimado": "Sigue sin responder ONVIF con ese usuario/clave",
                "metodo": "Reintento con credenciales",
            }
        self.resultado.emit(info)
