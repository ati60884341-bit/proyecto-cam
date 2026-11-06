"""Logica pura (sin Qt) para saber en que red(es) esta ESTA PC: IP y mascara
de subred de cada adaptador activo. La usa el panel "Mi red" (ver
app/views/UI/panel_mi_red.py) para que el tecnico compare a simple vista si
esta en la misma subred que la IP del DVR/camara que va a escribir, antes
de perder tiempo armando y probando la conexion."""

import ipaddress
import re
import subprocess

_PATRON_IP = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")


def listar_interfaces_red():
    """[{"interfaz": str, "ip": str, "mascara": str, "red": "192.168.1.0/24"}, ...]
    por cada adaptador con IPv4 activo. Lista vacia si no se pudo leer
    (ej. no es Windows, o `ipconfig` no esta disponible)."""
    texto = _salida_ipconfig()
    if texto is None:
        return []

    interfaces = []
    nombre_bloque = None
    lineas_bloque = []

    def cerrar_bloque():
        if nombre_bloque:
            interfaz = _interfaz_desde_bloque(nombre_bloque, lineas_bloque)
            if interfaz:
                interfaces.append(interfaz)

    for linea in texto.splitlines():
        # linea sin sangria y no vacia = encabezado de un adaptador nuevo
        # (ej. "Adaptador de Ethernet Ethernet 2:"); todo lo sangrado debajo
        # son sus datos, hasta el proximo encabezado
        if linea.strip() and not linea[:1].isspace():
            cerrar_bloque()
            nombre_bloque = linea.rstrip(": \t")
            lineas_bloque = []
        else:
            lineas_bloque.append(linea)
    cerrar_bloque()
    return interfaces


def _salida_ipconfig():
    try:
        proceso = subprocess.run(
            ["ipconfig"], capture_output=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return None
    # la consola de Windows usa su codepage OEM (850/437...), no UTF-8: con
    # "oem" Python decodifica con el codepage real de esta PC en vez de uno
    # fijo que podria no coincidir (y romper los acentos, aunque eso no
    # afecta la extraccion de IPs mas abajo, que es solo digitos y puntos)
    return proceso.stdout.decode("oem", errors="replace")


def _interfaz_desde_bloque(nombre, lineas):
    """Dentro del bloque de un adaptador, `ipconfig` siempre imprime en este
    orden: direccion IPv4, mascara de subred, puerta de enlace. Se toman
    POSICIONALMENTE (el primer numero con forma de IP es la IP, el segundo
    la mascara) en vez de buscar la palabra "mascara"/"mask": asi funciona
    igual sin importar el idioma de Windows o el codepage de la consola."""
    ips = [m.group(1) for linea in lineas for m in [_PATRON_IP.search(linea)] if m]
    if len(ips) < 2:
        return None  # adaptador sin IPv4 (desconectado, o solo IPv6)
    ip, mascara = ips[0], ips[1]
    try:
        red = str(ipaddress.IPv4Interface(f"{ip}/{mascara}").network)
    except ValueError:
        red = ""
    return {"interfaz": nombre, "ip": ip, "mascara": mascara, "red": red}
