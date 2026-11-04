"""Logica pura (sin Qt, sin red) para armar URLs RTSP de canales de un
DVR/NVR a partir de IP + usuario + clave + canal. La comparten la pestana
"Camaras" (una camara a la vez) y la pestana "NVR / DVR" (todos los canales
de un dispositivo de una sola vez)."""

# Marcas de DVR/NVR cuya URL RTSP se puede armar sola: no hace falta
# escribirla ni recordar su formato exacto.
MARCAS_CON_ASISTENTE_DVR = ("Hikvision", "Dahua")


def construir_url_canal(marca, ip, puerto, usuario, clave, canal, flujo_principal=True):
    """canal: numero de canal del DVR/NVR (1, 2, 3...), NO el indice de una
    camara IP independiente. flujo_principal=True pide el stream de mejor
    calidad (mas ancho de banda); False pide el sub-stream (mas liviano,
    sirve para conexiones mas lentas o muchos canales a la vez)."""
    if not ip:
        return ""
    puerto = puerto or "554"
    canal = canal or "1"
    usuario = usuario or "admin"
    if marca == "Hikvision":
        # canal 1 principal -> 101, canal 1 secundario -> 102, canal 2 -> 201/202, etc.
        sub = "01" if flujo_principal else "02"
        return f"rtsp://{usuario}:{clave}@{ip}:{puerto}/Streaming/Channels/{canal}{sub}"
    if marca == "Dahua":
        subtype = "0" if flujo_principal else "1"
        return f"rtsp://{usuario}:{clave}@{ip}:{puerto}/cam/realmonitor?channel={canal}&subtype={subtype}"
    return ""
