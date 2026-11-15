import 'package:flutter/material.dart';
import '../api_client.dart';
import '../theme.dart';
import '../widgets/icono_reloj_rebobinar.dart';
import '../widgets/mjpeg_view.dart';

class LiveCameraScreen extends StatefulWidget {
  final ApiClient api;
  final Camara camara;
  const LiveCameraScreen({super.key, required this.api, required this.camara});

  @override
  State<LiveCameraScreen> createState() => _LiveCameraScreenState();
}

class _LiveCameraScreenState extends State<LiveCameraScreen> {
  /// Acento secundario naranja que ya usa el escritorio (ver app/views/UI/tema.py).
  static const _naranja = Color(0xFFe0935a);

  bool _repitiendo = false;
  bool _terminoRepeticion = false;
  double _vueltas = 0;

  void _iniciarMaquinaDelTiempo() {
    // La vuelta del reloj se dispara primero, sola, para que el FAB
    // (que desaparece al entrar en modo repeticion) tenga tiempo de
    // mostrar el giro de 500ms antes de que cambie la vista.
    setState(() {
      _vueltas -= 1.0;
    });
    Future.delayed(const Duration(milliseconds: 500), () {
      if (mounted) {
        setState(() {
          _repitiendo = true;
          _terminoRepeticion = false;
        });
      }
    });
  }

  void _volverAEnVivo() {
    setState(() {
      _repitiendo = false;
      _terminoRepeticion = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(backgroundColor: AppColors.panel, title: Text(widget.camara.nombre)),
      body: Stack(
        children: [
          Column(
            children: [
              Expanded(
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 300),
                      child: _repitiendo
                          ? MjpegView(
                              key: ValueKey(_repitiendo),
                              uri: widget.api.rewindUri(widget.camara.zona),
                              headers: widget.api.authHeaders,
                              finito: true,
                              onTerminado: () {
                                if (mounted) setState(() => _terminoRepeticion = true);
                              },
                            )
                          : MjpegView(
                              key: ValueKey(_repitiendo),
                              uri: widget.api.streamUri(widget.camara.zona),
                              headers: widget.api.authHeaders,
                            ),
                    ),
                    if (_terminoRepeticion)
                      Center(
                        child: ElevatedButton.icon(
                          onPressed: _volverAEnVivo,
                          icon: const Icon(Icons.visibility),
                          label: const Text('Volver a en vivo'),
                        ),
                      ),
                  ],
                ),
              ),
              if (_repitiendo && !_terminoRepeticion)
                const LinearProgressIndicator(
                  minHeight: 3,
                  color: _naranja,
                  backgroundColor: Colors.black,
                ),
            ],
          ),
          Positioned(
            top: 8,
            left: 0,
            right: 0,
            child: AnimatedSlide(
              duration: const Duration(milliseconds: 300),
              offset: _repitiendo ? Offset.zero : const Offset(0, -1),
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                  decoration: BoxDecoration(
                    color: _naranja,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Text(
                    '⏪ Hace unos segundos',
                    style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
      floatingActionButton: _repitiendo
          ? null
          : FloatingActionButton(
              backgroundColor: AppColors.panel,
              onPressed: _iniciarMaquinaDelTiempo,
              child: AnimatedRotation(
                turns: _vueltas,
                duration: const Duration(milliseconds: 500),
                child: const IconoRelojRebobinar(),
              ),
            ),
    );
  }
}
