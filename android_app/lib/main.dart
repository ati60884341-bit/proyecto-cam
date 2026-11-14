import 'package:flutter/material.dart';
import 'api_client.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';
import 'screens/splash_screen.dart';

void main() {
  runApp(const CamApp());
}

class CamApp extends StatelessWidget {
  const CamApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CAM',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(scaffoldBackgroundColor: const Color(0xFF0a0f1a)),
      home: _Arranque(),
    );
  }
}

/// Decide con que pantalla abrir: si ya hay un token guardado, va directo
/// al Centro de Monitoreo; si no, pide login.
class _Arranque extends StatefulWidget {
  @override
  State<_Arranque> createState() => _ArranqueState();
}

class _ArranqueState extends State<_Arranque> {
  final _api = ApiClient();
  bool _listo = false;

  @override
  void initState() {
    super.initState();
    Future.wait([
      _api.cargarSesionGuardada(),
      Future.delayed(const Duration(milliseconds: 1100)),
    ]).then((_) => setState(() => _listo = true));
  }

  @override
  Widget build(BuildContext context) {
    if (!_listo) {
      return const SplashScreen();
    }
    return _api.tieneSesion ? HomeScreen(api: _api) : LoginScreen(api: _api);
  }
}
