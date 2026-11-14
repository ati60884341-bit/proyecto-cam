import 'dart:convert';
import 'dart:typed_data';

/// Saca los cuadros JPEG de un stream multipart (`multipart/x-mixed-replace`)
/// como el que entrega la API de CAM en /camaras/{zona}/stream.mjpg. Los
/// bytes pueden llegar partidos o con varios cuadros juntos: por eso guarda
/// lo que sobra entre llamadas en vez de asumir que cada llamada trae un
/// cuadro exacto.
class AnalizadorMjpeg {
  final List<int> _buffer = [];

  List<Uint8List> agregarBytes(List<int> datos) {
    _buffer.addAll(datos);
    final cuadros = <Uint8List>[];
    while (true) {
      final finHeader = _buscar(_buffer, utf8.encode('\r\n\r\n'));
      if (finHeader == -1) break;
      final textoHeader = utf8.decode(_buffer.sublist(0, finHeader), allowMalformed: true);
      final match = RegExp(r'Content-Length:\s*(\d+)').firstMatch(textoHeader);
      if (match == null) {
        _buffer.removeRange(0, finHeader + 4);
        continue;
      }
      final longitud = int.parse(match.group(1)!);
      final inicioCuadro = finHeader + 4;
      if (_buffer.length < inicioCuadro + longitud) break;
      cuadros.add(Uint8List.fromList(_buffer.sublist(inicioCuadro, inicioCuadro + longitud)));
      _buffer.removeRange(0, inicioCuadro + longitud);
    }
    return cuadros;
  }

  int _buscar(List<int> lista, List<int> patron) {
    for (var i = 0; i <= lista.length - patron.length; i++) {
      var iguales = true;
      for (var j = 0; j < patron.length; j++) {
        if (lista[i + j] != patron[j]) {
          iguales = false;
          break;
        }
      }
      if (iguales) return i;
    }
    return -1;
  }
}
