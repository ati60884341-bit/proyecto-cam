# Rediseño app Android CAM: video en vivo, ícono, animaciones — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar a la app Android de CAM video en vivo real por cámara, el ícono correcto (ojo con halo doble), la misma paleta que el escritorio, y animaciones de apertura/login — sin tocar la lógica MVC del escritorio.

**Architecture:** El escritorio agrega un método de lectura a `CamaraThread` y un endpoint de streaming de solo lectura a la API ya existente (misma autenticación JWT), que entrega los JPEG que la cámara ya genera como un multipart `multipart/x-mixed-replace`. La app Flutter agrega un parser de ese formato, un widget de video, una pantalla de cámara en vivo, un tema compartido, el ícono real y dos animaciones (splash, transición de login).

**Tech Stack:** Python/FastAPI/OpenCV (escritorio), Flutter/Dart con `http` y `shared_preferences` (celular, sin paquetes nuevos).

**Spec:** [docs/superpowers/specs/2026-11-14-android-video-en-vivo-rediseno-design.md](../specs/2026-11-14-android-video-en-vivo-rediseno-design.md)

## Global Constraints

- No se toca la lógica MVC de monitoreo/alarmas del escritorio: solo un método de lectura nuevo en `CamaraThread` y un endpoint de solo lectura en la API.
- Sin paquetes Flutter nuevos — solo `http` y `shared_preferences`, ya presentes.
- Sin ffmpeg, HLS ni WebRTC.
- No bloquear el hilo de Qt; no agregar locks nuevos a `CamaraThread`.
- Evitar descargas o toolchains nuevos (poco espacio en disco en la máquina de desarrollo).
- Animaciones con widgets implícitos de Flutter (`AnimatedScale`, `AnimatedOpacity`, `TweenAnimationBuilder`, `PageRouteBuilder`), sin `AnimationController` a medida.

## Review Focus

- Se cierra la pantalla de cámara en vivo (botón atrás) mientras la conexión http sigue abierta → no debe llamar `setState` tras desmontar el widget ni dejar la conexión abierta. (Task 7)
- Una cámara nunca transmitió un cuadro, o se cae mientras se la mira en vivo → no debe quedar el loader girando para siempre, tiene que avisar. (Task 7)
- Una sola lectura del socket trae dos o más cuadros completos juntos → el parser debe entregarlos todos, no solo el primero. (Task 6)
- Un cuadro llega partido a la mitad (header o cuerpo JPEG) entre dos lecturas del socket → el parser debe esperar el resto de los bytes, no romperse. (Task 6)
- El token quedó inválido al abrir el stream (pasa si se reinicia el programa de escritorio: genera un secreto JWT nuevo en cada arranque) → debe avisar "sesión vencida" en vez de reintentar para siempre contra un 401. (Task 7)

---

### Task 1: `CamaraThread.obtener_ultimo_jpeg()`

**Files:**
- Modify: `app/services/camera_service.py` (agregar método cerca de `capturar_snapshot`, ~línea 562)
- Test: Create `tests/test_camara_jpeg.py` (script standalone, mismo estilo que `tests/test_sabotaje.py`)

**Interfaces:**
- Produces: `CamaraThread.obtener_ultimo_jpeg(self) -> bytes | None`

- [ ] **Step 1: Escribir el test que falla**

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from app.services.camera_service import CamaraThread

hilo = CamaraThread(1, "w", "w", "USB", "0")
assert hilo.obtener_ultimo_jpeg() is None, "sin frame todavia, debe dar None"

hilo._ultimo_frame = np.zeros((480, 640, 3), np.uint8)
jpg = hilo.obtener_ultimo_jpeg()
assert isinstance(jpg, bytes) and jpg[:2] == b"\xff\xd8", "debe ser un JPEG valido"
import cv2
decodificado = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
assert decodificado.shape == (480, 640, 3)
print("OK: obtener_ultimo_jpeg")
```

- [ ] **Step 2: Correr y confirmar que falla**

Run: `python tests/test_camara_jpeg.py`
Expected: `AttributeError` — el método no existe.

- [ ] **Step 3: Implementar `obtener_ultimo_jpeg` en `app/services/camera_service.py`**

Mismo patrón que `capturar_snapshot` + la codificación ya usada en `_transmitir` (línea 553): `cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, CALIDAD_JPEG_BUFFER])`, devolviendo `None` si `self._ultimo_frame` es `None` o si la codificación falla, y `.tobytes()` del resultado si no.

- [ ] **Step 4: Correr y confirmar que pasa**

Run: `python tests/test_camara_jpeg.py`
Expected: imprime `OK: obtener_ultimo_jpeg`, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add app/services/camera_service.py tests/test_camara_jpeg.py
git commit -m "feat: agrega CamaraThread.obtener_ultimo_jpeg para el streaming de Android"
```

