import 'package:flutter/material.dart';

/// La misma escena nocturna animada (GIF) que el escritorio usa de fondo en
/// el splash/login (ver app/views/UI/fondo_nocturno.py), ajustada a la
/// pantalla del celular con BoxFit.cover. Flutter decodifica GIFs animados
/// de forma nativa con Image, sin paquetes nuevos.
class GifBackground extends StatelessWidget {
  final double opacidadOscuro;
  const GifBackground({super.key, this.opacidadOscuro = 0.45});

  @override
  Widget build(BuildContext context) {
    return Positioned.fill(
      child: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset(
            'assets/fondo_nocturno.gif',
            fit: BoxFit.cover,
            gaplessPlayback: true,
          ),
          Container(color: Colors.black.withValues(alpha: opacidadOscuro)),
        ],
      ),
    );
  }
}
