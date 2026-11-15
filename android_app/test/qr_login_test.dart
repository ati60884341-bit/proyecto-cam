import 'package:flutter_test/flutter_test.dart';
import 'package:cam_app/qr_login.dart';

void main() {
  test('un QR valido de CAM devuelve la ip', () {
    expect(parsearIpDeQr('{"ip": "192.168.1.10"}'), '192.168.1.10');
  });
  test('un QR de cualquier otra cosa no rompe nada', () {
    expect(parsearIpDeQr('https://ejemplo.com'), isNull);
    expect(parsearIpDeQr('{"otracosa": 1}'), isNull);
    expect(parsearIpDeQr(''), isNull);
  });
  test('garbage arbitrario nunca lanza', () {
    expect(parsearIpDeQr('{'), isNull);
    expect(parsearIpDeQr('{"ip":'), isNull);
    expect(parsearIpDeQr('{"ip": 123}'), isNull);
    expect(parsearIpDeQr('{"ip": null}'), isNull);
    expect(parsearIpDeQr('{"ip": ["192.168.1.10"]}'), isNull);
    expect(parsearIpDeQr('null'), isNull);
    expect(parsearIpDeQr('42'), isNull);
    expect(parsearIpDeQr('"192.168.1.10"'), isNull);
    expect(parsearIpDeQr('[1, 2, 3]'), isNull);
    expect(parsearIpDeQr('\u0000\u0001\u0002binario�'), isNull);
    expect(parsearIpDeQr(List.filled(5000, 'a').join()), isNull);
  });
}
