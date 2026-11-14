import 'dart:async';

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';
import '../welcome_content.dart';
import '../widgets/gif_background.dart';
import 'home_screen.dart';

/// Pantalla que recibe al usuario apenas inicia sesion, como "Inicio" en el
/// escritorio (app/views/inicio_view.py): saludo, resumen y frases que van
/// cambiando, con la misma escena nocturna de fondo.
class WelcomeScreen extends StatefulWidget {
  final ApiClient api;
  const WelcomeScreen({super.key, required this.api});

  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen> {
  static const _intervaloFrase = Duration(seconds: 6);

  List<String> _frases = frasesBienvenida(0);
  int _indiceFrase = 0;
  Timer? _rotador;

  @override
  void initState() {
    super.initState();
    _cargarResumen();
    _rotador = Timer.periodic(_intervaloFrase, (_) {
      if (mounted) {
        setState(() => _indiceFrase = (_indiceFrase + 1) % _frases.length);
      }
    });
  }

  Future<void> _cargarResumen() async {
    try {
      final resumen = await widget.api.getResumen();
      if (!mounted) return;
      setState(() => _frases = frasesBienvenida(resumen.camarasTotal));
    } catch (_) {
      // si todavia no se pudo traer el resumen, se queda con las frases
      // genericas (sin camaras) - no es razon para trabar la bienvenida
    }
  }

  @override
  void dispose() {
    _rotador?.cancel();
    super.dispose();
  }

  void _entrar() {
    Navigator.of(context).pushReplacement(
      PageRouteBuilder(
        transitionDuration: const Duration(milliseconds: 450),
        pageBuilder: (_, _, _) => HomeScreen(api: widget.api),
        transitionsBuilder: (_, animation, _, child) {
          final curva = CurvedAnimation(
            parent: animation,
            curve: Curves.easeOutCubic,
          );
          return FadeTransition(opacity: curva, child: child);
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final ahora = DateTime.now();
    return Scaffold(
      body: Stack(
        children: [
          const GifBackground(),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Spacer(flex: 2),
                  Text(
                    '${saludoPorHora(ahora.hour)}, ${widget.api.nombreUsuario ?? 'vigilante'}',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 20),
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 500),
                    child: Text(
                      _frases[_indiceFrase % _frases.length],
                      key: ValueKey(_indiceFrase),
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: Color(0xFFcfe9ef),
                        fontSize: 16,
                      ),
                    ),
                  ),
                  const Spacer(flex: 3),
                  ElevatedButton(
                    onPressed: _entrar,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.acento,
                      foregroundColor: AppColors.fondo,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 32,
                        vertical: 16,
                      ),
                    ),
                    child: const Text(
                      'Ir al Centro de monitoreo',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  const Spacer(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
