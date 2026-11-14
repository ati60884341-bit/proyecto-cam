import 'package:flutter/material.dart';
import '../theme.dart';

/// Pantalla que se ve al abrir la app: el ojo aparece con un pop suave
/// mientras se carga la sesion guardada (ver main.dart / _ArranqueState).
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  bool _visible = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) setState(() => _visible = true);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.fondo,
      body: Center(
        child: AnimatedScale(
          scale: _visible ? 1.0 : 0.85,
          duration: const Duration(milliseconds: 900),
          curve: Curves.easeOutBack,
          child: AnimatedOpacity(
            opacity: _visible ? 1.0 : 0.0,
            duration: const Duration(milliseconds: 700),
            child: Image.asset('assets/icono_ojo.png', width: 140),
          ),
        ),
      ),
    );
  }
}
