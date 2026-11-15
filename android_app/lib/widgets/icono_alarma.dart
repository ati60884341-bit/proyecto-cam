import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme.dart';

/// Icono "alarma": una campana de línea fina (cúpula semicircular + lados
/// en trapecio + badajo relleno abajo) con un pequeño triángulo de alerta
/// (signo de exclamación) superpuesto en la esquina superior derecha de la
/// campana, para el botón de disparar el simulacro de incidente. Dibujado a
/// mano con CustomPainter, mismo estilo de trazo fino y un solo color que
/// el resto de los íconos del programa (ver app/views/UI/iconos.py).
class IconoAlarma extends StatelessWidget {
  final double tamano;
  final Color color;

  const IconoAlarma({
    super.key,
    this.tamano = 28,
    this.color = AppColors.acento,
  });

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: Size(tamano, tamano),
      painter: _AlarmaPainter(color: color),
    );
  }
}

class _AlarmaPainter extends CustomPainter {
  final Color color;

  _AlarmaPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final trazo = math.max(1.6, size.width / 12);
    final pluma = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = trazo
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    final w = size.width;
    final h = size.height;
    final cx = w / 2;

    // --- Campana ---
    // Cúpula: semicírculo superior sin relleno.
    final radioCupula = w * 0.20;
    final yCupula = h * 0.36;
    final centroCupula = Offset(cx, yCupula);
    canvas.drawArc(
      Rect.fromCircle(center: centroCupula, radius: radioCupula),
      _gradosARadianes(180),
      _gradosARadianes(180),
      false,
      pluma,
    );

    // Pequeño vástago arriba de la cúpula.
    canvas.drawLine(
      Offset(cx, yCupula - radioCupula),
      Offset(cx, yCupula - radioCupula - h * 0.07),
      pluma,
    );

    // Lados en trapecio: de los extremos de la cúpula hacia la base, más
    // ancha (así la campana se abre hacia abajo).
    final yBase = h * 0.68;
    final anchoBase = w * 0.32;
    final puntoCupulaIzq = Offset(cx - radioCupula, yCupula);
    final puntoCupulaDer = Offset(cx + radioCupula, yCupula);
    final puntoBaseIzq = Offset(cx - anchoBase, yBase);
    final puntoBaseDer = Offset(cx + anchoBase, yBase);
    canvas.drawLine(puntoCupulaIzq, puntoBaseIzq, pluma);
    canvas.drawLine(puntoCupulaDer, puntoBaseDer, pluma);

    // Borde inferior (reborde de la campana).
    canvas.drawLine(puntoBaseIzq, puntoBaseDer, pluma);

    // Badajo: pequeño círculo relleno colgando del reborde.
    pluma.style = PaintingStyle.fill;
    canvas.drawCircle(Offset(cx, yBase + h * 0.08), w * 0.045, pluma);
    pluma.style = PaintingStyle.stroke;

    // --- Triángulo de alerta, superpuesto en la esquina superior derecha
    // de la campana ---
    final triCx = cx + w * 0.27;
    final triCy = h * 0.30;
    final triMedio = w * 0.15;
    final apice = Offset(triCx, triCy - triMedio);
    final baseIzq = Offset(triCx - triMedio, triCy + triMedio * 0.8);
    final baseDer = Offset(triCx + triMedio, triCy + triMedio * 0.8);
    final triangulo = Path()
      ..moveTo(apice.dx, apice.dy)
      ..lineTo(baseDer.dx, baseDer.dy)
      ..lineTo(baseIzq.dx, baseIzq.dy)
      ..close();
    canvas.drawPath(triangulo, pluma);

    // Signo de exclamación dentro del triángulo: línea corta + punto
    // relleno.
    canvas.drawLine(
      Offset(triCx, triCy - triMedio * 0.35),
      Offset(triCx, triCy + triMedio * 0.12),
      pluma,
    );
    pluma.style = PaintingStyle.fill;
    canvas.drawCircle(Offset(triCx, triCy + triMedio * 0.45), w * 0.025, pluma);
  }

  double _gradosARadianes(double grados) => grados * math.pi / 180;

  @override
  bool shouldRepaint(covariant _AlarmaPainter oldDelegate) {
    return oldDelegate.color != color;
  }
}
