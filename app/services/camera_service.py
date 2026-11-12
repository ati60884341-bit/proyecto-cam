import os
import socket
import subprocess
import threading
import time
from collections import deque
from urllib.parse import urlparse

# el backend FFMPEG de OpenCV solo respeta el timeout de conexion RTSP via
# esta variable de entorno (CAP_PROP_OPEN_TIMEOUT_MSEC no siempre funciona);
# debe fijarse antes de abrir cualquier VideoCapture RTSP
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|stimeout;4000000|timeout;4000000|max_delay;500000",
)

import cv2
from PyQt6.QtCore import QThread, pyqtSignal

from app.config import BUFFER_SEGUNDOS, CAPTURA_FPS, UMBRAL_SABOTAJE, EVIDENCIAS_DIR

TIMEOUT_CONEXION_RTSP_SEG = 4.0
LECTURAS_FALLIDAS_PARA_RECONECTAR = 40  # ~2s de lecturas fallidas seguidas -> reconectar
RESINCRONIZACION_PERIODICA_SEG = 600    # reconexion preventiva: limita cuanto se acumula
                                         # la corrupcion H.264 entre fotogramas clave (I-frames).
                                         # Era 120 s: cada reconexion congela ~1.5 s la imagen,
                                         # y el atraso ahora lo vigila ATRASO_MAXIMO_SEG
ATRASO_MAXIMO_SEG = 1.5                 # si el video va mas de esto detras del tiempo real, se resincroniza
CALIDAD_JPEG_BUFFER = 85                # "maquina del tiempo" comprimida (ver CamaraThread._buffer)
SEGUNDOS_FOTO_ANTES = 3                 # la foto de evidencia es de estos segundos antes del sabotaje
FPS_WEBCAM = 30                        # la webcam local da 30 fps de verdad; los DVR/NVR, CAPTURA_FPS
# exposicion de la webcam (escala de DirectShow: 2^n segundos). Con la
# automatica del driver, en poca luz la webcam alarga la exposicion y cae a
# ~5-8 fps (medido). Se controla a mano: -4 da ~24 fps y -3 ~13 fps. La
# ganancia tiene tope bajo: con ganancia alta el sensor pierde el color y la
# imagen queda gris (medido: saturacion 8 con ganancia 124, 25 con 80), asi
# que con poca luz se prefiere bajar a -3 antes que subir la ganancia.
EXPOSICION_WEBCAM_RAPIDA = -7
EXPOSICION_WEBCAM_FLUIDA = -4
EXPOSICION_WEBCAM_LENTA = -3
GANANCIA_WEBCAM_MAXIMA = 80
BRILLO_OBJETIVO = (80, 160)


def _abrir_captura(tipo_conexion, url_conexion):
    if tipo_conexion == "USB":
        try:
            indice = int(url_conexion)
        except (TypeError, ValueError):
            indice = 0
        cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
        # por defecto DirectShow abre la webcam a 640x480: se pide HD en MJPG
        # (comprimido en la camara: el USB alcanza para 720p a 30 fps sin
        # atraso). Si la webcam no lo soporta, se queda con lo que tenga.
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, FPS_WEBCAM)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    # los timeouts van COMO PARAMETROS de open(): fijarlos con cap.set() antes
    # de abrir (como se hacia) OpenCV los ignora y usa su default de 30s. Eso
    # importa mucho: OpenCV abre las capturas FFmpeg de a una (candado global),
    # asi que un solo canal colgado (ej. canal vacio de un NVR Dahua) frenaba
    # 30s la conexion de TODAS las demas camaras
    timeout_ms = int(TIMEOUT_CONEXION_RTSP_SEG * 1000)
    cap = cv2.VideoCapture()
    try:
        cap.open(url_conexion, cv2.CAP_FFMPEG, [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms,
        ])
    except (cv2.error, TypeError):
        cap.open(url_conexion, cv2.CAP_FFMPEG)  # build viejo sin parametros en open()
    try:
        # buffer minimo: sin esto, OpenCV acumula frames viejos en cola y el
        # video en pantalla se va atrasando cada vez mas respecto al tiempo real
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    return cap


