import 'package:flutter/material.dart';

/// Indicador de carga con la marca de CAM (el ojo pulsando) en vez del
/// spinner generico de Material, para que toda la app se sienta de una
/// sola pieza. Animacion implicita: sube y baja de opacidad en loop.
class EyeLoader extends StatefulWidget {
  final double tamano;
  const EyeLoader({super.key, this.tamano = 64});

  @override
  State<EyeLoader> createState() => _EyeLoaderState();
}

class _EyeLoaderState extends State<EyeLoader> {
  bool _tenue = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _alternar());
  }

  void _alternar() {
    if (!mounted) return;
    setState(() => _tenue = !_tenue);
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedOpacity(
      opacity: _tenue ? 0.35 : 1.0,
      duration: const Duration(milliseconds: 900),
      curve: Curves.easeInOut,
      onEnd: _alternar,
      child: Image.asset(
        'assets/icono_ojo.png',
        width: widget.tamano,
        height: widget.tamano,
      ),
    );
  }
}
