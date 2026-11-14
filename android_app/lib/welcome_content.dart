/// Saludo y frases de la pantalla de bienvenida (ver app/views/inicio_view.py
/// en el escritorio - misma idea, adaptada a lo que puede hacer el celular).
String saludoPorHora(int hora) {
  if (hora < 12) return 'Buenos dias';
  if (hora < 19) return 'Buenas tardes';
  return 'Buenas noches';
}

List<String> frasesBienvenida(int totalCamaras) {
  final primera = totalCamaras > 0
      ? 'Tenes $totalCamaras camara${totalCamaras == 1 ? '' : 's'} cuidando el lugar, visible desde donde estes.'
      : 'Todavia no hay camaras cargadas en el Centro de Monitoreo.';
  return [
    primera,
    'Toca una camara en linea para verla en vivo, en tiempo real.',
    'Las incidencias quedan firmadas: nadie puede alterarlas.',
    'No estas solo en este turno: el sistema sigue vigilando aunque cierres la app.',
    'Deslizá hacia abajo en cualquier pantalla para actualizar al toque.',
  ];
}
