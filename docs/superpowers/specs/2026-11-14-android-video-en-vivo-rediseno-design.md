# Rediseño app Android CAM: video en vivo, ícono, animaciones

## Intención y por qué

La app de Android (v1: solo estado de cámaras) pasa a ser una demo pulida
para presentar ante un jurado. Necesita verse como un producto terminado,
no un prototipo: ícono correcto, misma identidad visual que el programa de
escritorio, animaciones de apertura y login, y lo más importante — poder
ver la imagen real de cada cámara, no solo su estado.

## Goals

- Video casi en vivo (5-10 cuadros/seg) de cada cámara, al tocarla desde la
  lista.
- Ícono de la app correcto: el ojo con halo doble ya diseñado para
  escritorio (`icono_cam_android_foreground.png` / `icono_cam_1024.png`),
  como ícono adaptativo (Android 8+) y legacy.
- Paleta igual a la del programa de escritorio (fondo `#12151d`, paneles
  `#171b24`, acento turquesa `#36d6c9`) en vez de los colores actuales de
  la app, que son parecidos pero no iguales.
- Animación de apertura (splash con el ojo) y una transición animada de
  login → centro de monitoreo, en vez del salto brusco actual.
- Pulido general de las pantallas existentes (spacing, pequeñas
  animaciones de entrada/estado) sin reescribirlas desde cero.

## Non-goals (esta ronda)

- Notificaciones push.
- Mostrar fotos de evidencia en la app.
- Grilla de varias cámaras en vivo a la vez (una cámara en pantalla
  completa por vez).
- Audio.
- Endurecer la API para internet pública (sigue siendo solo LAN, como hoy).

## Anti-goals

- Romper la captura de cámaras o la detección de sabotaje del programa de
  escritorio.
- Meter ffmpeg, HLS o WebRTC.
- Agregar paquetes de Flutter nuevos/pesados (ya tuvimos dolores de disco
  y de Gradle en esta sesión con el toolchain de Android).

## Constraints

- Escritorio: Python/PySide6/OpenCV. No bloquear el hilo de la UI de Qt,
  no agregar locks ni complejidad nueva a `CamaraThread`.
- Celular: mismo proyecto Flutter, mismas dependencias de hoy (`http`,
  `shared_preferences`) — sin paquetes nuevos.
- La PC de desarrollo tiene poco espacio en disco: evitar descargas o
  toolchains nuevos.
- No tocar la lógica MVC de monitoreo/alarmas del escritorio — solo se
  agrega un método de lectura en `CamaraThread` y un endpoint de solo
  lectura en la API, igual que `estado_camaras()`/`resumen()` ya existentes.

## Approaches consideradas

1. **Foto que se repite (polling)** — el celular pide una foto nueva cada
   ~1s. Rechazada: se ve como una sucesión de fotos, no como video.
2. **Streaming tipo MJPEG sobre la API ya autenticada con JWT, reusando
   los frames que la cámara ya genera para la detección de sabotaje —
   ELEGIDA.** Se ve realmente en vivo, esfuerzo moderado, no toca la
   arquitectura del escritorio.
3. **Video real (ffmpeg/HLS/WebRTC)** — rechazada: mucha infraestructura
   nueva y riesgo de que algo falle justo antes de la demo.

## Cómo se construye (decidido)

### Escritorio

- `CamaraThread.obtener_ultimo_jpeg()` nuevo en `camera_service.py`:
  codifica `self._ultimo_frame` a JPEG bajo demanda (mismo patrón que
  `capturar_snapshot()`, sin locks nuevos — la reasignación de
  `_ultimo_frame` ya es atómica y se lee así en otros lados del código).
- Endpoint nuevo en `api_service.py`:
  `GET /camaras/{zona}/stream.mjpg`, protegido con el mismo
  `Authorization: Bearer <token>` que el resto de la API. Devuelve un
  `StreamingResponse` `multipart/x-mixed-replace` que va entregando el
  último JPEG de `monitoreo_controller.hilos_camara[zona]` a ~8 fps.
  Si la cámara no existe o no arrancó: 404/503, igual que los demás
  endpoints.
- No se agrega limpieza fina de conexión al desconectarse el celular (es
  una demo de un único usuario, no un servidor público) — riesgo
  aceptado, documentado acá para no sorprender después.

### Celular (Flutter)

- Paleta: archivo chico de constantes de color igual a las del
  escritorio, reemplazando los colores sueltos actuales en las pantallas.
- Ícono: se regeneran los `ic_launcher.png` de las 5 densidades a partir
  de `icono_cam_1024.png`, más el ícono adaptativo (Android 8+) usando
  `icono_cam_android_foreground.png` como capa de frente sobre un fondo
  sólido del mismo tono oscuro del ícono de escritorio.
- Pantalla nueva `LiveCameraScreen`: recibe la cámara tocada, reproduce el
  streaming a pantalla completa con un widget MJPEG hecho a mano (sin
  paquete nuevo: `http.Client().send()` + separar los cuadros por el
  boundary del multipart), con reintento simple si se corta.
  Tocar una cámara "sin señal" no navega (o avisa que no hay señal) en vez
  de abrir un stream vacío.
- Animaciones: splash de apertura con el ojo (escala + fade, ~1s) antes de
  la pantalla de login/arranque; transición de login → centro de
  monitoreo con `PageRouteBuilder` (fade + slide), en vez del salto
  directo actual. Pulido menor: pequeña animación de entrada en la lista
  de cámaras y en el punto de estado de sabotaje/alarma. Todo con
  animaciones implícitas de Flutter (`TweenAnimationBuilder`/
  `AnimatedOpacity`/`AnimatedScale`), sin `AnimationController` a medida.

## Qué queda a criterio del que construye

Duraciones y curvas exactas de las animaciones, tono exacto del fondo del
ícono adaptativo, espaciados finos — se deciden al construir y se muestran
para aprobación, no se vuelve a preguntar por cada detalle.