---

### Task 2: Endpoint `GET /camaras/{zona}/stream.mjpg`

**Files:**
- Modify: `app/services/api_service.py`
- Test: Modify `tests/test_api_service.py`

**Interfaces:**
- Consumes: `CamaraThread.obtener_ultimo_jpeg() -> bytes | None` (Task 1); `_monitoreo_controller.hilos_camara: dict[str, CamaraThread]` (ya existe en `MonitoreoController`)
- Produces: `GET /camaras/{zona}/stream.mjpg` → 200 `multipart/x-mixed-replace; boundary=cuadro` si la zona existe y hay token válido; 404 si la zona no existe; 503 si el Centro de Monitoreo no arrancó; 401 si falta o es inválido el token (vía `_validar_token`, ya existente)

- [ ] **Step 1: Escribir las aserciones que fallan**

Agregar a `tests/test_api_service.py`, antes de `os._exit(0)`:

```python
r = requests.get(f"{BASE}/camaras/Cam-Ingreso-01/stream.mjpg", headers=cabecera, stream=True, timeout=5)
assert r.status_code == 200, r.text
assert r.headers["content-type"].startswith("multipart/x-mixed-replace")
primer_cuadro = next(r.iter_content(chunk_size=4096))
assert b"\xff\xd8" in primer_cuadro
r.close()

r = requests.get(f"{BASE}/camaras/Zona-Que-No-Existe/stream.mjpg", headers=cabecera, timeout=3)
assert r.status_code == 404, r.text
```

Y agregar a `_MonitoreoFalso` (antes de `iniciar_api(...)`):

```python
class _HiloFalso:
    def obtener_ultimo_jpeg(self):
        import cv2, numpy as np
        return cv2.imencode(".jpg", np.zeros((4, 4, 3), np.uint8))[1].tobytes()

class _MonitoreoFalso:
    _alarma_sonando = False
    hilos_camara = {"Cam-Ingreso-01": _HiloFalso()}
    ...
```

- [ ] **Step 2: Correr y confirmar que falla**

Run: `python tests/test_api_service.py`
Expected: 404 (ruta no existe) en la primera aserción nueva.

- [ ] **Step 3: Implementar el endpoint en `app/services/api_service.py`**

Agregar `from fastapi.responses import StreamingResponse` y la constante `INTERVALO_STREAM_SEG = 0.12` (~8 fps), y el endpoint:

```python
@app.get("/camaras/{zona}/stream.mjpg")
def stream_camara(zona: str, authorization: str = Header(default=None)):
    _validar_token(authorization)
    if _monitoreo_controller is None:
        raise HTTPException(status_code=503, detail="El Centro de Monitoreo todavia no arranco.")
    hilo = _monitoreo_controller.hilos_camara.get(zona)
    if hilo is None:
        raise HTTPException(status_code=404, detail="Camara no encontrada.")

    def generar_cuadros():
        while True:
            jpg = hilo.obtener_ultimo_jpeg()
            if jpg:
                yield (b"--cuadro\r\nContent-Type: image/jpeg\r\nContent-Length: "
                       + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
            time.sleep(INTERVALO_STREAM_SEG)

    return StreamingResponse(generar_cuadros(), media_type="multipart/x-mixed-replace; boundary=cuadro")
```

No se agrega limpieza de conexión al desconectarse el celular (riesgo aceptado, ya documentado en el spec).

- [ ] **Step 4: Correr y confirmar que pasa**

