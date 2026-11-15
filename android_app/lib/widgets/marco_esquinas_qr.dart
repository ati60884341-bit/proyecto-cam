import 'package:flutter/material.dart';

import '../theme.dart';

/// Las 4 esquinas en forma de "L" del marco de escaneo de QR. Se usa
/// grande en QrScanScreen (ver lib/screens/qr_scan_screen.dart) sobre
/// la vista de la camara, y reusada chica como icono estatico en el
/// boton "Escanear QR" del login (siempre con `verde: false`).
class MarcoEsquinasQr extends StatelessWidget {
  final double tamano;
  final Color color;
  final bool verde; // true = esquinas en verde (QR detectado), false = color normal

  static const _colorVerde = Color(0xFF4CD964);

  const MarcoEsquinasQr({
    super.key,
    this.tamano = 220,
    this.color = AppColors.acento,
    this.verde = false,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: tamano,
      height: tamano,
      child: CustomPaint(
        painter: _EsquinasPainter(color: verde ? _colorVerde : color),
      ),
    );
  }
}

class _EsquinasPainter extends CustomPainter {
  final Color color;
  const _EsquinasPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final largo = size.shortestSide * 0.18;
    final trazo = Paint()
      ..color = color
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;

    canvas.drawPath(
      Path()
        ..moveTo(0, largo)
        ..lineTo(0, 0)
        ..lineTo(largo, 0),
      trazo,
    );
    canvas.drawPath(
      Path()
        ..moveTo(size.width - largo, 0)
        ..lineTo(size.width, 0)
        ..lineTo(size.width, largo),
      trazo,
    );
    canvas.drawPath(
      Path()
        ..moveTo(0, size.height - largo)
        ..lineTo(0, size.height)
        ..lineTo(largo, size.height),
      trazo,
    );
    canvas.drawPath(
      Path()
        ..moveTo(size.width - largo, size.height)
        ..lineTo(size.width, size.height)
        ..lineTo(size.width, size.height - largo),
      trazo,
    );
  }

  @override
  bool shouldRepaint(covariant _EsquinasPainter oldDelegate) =>
      oldDelegate.color != color;
}
