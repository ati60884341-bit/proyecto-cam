import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';
import '../theme.dart';
import 'login_screen.dart';
import 'incidencias_screen.dart';
import 'live_camera_screen.dart';

/// Pantalla principal: resumen + estado en vivo de cada camara. Se actualiza
/// sola cada 5 s (sondeo simple - no hay push todavia, ver README del
/// proyecto Flutter para los proximos pasos).
class HomeScreen extends StatefulWidget {
  final ApiClient api;
  const HomeScreen({super.key, required this.api});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  Resumen? _resumen;
  List<Camara> _camaras = [];
  String? _error;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _actualizar();
    _timer = Timer.periodic(const Duration(seconds: 5), (_) => _actualizar());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _actualizar() async {
    try {
      final resumen = await widget.api.getResumen();
      final camaras = await widget.api.getCamaras();
      if (!mounted) return;
      setState(() {
        _resumen = resumen;
        _camaras = camaras;
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '$e');
      if (e.toString().contains('vencio')) _cerrarSesion();
    }
  }

  Future<void> _cerrarSesion() async {
    // cancela el sondeo antes de navegar: si no, con una pantalla (camara en
    // vivo, incidencias) encima de esta, Inicio seguia vivo debajo y el
    // sondeo repetia el cierre de sesion cada 5s, borrando el login a medio
    // escribir una y otra vez
    _timer?.cancel();
    await widget.api.cerrarSesion();
    if (!mounted) return;
    Navigator.of(context)
        .pushAndRemoveUntil(MaterialPageRoute(builder: (_) => LoginScreen(api: widget.api)), (route) => false);
  }

  @override
  Widget build(BuildContext context) {
    final resumen = _resumen;
    return Scaffold(
      backgroundColor: AppColors.fondo,
      appBar: AppBar(
        backgroundColor: AppColors.fondo,
        title: const Text('Centro de monitoreo'),
        actions: [
          IconButton(
            icon: const Icon(Icons.warning_amber_outlined),
            tooltip: 'Incidencias',
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => IncidenciasScreen(api: widget.api))),
          ),
          IconButton(icon: const Icon(Icons.logout), onPressed: _cerrarSesion),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _actualizar,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (_error != null)
              Container(
                padding: const EdgeInsets.all(12),
                margin: const EdgeInsets.only(bottom: 12),
                decoration: BoxDecoration(color: AppColors.error.withAlpha(0x33), borderRadius: BorderRadius.circular(8)),
                child: Text(_error!, style: const TextStyle(color: AppColors.error)),
              ),
            if (resumen != null) _tarjetaResumen(resumen),
            const SizedBox(height: 20),
            const Text('Camaras', style: TextStyle(color: AppColors.texto, fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            ..._camaras.asMap().entries.map((entrada) => _filaAnimada(entrada.key, entrada.value)),
          ],
        ),
      ),
    );
  }

  Widget _tarjetaResumen(Resumen r) {
    final colorAlarma = r.alarmaSonando ? AppColors.error : AppColors.acento;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: AppColors.panel, borderRadius: BorderRadius.circular(14)),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          _dato('${r.camarasEnLinea} de ${r.camarasTotal}', 'camaras en linea'),
          _dato('${r.incidenciasHoy}', 'incidencias hoy'),
          _dato(r.alarmaSonando ? 'Sonando' : 'Apagada', 'alarma', color: colorAlarma),
        ],
      ),
    );
  }

  Widget _dato(String valor, String etiqueta, {Color color = AppColors.texto}) {
    return Column(
      children: [
        Text(valor, style: TextStyle(color: color, fontSize: 20, fontWeight: FontWeight.bold)),
        Text(etiqueta, style: const TextStyle(color: AppColors.textoMuted, fontSize: 12)),
      ],
    );
  }

  Widget _filaAnimada(int indice, Camara c) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 300 + indice * 60),
      curve: Curves.easeOut,
      builder: (_, v, child) => Opacity(
        opacity: v,
        child: Transform.translate(offset: Offset(0, (1 - v) * 12), child: child),
      ),
      child: _filaCamara(c),
    );
  }

  Widget _filaCamara(Camara c) {
    final color = c.enSabotaje ? AppColors.error : (c.enLinea ? AppColors.acento : AppColors.textoMuted);
    final estado = c.enSabotaje ? 'Posible sabotaje' : (c.enLinea ? 'En linea' : 'Sin senal');
    return GestureDetector(
      onTap: () {
        if (!c.enLinea) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Camara sin senal.')));
          return;
        }
        Navigator.of(context).push(MaterialPageRoute(builder: (_) => LiveCameraScreen(api: widget.api, camara: c)));
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(color: AppColors.panel, borderRadius: BorderRadius.circular(10)),
        child: Row(
          children: [
            Icon(Icons.circle, size: 10, color: color),
            const SizedBox(width: 12),
            Expanded(child: Text(c.nombre, style: const TextStyle(color: AppColors.texto))),
            Text(estado, style: TextStyle(color: color, fontSize: 12)),
          ],
        ),
      ),
    );
  }
}
