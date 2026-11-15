sealed class ComandoVoz {}
class AbrirCamaraPorIndice extends ComandoVoz { final int indice; AbrirCamaraPorIndice(this.indice); }
class IrAIncidencias extends ComandoVoz {}
class IrAInicio extends ComandoVoz {}
class SimularIncidenteVoz extends ComandoVoz {}
class CerrarSesionVoz extends ComandoVoz {}

String _normalizar(String s) => s
    .toLowerCase()
    .replaceAll('á', 'a').replaceAll('é', 'e').replaceAll('í', 'i')
    .replaceAll('ó', 'o').replaceAll('ú', 'u').replaceAll('ñ', 'n');

ComandoVoz? interpretarComandoVoz(String texto) {
  final t = _normalizar(texto);
  if (t.contains('simular incidente') || t.contains('panico') || t.contains('ayuda')) {
    return SimularIncidenteVoz();
  }
  if (t.contains('cerrar sesion')) return CerrarSesionVoz();
  if (t.contains('incidencia')) return IrAIncidencias();
  if (t.contains('inicio') || t.contains('resumen')) return IrAInicio();
  final match = RegExp(r'camara\s*(\d+)').firstMatch(t);
  if (match != null) {
    final n = int.parse(match.group(1)!);
    if (n >= 1) return AbrirCamaraPorIndice(n - 1);
  }
  return null;
}
