import io
import json
import socket

import qrcode


def detectar_ip_lan():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def generar_qr_png_bytes(ip):
    imagen = qrcode.make(json.dumps({"ip": ip}))
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()
