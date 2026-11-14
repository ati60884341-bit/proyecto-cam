// Prueba minima de arranque: sin sesion guardada, la app debe abrir en
// la pantalla de login.
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:cam_app/main.dart';

void main() {
  testWidgets('sin sesion guardada, arranca en la pantalla de login', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(const CamApp());
    await tester.pump(const Duration(milliseconds: 1200));
    await tester.pumpAndSettle();

    expect(find.text('CAM - Visor remoto'), findsOneWidget);
  });
}
