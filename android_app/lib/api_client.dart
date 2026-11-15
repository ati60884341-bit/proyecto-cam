import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class Camara {
  final String zona;
  final String nombre;
  final bool enLinea;
  final bool enSabotaje;

  Camara({required this.zona, required this.nombre, required this.enLinea, required this.enSabotaje});

  factory Camara.fromJson(Map<String, dynamic> j) => Camara(
        zona: j['zona'],
        nombre: j['nombre'],
        enLinea: j['en_linea'],
        enSabotaje: j['en_sabotaje'],
      );
}

class Incidencia {
  final String zona;
  final String tipo;
  final String severidad;
  final String descripcion;
  final String fechaHora;

  Incidencia({
    required this.zona,
    required this.tipo,
    required this.severidad,
    required this.descripcion,
    required this.fechaHora,
  });

  factory Incidencia.fromJson(Map<String, dynamic> j) => Incidencia(
        zona: j['Zona'] ?? '',
        tipo: j['Tipo'] ?? '',
        severidad: j['Severidad'] ?? '',
        descripcion: j['Descripcion'] ?? '',
        fechaHora: j['FechaHora'] ?? '',
      );
}

class Resumen {
  final int camarasEnLinea;
  final int camarasTotal;
  final int incidenciasHoy;
  final bool alarmaSonando;

  Resumen({
    required this.camarasEnLinea,
    required this.camarasTotal,
    required this.incidenciasHoy,
    required this.alarmaSonando,
  });

  factory Resumen.fromJson(Map<String, dynamic> j) => Resumen(
        camarasEnLinea: j['camaras_en_linea'],
        camarasTotal: j['camaras_total'],
        incidenciasHoy: j['incidencias_hoy'],
        alarmaSonando: j['alarma_sonando'],
      );
}

/// Habla con la API chica que corre adentro de la app de escritorio CAM
/// (ver app/services/api_service.py). Guarda la ip del servidor y el token
/// en el dispositivo para no pedir login cada vez que se abre la app.
class ApiClient {
  static const _claveIp = 'cam_ip';
  static const _claveToken = 'cam_token';

  String? ip;
  String? token;
  String? nombreUsuario;
  String? rol;

  Uri _uri(String path) => Uri.parse('http://$ip:8765$path');

  Future<void> cargarSesionGuardada() async {
    final prefs = await SharedPreferences.getInstance();
    ip = prefs.getString(_claveIp);
    token = prefs.getString(_claveToken);
  }

  Future<void> _guardarSesion() async {
    final prefs = await SharedPreferences.getInstance();
    if (ip != null) await prefs.setString(_claveIp, ip!);
    if (token != null) await prefs.setString(_claveToken, token!);
  }

  Future<void> cerrarSesion() async {
    token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_claveToken);
  }

  bool get tieneSesion => ip != null && token != null;

  Future<void> login(String ip, String usuario, String clave) async {
    this.ip = ip;
    final respuesta = await http
        .post(_uri('/login'), headers: {'Content-Type': 'application/json'}, body: jsonEncode({'usuario': usuario, 'clave': clave}))
        .timeout(const Duration(seconds: 8));
    if (respuesta.statusCode != 200) {
      throw Exception(jsonDecode(respuesta.body)['detail'] ?? 'No se pudo iniciar sesion.');
    }
    final datos = jsonDecode(respuesta.body);
    token = datos['token'];
    nombreUsuario = datos['nombre'];
    rol = datos['rol'];
    await _guardarSesion();
  }

  Map<String, String> get _cabeceras => {'Authorization': 'Bearer $token'};

  Uri streamUri(String zona) => _uri('/camaras/$zona/stream.mjpg');
  Uri rewindUri(String zona) => _uri('/camaras/$zona/rewind.mjpg');
  Map<String, String> get authHeaders => _cabeceras;

  Future<T> _get<T>(String path, T Function(dynamic) parse) async {
    final respuesta = await http.get(_uri(path), headers: _cabeceras).timeout(const Duration(seconds: 8));
    if (respuesta.statusCode == 401) {
      throw Exception('La sesion vencio, inicie sesion de nuevo.');
    }
    if (respuesta.statusCode != 200) {
      throw Exception('Error del servidor (${respuesta.statusCode}).');
    }
    return parse(jsonDecode(utf8.decode(respuesta.bodyBytes)));
  }

  Future<List<Camara>> getCamaras() => _get('/camaras', (j) => (j as List).map((e) => Camara.fromJson(e)).toList());

  Future<List<Incidencia>> getIncidencias({int limite = 20}) =>
      _get('/incidencias?limite=$limite', (j) => (j as List).map((e) => Incidencia.fromJson(e)).toList());

  Future<Resumen> getResumen() => _get('/resumen', (j) => Resumen.fromJson(j));
}