Run: `python tests/test_api_service.py`
Expected: imprime `OK: API (login, camaras, incidencias, resumen) funciona de punta a punta`, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add app/services/api_service.py tests/test_api_service.py
git commit -m "feat: agrega streaming MJPEG por camara a la API de Android"
```

---

### Task 3: Paleta compartida (`AppColors`)

**Files:**
- Create: `android_app/lib/theme.dart`

**Interfaces:**
- Produces: `class AppColors` con `static const Color fondo = Color(0xFF12151D)`, `panel = Color(0xFF171B24)`, `borde = Color(0xFF2A303C)`, `texto = Color(0xFFE7E9EE)`, `textoMuted = Color(0xFF9AA6B3)`, `acento = Color(0xFF36D6C9)`, `error = Color(0xFFFF8A8A)`

Sin ciclo rojo/verde posible (son constantes, no lógica); se verifica con análisis estático.

- [ ] **Step 1: Crear `android_app/lib/theme.dart`** con la clase `AppColors` y los 7 valores de arriba, exactos.

- [ ] **Step 2: Verificar**

Run: `cd android_app && flutter analyze lib/theme.dart`
Expected: `No issues found!`

- [ ] **Step 3: Commit**

```bash
git add android_app/lib/theme.dart
git commit -m "feat: agrega paleta de colores compartida con el escritorio"
```

---

### Task 4: Ícono real de la app (adaptativo + legacy)

**Files:**
- Create (binarios generados): `android_app/android/app/src/main/res/mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher.png` (reemplazan los actuales)
- Create: `android_app/android/app/src/main/res/mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher_foreground.png`
- Create: `android_app/android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml`
- Modify/Create: `android_app/android/app/src/main/res/values/colors.xml`

**Interfaces:** ninguna (solo assets).

- [ ] **Step 1: Escribir y correr un script de una vez** (en el scratchpad, no se comitea) con PIL:
  - `icono_cam_1024.png` → `ic_launcher.png` en 48/72/96/144/192 px (mdpi/hdpi/xhdpi/xxhdpi/xxxhdpi), `Image.LANCZOS`.
  - `icono_cam_android_foreground.png` (mantiene transparencia) → `ic_launcher_foreground.png` en 108/162/216/324/432 px, mismas densidades.

- [ ] **Step 2: Crear `mipmap-anydpi-v26/ic_launcher.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/ic_launcher_background"/>
    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
</adaptive-icon>
```

- [ ] **Step 3: Agregar en `values/colors.xml`** (crearlo si no existe): `<color name="ic_launcher_background">#12151D</color>`

- [ ] **Step 4: Verificar**

Run: un script corto que abra cada uno de los 10 PNG generados con PIL y confirme tamaño de archivo > 0 y dimensiones exactas esperadas.
Expected: los 10 archivos existen con las dimensiones correctas.

- [ ] **Step 5: Commit**

```bash
git add android_app/android/app/src/main/res
git commit -m "feat: ícono real de la app (ojo con halo doble), adaptativo y legacy"
```

---

### Task 5: `ApiClient` — URI y cabeceras del streaming

**Files:**
- Modify: `android_app/lib/api_client.dart` (agregar después del getter `_cabeceras`, ~línea 115)
- Test: Create `android_app/test/api_client_test.dart`

**Interfaces:**
- Produces: `ApiClient.streamUri(String zona) -> Uri`; `ApiClient.authHeaders -> Map<String, String>` (getter)

- [ ] **Step 1: Escribir el test que falla**

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:cam_app/api_client.dart';

