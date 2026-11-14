import 'package:flutter_test/flutter_test.dart';
import 'package:cam_app/welcome_content.dart';

void main() {
  test('saludoPorHora da buenos dias/tardes/noches segun la hora', () {
    expect(saludoPorHora(8), 'Buenos dias');
    expect(saludoPorHora(11), 'Buenos dias');
    expect(saludoPorHora(12), 'Buenas tardes');
    expect(saludoPorHora(18), 'Buenas tardes');
    expect(saludoPorHora(19), 'Buenas noches');
    expect(saludoPorHora(23), 'Buenas noches');
  });

  test('frasesBienvenida menciona la cantidad de camaras en la primera frase', () {
    final frases = frasesBienvenida(3);
    expect(frases.first, contains('3'));
    expect(frases.length, greaterThan(1));
  });

  test('frasesBienvenida avisa cuando no hay camaras todavia', () {
    final frases = frasesBienvenida(0);
    expect(frases.first, contains('camaras'));
  });
}