def _puerto_abierto(host, puerto, timeout=2.0):
    try:
        with socket.create_connection((host, puerto), timeout=timeout):
            return True
    except OSError:
        return False


def _servidor_alcanzable(url_rtsp, timeout=2.0):
    """Verificacion TCP rapida antes de invocar a FFmpeg: si el host:puerto no
    responde en `timeout` segundos, no tiene sentido lanzar el intento de
    apertura RTSP (que de otro modo puede tardar ~30s en fallar)."""
    partes = urlparse(url_rtsp)
    host = partes.hostname
    if not host:
        return True  # url no estandar: se deja intentar con cv2 igual
    puerto = partes.port or 554
    return _puerto_abierto(host, puerto, timeout)


def _hay_ruta_de_red(ip, timeout=1.5):
    """Ping ICMP real al equipo (no solo su puerto RTSP): distingue "no hay
    ruta de red hasta el" (cable/switch/subred) de "la red llega pero el
    puerto no responde" (servicio apagado/credenciales). Usa el comando de
    ping del sistema operativo en vez de una libreria nueva, siguiendo el
    mismo criterio que el Radar de camaras (sin dependencias nuevas)."""
    try:
        if os.name == "nt":
            comando = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
            flags = subprocess.CREATE_NO_WINDOW
        else:
            comando = ["ping", "-c", "1", "-W", str(max(1, int(timeout))), ip]
            flags = 0
        resultado = subprocess.run(
            comando, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=timeout + 1, creationflags=flags,
        )
        # en Windows, si el ARP falla la PC se responde a si misma "Host de
        # destino inaccesible" y ping sale con codigo 0 aunque el equipo no
        # exista: solo una respuesta real trae TTL=
        return resultado.returncode == 0 and b"TTL=" in resultado.stdout.upper()
    except Exception:
        return False


def _diagnostico_red(host, puerto, timeout_ping=1.5, timeout_puerto=2.0):
    """Cuando un DVR/camara no respondio, arma un mensaje que distingue EN QUE
    CAPA se corto la conexion, para no dejar al tecnico en terreno con un
    generico "revise la red":
    1) ping ICMP: hay ruta de red hasta el equipo (cable/switch/misma subred)
    2) puerto TCP: el equipo responde pero el servicio/puerto no
    Devuelve None si en realidad el puerto ya responde (nada que explicar)."""
    if _puerto_abierto(host, puerto, timeout_puerto):
        return None
    if not _hay_ruta_de_red(host, timeout_ping):
        return (
            f"Sin respuesta de red (ping) a {host}. Revise que el equipo este "
            "encendido, el cable de red al switch/router, y que esta PC este en "
            f"la misma red (misma subred) que {host}."
        )
    return (
        f"La red llega a {host} pero el puerto {puerto} no responde. Revise que "
        "el DVR/NVR tenga el servicio de video en red activo, el puerto "
        "configurado, y que no haya un firewall bloqueandolo."
    )


def _ips_locales():
    """IPv4 de esta PC (cable y Wi-Fi), sin loopback ni APIPA (169.254.x)."""
    try:
        ips = socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        ips = []
    return [ip for ip in ips if not ip.startswith(("127.", "169.254."))]


def _buscar_equipos_de_video(ip_esperada, puerto):
    """Cuando el DVR no responde en la IP registrada, lo mas comun es que
    haya cambiado de IP: con DHCP activo el router le da otra (ej. queda en
    .103 en vez del .64 de fabrica de Hikvision). Barre el puerto de video
    en las subredes /24 de esta PC y devuelve las IPs que lo tienen abierto,
    para que el tecnico vea donde quedo el grabador en vez de un "no responde"."""
    from concurrent.futures import ThreadPoolExecutor
    import ipaddress

    locales = _ips_locales()
    redes = {ipaddress.ip_network(f"{ip}/24", strict=False) for ip in locales}
    candidatos = [str(h) for red in redes for h in red.hosts()
                  if str(h) not in locales and str(h) != ip_esperada]
    if not candidatos:
        return []
    with ThreadPoolExecutor(max_workers=64) as pool:
        abiertos = pool.map(lambda ip: ip if _puerto_abierto(ip, puerto, 0.4) else None, candidatos)
        return sorted((ip for ip in abiertos if ip), key=lambda ip: tuple(int(p) for p in ip.split(".")))