void main() {
  test('streamUri arma la url correcta y authHeaders trae el Bearer', () {
    final api = ApiClient()..ip = '192.168.1.5'..token = 'abc';
    expect(api.streamUri('Cam-1').toString(), 'http://192.168.1.5:8765/camaras/Cam-1/stream.mjpg');
    expect(api.authHeaders['Authorization'], 'Bearer abc');
  });
}
```

- [ ] **Step 2: Correr y confirmar que falla**

Run: `cd android_app && flutter test test/api_client_test.dart`
Expected: error de compilación, `streamUri`/`authHeaders` no existen.

- [ ] **Step 3: Implementar en `android_app/lib/api_client.dart`**

```dart
Uri streamUri(String zona) => _uri('/camaras/$zona/stream.mjpg');
Map<String, String> get authHeaders => _cabeceras;
```

- [ ] **Step 4: Correr y confirmar que pasa**

Run: `cd android_app && flutter test test/api_client_test.dart`
Expected: `All tests passed!`

- [ ] **Step 5: Commit**

```bash
git add android_app/lib/api_client.dart android_app/test/api_client_test.dart
git commit -m "feat: ApiClient arma la url y cabeceras del streaming de camara"
```

---

### Task 6: Parser del formato MJPEG (`AnalizadorMjpeg`)

**Files:**
- Create: `android_app/lib/widgets/mjpeg_parser.dart`
- Test: Create `android_app/test/mjpeg_parser_test.dart`

**Interfaces:**
- Produces: `class AnalizadorMjpeg { List<Uint8List> agregarBytes(List<int> datos); }`

- [ ] **Step 1: Escribir los tests que fallan**

```dart
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:cam_app/widgets/mjpeg_parser.dart';

List<int> _cuadro(List<int> datos) =>
    utf8.encode('--cuadro\r\nContent-Type: image/jpeg\r\nContent-Length: ${datos.length}\r\n\r\n') + datos + utf8.encode('\r\n');

void main() {
  test('un cuadro completo en un solo bloque', () {
    final a = AnalizadorMjpeg();
    final r = a.agregarBytes(_cuadro([1, 2, 3, 4]));
    expect(r, [Uint8List.fromList([1, 2, 3, 4])]);
  });

  test('dos cuadros completos llegan juntos', () {
    final a = AnalizadorMjpeg();
    final r = a.agregarBytes([..._cuadro([1, 2]), ..._cuadro([3, 4, 5])]);
    expect(r, [Uint8List.fromList([1, 2]), Uint8List.fromList([3, 4, 5])]);
  });

  test('un cuadro llega partido entre dos llamadas', () {
    final a = AnalizadorMjpeg();
    final completo = _cuadro([9, 9, 9]);
    final mitad = completo.length ~/ 2;
    expect(a.agregarBytes(completo.sublist(0, mitad)), []);
    expect(a.agregarBytes(completo.sublist(mitad)), [Uint8List.fromList([9, 9, 9])]);
  });
}
```

- [ ] **Step 2: Correr y confirmar que falla**

Run: `cd android_app && flutter test test/mjpeg_parser_test.dart`
Expected: error de compilación, `AnalizadorMjpeg` no existe.

- [ ] **Step 3: Implementar `AnalizadorMjpeg` en `android_app/lib/widgets/mjpeg_parser.dart`**

```dart
import 'dart:convert';
import 'dart:typed_data';

class AnalizadorMjpeg {
  final List<int> _buffer = [];

  List<Uint8List> agregarBytes(List<int> datos) {
    _buffer.addAll(datos);
    final cuadros = <Uint8List>[];
    while (true) {
      final finHeader = _buscar(_buffer, utf8.encode('\r\n\r\n'));
      if (finHeader == -1) break;
      final textoHeader = utf8.decode(_buffer.sublist(0, finHeader), allowMalformed: true);
      final match = RegExp(r'Content-Length:\s*(\d+)').firstMatch(textoHeader);
      if (match == null) {
        _buffer.removeRange(0, finHeader + 4);
        continue;
      }
      final longitud = int.parse(match.group(1)!);
      final inicioCuadro = finHeader + 4;
      if (_buffer.length < inicioCuadro + longitud) break;
      cuadros.add(Uint8List.fromList(_buffer.sublist(inicioCuadro, inicioCuadro + longitud)));
      _buffer.removeRange(0, inicioCuadro + longitud);
    }
    return cuadros;
  }

