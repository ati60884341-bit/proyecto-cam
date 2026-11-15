import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme.dart';

/// Icono "reloj rebobinar": una carátula de reloj con dos manecillas y una
/// flecha curva antihoraria alrededor, para el botón de la máquina del
/// tiempo. Dibujado a mano con CustomPainter, mismo estilo de trazo fino y
/// un solo color que el resto de los íconos del programa de escritorio
/// (ver app/views/UI/iconos.py).
class IconoRelojRebobinar extends StatelessWidget {
  final double tamano;
  final Color color;

  const IconoRelojRebobinar({
    super.key,
    this.tamano = 24,
    this.color = AppColors.acento,
  });

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: Size(tamano, tamano),
      painter: _RelojRebobinarPainter(color: color),
    );
  }
}

class _RelojRebobinarPainter extends CustomPainter {
  final Color color;

  _RelojRebobinarPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final trazo = math.max(1.6, size.width / 12);
    final pluma = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = trazo
      ..strokeCap = StrokeCap.round;

    final centro = Offset(size.width / 2, size.height / 2);
    // La carátula del reloj deja aire alrededor para la flecha que la rodea.
    final radioReloj = size.width * 0.3;

    // Carátula: círculo sin relleno.
    canvas.drawCircle(centro, radioReloj, pluma);

    // Manecilla corta hacia las 12 (arriba).
    canvas.drawLine(
      centro,
      Offset(centro.dx, centro.dy - radioReloj * 0.55),
      pluma,
    );

    // Manecilla larga hacia las 4 (abajo-derecha).
    // Convención: 0° = posición de las 3, 90° = posición de las 6.
    final anguloManecillaLarga = _gradosARadianes(30); // las 4 = 1/3 de 3 a 6
    canvas.drawLine(
      centro,
      Offset(
        centro.dx + math.cos(anguloManecillaLarga) * radioReloj * 0.75,
        centro.dy + math.sin(anguloManecillaLarga) * radioReloj * 0.75,
      ),
      pluma,
    );

    // Flecha curva antihoraria: arco de ~270° alrededor de la carátula.
    final radioFlecha = size.width * 0.42;
    final rectoFlecha = Rect.fromCircle(center: centro, radius: radioFlecha);
    const inicioGrados = -20.0; // ligeramente sobre la horizontal derecha
    const barridoGrados = -270.0; // antihorario
    canvas.drawArc(
      rectoFlecha,
      _gradosARadianes(inicioGrados),
      _gradosARadianes(barridoGrados),
      false,
      pluma,
    );

    // Punta de flecha en el extremo final del arco (sentido antihorario).
    final anguloFinal = _gradosARadianes(inicioGrados + barridoGrados);
    final puntaArco = Offset(
      centro.dx + math.cos(anguloFinal) * radioFlecha,
      centro.dy + math.sin(anguloFinal) * radioFlecha,
    );
    // Tangente al círculo en ese punto, apuntando en la dirección en que
    // avanza el barrido antihorario.
    final anguloTangente = anguloFinal - math.pi / 2;
    final largoPunta = size.width * 0.14;
    const aberturaPunta = 0.5; // radianes entre cada ala y la tangente

    final ala1 = Offset(
      puntaArco.dx - math.cos(anguloTangente - aberturaPunta) * largoPunta,
      puntaArco.dy - math.sin(anguloTangente - aberturaPunta) * largoPunta,
    );
    final ala2 = Offset(
      puntaArco.dx - math.cos(anguloTangente + aberturaPunta) * largoPunta,
      puntaArco.dy - math.sin(anguloTangente + aberturaPunta) * largoPunta,
    );

    final puntaFlecha = Path()
      ..moveTo(ala1.dx, ala1.dy)
      ..lineTo(puntaArco.dx, puntaArco.dy)
      ..lineTo(ala2.dx, ala2.dy);
    canvas.drawPath(puntaFlecha, pluma);
  }

  double _gradosARadianes(double grados) => grados * math.pi / 180;

  @override
  bool shouldRepaint(covariant _RelojRebobinarPainter oldDelegate) {
    return oldDelegate.color != color;
  }
}
