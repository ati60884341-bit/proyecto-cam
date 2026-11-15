import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme.dart';

/// Icono "micrófono": cápsula vertical rellena, un arco por debajo
/// abrazando los costados, un tallo corto y una línea de base — para el
/// botón de comandos de voz. Reproduce el diseño exacto del ícono
/// `_microfono` del escritorio (ver app/views/UI/iconos.py), mismo trazo
/// fino y un solo color que el resto de los íconos del programa.
class IconoMicrofono extends StatelessWidget {
  final double tamano;
  final Color color;

  const IconoMicrofono({
    super.key,
    this.tamano = 28,
    this.color = AppColors.acento,
  });

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: Size(tamano, tamano),
      painter: _MicrofonoPainter(color: color),
    );
  }
}

class _MicrofonoPainter extends CustomPainter {
  final Color color;

  _MicrofonoPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final trazo = math.max(1.6, size.width / 12);
    final pluma = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = trazo
      ..strokeCap = StrokeCap.round;

    const left = 0.0;
    const top = 0.0;
    final width = size.width;
    final height = size.height;
    final centerX = width / 2;

    // Cápsula rellena: el cuerpo del micrófono.
    final anchoCapsula = width * 0.36;
    final capsula = Rect.fromLTWH(
      centerX - anchoCapsula / 2,
      top + height * 0.08,
      anchoCapsula,
      height * 0.52,
    );
    pluma.style = PaintingStyle.fill;
    canvas.drawRRect(
      RRect.fromRectAndRadius(capsula, Radius.circular(anchoCapsula / 2)),
      pluma,
    );

    // Arco por debajo de la cápsula, sin relleno (misma pluma, solo trazo).
    pluma.style = PaintingStyle.stroke;
    final arco = Rect.fromLTWH(
      left + width * 0.2,
      top + height * 0.2,
      width * 0.6,
      height * 0.55,
    );
    // Conversión Qt -> Flutter de los ángulos del arco:
    // Qt (QPainter.drawArc) mide en 1/16 de grado, 0° a las 3 en punto,
    // positivo = antihorario EN PANTALLA (así lo define la documentación
    // de Qt, aun con el eje Y hacia abajo). Flutter (Canvas.drawArc) mide
    // en radianes, 0° también a las 3 en punto, pero positivo = horario
    // en pantalla (fórmula directa punto = centro + r*(cos θ, sen θ) con Y
    // hacia abajo). Ambas parten del mismo 0°, así que son espejo una de
    // la otra: ángulo_flutter = -ángulo_qt (se puede verificar evaluando
    // los puntos de inicio, mitad y fin del arco con cada fórmula: dan las
    // mismas coordenadas en pantalla).
    //
    // El escritorio llama drawArc(arco, 200*16, 140*16): empieza en 200°,
    // barre 140° antihorario, termina en 340°. En pantalla eso va de la
    // esquina inferior-izquierda de "arco" (200°), pasando por abajo del
    // todo (270°), hasta la esquina inferior-derecha (340°) — el arco que
    // abraza los costados y la base de la cápsula, abierto arriba (donde
    // ya la cápsula rellena ocupa el espacio visualmente).
    //
    // Aplicando ángulo_flutter = -ángulo_qt:
    //   inicio_flutter = -200°, barrido_flutter = -140°
    // reproduce el mismo recorrido (mismo punto de inicio, mismo punto de
    // fin, mismo paso por abajo).
    canvas.drawArc(
      arco,
      _gradosARadianes(-200),
      _gradosARadianes(-140),
      false,
      pluma,
    );

    // Tallo vertical corto bajando del arco.
    final baseY = top + height * 0.76;
    final finDelTallo = top + height - height * 0.08;
    canvas.drawLine(
      Offset(centerX, baseY),
      Offset(centerX, finDelTallo),
      pluma,
    );

    // Línea horizontal de base.
    canvas.drawLine(
      Offset(centerX - width * 0.16, finDelTallo),
      Offset(centerX + width * 0.16, finDelTallo),
      pluma,
    );
  }

  double _gradosARadianes(double grados) => grados * math.pi / 180;

  @override
  bool shouldRepaint(covariant _MicrofonoPainter oldDelegate) {
    return oldDelegate.color != color;
  }
}
