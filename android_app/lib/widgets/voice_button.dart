import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart';

import '../theme.dart';
import '../voice_commands.dart';
import 'icono_microfono.dart';

/// Botón de comandos de voz: mantener presionado para hablar, soltar para
/// interpretar lo dicho con [interpretarComandoVoz] y avisar a
/// [onComando]. Si no se entendió nada, muestra el aviso de "no
/// entendí" en vez de llamar a [onComando].
///
/// Estados visuales (ver brief de la tarea 9):
/// - reposo: ícono quieto sobre un círculo [AppColors.panel].
/// - escuchando: anillos concéntricos que pulsan hacia afuera y el ícono
///   late de escala.
/// - procesando: los anillos colapsan al soltar.
/// - reconocido: un tilde verde reemplaza al ícono por un instante.
/// - no reconocido: el botón "tiembla" y aparece un SnackBar.
class VoiceButton extends StatefulWidget {
  final void Function(ComandoVoz) onComando;

  const VoiceButton({super.key, required this.onComando});

  @override
  State<VoiceButton> createState() => _VoiceButtonState();
}

enum _EstadoVoz { reposo, escuchando, procesando, reconocido, noReconocido }

class _VoiceButtonState extends State<VoiceButton> {
  final SpeechToText _speech = SpeechToText();
  bool _speechListo = false;
  bool _initializando = false;

  _EstadoVoz _estado = _EstadoVoz.reposo;
  double _shakeOffset = 0;
  // true mientras el dedo sigue presionado; permite detectar que se soltó
  // mientras _asegurarInicializado() seguía pendiente (ver _empezarAEscuchar).
  bool _presionando = false;

  Future<void> _asegurarInicializado() async {
    if (_speechListo || _initializando) return;
    _initializando = true;
    try {
      _speechListo = await _speech.initialize(
        onError: (_) {
          if (mounted) setState(() => _estado = _EstadoVoz.reposo);
        },
        onStatus: (status) {
          if (status == 'done' || status == 'notListening') {
            if (mounted && _estado == _EstadoVoz.escuchando) {
              setState(() => _estado = _EstadoVoz.procesando);
            }
          }
        },
      );
    } finally {
      _initializando = false;
    }
  }

  Future<void> _empezarAEscuchar() async {
    _presionando = true;
    await _asegurarInicializado();
    if (!mounted) return;
    if (!_speechListo) {
      _mostrarNoEntendido();
      return;
    }
    // si ya soltó el dedo mientras esperábamos la inicialización, no
    // arrancamos el micrófono: no hay nada que lo pare hasta la próxima
    // vez que presionen.
    if (!_presionando) return;
    setState(() => _estado = _EstadoVoz.escuchando);
    await _speech.listen(onResult: (result) {
      if (!result.finalResult) return;
      _procesarTexto(result.recognizedWords);
    });
  }

  Future<void> _soltar() async {
    _presionando = false;
    if (_estado != _EstadoVoz.escuchando) return;
    setState(() => _estado = _EstadoVoz.procesando);
    await _speech.stop();
  }

  void _procesarTexto(String texto) {
    if (!mounted) return;
    final comando = interpretarComandoVoz(texto);
    if (comando != null) {
      setState(() => _estado = _EstadoVoz.reconocido);
      widget.onComando(comando);
      Future.delayed(const Duration(milliseconds: 900), () {
        if (mounted && _estado == _EstadoVoz.reconocido) {
          setState(() => _estado = _EstadoVoz.reposo);
        }
      });
    } else {
      _mostrarNoEntendido();
    }
  }

