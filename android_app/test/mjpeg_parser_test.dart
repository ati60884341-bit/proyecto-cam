import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:cam_app/widgets/mjpeg_parser.dart';

List<int> _cuadro(List<int> datos) =>
    utf8.encode('--cuadro\r\nContent-Type: image/jpeg\r\nContent-Length: ${datos.length}\r\n\r\n') + datos + utf8.encode('\r\n');

void main() {
  test('un cuadro completo en un solo bloque', () {
    final a = AnalizadorMjpeg();
    final r = a.agregarBytes(_cuadro([1, 2, 3, 4]));
    expect(r, [Uint8List.fromList([1, 2, 3, 4])]);
  });

  test('dos cuadros completos llegan juntos', () {
    final a = AnalizadorMjpeg();
    final r = a.agregarBytes([..._cuadro([1, 2]), ..._cuadro([3, 4, 5])]);
    expect(r, [Uint8List.fromList([1, 2]), Uint8List.fromList([3, 4, 5])]);
  });

  test('un cuadro llega partido entre dos llamadas', () {
    final a = AnalizadorMjpeg();
    final completo = _cuadro([9, 9, 9]);
    final mitad = completo.length ~/ 2;
    expect(a.agregarBytes(completo.sublist(0, mitad)), []);
    expect(a.agregarBytes(completo.sublist(mitad)), [Uint8List.fromList([9, 9, 9])]);
  });
}
