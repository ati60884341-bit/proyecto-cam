import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';
import '../widgets/eye_loader.dart';

const _colorSeveridad = {
  'Critica': AppColors.error,
  'Alta': Color(0xFFf0c060),
  'Normal': AppColors.textoMuted,
};

class IncidenciasScreen extends StatefulWidget {
  final ApiClient api;
  const IncidenciasScreen({super.key, required this.api});

  @override
  State<IncidenciasScreen> createState() => _IncidenciasScreenState();
}

class _IncidenciasScreenState extends State<IncidenciasScreen> {
  List<Incidencia> _incidencias = [];
  String? _error;
  bool _cargando = true;

  @override
  void initState() {
    super.initState();
    _cargar();
  }

  Future<void> _cargar() async {
    setState(() => _cargando = true);
    try {
      final datos = await widget.api.getIncidencias(limite: 50);
      setState(() {
        _incidencias = datos;
        _error = null;
      });
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      setState(() => _cargando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.fondo,
      appBar: AppBar(
        backgroundColor: AppColors.fondo,
        title: const Text('Incidencias'),
      ),
      body: RefreshIndicator(
        onRefresh: _cargar,
        child: _cargando
            ? const Center(child: EyeLoader())
            : _error != null
            ? Center(
                child: Text(
                  _error!,
                  style: const TextStyle(color: AppColors.error),
                ),
              )
            : _incidencias.isEmpty
            ? const Center(
                child: Text(
                  'Sin incidencias',
                  style: TextStyle(color: AppColors.textoMuted),
                ),
              )
            : ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: _incidencias.length,
                itemBuilder: (_, i) => _tarjeta(_incidencias[i]),
              ),
      ),
    );
  }

  Widget _tarjeta(Incidencia inc) {
    final color = _colorSeveridad[inc.severidad] ?? Colors.white;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.panel,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                inc.tipo,
                style: const TextStyle(
                  color: AppColors.texto,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(
                inc.severidad,
                style: TextStyle(
                  color: color,
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            '${inc.zona} · ${inc.fechaHora}',
            style: const TextStyle(color: AppColors.textoMuted, fontSize: 12),
          ),
          const SizedBox(height: 6),
          Text(
            inc.descripcion,
            style: const TextStyle(color: Color(0xFFcfe9ef)),
          ),
        ],
      ),
    );
  }
}