  int _buscar(List<int> lista, List<int> patron) {
    for (var i = 0; i <= lista.length - patron.length; i++) {
      var iguales = true;
      for (var j = 0; j < patron.length; j++) {
        if (lista[i + j] != patron[j]) {
          iguales = false;
          break;
        }
      }
      if (iguales) return i;
    }
    return -1;
  }
}
```

- [ ] **Step 4: Correr y confirmar que pasa**

Run: `cd android_app && flutter test test/mjpeg_parser_test.dart`
Expected: `All tests passed!` (3 tests)

- [ ] **Step 5: Commit**

```bash
git add android_app/lib/widgets/mjpeg_parser.dart android_app/test/mjpeg_parser_test.dart
git commit -m "feat: parser del stream MJPEG de camaras"
```

---

### Task 7: Widget de video en vivo (`MjpegView`)

**Files:**
- Create: `android_app/lib/widgets/mjpeg_view.dart`

**Interfaces:**
- Consumes: `AnalizadorMjpeg.agregarBytes` (Task 6)
- Produces: `class MjpegView extends StatefulWidget { final Uri uri; final Map<String, String> headers; const MjpegView({super.key, required this.uri, required this.headers}); }`

Sin test unitario (requiere red real); se verifica con `flutter analyze` y luego, en el dispositivo, por el usuario.

- [ ] **Step 1: Implementar `_MjpegViewState`**

Campos: `http.Client? _client`, `StreamSubscription<List<int>>? _sub`, `final _analizador = AnalizadorMjpeg()`, `Uint8List? _ultimoCuadro`, `String? _error`, `Timer? _temporizadorInactividad`.

`_conectar()`: crea un `http.Client`, envía `http.Request('GET', widget.uri)..headers.addAll(widget.headers)` con `_client!.send(...)`. Si `response.statusCode != 200`: setea `_error` con un mensaje según el código (401 → `'Sesion vencida, volve a iniciar sesion.'`; 404 → `'Camara no encontrada.'`; otro → `'No se pudo conectar (${response.statusCode}).'`) y **no reintenta**. Si es 200: escucha `response.stream`, por cada `chunk` llama a `_analizador.agregarBytes(chunk)`; por cada cuadro devuelto, si `mounted`, `setState` actualizando `_ultimoCuadro` y reinicia `_temporizadorInactividad` (`Timer(const Duration(seconds: 5), () { if (mounted) setState(() => _error = 'La camara dejo de responder.'); })`). Si el stream corta con error (no fue un 401/404 explícito) y `mounted`, programa `Future.delayed(const Duration(seconds: 2), _conectar)`.

`dispose()`: cancela `_sub`, cancela `_temporizadorInactividad`, cierra `_client`.

`build()`: si `_ultimoCuadro != null`, `Image.memory(_ultimoCuadro!, gaplessPlayback: true, fit: BoxFit.contain)` (con el texto de `_error` superpuesto abajo si también hay uno); si no y `_error != null`, texto centrado con el error; si no, `CircularProgressIndicator` centrado.

- [ ] **Step 2: Verificar**

Run: `cd android_app && flutter analyze lib/widgets/mjpeg_view.dart`
Expected: `No issues found!`

- [ ] **Step 3: Commit**

```bash
git add android_app/lib/widgets/mjpeg_view.dart
git commit -m "feat: widget de video en vivo MJPEG"
```

---

### Task 8: Pantalla de cámara en vivo

**Files:**
- Create: `android_app/lib/screens/live_camera_screen.dart`

**Interfaces:**
- Consumes: `MjpegView` (Task 7); `ApiClient.streamUri`/`authHeaders` (Task 5); `Camara` (ya existe en `api_client.dart`)
- Produces: `class LiveCameraScreen extends StatelessWidget { final ApiClient api; final Camara camara; const LiveCameraScreen({super.key, required this.api, required this.camara}); }`

- [ ] **Step 1: Implementar** — `Scaffold(backgroundColor: Colors.black, appBar: AppBar(backgroundColor: AppColors.panel, title: Text(camara.nombre)), body: Center(child: MjpegView(uri: api.streamUri(camara.zona), headers: api.authHeaders)))`.

- [ ] **Step 2: Verificar**

Run: `cd android_app && flutter analyze lib/screens/live_camera_screen.dart`
Expected: `No issues found!`

- [ ] **Step 3: Commit**

```bash
git add android_app/lib/screens/live_camera_screen.dart
git commit -m "feat: pantalla de camara en vivo"
```

---

### Task 9: `HomeScreen` — tema, navegación a video en vivo, animación de entrada

**Files:**
- Modify: `android_app/lib/screens/home_screen.dart`
- Modify: `android_app/lib/screens/incidencias_screen.dart`

**Interfaces:**
- Consumes: `AppColors` (Task 3); `LiveCameraScreen` (Task 8)

- [ ] **Step 1:** en `_filaCamara`, envolver el `Container` en un `GestureDetector`/`InkWell` con `onTap`: si `!c.enLinea`, `ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Camara sin senal.')))`; si no, `Navigator.of(context).push(MaterialPageRoute(builder: (_) => LiveCameraScreen(api: widget.api, camara: c)))`.

