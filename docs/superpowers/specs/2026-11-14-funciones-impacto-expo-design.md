# Funciones de impacto para la expo-feria: máquina del tiempo, voz, simulacro, QR

## Intención y por qué

La app Android ya impresiona con video en vivo y diseño cuidado. Para la
expo-feria se agregan cuatro funciones pensadas específicamente para un
jurado: rebobinar video sin haber "grabado" nada a propósito, controlar la
app por voz, disparar una demo completa del sistema de seguridad con un
botón, y conectarse al centro de monitoreo escaneando un código QR en vez
de tipear una IP. El usuario pidió explícitamente que no haya fallos: cada
función se construye con su propio ciclo de test y se revisa antes de
darla por terminada.

## Goals

- **Máquina del tiempo**: desde la cámara en vivo, ver los últimos ~8
  segundos ya grabados en el buffer del escritorio, sin haber iniciado
  ninguna grabación manual.
- **Comandos de voz**: controlar la app (abrir una cámara, ver incidencias,
  volver a inicio, simular un incidente, cerrar sesión) hablando, con el
  mismo vocabulario que ya usa el escritorio donde aplica.
- **Botón de simulación de incidente**: desde el celular, disparar en el
  escritorio la secuencia completa de un sabotaje real (evidencia firmada +
  alarma) marcada como simulacro, y ver en el celular una confirmación
  paso a paso de que cada parte ocurrió de verdad.
- **Login por QR**: escanear un código QR que muestra el login del
  escritorio para completar la IP del celular automáticamente.
- Cuatro íconos nuevos (reloj/rebobinar, micrófono, alarma de simulacro,
  QR) dibujados con el mismo lenguaje visual del escritorio (líneas finas,
  un solo color), no íconos genéricos de Material.
- Animaciones propias y detalladas para cada función (especificadas abajo),
  no solo spinners o transiciones genéricas.

## Non-goals (esta ronda)

- Notificaciones push reales (Firebase) — ninguna de las cuatro funciones
  las necesita.
- Reconocimiento de voz offline/sin internet — se usa el reconocedor de
  voz nativo de Android, igual de válido que el que ya usa el escritorio
  (que tampoco es local: usa la API gratuita de Google).
- Comandos de voz de PTZ/zoom/presets — no aplican al celular.
- Rebobinar más allá de lo que el buffer del escritorio ya guarda
  (`BUFFER_SEGUNDOS = 8`).

## Anti-goals

- Que un simulacro de incidente se mezcle con incidencias reales en los
  reportes o en el resumen de "incidencias de hoy".
- Que el QR exponga la contraseña o cualquier credencial.
- Que la detección de voz quede escuchando todo el tiempo (pilas, privacidad).
- Romper el flujo de detección de sabotaje real existente.

## Constraints

- Nueva excepción puntual a "sin paquetes nuevos" (regla de la ronda
  anterior): se agregan `speech_to_text` y `mobile_scanner` en Flutter, y
  `qrcode` en Python — los tres paquetes son ampliamente usados y
  mantenidos, sin alternativa razonable para estas funciones.
- El simulacro reutiliza el pipeline real de sabotaje (evidencia firmada +
  alarma) en vez de duplicarlo, para no mantener dos caminos de código que
  hacen casi lo mismo.
- Los íconos nuevos siguen el estilo de `app/views/UI/iconos.py`: trazo
  fino de un solo color, formas simples, sin relleno.
- Las animaciones usan widgets implícitos de Flutter (`AnimatedOpacity`,
  `AnimatedRotation`, `AnimatedSlide`, `AnimatedContainer`,
  `TweenAnimationBuilder`), sin `AnimationController` a medida — mismo
  criterio que la ronda anterior.
- No se agrega permiso de ubicación ni de contactos; solo lo que cada
  función necesita puntualmente (micrófono para voz, cámara para QR).

## Approaches consideradas (resumen de lo ya charlado y acordado)

