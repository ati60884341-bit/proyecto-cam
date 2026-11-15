import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';

enum _EstadoPaso { pendiente, confirmado, expirado }

/// Pantalla de demo: simula un incidente en [zona] con un botón de
/// "mantené presionado para armar" (1.5s, para no disparar nada por
/// accidente) y luego muestra un checklist de 3 pasos que se confirma
/// sondeando la API real (no una animación falsa) — ver brief de la
/// tarea 16.
class SimulacroScreen extends StatefulWidget {
  final ApiClient api;
  final String zona;

  const SimulacroScreen({super.key, required this.api, required this.zona});

  @override
  State<SimulacroScreen> createState() => _SimulacroScreenState();
}

class _SimulacroScreenState extends State<SimulacroScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _anillo;
  bool _enviando = false;
  bool _confirmando = false;
  double _opacidadDestello = 0;

  _EstadoPaso _paso1 = _EstadoPaso.pendiente;
  _EstadoPaso _paso2 = _EstadoPaso.pendiente;
  _EstadoPaso _paso3 = _EstadoPaso.pendiente;

  @override
  void initState() {
    super.initState();
    _anillo = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..addStatusListener((estado) {
        if (estado == AnimationStatus.completed) _armar();
      });
  }

  @override
  void dispose() {
    _anillo.dispose();
    super.dispose();
  }

  void _onPressStart() {
    if (_enviando || _confirmando) return;
    _anillo.forward(from: 0);
  }

  /// Soltar antes de llegar al final de los 1.5s retrocede el anillo y no
  /// dispara nada. Si ya completó (el listener de `_anillo` ya llamó a
  /// `_armar`), no hay nada que retroceder.
  void _onPressEndOCancel() {
    if (_anillo.status == AnimationStatus.forward) {
      _anillo.animateTo(0, duration: const Duration(milliseconds: 200));
    }
  }

  Future<void> _armar() async {
    if (_enviando || _confirmando) return;
    setState(() => _enviando = true);

    // Captura la foto de "antes" justo antes de disparar el POST: así el
    // paso 2 puede exigir una fila que no estaba acá, en vez de confundirse
    // con un simulacro viejo que ya estuviera en la lista (esa es la
    // trampa: si comparáramos contra el primer sondeo DESPUÉS del POST,
    // una fila creada al instante ya estaría ahí y nunca se vería "nueva").
    List<Incidencia> antes;
    try {
      antes = await widget.api.getIncidencias(limite: 5);
    } catch (_) {
      antes = const [];
    }

    try {
      await widget.api.simularIncidente(widget.zona);
    } catch (e) {
      if (!mounted) return;
      setState(() => _enviando = false);
      _anillo.value = 0;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      return;
    }

    if (!mounted) return;
    setState(() {
      _enviando = false;
      _confirmando = true;
      _paso1 = _EstadoPaso.confirmado; // el POST ya respondió 200
    });
    _destello();
    _confirmarPasos(antes);
  }

  Future<void> _destello() async {
    setState(() => _opacidadDestello = 0.4);
    await Future.delayed(const Duration(milliseconds: 150));
    if (!mounted) return;
    setState(() => _opacidadDestello = 0);
  }

  String _firma(Incidencia i) => '${i.zona}|${i.tipo}|${i.fechaHora}';

  /// Sondea [condicion] cada 500ms hasta que devuelva true o pasen 8s (evita
  /// quedar esperando para siempre si el backend nunca confirma).
  Future<bool> _sondear(Future<bool> Function() condicion) async {
    final limite = DateTime.now().add(const Duration(seconds: 8));
    while (DateTime.now().isBefore(limite)) {
      if (!mounted) return false;
      try {
        if (await condicion()) return true;
      } catch (_) {
        // sigue sondeando: un error transitorio no cuenta como confirmación
        // ni corta el sondeo antes de los 8s.
      }
      if (!mounted) return false;
      await Future.delayed(const Duration(milliseconds: 500));
    }
    return false;
  }

  Future<void> _confirmarPasos(List<Incidencia> antes) async {
    final firmasAntes = antes.map(_firma).toSet();

    final evidenciaOk = await _sondear(() async {
      final incidencias = await widget.api.getIncidencias(limite: 5);
      return incidencias.any((i) =>
          i.tipo == 'Simulacro' &&
          i.zona == widget.zona &&
          !firmasAntes.contains(_firma(i)));
    });
    if (!mounted) return;
    setState(() {
      _paso2 = evidenciaOk ? _EstadoPaso.confirmado : _EstadoPaso.expirado;
    });

    final alarmaOk = await _sondear(() async {
      final resumen = await widget.api.getResumen();
      return resumen.alarmaSonando;
    });
    if (!mounted) return;
    setState(() {
      _paso3 = alarmaOk ? _EstadoPaso.confirmado : _EstadoPaso.expirado;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.fondo,
      appBar: AppBar(
        backgroundColor: AppColors.fondo,
        title: const Text('Simulacro de incidente'),
      ),
      body: Stack(
        children: [
          Center(child: _confirmando ? _listaPasos() : _botonArmar()),
          IgnorePointer(
            child: AnimatedOpacity(
              opacity: _opacidadDestello,
              duration: const Duration(milliseconds: 150),
              child: Container(color: AppColors.error),
            ),
          ),
        ],
      ),
    );
  }

  Widget _botonArmar() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          'Zona: ${widget.zona}',
          style: const TextStyle(color: AppColors.textoMuted),
        ),
        const SizedBox(height: 24),
        GestureDetector(
          onLongPressStart: (_) => _onPressStart(),
          onLongPressEnd: (_) => _onPressEndOCancel(),
          onLongPressCancel: _onPressEndOCancel,
          child: AnimatedBuilder(
            animation: _anillo,
            builder: (_, _) => SizedBox(
              width: 140,
              height: 140,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  SizedBox(
                    width: 140,
                    height: 140,
                    child: CircularProgressIndicator(
                      value: _anillo.value,
                      strokeWidth: 6,
                      color: AppColors.error,
                      backgroundColor: AppColors.borde,
                    ),
                  ),
                  Container(
                    width: 108,
                    height: 108,
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      color: AppColors.panel,
                    ),
                    alignment: Alignment.center,
                    child: _enviando
                        ? const CircularProgressIndicator(color: AppColors.acento)
                        : const Icon(
                            Icons.warning_amber_rounded,
                            color: AppColors.error,
                            size: 40,
                          ),
                  ),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(height: 20),
        const Text(
          'Mantené presionado para armar',
          style: TextStyle(color: AppColors.texto),
        ),
      ],
    );
  }

  Widget _listaPasos() {
    final pasos = [
      ('Incidente simulado', _paso1),
      ('Evidencia firmada con SHA-256', _paso2),
      ('Alarma activada', _paso3),
    ];
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final (indice, paso) in pasos.indexed)
            _filaPaso(indice, paso.$1, paso.$2),
        ],
      ),
    );
  }

  Widget _filaPaso(int indice, String etiqueta, _EstadoPaso estado) {
    return TweenAnimationBuilder<double>(
      key: ValueKey(indice),
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 250 + indice * 100),
      curve: Curves.easeOut,
      builder: (_, v, child) => Opacity(
        opacity: v,
        child: Transform.translate(
          offset: Offset((1 - v) * 40, 0),
          child: child,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Row(
          children: [
            _iconoPaso(estado),
            const SizedBox(width: 12),
            Expanded(
              child: Text(etiqueta, style: const TextStyle(color: AppColors.texto)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _iconoPaso(_EstadoPaso estado) {
    switch (estado) {
      case _EstadoPaso.pendiente:
        return const SizedBox(
          width: 22,
          height: 22,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            color: AppColors.textoMuted,
          ),
        );
      case _EstadoPaso.confirmado:
        return TweenAnimationBuilder<double>(
          tween: Tween(begin: 0.5, end: 1.0),
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOutBack,
          builder: (_, v, child) => Transform.scale(scale: v, child: child),
          child: const Icon(Icons.check_circle, color: AppColors.acento, size: 22),
        );
      case _EstadoPaso.expirado:
        return const Icon(Icons.error_outline, color: AppColors.error, size: 22);
    }
  }
}