- [ ] **Step 2:** reemplazar los colores literales por `AppColors` en `home_screen.dart` e `incidencias_screen.dart` (`0xFF0a0f1a`→`fondo`, `0xFF111a2a`→`panel`, `0xFF9aa6b3`→`textoMuted`, `0xFFff8a8a`→`error`, `0xFF36d6a0`→`acento` cuando indica "en línea"/ok).

- [ ] **Step 3:** envolver cada item de `..._camaras.map(_filaCamara)` con `TweenAnimationBuilder<double>(tween: Tween(begin: 0, end: 1), duration: Duration(milliseconds: 300 + i * 60), curve: Curves.easeOut, builder: (_, v, child) => Opacity(opacity: v, child: Transform.translate(offset: Offset(0, (1 - v) * 12), child: child)), child: ...)` (usar el índice de la lista, por ejemplo con `List.generate` o `.asMap().entries.map`).

- [ ] **Step 4: Verificar**

Run: `cd android_app && flutter analyze && flutter test`
Expected: `No issues found!` y todos los tests existentes siguen pasando.

- [ ] **Step 5: Commit**

```bash
git add android_app/lib/screens/home_screen.dart android_app/lib/screens/incidencias_screen.dart
git commit -m "feat: navegacion a camara en vivo, paleta compartida y animacion de entrada en Inicio"
```

---

### Task 10: `LoginScreen` — tema y transición animada

**Files:**
- Modify: `android_app/lib/screens/login_screen.dart`

**Interfaces:**
- Consumes: `AppColors` (Task 3)

- [ ] **Step 1:** reemplazar los colores literales por `AppColors`.

- [ ] **Step 2:** reemplazar la línea 38 (`Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => HomeScreen(api: widget.api)));`) por:

```dart
Navigator.of(context).pushReplacement(PageRouteBuilder(
  transitionDuration: const Duration(milliseconds: 450),
  pageBuilder: (_, __, ___) => HomeScreen(api: widget.api),
  transitionsBuilder: (_, animation, __, child) {
    final curva = CurvedAnimation(parent: animation, curve: Curves.easeOutCubic);
    return FadeTransition(
      opacity: curva,
      child: SlideTransition(
        position: Tween<Offset>(begin: const Offset(0, 0.06), end: Offset.zero).animate(curva),
        child: child,
      ),
    );
  },
));
```

- [ ] **Step 3: Verificar**

Run: `cd android_app && flutter analyze && flutter test`
Expected: `No issues found!`, tests existentes en verde.

- [ ] **Step 4: Commit**

```bash
git add android_app/lib/screens/login_screen.dart
git commit -m "feat: paleta compartida y transicion animada de login a Inicio"
```

---

### Task 11: Splash de apertura con el ojo

**Files:**
- Create: `android_app/lib/screens/splash_screen.dart`
- Modify: `android_app/lib/main.dart`
- Modify: `android_app/pubspec.yaml`
- Create (copia): `android_app/assets/icono_ojo.png` (copia de `app/recursos/imagenes/icono_cam_android_foreground.png`)
- Modify: `android_app/test/widget_test.dart`

**Interfaces:**
- Produces: `class SplashScreen extends StatefulWidget { const SplashScreen({super.key}); }`
- Consumes: `AppColors` (Task 3)

- [ ] **Step 1:** copiar el PNG y agregar en `pubspec.yaml`, dentro de `flutter:`, después de `uses-material-design: true`:

```yaml
  assets:
    - assets/icono_ojo.png
```

- [ ] **Step 2: Implementar `SplashScreen`**