def _sugerencia_ip_alternativa(ip_esperada, puerto):
    encontrados = _buscar_equipos_de_video(ip_esperada, puerto)
    if not encontrados:
        return ""
    lista = ", ".join(encontrados[:5])
    return (
        f" En esta red SI hay equipo(s) de video con el puerto {puerto} abierto: {lista}. "
        "Probablemente el grabador cambio de IP (DHCP activo): vea su IP real en el "
        "DVR (Configuracion > Red > TCP/IP), registrelo con esa IP y, para que no vuelva "
        "a cambiar, desactive DHCP en el DVR y deje esa IP fija."
    )


def _diagnostico_credenciales(marca, ip, usuario, clave, timeout=4.0):
    """Si el grabador responde pero ningun canal dio imagen, la causa mas
    comun es usuario/clave. RTSP (via FFmpeg) no distingue ese caso, asi que
    se pregunta a la API web del grabador con autenticacion Digest: un 401
    ahi confirma que la clave es la que esta mal. Devuelve None si no se
    puede saber (sin web, marca desconocida) o si la clave es correcta."""
    if not clave:
        return (
            "Este grabador quedo registrado SIN clave y el DVR la exige. Quitelo "
            "y registrelo de nuevo escribiendo la clave del DVR."
        )
    rutas = {
        "Hikvision": "/ISAPI/System/deviceInfo",
        "Dahua": "/cgi-bin/magicBox.cgi?action=getDeviceType",
    }
    ruta = rutas.get(marca)
    if not ruta:
        return None
    try:
        import requests
        from requests.auth import HTTPDigestAuth

        r = requests.get(f"http://{ip}{ruta}", auth=HTTPDigestAuth(usuario, clave), timeout=timeout)
    except Exception:
        return None
    if r.status_code == 401:
        return (
            f"El grabador {ip} rechazo el usuario \"{usuario}\" o la clave. Revise la "
            "clave (distingue mayusculas) y vuelva a registrarlo. Ojo: tras varios "
            "intentos fallidos el DVR bloquea al usuario unos 30 minutos."
        )
    return None


def _abrir_captura_sin_bloqueo(tipo_conexion, url_conexion):
    """Para RTSP: verificacion TCP rapida (2s) y, si el host responde, apertura
    con timeout real (ver _abrir_captura). Se llama solo desde hilos de fondo
    (CamaraThread, deteccion de canales, prueba de conexion), nunca desde la UI.

    Antes se abria en un hilo daemon con un watchdog de 4s: si se pasaba, se
    devolvia "sin senal" pero el intento seguia vivo esperando el candado
    global de OpenCV, y cada reintento (cada ~7s por camara) sumaba otro a la
    fila. Con un canal colgado la fila crecia sin fin y ninguna camara volvia
    a conectar; las que si abrian en segundo plano quedaban sin liberar,
    ocupando conexiones del DVR. Ahora cada hilo hace un solo intento a la vez."""
    if tipo_conexion == "USB":
        return _abrir_captura(tipo_conexion, url_conexion)

    if not _servidor_alcanzable(url_conexion):
        return None
    return _abrir_captura(tipo_conexion, url_conexion)