1. **Máquina del tiempo** — exponer el buffer ya existente
   (`CamaraThread._buffer`) como un segundo endpoint de streaming finito,
   reusando el mismo formato multipart que `/stream.mjpg` (así el parser
   `AnalizadorMjpeg` de Android no cambia). Alternativa descartada: generar
   un archivo de video (.mp4/.avi) y servirlo — más pesado, más lento de
   generar bajo demanda, y el celular ya sabe reproducir JPEGs en
   secuencia.
2. **Simulacro de incidente** — reusar `_exportar_evidencia_sabotaje` (ya
   hace evidencia firmada + incidencia + dispara la alarma) agregándole un
   parámetro `es_simulacro`, en vez de escribir un camino nuevo. Alternativa
   descartada: simular solo "de mentira" en la UI del celular sin tocar el
   escritorio — no cumple el objetivo de mostrar la cadena real
   funcionando.
3. **QR** — el QR lleva solo la IP (JSON `{"ip": "..."}`), nunca la clave.
   Alternativa descartada: QR con usuario+clave — inseguro, cualquiera que
   fotografíe la pantalla del login se loguea.
4. **Voz** — `speech_to_text` (reconocedor nativo de Android) con
   mantener-presionado (como el escritorio), vocabulario acotado por
   palabras clave. Alternativa descartada: activación por palabra clave
   ("hey CAM") — consume batería/CPU todo el tiempo y es mucho más difícil
   de calibrar bien para una demo de pocos minutos.

## Cómo se construye (decidido)

### 1. Máquina del tiempo

**Escritorio:**
- `CamaraThread.obtener_buffer_jpeg_brillante(self) -> list[bytes]`: copia
  `self._buffer` (ya son JPEGs), decodifica cada uno, le aplica el mismo
  realce de brillo que `obtener_ultimo_jpeg` (`BRILLO_EXTRA_ANDROID_ALPHA`/
  `BETA`), y vuelve a codificar. Se llama una sola vez por cada "ver
  rebobinado", no en el loop de captura — no afecta el video en vivo ni el
  archivo de evidencia real (ese sigue usando el buffer crudo tal cual).
- `GET /camaras/{zona}/rewind.mjpg` en `api_service.py`: mismo esquema de
  auth/404/503 que `/stream.mjpg`. A diferencia de ese, el generador
  recorre la lista UNA sola vez (no `while True`) y termina la respuesta
  al llegar al final — el celular ve el stream "cerrarse solo" al terminar
  la repetición.

**Android:**
- `MjpegView` gana un parámetro `finito: bool` (default `false`): cuando
  es `true`, al terminar el stream (`onDone`) no reintenta — en cambio
  llama a un callback `onTerminado` provisto por quien lo use.
- `LiveCameraScreen` agrega un botón flotante (ícono reloj/rebobinar,
  ver más abajo) que alterna entre `MjpegView(uri: streamUri, finito:
  false)` y `MjpegView(uri: rewindUri, finito: true)`.
- **Ícono** ("reloj rebobinar"): un círculo de reloj (línea fina,
  `AppColors.acento`) con una flecha curva antihoraria alrededor,
  dibujado con `CustomPainter` — mismo lenguaje que el ícono de
  micrófono del escritorio (trazo ~1.6px, sin relleno).
- **Animación detallada:**
  1. Al tocar el botón: el ícono gira 360° en sentido antihorario en
     ~500ms (`AnimatedRotation`), como si "rebobinara".
  2. La vista cruza de en-vivo a repetición con un fundido (300ms,
     `AnimatedSwitcher`) y aparece una pastilla naranja/ámbar deslizándose
     desde arriba (`AnimatedSlide`, no teal — para que no se confunda con
     "en vivo") con el texto "⏪ Hace unos segundos".
  3. Mientras repite: una franja fina en la parte de abajo del video
     pulsa/se desliza (indicador indeterminado, no exacto) para marcar que
     hay una repetición en curso.
  4. Al terminar (`onTerminado`): aparece un botón "Volver a en vivo"
     centrado sobre el último cuadro; al tocarlo, fundido inverso de
     vuelta a `streamUri`, la pastilla naranja se desliza hacia afuera.

