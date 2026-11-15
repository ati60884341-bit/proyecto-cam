import 'dart:convert';

/// Extrae la IP de un QR generado por el panel de escritorio de CAM (el
/// QR codifica `{"ip": "<ip detectada>"}`). Cualquier otro contenido -
/// QR ajeno a la app, texto cualquiera, JSON malformado - no es un error,
/// simplemente no es de CAM: esta funcion nunca lanza, devuelve null.
String? parsearIpDeQr(String contenido) {
  try {
    final datos = jsonDecode(contenido);
    if (datos is Map && datos['ip'] is String) return datos['ip'] as String;
  } catch (_) {
    // QR de cualquier otra cosa: no es un error, simplemente no es de CAM
  }
  return null;
}
