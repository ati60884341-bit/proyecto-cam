import 'package:flutter_test/flutter_test.dart';
import 'package:cam_app/voice_commands.dart';

void main() {
  test('camara N abre esa camara (indice base 0)', () {
    expect((interpretarComandoVoz('camara 1') as AbrirCamaraPorIndice).indice, 0);
    expect((interpretarComandoVoz('mostrar camara 2') as AbrirCamaraPorIndice).indice, 1);
    expect((interpretarComandoVoz('cámara 3') as AbrirCamaraPorIndice).indice, 2);
  });
  test('camara 0 no es una camara valida', () {
    expect(interpretarComandoVoz('camara 0'), isNull);
  });
  test('incidencias / inicio / simular / cerrar sesion', () {
    expect(interpretarComandoVoz('incidencias'), isA<IrAIncidencias>());
    expect(interpretarComandoVoz('inicio'), isA<IrAInicio>());
    expect(interpretarComandoVoz('resumen'), isA<IrAInicio>());
    expect(interpretarComandoVoz('simular incidente'), isA<SimularIncidenteVoz>());
    expect(interpretarComandoVoz('panico'), isA<SimularIncidenteVoz>());
    expect(interpretarComandoVoz('cerrar sesion'), isA<CerrarSesionVoz>());
  });
  test('frase sin sentido no matchea nada', () {
    expect(interpretarComandoVoz('que lindo dia hace hoy'), isNull);
  });
}