### 2. Comandos de voz

**Android únicamente** (no toca el escritorio):
- Paquete `speech_to_text`; permiso `RECORD_AUDIO` en
  `AndroidManifest.xml`.
- Botón flotante de micrófono en `HomeScreen`, mantener presionado para
  hablar (igual que el escritorio).
- Vocabulario (reconocido por palabras clave en el texto, no NLP):
  - `"camara N"` / `"mostrar camara N"` / `"abrir camara N"` → abre la
    N-ésima cámara de la lista actual en `LiveCameraScreen`.
  - `"incidencias"` → `IncidenciasScreen`.
  - `"inicio"` / `"resumen"` → vuelve a `HomeScreen` si está en otra
    pantalla.
  - `"simular incidente"` / `"panico"` / `"ayuda"` → abre la pantalla de
    simulación (función 3).
  - `"cerrar sesion"` → `_cerrarSesion`.
- **Ícono** ("micrófono"): cápsula redondeada + arco + tallo + base,
  recreando el ícono `_microfono` del escritorio (mismo trazo, misma
  composición) con `CustomPainter`.
- **Animación detallada:**
  1. Reposo: ícono quieto, color `AppColors.acento` sobre fondo
     `AppColors.panel`.
  2. Mientras se mantiene presionado (escuchando): 3 anillos concéntricos
     se expanden y se desvanecen en bucle (estilo sonar/radar, escalonados
     en el tiempo con `TweenAnimationBuilder` + `onEnd` reiniciando), el
     ícono pulsa de escala 1.0 a 1.15 y vuelta.
  3. Al soltar, mientras se procesa el texto: los anillos se congelan y
     colapsan hacia adentro (fundido + escala a 0 en 300ms).
  4. Comando reconocido: un tilde verde reemplaza al micrófono por 600ms
     (`AnimatedSwitcher`) antes de volver al reposo.
  5. Comando no reconocido: el botón completo hace un "shake" (3
     traslaciones horizontales cortas, ~400ms en total) y aparece un
     `SnackBar` "No entendí, probá de nuevo".

### 3. Botón de simulación de incidente

**Escritorio:**
- `camera_service.py`: la señal `sabotaje_detectado` gana un cuarto
  parámetro `es_simulacro: bool` (con `False` en el único lugar que ya la
  emite, para no cambiar el comportamiento real). Nuevo método público
  `CamaraThread.disparar_simulacro(self)`: arranca un hilo daemon que
  llama a `self._exportar_evidencia_sabotaje(list(self._buffer),
  es_simulacro=True)` — reusa el mismo código que ya arma evidencia +
  video + firma SHA-256 para el sabotaje real.
- `monitoreo_controller.py`: `_on_sabotaje` recibe el nuevo parámetro y se
  lo pasa a `_GuardarEvidenciaSabotajeThread`, que ahora acepta
  `tipo="Sabotaje"` (default, sin cambios en el llamado real) o
  `tipo="Simulacro"`/`severidad="Normal"` cuando `es_simulacro=True`. El
  resto del pipeline (evidencia, firma, alarma) corre exactamente igual.
- `incidencia_model.py`: `contar_hoy()` y lo que alimenta el resumen de
  Android/reportes excluye `Tipo="Simulacro"` por defecto (parámetro nuevo
  `incluir_simulacros=False`), para que un simulacro en la feria no
  infle las estadísticas reales.
- `api_service.py`: `POST /camaras/{zona}/simular-incidente` — auth,
  busca el hilo, llama `disparar_simulacro()`, responde al instante
  (`{"disparado": true}`); el trabajo real sigue en segundo plano, igual
  que ya hace el escritorio con el sabotaje real.

