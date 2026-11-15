import 'dart:async';

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';
import '../widgets/gif_background.dart';
import '../widgets/marco_esquinas_qr.dart';
import 'qr_scan_screen.dart';
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
  Timer? _qrTimer;

  @override
  void initState() {
    super.initState();
    _ipCtrl.text = widget.api.ip ?? '';
  }

  @override
  void dispose() {
    _qrTimer?.cancel();
    _ipCtrl.dispose();
    _usuarioCtrl.dispose();
    _claveCtrl.dispose();
    super.dispose();
  }

  Future<void> _escanearQr() async {
    final ip = await Navigator.push<String>(
      context,
      MaterialPageRoute(builder: (_) => const QrScanScreen()),
    );
    if (ip == null || !mounted) return;
    _animarEscrituraIp(ip);
  }

  // Efecto "maquina de escribir": completa _ipCtrl caracter por caracter.
  // Se actualiza con `.value` (no `.text`) para fijar texto y seleccion
  // juntos y evitar el assert de TextSelection fuera de rango; al ser
  // ChangeNotifier, el TextField se redibuja solo, sin setState.
  void _animarEscrituraIp(String ip) {
    _qrTimer?.cancel();
    _ipCtrl.value = const TextEditingValue(text: '');
    var i = 0;
    _qrTimer = Timer.periodic(const Duration(milliseconds: 25), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      i++;
      final texto = ip.substring(0, i);
      _ipCtrl.value = TextEditingValue(
        text: texto,
        selection: TextSelection.collapsed(offset: texto.length),
      );
      if (i >= ip.length) timer.cancel();
    });
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
                    Center(
                      child: Image.asset(
                        'assets/icono_ojo.png',
                        width: 64,
                        height: 64,
                      ),
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
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        Expanded(
                          child: _campo(
                            _ipCtrl,
                            'IP del centro de monitoreo',
                            hint: '192.168.1.10',
                          ),
                        ),
                        const SizedBox(width: 4),
                        IconButton(
                          tooltip: 'Escanear código QR',
                          onPressed: _escanearQr,
                          icon: const MarcoEsquinasQr(tamano: 24),
                        ),
                      ],
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
