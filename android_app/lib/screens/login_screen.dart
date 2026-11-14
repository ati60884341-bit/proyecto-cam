import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';
import '../widgets/gif_background.dart';
import 'welcome_screen.dart';

class LoginScreen extends StatefulWidget {
  final ApiClient api;
  const LoginScreen({super.key, required this.api});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _ipCtrl = TextEditingController();
  final _usuarioCtrl = TextEditingController();
  final _claveCtrl = TextEditingController();
  bool _cargando = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _ipCtrl.text = widget.api.ip ?? '';
  }

  Future<void> _ingresar() async {
    if (_ipCtrl.text.trim().isEmpty ||
        _usuarioCtrl.text.trim().isEmpty ||
        _claveCtrl.text.isEmpty) {
      setState(() => _error = 'Completa la IP, el usuario y la clave.');
      return;
    }
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      await widget.api.login(
        _ipCtrl.text.trim(),
        _usuarioCtrl.text.trim(),
        _claveCtrl.text,
      );
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        PageRouteBuilder(
          transitionDuration: const Duration(milliseconds: 450),
          pageBuilder: (_, _, _) => WelcomeScreen(api: widget.api),
          transitionsBuilder: (_, animation, _, child) {
            final curva = CurvedAnimation(
              parent: animation,
              curve: Curves.easeOutCubic,
            );
            return FadeTransition(
              opacity: curva,
              child: SlideTransition(
                position: Tween<Offset>(
                  begin: const Offset(0, 0.06),
                  end: Offset.zero,
                ).animate(curva),
                child: child,
              ),
            );
          },
        ),
      );
    } catch (e) {
      setState(() => _error = 'No se pudo conectar: $e');
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.fondo,
      body: Stack(
        children: [
          const GifBackground(),
          SafeArea(
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Icon(
                      Icons.remove_red_eye_outlined,
                      color: AppColors.acento,
                      size: 64,
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'CAM - Visor remoto',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: AppColors.texto,
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 32),
                    _campo(
                      _ipCtrl,
                      'IP del centro de monitoreo',
                      hint: '192.168.1.10',
                    ),
                    const SizedBox(height: 12),
                    _campo(_usuarioCtrl, 'Usuario'),
                    const SizedBox(height: 12),
                    _campo(_claveCtrl, 'Clave', oculto: true),
                    const SizedBox(height: 20),
                    if (_error != null)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Text(
                          _error!,
                          style: const TextStyle(color: AppColors.error),
                        ),
                      ),
                    ElevatedButton(
                      onPressed: _cargando ? null : _ingresar,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF1f8f86),
                        padding: const EdgeInsets.symmetric(vertical: 16),
                      ),
                      child: _cargando
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Text(
                              'Ingresar',
                              style: TextStyle(fontSize: 16),
                            ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _campo(
    TextEditingController ctrl,
    String etiqueta, {
    String? hint,
    bool oculto = false,
  }) {
    return TextField(
      controller: ctrl,
      obscureText: oculto,
      style: const TextStyle(color: AppColors.texto),
      decoration: InputDecoration(
        labelText: etiqueta,
        hintText: hint,
        labelStyle: const TextStyle(color: AppColors.textoMuted),
        hintStyle: const TextStyle(color: Color(0xFF5a6472)),
        enabledBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: AppColors.borde),
        ),
        focusedBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: AppColors.acento),
        ),
      ),
    );
  }
}