`Scaffold(backgroundColor: AppColors.fondo, body: Center(child: <imagen que escala 0.85→1.0 en 900ms con Curves.easeOutBack y hace fade de opacidad 0→1 en 700ms, disparado en el primer frame con WidgetsBinding.instance.addPostFrameCallback>))`, envolviendo `Image.asset('assets/icono_ojo.png', width: 140)` con `AnimatedScale` + `AnimatedOpacity` (ambas controladas por un único `bool _visible` que pasa a `true` en ese callback).

- [ ] **Step 3:** en `main.dart`, modificar `_ArranqueState.initState` para que espere lo que tarde más entre cargar la sesión y un mínimo de tiempo, y usar `SplashScreen` como placeholder:

```dart
@override
void initState() {
  super.initState();
  Future.wait([
    _api.cargarSesionGuardada(),
    Future.delayed(const Duration(milliseconds: 1100)),
  ]).then((_) => setState(() => _listo = true));
}
```

Y reemplazar el `return const Scaffold(... CircularProgressIndicator ...)` del `if (!_listo)` por `return const SplashScreen();`.

- [ ] **Step 4:** en `test/widget_test.dart`, después de `pumpWidget`, reemplazar el único `pumpAndSettle()` por:

```dart
await tester.pump(const Duration(milliseconds: 1200));
await tester.pumpAndSettle();
```

antes del `expect` existente.

- [ ] **Step 5: Correr y confirmar que pasa**

Run: `cd android_app && flutter test`
Expected: `All tests passed!`

- [ ] **Step 6: Verificar análisis estático**

Run: `cd android_app && flutter analyze`
Expected: `No issues found!`

- [ ] **Step 7: Commit**

```bash
git add android_app/lib/screens/splash_screen.dart android_app/lib/main.dart android_app/pubspec.yaml android_app/assets/icono_ojo.png android_app/test/widget_test.dart
git commit -m "feat: splash animado del ojo al abrir la app"
```

---

### Task 12: Compilar el APK y entregarlo

**Files:** ninguno nuevo.

- [ ] **Step 1:** `cd android_app && flutter analyze` (proyecto completo) — debe salir limpio.
- [ ] **Step 2:** `cd android_app && flutter test` (proyecto completo) — todos en verde.
- [ ] **Step 3:** `cd android_app && flutter build apk --debug`.
- [ ] **Step 4:** Verificar que `android_app/build/app/outputs/flutter-apk/app-debug.apk` existe y pesa más de 0 bytes.
- [ ] **Step 5:** Entregar el APK al usuario (SendUserFile) explicando qué cambió: ícono real, mismos colores que el escritorio, animación al abrir y al entrar, y que tocar una cámara en línea abre su video en vivo.
- [ ] **Step 6:** No commitear el build (ya está fuera de `android_app/build/` vía `.gitignore` estándar de Flutter).

---

## Self-Review

**1. Cobertura del spec:** video en vivo (Tasks 1-2, 5-8), ícono (Task 4), paleta (Task 3, aplicada en 9-11), animación de apertura (Task 11), transición de login (Task 10), pulido de listas (Task 9), build y entrega (Task 12). Todo el spec tiene tarea.

**2. Pasos:** cada paso de test fija nombre/aserciones exactas; cada paso de código fija firma y archivo exactos, con cuerpo solo donde el algoritmo no es obvio (parser, generador del stream, transición, splash). Nada quedó en "TBD" o "manejar casos borde".

**3. Consistencia de tipos:** `ApiClient.streamUri`/`authHeaders` (Task 5) se usan igual en `MjpegView`/`LiveCameraScreen` (Tasks 7-8); `AnalizadorMjpeg.agregarBytes` (Task 6) se usa igual en `MjpegView` (Task 7); `AppColors` (Task 3) se usa igual en Tasks 9-11; `CamaraThread.obtener_ultimo_jpeg` (Task 1) se usa igual en el endpoint (Task 2).

**4. Review Focus:** los 5 puntos están cada uno cubierto por un test o un paso explícito (ver la lista, con la tarea entre paréntesis).

**5. Proporción:** el plan es más largo que el spec porque detalla 12 tareas chicas con su propio ciclo de test — pero cada bloque de código es una firma, un test o el único algoritmo no obvio de esa tarea (parser, generador MJPEG, transición de página, splash), no una transcripción completa de archivos existentes.
