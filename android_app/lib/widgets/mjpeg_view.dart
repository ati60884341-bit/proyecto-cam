import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import 'eye_loader.dart';
import 'mjpeg_parser.dart';

/// Reproduce el stream en vivo de una camara (ver api_service.py /stream.mjpg)
/// como una seguidilla de imagenes JPEG, sin paquetes nuevos: arma el
/// pedido http a mano y usa AnalizadorMjpeg para separar los cuadros.
class MjpegView extends StatefulWidget {
  final Uri uri;
  final Map<String, String> headers;
  /// Si es true, cuando el stream termina (onDone) sin que haya sido un
  /// 401/404 explicito, en vez de reconectar se llama a [onTerminado] una
  /// vez y no se reintenta mas (usado por la maquina del tiempo para
  /// reproducir una grabacion finita en vez del feed en vivo).
  final bool finito;
  final VoidCallback? onTerminado;
  const MjpegView({
    super.key,
    required this.uri,
    required this.headers,
    this.finito = false,
    this.onTerminado,
  });

  @override
  State<MjpegView> createState() => _MjpegViewState();
}

class _MjpegViewState extends State<MjpegView> {
  final _analizador = AnalizadorMjpeg();
  http.Client? _client;
  StreamSubscription<List<int>>? _sub;
  Timer? _temporizadorInactividad;
  Uint8List? _ultimoCuadro;
  String? _error;

  @override
  void initState() {
    super.initState();
    // arranca una sola vez, no en cada intento de reconexion: si no, cada
    // reintento (cada 2s) pisaba el plazo y el aviso de "dejo de responder"
    // nunca llegaba a dispararse mientras la camara jamas mandaba un cuadro
    _reiniciarTemporizadorInactividad();
    _conectar();
  }

  Future<void> _conectar() async {
    _client?.close();
    final client = http.Client();
    _client = client;
    try {
      final respuesta = await client.send(
        http.Request('GET', widget.uri)..headers.addAll(widget.headers),
      );
      if (respuesta.statusCode != 200) {
        final mensaje = respuesta.statusCode == 401
            ? 'Sesion vencida, volve a iniciar sesion.'
            : respuesta.statusCode == 404
            ? 'Camara no encontrada.'
            : 'No se pudo conectar (${respuesta.statusCode}).';
        if (mounted) setState(() => _error = mensaje);
        return;
      }
      _sub = respuesta.stream.listen(
        (chunk) {
          for (final cuadro in _analizador.agregarBytes(chunk)) {
            if (!mounted) return;
            setState(() {
              _ultimoCuadro = cuadro;
              _error = null;
            });
            _reiniciarTemporizadorInactividad();
          }
        },
        onError: (_) => _reintentar(),
        onDone: () {
          if (widget.finito) {
            if (mounted) widget.onTerminado?.call();
            return;
          }
          _reintentar();
        },
        cancelOnError: true,
      );
    } catch (_) {
      _reintentar();
    }
  }

  void _reintentar() {
    if (!mounted) return;
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) _conectar();
    });
  }

  void _reiniciarTemporizadorInactividad() {
    _temporizadorInactividad?.cancel();
    _temporizadorInactividad = Timer(const Duration(seconds: 5), () {
      if (mounted) setState(() => _error = 'La camara dejo de responder.');
    });
  }

  @override
  void dispose() {
    _sub?.cancel();
    _temporizadorInactividad?.cancel();
    _client?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_ultimoCuadro != null) {
      return Stack(
        alignment: Alignment.bottomCenter,
        children: [
          Image.memory(
            _ultimoCuadro!,
            gaplessPlayback: true,
            fit: BoxFit.contain,
          ),
          if (_error != null)
            Container(
              width: double.infinity,
              color: const Color(0x99000000),
              padding: const EdgeInsets.all(8),
              child: Text(
                _error!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.white),
              ),
            ),
        ],
      );
    }
    if (_error != null) {
      return Center(
        child: Text(_error!, style: const TextStyle(color: Colors.white)),
      );
    }
    return const Center(child: EyeLoader());
  }
}