class CamaraThread(QThread):
    """Hilo independiente por camara (QThread): captura, deteccion de sabotaje
    y buffer RAM de los ultimos BUFFER_SEGUNDOS ("maquina del tiempo")."""

    frame_listo = pyqtSignal(object)          # numpy array BGR, para pintar en la UI
    estado_cambiado = pyqtSignal(str)         # "conectada" | "sin_senal" | "sabotaje" | "reconectando"
    sabotaje_detectado = pyqtSignal(str, str, str)  # zona, ruta_video, ruta_foto

    def __init__(self, id_camara, zona, nombre_camara, tipo_conexion, url_conexion, parent=None):
        super().__init__(parent)
        self.id_camara = id_camara
        self.zona = zona
        self.nombre_camara = nombre_camara
        self.tipo_conexion = tipo_conexion
        self.url_conexion = url_conexion
        self._activo = True
        self._fps = FPS_WEBCAM if tipo_conexion == "USB" else CAPTURA_FPS

        # los ultimos BUFFER_SEGUNDOS en JPEG, no en crudo: un frame 1080p
        # crudo pesa 6.2 MB (8 s = ~500 MB por camara, la app llego a 1.1 GB
        # con 2 camaras); en JPEG son ~325 KB (~26 MB por camara)
        self._buffer = deque(maxlen=BUFFER_SEGUNDOS * self._fps)
        self._ultimo_frame = None
        self._baseline_brillo = None
        self._baseline_bordes = None
        self._lecturas_tapada = 0
        self._en_sabotaje = False
        self._ultimo_sabotaje = 0.0
        self._aprender_desde = 0.0
        self._forzar_reconexion = False
        # entrega a la UI "solo el ultimo frame": no se manda uno nuevo hasta
        # que la interfaz pinto el anterior (ver confirmar_entrega). Sin esto
        # las senales se encolaban sin limite cuando la UI iba mas lenta, el
        # video se atrasaba y los avisos de sabotaje (misma cola) llegaban tarde
        self._entrega_pendiente = False

    def confirmar_entrega(self):
        """La UI llama esto al terminar de pintar un frame de esta camara."""
        self._entrega_pendiente = False

    def detener(self):
        self._activo = False

    def forzar_reconexion(self):
        """Pide resincronizar con un fotograma clave nuevo (ej. justo despues
        de un movimiento PTZ, cuando el video suele verse mas distorsionado)."""
        self._forzar_reconexion = True

    # % de pixeles de borde (Canny) por debajo del cual la escena "perdio el
    # detalle", relativo a su linea base: una camara tapada queda en ~0%
    PROPORCION_BORDES_TAPADA = 0.2
    BORDES_MINIMOS_PARA_COMPARAR = 0.5   # escena muy oscura/lisa: solo regla de brillo
    LECTURAS_PARA_CONFIRMAR = 2          # 2 frames seguidos (~0.2s): evita falsos por un frame raro
    ESPERA_APRENDER_SEG = 1.5            # lo que tarda la imagen en estabilizarse (al encender / tras exposicion)

    def _iniciar_aprendizaje(self):
        """Olvida la linea base y la vuelve a tomar de la escena ya estable.
        La linea base solo se actualiza mientras la camara NO parece tapada:
        si arranca mal (el primer cuadro de una webcam suele ser negro) o
        queda vieja tras un cambio de exposicion, el detector se trababa en
        "sabotaje" para siempre y una tapada real ya no hacia sonar nada."""
        self._baseline_brillo = None
        self._baseline_bordes = None
        self._lecturas_tapada = 0
        self._aprender_desde = time.time() + self.ESPERA_APRENDER_SEG

    def _actualizar_sabotaje(self, frame):
        if time.time() < self._aprender_desde:
            return
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # meanStdDev de OpenCV: mismo resultado que numpy mean/std pero ~10x
        # mas rapido (std de numpy tomaba ~12 ms por cuadro y bajaba los fps)
        media, desv = cv2.meanStdDev(gris)
        brillo = float(media[0][0])
        desviacion = float(desv[0][0])
        chico = cv2.resize(gris, (320, 240), interpolation=cv2.INTER_AREA)
        bordes = float((cv2.Canny(cv2.GaussianBlur(chico, (5, 5), 0), 40, 120) > 0).mean() * 100)

        if self._baseline_brillo is None:
            self._baseline_brillo = brillo
            self._baseline_bordes = bordes
            return

        # 1) regla original: cambio brusco de brillo + imagen uniforme (la
        #    camara se pone negra, o la apuntan a una luz)
        cambio_brillo = abs(brillo - self._baseline_brillo) > UMBRAL_SABOTAJE and desviacion < 28.0
        # 2) perdida de detalle: las camaras analogicas/IP con ganancia
        #    automatica (las del DVR) suben el brillo al taparlas y quedan en
        #    un gris con ruido - la regla 1 no se cumplia (o tarde, solo el
        #    instante antes de que la ganancia compensara). Los bordes, en
        #    cambio, caen a ~0% apenas se tapa, sin importar la ganancia.
        perdida_detalle = (
            self._baseline_bordes >= self.BORDES_MINIMOS_PARA_COMPARAR
            and bordes < self._baseline_bordes * self.PROPORCION_BORDES_TAPADA
            and desviacion < 40.0
        )
        self._lecturas_tapada = self._lecturas_tapada + 1 if (cambio_brillo or perdida_detalle) else 0
        cambio_brusco = self._lecturas_tapada >= self.LECTURAS_PARA_CONFIRMAR
        ahora = time.time()
        enfriamiento_activo = (ahora - self._ultimo_sabotaje) < 15.0

        if cambio_brusco and not self._en_sabotaje and not enfriamiento_activo:
            self._en_sabotaje = True
            self._ultimo_sabotaje = ahora
            self.estado_cambiado.emit("sabotaje")
            # en otro hilo: armar el video (descomprimir 8 s y escribirlo) tardaba
            # 1.5-4 s y, mientras tanto, esta camara dejaba de leer: la imagen se congelaba
            threading.Thread(
                target=self._exportar_evidencia_sabotaje, args=(list(self._buffer),), daemon=True,
            ).start()
        elif self._lecturas_tapada == 0:
            if self._en_sabotaje:
                self.estado_cambiado.emit("conectada")
            self._en_sabotaje = False
            # linea base lenta: se adapta a cambios normales de iluminacion
            self._baseline_brillo = 0.98 * self._baseline_brillo + 0.02 * brillo
            self._baseline_bordes = 0.98 * self._baseline_bordes + 0.02 * bordes

    def _exportar_evidencia_sabotaje(self, jpgs):
        frames = [f for f in (cv2.imdecode(j, cv2.IMREAD_COLOR) for j in jpgs) if f is not None]
        if not frames:
            return
        marca_tiempo = time.strftime("%Y%m%d_%H%M%S")
        base = f"sabotaje_{self.zona}_{marca_tiempo}".replace(" ", "_")

        # foto unos segundos antes del bloqueo (el rostro del culpable acercandose)
        indice_foto = max(0, len(frames) - SEGUNDOS_FOTO_ANTES * self._fps)
        ruta_foto = os.path.join(EVIDENCIAS_DIR, base + ".jpg")
        cv2.imwrite(ruta_foto, frames[indice_foto])

        # video con los BUFFER_SEGUNDOS previos al bloqueo (la "maquina del tiempo")
        alto, ancho = frames[0].shape[:2]
        ruta_video = os.path.join(EVIDENCIAS_DIR, base + ".avi")
        escritor = cv2.VideoWriter(ruta_video, cv2.VideoWriter_fourcc(*"XVID"), self._fps, (ancho, alto))
        for f in frames:
            escritor.write(f)
        escritor.release()

        self.sabotaje_detectado.emit(self.zona, ruta_video, ruta_foto)

    def _iniciar_exposicion_webcam(self, captura):
        captura.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # 0.25 = manual en DirectShow
        self._exposicion = EXPOSICION_WEBCAM_FLUIDA
        captura.set(cv2.CAP_PROP_EXPOSURE, self._exposicion)
        self._ganancia_original = captura.get(cv2.CAP_PROP_GAIN)
        self._ganancia = min(self._ganancia_original, GANANCIA_WEBCAM_MAXIMA)
        captura.set(cv2.CAP_PROP_GAIN, self._ganancia)

    def _poner_exposicion(self, captura, exposicion):
        self._exposicion = exposicion
        captura.set(cv2.CAP_PROP_EXPOSURE, exposicion)
        # el brillo cambia de golpe (y no en una proporcion fija): se vuelve a
        # aprender la escena en vez de tomarlo como camara tapada
        self._iniciar_aprendizaje()

    def _poner_ganancia(self, captura, ganancia):
        if ganancia < 0 or not captura.set(cv2.CAP_PROP_GAIN, ganancia):
            return False
        self._ganancia = ganancia
        return True

    def _ajustar_exposicion_webcam(self, captura, frame):
        """Un paso por llamada, y pasos chicos de ganancia: un salto de brillo
        grande se confundiria con una camara tapada. Con poca luz: exposicion
        hasta la fluida, ganancia hasta su tope, y recien ahi la lenta. Con
        mucha luz, al reves."""
        if self._en_sabotaje or self._lecturas_tapada:
            return  # parece tapada: compensar la oscuridad taparia el sabotaje
        brillo = float(frame[::8, ::8].mean())
        minimo, maximo = BRILLO_OBJETIVO
        if minimo <= brillo <= maximo:
            return
        if brillo < minimo:
            if self._exposicion < EXPOSICION_WEBCAM_FLUIDA:
                self._poner_exposicion(captura, self._exposicion + 1)
            elif self._ganancia + 6 <= GANANCIA_WEBCAM_MAXIMA and self._poner_ganancia(captura, self._ganancia + 6):
                pass
            elif self._exposicion < EXPOSICION_WEBCAM_LENTA:
                self._poner_exposicion(captura, self._exposicion + 1)
        else:
            if self._exposicion > EXPOSICION_WEBCAM_FLUIDA:
                self._poner_exposicion(captura, self._exposicion - 1)
            elif self._poner_ganancia(captura, self._ganancia - 6):
                pass
            elif self._exposicion > EXPOSICION_WEBCAM_RAPIDA:
                self._poner_exposicion(captura, self._exposicion - 1)

    def run(self):
        # bucle externo: (re)conecta; si la transmision se degrada de forma
        # sostenida, se reabre la captura entera en vez de quedarse mostrando
        # "sin senal" para siempre (se resincroniza con un fotograma clave
        # nuevo, lo que tambien ayuda con la fluidez tras un movimiento PTZ)
        while self._activo:
            captura = _abrir_captura_sin_bloqueo(self.tipo_conexion, self.url_conexion)
            if not captura or not captura.isOpened():
                self.estado_cambiado.emit("sin_senal")
                self.msleep(3000)
                continue

            self._forzar_reconexion = False  # descarta pedidos de reconexion viejos, ya se reconecto
            if self.tipo_conexion == "USB":
                self._iniciar_exposicion_webcam(captura)
            if self._baseline_brillo is None:
                self._iniciar_aprendizaje()  # primera conexion: no tomar de base el cuadro negro inicial

            self.estado_cambiado.emit("conectada")
            razon = self._transmitir(captura)
            if razon == "fallo":
                # esto si es una desconexion real (la camara dejo de responder)
                self.estado_cambiado.emit("sin_senal")
            elif razon == "resync":
                # resincronizacion PEDIDA (tras un PTZ, o preventiva cada
                # RESINCRONIZACION_PERIODICA_SEG), no un error: antes esto
                # tambien emitia "sin_senal" y la zona mostraba el aviso de
                # "SIN SENAL" durante toda la reconexion (1-4s) - justo
                # despues de mover la camara por voz, que es cuando mas se
                # nota. Con "reconectando" la vista deja el ultimo fotograma
                # quieto en pantalla (no lo borra) en vez de taparlo con el
                # aviso de error, mientras se reconecta en segundo plano.
                self.estado_cambiado.emit("reconectando")
            if self.tipo_conexion == "USB":
                # el driver recuerda el modo manual: se devuelve la webcam en
                # automatico para que Zoom/Teams/etc. no la vean oscura
                captura.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
                captura.set(cv2.CAP_PROP_GAIN, self._ganancia_original)
            captura.release()

    def _transmitir(self, captura):
        """Lee y procesa frames hasta que se pida detener o la transmision se
        degrade. Devuelve "fallo" (desconexion real: hay que avisar "sin
        senal"), "resync" (reconexion pedida o preventiva: no es un error,
        no hay que avisar nada) o "detenido" (se esta apagando la app)."""
        # 10% de margen: con el intervalo justo, un frame real que llegaba
        # apenas antes de tiempo (jitter) se salteaba y el video daba saltos
        intervalo = 0.9 / self._fps
        fallos_seguidos = 0
        ultimo_procesado = 0.0
        ultimo_ajuste_exposicion = 0.0
        inicio_transmision = time.time()
        es_rtsp = self.tipo_conexion != "USB"
        # vigilancia de atraso: reloj de la PC menos marca de tiempo del video
        # (PTS). Si la PC lee mas lento de lo que el grabador transmite (CPU
        # ocupada, muchas camaras 1080p), esa diferencia crece; se toma como
        # referencia el punto de menor diferencia (el mas "al dia")
        deriva_minima = None

        while self._activo:
            # se lee SIN pausa, tan rapido como llegan los frames: en RTSP esto
            # drena la cola de red/decodificador y evita que el video se vaya
            # atrasando respecto al tiempo real (si se duerme entre lecturas,
            # el retraso se acumula minuto a minuto). Solo se procesa/muestra
            # uno cada `intervalo` segundos, para no saturar la UI.
            ok, frame = captura.read()
            if not ok or frame is None:
                fallos_seguidos += 1
                if fallos_seguidos > LECTURAS_FALLIDAS_PARA_RECONECTAR:
                    return "fallo"  # la captura esta degradada: se reabre de cero
                self.msleep(50)
                continue
            fallos_seguidos = 0

            if self._forzar_reconexion:
                self._forzar_reconexion = False
                return "resync"  # resincronizacion pedida desde afuera (ej. tras un PTZ)

            if es_rtsp and (time.time() - inicio_transmision) > RESINCRONIZACION_PERIODICA_SEG:
                return "resync"  # reconexion preventiva: pide un I-frame nuevo

            ahora = time.time()
            if es_rtsp:
                pts = captura.get(cv2.CAP_PROP_POS_MSEC)
                if pts and pts > 0:
                    deriva = ahora - pts / 1000.0
                    if deriva_minima is None or deriva < deriva_minima:
                        deriva_minima = deriva
                    elif deriva - deriva_minima > ATRASO_MAXIMO_SEG and ahora - inicio_transmision > 5:
                        # se quedo atras: reconectar entrega de nuevo el video en vivo
                        return "resync"

            if ahora - ultimo_procesado < intervalo:
                continue
            ultimo_procesado = ahora
            if not es_rtsp and ahora - ultimo_ajuste_exposicion > 1.5:
                ultimo_ajuste_exposicion = ahora
                self._ajustar_exposicion_webcam(captura, frame)

            self._ultimo_frame = frame
            # deteccion ANTES de pintar y de comprimir: el aviso sale apenas se ve tapada
            self._actualizar_sabotaje(frame)
            ok_jpg, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, CALIDAD_JPEG_BUFFER])
            if ok_jpg:
                self._buffer.append(jpg)
            if not self._entrega_pendiente:
                self._entrega_pendiente = True
                self.frame_listo.emit(frame)

        return "detenido"

    def capturar_snapshot(self):
        # el ultimo frame en crudo (calidad completa, sin pasar por JPEG)
        frame = self._ultimo_frame
        return frame.copy() if frame is not None else None


