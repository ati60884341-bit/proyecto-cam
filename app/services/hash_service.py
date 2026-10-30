import hashlib


def firmar_archivo(ruta_archivo):
    """Calcula la firma SHA-256 de un archivo (cadena de custodia legal)."""
    sha = hashlib.sha256()
    with open(ruta_archivo, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            sha.update(bloque)
    return sha.hexdigest()


def firmar_bytes(datos):
    return hashlib.sha256(datos).hexdigest()
