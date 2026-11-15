import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../qr_login.dart';
import '../theme.dart';
import '../widgets/marco_esquinas_qr.dart';

/// Pantalla de escaneo de QR para conectar con la IP del centro de
/// monitoreo (el escritorio muestra un QR con `{"ip": "<detectada>"}`).
/// Al leer un QR valido, las esquinas se ponen en verde y el marco hace
/// un "pop" de escala antes de cerrar la pantalla con
/// `Navigator.pop(context, ip)`.
///
/// No crea un MobileScannerController propio: sin uno explicito,
/// MobileScanner arma y descarta el suyo solo (attach/start al montar,
/// stop/dispose al desmontar), asi que la camara queda liberada al
/// hacer pop sin trabajo extra de nuestra parte.
class QrScanScreen extends StatefulWidget {
  const QrScanScreen({super.key});

  @override
  State<QrScanScreen> createState() => _QrScanScreenState();
}

class _QrScanScreenState extends State<QrScanScreen> {
  static const _tamanoMarco = 240.0;

  bool _detectado = false;
  bool _verde = false;
  double _escala = 1.0;

  void _alDetectar(BarcodeCapture captura) {
    if (_detectado) return;
    for (final codigo in captura.barcodes) {
      final crudo = codigo.rawValue;
      if (crudo == null) continue;
      final ip = parsearIpDeQr(crudo);
      if (ip != null) {
        _confirmar(ip);
        return;
      }
    }
  }

  Future<void> _confirmar(String ip) async {
    setState(() {
      _detectado = true;
      _verde = true;
      _escala = 1.08;
    });
    await Future.delayed(const Duration(milliseconds: 150));
    if (!mounted) return;
    setState(() => _escala = 1.0);
    await Future.delayed(const Duration(milliseconds: 150));
    if (!mounted) return;
    Navigator.pop(context, ip);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.fondo,
      appBar: AppBar(
        backgroundColor: AppColors.fondo,
        iconTheme: const IconThemeData(color: AppColors.texto),
        title: const Text(
          'Escanear QR',
          style: TextStyle(color: AppColors.texto),
        ),
      ),
      body: Stack(
        alignment: Alignment.center,
        children: [
          MobileScanner(onDetect: _alDetectar),
          AnimatedScale(
            scale: _escala,
            duration: const Duration(milliseconds: 150),
            curve: Curves.easeOut,
            child: SizedBox(
              width: _tamanoMarco,
              height: _tamanoMarco,
              child: Stack(
                children: [
                  ClipRect(child: _LineaEscaneo()),
                  MarcoEsquinasQr(tamano: _tamanoMarco, verde: _verde),
                ],
              ),
            ),
          ),
          const Positioned(
            bottom: 48,
            left: 24,
            right: 24,
            child: Text(
              'Apunta la camara al codigo QR del panel de escritorio',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textoMuted),
            ),
          ),
        ],
      ),
    );
  }
}

/// La linea horizontal que rebota de arriba a abajo dentro del marco,
/// en bucle. Animacion implicita (TweenAnimationBuilder, sin
/// AnimationController): al terminar cada pasada invierte el tween y
/// vuelve a empezar, igual que el patron de EyeLoader.
class _LineaEscaneo extends StatefulWidget {
  @override
  State<_LineaEscaneo> createState() => _LineaEscaneoState();
}

class _LineaEscaneoState extends State<_LineaEscaneo> {
  double _destino = 1;

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween<double>(begin: 1 - _destino, end: _destino),
      duration: const Duration(milliseconds: 1400),
      curve: Curves.easeInOut,
      onEnd: () {
        if (mounted) setState(() => _destino = 1 - _destino);
      },
      builder: (context, valor, child) {
        return Align(
          alignment: Alignment(0, -1 + 2 * valor),
          child: Container(
            height: 2,
            width: double.infinity,
            color: AppColors.acento,
          ),
        );
      },
    );
  }
}
