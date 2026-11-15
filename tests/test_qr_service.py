import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services import qr_service

ip = qr_service.detectar_ip_lan()
assert re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip), f"debe ser una IP valida, dio {ip!r}"

png = qr_service.generar_qr_png_bytes("192.168.1.10")
assert png[:8] == b"\x89PNG\r\n\x1a\n", "debe ser un PNG valido"
print("OK: qr_service")