class DeteccionCamarasUSBThread(QThread):
    """Prueba los indices 0..4 de camara USB/integrada: cual es la webcam
    depende de cada laptop (la integrada puede caer en el indice 0, 1 o
    incluso 2 segun el equipo y los drivers), asi que en vez de pedirle al
    instalador que adivine, se prueban todos y se devuelven los que
    respondieron con imagen real."""

    resultado = pyqtSignal(list)  # [{"indice": int, "resolucion": "WxH"}, ...]

    def run(self):
        encontradas = []
        for indice in range(5):
            cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
            if cap.isOpened():
                ok, frame = cap.read()
                if ok and frame is not None:
                    alto, ancho = frame.shape[:2]
                    encontradas.append({"indice": indice, "resolucion": f"{ancho}x{alto}"})
            cap.release()
        self.resultado.emit(encontradas)


class PruebaConexionThread(QThread):
    """Prueba de conectividad para la pestana Camaras (ej. al dar de alta un
    canal del DVR Hikvision in situ): abre la captura y espera un fotograma
    real, no solo isOpened() (que en RTSP a veces da "abierto" igual aunque
    el stream nunca entregue nada). Corre en su propio hilo para no congelar
    la UI mientras FFmpeg intenta conectar."""

    resultado = pyqtSignal(bool, str)

    def __init__(self, tipo_conexion, url_conexion, parent=None):
        super().__init__(parent)
        self.tipo_conexion = tipo_conexion
        self.url_conexion = url_conexion

    def run(self):
        captura = _abrir_captura_sin_bloqueo(self.tipo_conexion, self.url_conexion)
        if not captura or not captura.isOpened():
            self.resultado.emit(False, self._mensaje_fallo_conexion())
            return
        try:
            for _ in range(15):  # hasta ~1.5s: algunas camaras tardan el primer fotograma
                ok, frame = captura.read()
                if ok and frame is not None:
                    alto, ancho = frame.shape[:2]
                    self.resultado.emit(True, f"Conexion exitosa: se recibio una imagen de {ancho}x{alto}.")
                    return
                self.msleep(100)
            self.resultado.emit(
                False, "Conecto pero no llego ninguna imagen. Revise el numero de canal o el tipo de stream.",
            )
        finally:
            captura.release()

    def _mensaje_fallo_conexion(self):
        """Mensaje generico de siempre, salvo que se pueda precisar en que
        capa de red se corto (ver _diagnostico_red): USB no tiene IP que
        diagnosticar, asi que se queda con el generico."""
        generico = (
            "No se pudo conectar. Revise IP, puerto, usuario/clave, el numero "
            "de canal, y que esta PC este en la misma red que la camara/DVR."
        )
        if self.tipo_conexion == "USB":
            return generico
        host = urlparse(self.url_conexion).hostname
        if not host:
            return generico
        puerto = urlparse(self.url_conexion).port or 554
        return _diagnostico_red(host, puerto) or generico