**Android:**
- Pantalla nueva con un botón grande "Mantené presionado para armar" —
  mantener apretado ~1.5s (anillo de progreso circular alrededor del
  botón) antes de disparar, para que no se dispare por accidente.
- Al completarse el mantenido: `POST` al endpoint, destello rojo breve en
  toda la pantalla, y una lista de 3 pasos que van apareciendo con tilde
  a medida que se confirman de verdad (no una animación de mentira):
  1. "Incidente simulado" — se marca apenas el POST responde 200.
  2. "Evidencia firmada con SHA-256" — se marca cuando `/incidencias`
     devuelve una fila nueva con `Tipo="Simulacro"` (sondeo cada ~0.5s).
  3. "Alarma activada" — se marca cuando `/resumen` devuelve
     `alarma_sonando: true`.
- **Ícono** ("alarma de simulacro"): campana de línea fina con un pequeño
  rayo/triángulo de alerta superpuesto, mismo trazo que el resto.
- **Animación detallada:**
  1. Mantener presionado: anillo de `CircularProgressIndicator` (color
     rojo/ámbar) llena de 0 a 1 en 1.5s alrededor del botón; si se suelta
     antes, el anillo retrocede a 0 en 200ms en vez de disparar.
  2. Al completarse: destello rojo de toda la pantalla
     (`AnimatedOpacity` 0→0.4→0 en 300ms).
  3. Los 3 pasos aparecen uno por uno con fundido + deslizamiento desde la
     derecha (`AnimatedSlide`), cada uno con su tilde aaparenciendo con un
     pequeño "pop" de escala al confirmarse.
  4. Si algún paso no se confirma en 8s (p. ej. no hay alarma activa),
     ese paso se marca con un ícono de advertencia en vez de tilde, en vez
     de quedar girando para siempre.

### 4. Login por QR

**Escritorio:**
- Dependencia nueva: `qrcode` (Python, sin dependencias de sistema).
- Nueva función para detectar la IP LAN (truco estándar
  `socket.connect(("8.8.8.8", 80))` + `getsockname()[0]`, no manda
  paquetes reales) — no hay nada para reusar, se escribe de cero.
- `login_view.py`: un `QLabel` con el QR (120×120px) siempre visible en la
  tarjeta de login, generado con `qrcode` codificando
  `{"ip": "<ip-detectada>"}` como JSON.

**Android:**
- Dependencia nueva: `mobile_scanner`; permiso `CAMERA` en
  `AndroidManifest.xml` (primera vez que la app usa la cámara del
  celular, hasta ahora solo mostraba cámaras remotas).
- Botón "Escanear código QR" en `LoginScreen` → pantalla nueva con
  `MobileScanner`; al decodificar un JSON válido con `"ip"`, vuelve al
  login y completa el campo IP.
- **Ícono** ("QR"): cuadrado con solo las 4 esquinas dibujadas (estilo
  visor de escáner), línea fina.
- **Animación detallada:**
  1. Pantalla de escaneo: marco cuadrado con las 4 esquinas, y una línea
     horizontal que sube y baja en bucle dentro del marco
     (`TweenAnimationBuilder` rebotando 0→1→0), color `AppColors.acento`.
  2. Al detectar un QR válido: las 4 esquinas destellan en verde (~300ms),
     la línea de escaneo desaparece, y hay un pequeño "pop" de escala del
     marco completo antes de volver al login.
  3. De vuelta en el login: el campo IP se completa letra por letra
     (efecto máquina de escribir, ~400ms en total) en vez de aparecer de
     golpe.

## Qué queda a criterio del que construye

Duraciones y curvas exactas donde no se especificaron, el texto exacto de
los mensajes de error de voz/QR/simulacro, el orden de los campos en la
pantalla de simulación — se deciden al construir y se muestran para
aprobación, no se vuelve a preguntar por cada detalle.