  void _mostrarNoEntendido() {
    if (!mounted) return;
    setState(() => _estado = _EstadoVoz.noReconocido);
    _dispararShake();
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('No entendí, probá de nuevo.')),
    );
    Future.delayed(const Duration(milliseconds: 500), () {
      if (mounted && _estado == _EstadoVoz.noReconocido) {
        setState(() => _estado = _EstadoVoz.reposo);
      }
    });
  }

  Future<void> _dispararShake() async {
    const pasos = [8.0, -8.0, 0.0];
    for (final offset in pasos) {
      if (!mounted) return;
      setState(() => _shakeOffset = offset);
      await Future.delayed(const Duration(milliseconds: 130));
    }
  }

  @override
  void dispose() {
    if (_speech.isListening) {
      _speech.stop();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final escuchando = _estado == _EstadoVoz.escuchando;
    return GestureDetector(
      onLongPressStart: (_) => _empezarAEscuchar(),
      onLongPressEnd: (_) => _soltar(),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 130),
        transform: Matrix4.translationValues(_shakeOffset, 0, 0),
        child: SizedBox(
          width: 88,
          height: 88,
          child: Stack(
            alignment: Alignment.center,
            children: [
              for (var i = 0; i < 3; i++)
                _AnilloPulsante(activo: escuchando, offsetInicial: i * 400),
              AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: escuchando ? AppColors.acento : AppColors.panel,
                  shape: BoxShape.circle,
                  boxShadow: escuchando
                      ? [
                          BoxShadow(
                            color: AppColors.acento.withValues(alpha: 0.6),
                            blurRadius: 18,
                            spreadRadius: 2,
                          ),
                        ]
                      : null,
                ),
                alignment: Alignment.center,
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 600),
                  child: _estado == _EstadoVoz.reconocido
                      ? const Icon(
                          Icons.check,
                          key: ValueKey('tilde'),
                          color: Colors.greenAccent,
                          size: 28,
                        )
                      : _IconoPulsante(
                          key: const ValueKey('microfono'),
                          activo: escuchando,
                          // mientras se escucha, el circulo se ilumina de
                          // acento: el icono pasa a oscuro para seguir
                          // contrastando (si no, queda acento sobre acento).
                          color: escuchando
                              ? AppColors.panel
                              : AppColors.acento,
                        ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Uno de los 3 anillos concéntricos del estado "escuchando": escala de
/// 1.0 a 1.6 mientras se desvanece de opacidad 0.5 a 0, reiniciando en
/// bucle con [offsetInicial] ms de espera antes del primer ciclo (y entre
/// ciclos, para que los 3 queden escalonados). Al dejar de escuchar,
/// colapsa a escala 0 con fundido en 300ms.
class _AnilloPulsante extends StatefulWidget {
  final bool activo;
  final int offsetInicial;

  const _AnilloPulsante({required this.activo, required this.offsetInicial});

  @override
  State<_AnilloPulsante> createState() => _AnilloPulsanteState();
}

class _AnilloPulsanteState extends State<_AnilloPulsante> {
  bool _vivo = true;
  // se incrementa en cada ciclo nuevo: cambia la key del
  // TweenAnimationBuilder interno para que cada vuelta anime 0->1 de
  // cero, en vez de rebotar desde donde quedó la vuelta anterior.
  int _cicloId = 0;

  @override
  void initState() {
    super.initState();
    if (widget.activo) _programarCiclo(widget.offsetInicial);
  }

  @override
  void didUpdateWidget(_AnilloPulsante oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.activo && !oldWidget.activo) {
      _programarCiclo(widget.offsetInicial);
    }
  }

  @override
  void dispose() {
    _vivo = false;
    super.dispose();
  }

  void _programarCiclo(int esperaMs) {
    Future.delayed(Duration(milliseconds: esperaMs), () {
      if (!_vivo || !mounted || !widget.activo) return;
      setState(() => _cicloId++);
    });
  }

  void _onCicloTerminado() {
    if (!_vivo || !mounted || !widget.activo) return;
    // arranca el proximo ciclo ya mismo, para que el pulso se vea continuo
    _programarCiclo(0);
  }

  @override
  Widget build(BuildContext context) {
    // el pulso en si: crece de escala 1.0 a 1.6 mientras se desvanece de
    // opacidad 0.5 a 0, en bucle mientras este activo.
    final pulso = TweenAnimationBuilder<double>(
      key: ValueKey(_cicloId),
      tween: Tween(begin: 0.0, end: 1.0),
      duration: const Duration(milliseconds: 1200),
      onEnd: _onCicloTerminado,
      builder: (context, t, child) {
        return Transform.scale(
          scale: 1.0 + 0.6 * t,
          child: Opacity(
            opacity: (0.5 * (1 - t)).clamp(0.0, 1.0),
            child: Container(
              width: 56,
              height: 56,
              decoration: const BoxDecoration(
                color: AppColors.acento,
                shape: BoxShape.circle,
              ),
            ),
          ),
        );
      },
    );
    // al soltar: el anillo entero colapsa a escala 0 con fundido, 300ms.
    return AnimatedScale(
      scale: widget.activo ? 1.0 : 0.0,
      duration: const Duration(milliseconds: 300),
      child: AnimatedOpacity(
        opacity: widget.activo ? 1.0 : 0.0,
        duration: const Duration(milliseconds: 300),
        child: pulso,
      ),
    );
  }
}

/// El ícono del micrófono, que late entre escala 1.0 y 1.15 todo el
/// tiempo que [activo] sea true (mientras se escucha), y queda quieto en
/// 1.0 en reposo.
class _IconoPulsante extends StatefulWidget {
  final bool activo;
  final Color color;

  const _IconoPulsante({
    super.key,
    required this.activo,
    this.color = AppColors.acento,
  });

  @override
  State<_IconoPulsante> createState() => _IconoPulsanteState();
}

class _IconoPulsanteState extends State<_IconoPulsante> {
  bool _arriba = false;

  @override
  void didUpdateWidget(_IconoPulsante oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!widget.activo && oldWidget.activo) {
      // vuelve a quedar quieto en 1.0 al dejar de escuchar
      setState(() => _arriba = false);
    } else if (widget.activo && !oldWidget.activo) {
      setState(() => _arriba = true);
    }
  }

  void _onLatidoTerminado() {
    if (!mounted || !widget.activo) return;
    setState(() => _arriba = !_arriba);
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedScale(
      scale: widget.activo && _arriba ? 1.15 : 1.0,
      duration: const Duration(milliseconds: 400),
      onEnd: _onLatidoTerminado,
      child: IconoMicrofono(color: widget.color),
    );
  }
}