class DeteccionCanalesDVRThread(QThread):
    """Prueba de una sola vez todos los canales de un DVR/NVR (Hikvision o
    Dahua): en vez de agregar camara por camara, se registra el dispositivo
    (IP, usuario, clave, cantidad de canales) y esto devuelve cuales canales
    respondieron con imagen real, listos para darse de alta todos juntos."""

    progreso = pyqtSignal(int, int)  # canal_actual, total
    resultado = pyqtSignal(list)  # [{"canal": int, "url": str, "resolucion": "WxH"}, ...]
    diagnostico = pyqtSignal(str)  # detalle de red cuando resultado sale vacio (ver _diagnostico_red)

    def __init__(self, marca, ip, puerto, usuario, clave, cantidad_canales, canales_a_omitir=None, parent=None):
        super().__init__(parent)
        self.marca = marca
        self.ip = ip
        self.puerto = puerto
        self.usuario = usuario
        self.clave = clave
        self.cantidad_canales = cantidad_canales
        # canales que ya tienen una camara activa (de una deteccion previa):
        # se saltan para no duplicarlos ni interrumpir su transmision
        self.canales_a_omitir = canales_a_omitir or set()

    def run(self):
        from app.services.dvr_urls import construir_url_canal

        # el host/puerto es el mismo para los N canales de un mismo
        # dispositivo: si no responde, no tiene sentido reintentar la
        # verificacion TCP (2s) canal por canal
        url_prueba = construir_url_canal(self.marca, self.ip, self.puerto, self.usuario, self.clave, 1, True)
        if not _servidor_alcanzable(url_prueba, timeout=3.0):
            puerto = urlparse(url_prueba).port or 554
            mensaje = _diagnostico_red(self.ip, puerto)
            if mensaje:
                self.diagnostico.emit(mensaje + _sugerencia_ip_alternativa(self.ip, puerto))
            self.resultado.emit([])
            return

        encontrados = []
        for canal in range(1, self.cantidad_canales + 1):
            self.progreso.emit(canal, self.cantidad_canales)
            if canal in self.canales_a_omitir:
                continue
            url = construir_url_canal(self.marca, self.ip, self.puerto, self.usuario, self.clave, canal, True)
            captura = _abrir_captura_sin_bloqueo("RTSP", url)
            if not captura or not captura.isOpened():
                continue
            try:
                ok, frame = captura.read()
                if ok and frame is not None:
                    alto, ancho = frame.shape[:2]
                    encontrados.append({"canal": canal, "url": url, "resolucion": f"{ancho}x{alto}"})
            finally:
                captura.release()
        if not encontrados:
            mensaje = _diagnostico_credenciales(self.marca, self.ip, self.usuario, self.clave)
            if mensaje:
                self.diagnostico.emit(mensaje)
        self.resultado.emit(encontrados)
