import 'package:flutter_test/flutter_test.dart';
import 'package:cam_app/api_client.dart';

void main() {
  test('streamUri arma la url correcta y authHeaders trae el Bearer', () {
    final api = ApiClient()
      ..ip = '192.168.1.5'
      ..token = 'abc';
    expect(api.streamUri('Cam-1').toString(), 'http://192.168.1.5:8765/camaras/Cam-1/stream.mjpg');
    expect(api.authHeaders['Authorization'], 'Bearer abc');
  });
}
