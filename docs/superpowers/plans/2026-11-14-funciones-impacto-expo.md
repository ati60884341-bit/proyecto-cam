# Funciones de impacto para la expo-feria — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar cuatro funciones de impacto a la app Android de CAM — máquina del tiempo, comandos de voz, botón de simulación de incidente y login por QR — con íconos propios y animaciones detalladas, sin romper nada de lo ya construido.

**Architecture:** Cada función reusa infraestructura ya existente en vez de duplicarla: la máquina del tiempo expone el buffer de video que ya arma la evidencia de sabotaje; el simulacro reusa el pipeline real de sabotaje (evidencia firmada + alarma) con una bandera `es_simulacro`; el login por QR solo agrega un generador de QR y un lector en el celular; la voz es pura lógica en Android, sin tocar el escritorio.

**Tech Stack:** Python/FastAPI/OpenCV + `qrcode` (ya instalado) del lado del escritorio; Flutter/Dart + `speech_to_text` y `mobile_scanner` (paquetes nuevos, únicos permitidos esta ronda) del lado del celular.

**Spec:** [docs/superpowers/specs/2026-11-14-funciones-impacto-expo-design.md](../specs/2026-11-14-funciones-impacto-expo-design.md)

## Global Constraints

- Paquetes nuevos permitidos solo para estas 4 funciones: `speech_to_text`, `mobile_scanner` (Flutter). `qrcode` en Python ya está instalado y en `requirements.txt`.
- El simulacro reusa `CamaraThread._exportar_evidencia_sabotaje` (no se duplica el pipeline de evidencia/alarma).
- `Tipo="Simulacro"` se excluye de `incidencia_model.contar_hoy()` por defecto.
- El QR de login lleva únicamente `{"ip": "..."}` — nunca usuario ni clave.
- Animaciones con widgets implícitos de Flutter (`AnimatedOpacity`, `AnimatedRotation`, `AnimatedSlide`, `AnimatedContainer`, `TweenAnimationBuilder`), sin `AnimationController` a medida.
- Los 4 íconos nuevos son `CustomPainter` de línea fina en `AppColors.acento`, mismo lenguaje visual que `app/views/UI/iconos.py` — no íconos de Material por defecto.

## Review Focus

- Se pide simular un incidente en una zona que no existe o sin cámaras conectadas → debe dar 404 claro, no colgarse ni "simular" sobre nada. (Task 14)
- Un comando de voz pide una cámara fuera de rango (p. ej. "cámara 9" con solo 3 cámaras en la lista) → no debe crashear ni navegar a un índice inválido, debe avisar que no existe. (Task 10)
- Se escanea un código QR que no es de la app CAM (cualquier QR del mundo real) → no debe intentar nada con JSON inválido ni crashear, debe avisar "código no válido". (Task 20)
- El checklist de simulación nunca termina de confirmarse (el escritorio se cae a mitad de la demo) → no debe quedar esperando para siempre, cada paso sin confirmar pasa a "no confirmado" tras un tiempo. (Task 16)
- Se pide rebobinar una cámara que recién se conectó y el buffer todavía está vacío → el stream debe cerrarse de inmediato (cero cuadros), no quedar colgado esperando el primero que nunca llega. (Task 2)

---

## Feature A: Máquina del tiempo

### Task 1: `CamaraThread.obtener_buffer_jpeg_brillante()`

**Files:**
- Modify: `app/services/camera_service.py` (cerca de `obtener_ultimo_jpeg`)
- Test: Create `tests/test_rebobinar.py`

**Interfaces:**
- Produces: `CamaraThread.obtener_buffer_jpeg_brillante(self) -> list[bytes]`

- [ ] **Step 1: Escribir el test que falla**

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2
from app.services.camera_service import CamaraThread

hilo = CamaraThread(1, "w", "w", "USB", "0")
assert hilo.obtener_buffer_jpeg_brillante() == [], "sin buffer todavia, debe dar lista vacia"

oscuro = cv2.imencode(".jpg", np.full((10, 10, 3), 40, np.uint8))[1].tobytes()
hilo._buffer.append(oscuro)
hilo._buffer.append(oscuro)
cuadros = hilo.obtener_buffer_jpeg_brillante()
assert len(cuadros) == 2
decodificado = cv2.imdecode(np.frombuffer(cuadros[0], np.uint8), cv2.IMREAD_COLOR)
assert decodificado.mean() > 40 + 10, "debe salir mas claro, igual que obtener_ultimo_jpeg"
print("OK: obtener_buffer_jpeg_brillante")
```

- [ ] **Step 2: Correr y confirmar que falla**

Run: `python tests/test_rebobinar.py`
Expected: `AttributeError` — el método no existe.

- [ ] **Step 3: Implementar**

Decodifica cada entrada de `self._buffer` con `cv2.imdecode`, aplica el mismo
`cv2.convertScaleAbs(frame, alpha=BRILLO_EXTRA_ANDROID_ALPHA, beta=BRILLO_EXTRA_ANDROID_BETA)`
que ya usa `obtener_ultimo_jpeg`, y vuelve a codificar con
`CALIDAD_JPEG_BUFFER`. Devuelve `[]` si `self._buffer` está vacío (no hace
falta caso especial: un `for` sobre una deque vacía ya no itera nada).

- [ ] **Step 4: Correr y confirmar que pasa**

Run: `python tests/test_rebobinar.py`
Expected: imprime `OK: obtener_buffer_jpeg_brillante`, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add app/services/camera_service.py tests/test_rebobinar.py
git commit -m "feat: agrega CamaraThread.obtener_buffer_jpeg_brillante para la maquina del tiempo"
```

---

### Task 2: Endpoint `GET /camaras/{zona}/rewind.mjpg`

**Files:**
- Modify: `app/services/api_service.py`
- Test: Modify `tests/test_rebobinar.py`

**Interfaces:**
- Consumes: `CamaraThread.obtener_buffer_jpeg_brillante() -> list[bytes]` (Task 1)
- Produces: `GET /camaras/{zona}/rewind.mjpg` → 200 `multipart/x-mixed-replace; boundary=cuadro` que termina solo tras mandar todos los cuadros del buffer (0 si está vacío); 404/503/401 igual que `/stream.mjpg`

- [ ] **Step 1: Escribir las aserciones que fallan**

Agregar a `tests/test_api_service.py` (reusa `_HiloFalso`, agregarle
`obtener_buffer_jpeg_brillante` que devuelva 3 copias del mismo JPEG fijo):

```python
r = requests.get(f"{BASE}/camaras/Cam-Ingreso-01/rewind.mjpg", headers=cabecera, timeout=5)
assert r.status_code == 200, r.text
assert r.content.count(b"--cuadro\r\n") == 3, r.content.count(b"--cuadro\r\n")

r = requests.get(f"{BASE}/camaras/Zona-Que-No-Existe/rewind.mjpg", headers=cabecera, timeout=3)
assert r.status_code == 404, r.text
```

- [ ] **Step 2: Correr y confirmar que falla**

Run: `python -u tests/test_api_service.py`
Expected: 404 (ruta no existe) en la primera aserción nueva.

- [ ] **Step 3: Implementar el endpoint**

```python
@app.get("/camaras/{zona}/rewind.mjpg")
def rewind_camara(zona: str, authorization: str = Header(default=None)):
    _validar_token(authorization)
    if _monitoreo_controller is None:
        raise HTTPException(status_code=503, detail="El Centro de Monitoreo todavia no arranco.")
    hilo = _monitoreo_controller.hilos_camara.get(zona)
    if hilo is None:
        raise HTTPException(status_code=404, detail="Camara no encontrada.")

    def generar_repeticion():
        for jpg in hilo.obtener_buffer_jpeg_brillante():
            yield (b"--cuadro\r\nContent-Type: image/jpeg\r\nContent-Length: "
                   + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
            time.sleep(INTERVALO_STREAM_SEG)

    return StreamingResponse(generar_repeticion(), media_type="multipart/x-mixed-replace; boundary=cuadro")
```

A diferencia de `stream_camara`, el generador recorre la lista UNA sola vez
(`for`, no `while True`) — la respuesta termina sola al agotarse el buffer,
el Review Focus de buffer vacío queda cubierto porque un `for` sobre `[]`
no itera nada y la respuesta se cierra de inmediato con cero cuadros.

- [ ] **Step 4: Correr y confirmar que pasa**

Run: `python -u tests/test_api_service.py`
Expected: imprime `OK: API (login, camaras, incidencias, resumen) funciona de punta a punta`, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add app/services/api_service.py tests/test_api_service.py
git commit -m "feat: agrega endpoint de rebobinado (maquina del tiempo) a la API"
```

---

### Task 3: `MjpegView` admite reproducción finita

**Files:**
- Modify: `android_app/lib/widgets/mjpeg_view.dart`

**Interfaces:**
- Produces: `MjpegView` gana `final bool finito` (default `false`) y `final VoidCallback? onTerminado`

- [ ] **Step 1:** en `_MjpegViewState`, cuando `respuesta.stream` termina (`onDone`) sin que haya sido un 401/404 explícito: si `widget.finito` es `true`, en vez de `_reintentar()`, llamar a `widget.onTerminado?.call()` (si `mounted`) y no programar ningún reintento. Si `widget.finito` es `false`, el comportamiento sigue igual que hoy (reintenta).
- [ ] **Step 2: Verificar**

Run: `cd android_app && flutter analyze lib/widgets/mjpeg_view.dart`
Expected: solo el info preexistente de `material.dart`, cero errores/warnings nuevos.

- [ ] **Step 3: Commit**

```bash
git add android_app/lib/widgets/mjpeg_view.dart
git commit -m "feat: MjpegView admite reproduccion finita para la maquina del tiempo"
```

---

### Task 4: Ícono "reloj rebobinar"

**Files:**
- Create: `android_app/lib/widgets/icono_reloj_rebobinar.dart`

**Interfaces:**
- Produces: `class IconoRelojRebobinar extends StatelessWidget { final double tamano; final Color color; const IconoRelojRebobinar({super.key, this.tamano = 24, this.color = AppColors.acento}); }`

- [ ] **Step 1: Implementar** con `CustomPaint` + un `CustomPainter`: un círculo (contorno, sin relleno, trazo 1.6) con una manecilla corta hacia las 12 y otra más larga hacia las 4, y una flecha curva antihoraria alrededor del círculo (un arco de ~270° con una punta de flecha en el extremo) — mismo trazo fino de un solo color que el resto de los íconos del proyecto.
- [ ] **Step 2: Verificar**

Run: `cd android_app && flutter analyze lib/widgets/icono_reloj_rebobinar.dart`
Expected: solo el info preexistente.

- [ ] **Step 3: Commit**

```bash
git add android_app/lib/widgets/icono_reloj_rebobinar.dart
git commit -m "feat: icono de reloj/rebobinar para la maquina del tiempo"
```

---

### Task 5: Botón y animaciones de la máquina del tiempo en `LiveCameraScreen`

**Files:**
- Modify: `android_app/lib/screens/live_camera_screen.dart`

**Interfaces:**
- Consumes: `MjpegView(finito, onTerminado)` (Task 3), `IconoRelojRebobinar` (Task 4), `ApiClient.streamUri`/`authHeaders` (ya existentes — agregar `rewindUri(zona)` análogo a `streamUri` en `android_app/lib/api_client.dart` como parte de este task)

- [ ] **Step 1:** en `api_client.dart`, agregar `Uri rewindUri(String zona) => _uri('/camaras/$zona/rewind.mjpg');` junto a `streamUri`.
- [ ] **Step 2:** convertir `LiveCameraScreen` a `StatefulWidget` con un `bool _repitiendo = false` y un `Key` que cambia (`ValueKey(_repitiendo)`) para forzar que `MjpegView` se reconstruya al alternar entre vivo y repetición.
- [ ] **Step 3:** agregar un `FloatingActionButton` con `IconoRelojRebobinar`: al tocarlo, el ícono gira 360° antihorario en 500ms (`AnimatedRotation` con un `double _vueltas` que decrementa en 1.0 en cada toque) y `_repitiendo` pasa a `true`.
- [ ] **Step 4:** cuando `_repitiendo` es `true`: `MjpegView(uri: api.rewindUri(camara.zona), headers: api.authHeaders, finito: true, onTerminado: () => mostrar el boton "Volver a en vivo")`, con un `AnimatedSwitcher` (300ms) alternando entre el `MjpegView` en vivo y el de repetición, y una pastilla naranja (`Color(0xFFe0935a)`, el acento secundario que ya usa el escritorio) con el texto "⏪ Hace unos segundos" que entra con `AnimatedSlide` desde arriba mientras `_repitiendo` es `true`.
- [ ] **Step 5:** mientras repite, una `LinearProgressIndicator` indeterminada (sin `value`, color naranja) fina pegada abajo del video.
- [ ] **Step 6:** al terminar (`onTerminado`): mostrar un botón centrado "Volver a en vivo" (con ícono de ojo) superpuesto al último cuadro; al tocarlo, `_repitiendo = false` (dispara el `AnimatedSwitcher`/`AnimatedSlide` en reversa).
- [ ] **Step 7: Verificar**

Run: `cd android_app && flutter analyze && flutter test`
Expected: solo infos preexistentes, todos los tests en verde.

- [ ] **Step 8: Commit**

```bash
git add android_app/lib/screens/live_camera_screen.dart android_app/lib/api_client.dart
git commit -m "feat: boton y animaciones de la maquina del tiempo en la camara en vivo"
```

---

## Feature B: Comandos de voz

### Task 6: Dependencia y permiso

**Files:**
- Modify: `android_app/pubspec.yaml`
- Modify: `android_app/android/app/src/main/AndroidManifest.xml`

- [ ] **Step 1:** `cd android_app && flutter pub add speech_to_text`.
- [ ] **Step 2:** agregar `<uses-permission android:name="android.permission.RECORD_AUDIO" />` junto al `INTERNET` existente en `AndroidManifest.xml`.
- [ ] **Step 3: Verificar**

Run: `cd android_app && flutter pub get && flutter analyze`
Expected: resuelve sin error; solo infos preexistentes en el analyze.

- [ ] **Step 4: Commit**

```bash
git add android_app/pubspec.yaml android_app/pubspec.lock android_app/android/app/src/main/AndroidManifest.xml
git commit -m "feat: agrega speech_to_text y permiso de microfono"
```

---

### Task 7: Parser de comandos de voz (`interpretarComandoVoz`)

**Files:**
- Create: `android_app/lib/voice_commands.dart`
- Test: Create `android_app/test/voice_commands_test.dart`

**Interfaces:**
- Produces:
  ```dart
  sealed class ComandoVoz {}
  class AbrirCamaraPorIndice extends ComandoVoz { final int indice; AbrirCamaraPorIndice(this.indice); }
  class IrAIncidencias extends ComandoVoz {}
  class IrAInicio extends ComandoVoz {}
  class SimularIncidenteVoz extends ComandoVoz {}
  class CerrarSesionVoz extends ComandoVoz {}
  ComandoVoz? interpretarComandoVoz(String texto);
  ```

- [ ] **Step 1: Escribir los tests que fallan**

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:cam_app/voice_commands.dart';

void main() {
  test('camara N abre esa camara (indice base 0)', () {
    expect((interpretarComandoVoz('camara 1') as AbrirCamaraPorIndice).indice, 0);
    expect((interpretarComandoVoz('mostrar camara 2') as AbrirCamaraPorIndice).indice, 1);
    expect((interpretarComandoVoz('cámara 3') as AbrirCamaraPorIndice).indice, 2);
  });
  test('camara 0 no es una camara valida', () {
    expect(interpretarComandoVoz('camara 0'), isNull);
  });
  test('incidencias / inicio / simular / cerrar sesion', () {
    expect(interpretarComandoVoz('incidencias'), isA<IrAIncidencias>());
    expect(interpretarComandoVoz('inicio'), isA<IrAInicio>());
    expect(interpretarComandoVoz('resumen'), isA<IrAInicio>());
    expect(interpretarComandoVoz('simular incidente'), isA<SimularIncidenteVoz>());
    expect(interpretarComandoVoz('panico'), isA<SimularIncidenteVoz>());
    expect(interpretarComandoVoz('cerrar sesion'), isA<CerrarSesionVoz>());
  });
  test('frase sin sentido no matchea nada', () {
    expect(interpretarComandoVoz('que lindo dia hace hoy'), isNull);
  });
}
```

- [ ] **Step 2: Correr y confirmar que falla**

Run: `cd android_app && flutter test test/voice_commands_test.dart`
Expected: error de compilación, el archivo no existe.

- [ ] **Step 3: Implementar**

```dart
sealed class ComandoVoz {}
class AbrirCamaraPorIndice extends ComandoVoz { final int indice; AbrirCamaraPorIndice(this.indice); }
class IrAIncidencias extends ComandoVoz {}
class IrAInicio extends ComandoVoz {}
class SimularIncidenteVoz extends ComandoVoz {}
class CerrarSesionVoz extends ComandoVoz {}

String _normalizar(String s) => s
    .toLowerCase()
    .replaceAll('á', 'a').replaceAll('é', 'e').replaceAll('í', 'i')
    .replaceAll('ó', 'o').replaceAll('ú', 'u').replaceAll('ñ', 'n');

ComandoVoz? interpretarComandoVoz(String texto) {
  final t = _normalizar(texto);
  if (t.contains('simular incidente') || t.contains('panico') || t.contains('ayuda')) {
    return SimularIncidenteVoz();
  }
  if (t.contains('cerrar sesion')) return CerrarSesionVoz();
  if (t.contains('incidencia')) return IrAIncidencias();
  if (t.contains('inicio') || t.contains('resumen')) return IrAInicio();
  final match = RegExp(r'camara\s*(\d+)').firstMatch(t);
  if (match != null) {
    final n = int.parse(match.group(1)!);
    if (n >= 1) return AbrirCamaraPorIndice(n - 1);
  }
  return null;
}
```

- [ ] **Step 4: Correr y confirmar que pasa**

Run: `cd android_app && flutter test test/voice_commands_test.dart`
Expected: `All tests passed!` (4 tests)

- [ ] **Step 5: Commit**

```bash
git add android_app/lib/voice_commands.dart android_app/test/voice_commands_test.dart
git commit -m "feat: parser de comandos de voz"
```

---

### Task 8: Ícono "micrófono"

**Files:**
- Create: `android_app/lib/widgets/icono_microfono.dart`

**Interfaces:**
- Produces: `class IconoMicrofono extends StatelessWidget { final double tamano; final Color color; const IconoMicrofono({super.key, this.tamano = 28, this.color = AppColors.acento}); }`

- [ ] **Step 1: Implementar** con `CustomPaint`: cápsula redondeada vertical (el "micrófono"), un arco por debajo abriendo hacia los costados, un tallo vertical corto bajando del arco, y una línea horizontal de base — misma composición que el ícono `_microfono` del escritorio (`app/views/UI/iconos.py`), mismo trazo fino de un solo color.
- [ ] **Step 2: Verificar**

Run: `cd android_app && flutter analyze lib/widgets/icono_microfono.dart`
Expected: solo el info preexistente.

- [ ] **Step 3: Commit**

```bash
git add android_app/lib/widgets/icono_microfono.dart
git commit -m "feat: icono de microfono para comandos de voz"
```

---

### Task 9: Botón de voz con animaciones (`VoiceButton`)

**Files:**
- Create: `android_app/lib/widgets/voice_button.dart`

**Interfaces:**
- Consumes: `IconoMicrofono` (Task 8), `interpretarComandoVoz` (Task 7)
- Produces: `class VoiceButton extends StatefulWidget { final void Function(ComandoVoz) onComando; const VoiceButton({super.key, required this.onComando}); }`

- [ ] **Step 1:** usar `speech_to_text`: `GestureDetector` con `onLongPressStart` que inicia `SpeechToText().listen(...)` y `onLongPressEnd` que lo detiene (`stop()`), mostrando el resultado final (`result.finalResult`) a `interpretarComandoVoz`; si da un comando no nulo, llamar `widget.onComando(comando)`; si da `null`, mostrar el estado de "no reconocido".
- [ ] **Step 2:** animaciones, todas implícitas:
  - Reposo: `IconoMicrofono` quieto sobre un `Container` circular `AppColors.panel`.
  - Escuchando (mientras se mantiene presionado): 3 `AnimatedContainer`/`TweenAnimationBuilder` circulares concéntricos que escalan de 1.0 a 1.6 mientras se desvanecen de opacidad 0.5 a 0, reiniciando en bucle con offsets escalonados (`onEnd` reprogramando el próximo ciclo); el ícono pulsa escala 1.0↔1.15 con `AnimatedScale`.
  - Al soltar (procesando): los anillos colapsan a escala 0 con fundido en 300ms.
  - Comando reconocido: `AnimatedSwitcher` de 600ms muestra un ícono de tilde verde en vez del micrófono, después vuelve a reposo.
  - No reconocido: el botón completo hace un "shake" (`AnimatedContainer`/`Transform.translate` alternando offset horizontal +8/-8/0 en 3 pasos de ~130ms) y aparece un `SnackBar` "No entendí, probá de nuevo.".
- [ ] **Step 3: Verificar**

Run: `cd android_app && flutter analyze lib/widgets/voice_button.dart`
Expected: solo el info preexistente.

- [ ] **Step 4: Commit**

```bash
git add android_app/lib/widgets/voice_button.dart
git commit -m "feat: boton de comandos de voz con animaciones"
```

---

### Task 10: Wiring de voz en `HomeScreen`

**Files:**
- Modify: `android_app/lib/screens/home_screen.dart`

**Interfaces:**
- Consumes: `VoiceButton` (Task 9), `ComandoVoz`/variantes (Task 7)

- [ ] **Step 1:** agregar un `VoiceButton` (p. ej. como segundo FAB o junto a los íconos del `AppBar`) con `onComando` que hace `switch` sobre el `ComandoVoz`:
  - `AbrirCamaraPorIndice(i)`: si `i < _camaras.length` y `_camaras[i].enLinea`, navega a `LiveCameraScreen` con esa cámara; si `i >= _camaras.length`, `ScaffoldMessenger` con `"No existe la camara ${i + 1}."` (cubre el Review Focus de índice fuera de rango); si existe pero está sin señal, el mismo mensaje que ya usa el tap manual ("Camara sin senal.").
  - `IrAIncidencias()`: navega a `IncidenciasScreen`.
  - `IrAInicio()`: si hay alguna pantalla encima, `Navigator.popUntil` hasta `HomeScreen`.
  - `SimularIncidenteVoz()`: navega a la pantalla de simulación (Task 16).
  - `CerrarSesionVoz()`: llama `_cerrarSesion()`.
- [ ] **Step 2: Verificar**

Run: `cd android_app && flutter analyze && flutter test`
Expected: solo infos preexistentes, todos los tests en verde.

- [ ] **Step 3: Commit**

```bash
git add android_app/lib/screens/home_screen.dart
git commit -m "feat: conecta los comandos de voz a la navegacion de Inicio"
```

---

## Feature C: Simulación de incidente

### Task 11: `CamaraThread.disparar_simulacro()`

**Files:**
- Modify: `app/services/camera_service.py`
- Test: Create `tests/test_simulacro.py`

**Interfaces:**
- Produces: `CamaraThread.sabotaje_detectado` gana un 4º parámetro `es_simulacro: bool`; `CamaraThread.disparar_simulacro(self)`

- [ ] **Step 1: Escribir el test que falla**

Mismo patrón que `tests/test_evidencia_sabotaje_sin_bloqueo.py` (QApplication +
`processEvents()` esperando la señal, porque `disparar_simulacro` arranca un
hilo de verdad):

```python
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2
from PySide6.QtWidgets import QApplication
from app.services.camera_service import CamaraThread

aplicacion = QApplication.instance() or QApplication([])
hilo = CamaraThread(1, "zona1", "zona1", "USB", "0")
jpg = cv2.imencode(".jpg", np.zeros((10, 10, 3), np.uint8))[1].tobytes()
hilo._buffer.append(jpg)
hilo._ultimo_frame = np.zeros((10, 10, 3), np.uint8)

resultado = []
hilo.sabotaje_detectado.connect(lambda *args: resultado.append(args))
hilo.disparar_simulacro()

limite = time.time() + 5
while not resultado and time.time() < limite:
    aplicacion.processEvents()
    time.sleep(0.02)

assert resultado, "no llego la señal sabotaje_detectado"
zona, ruta_video, ruta_foto, es_simulacro = resultado[0]
assert zona == "zona1" and es_simulacro is True
print("OK: disparar_simulacro")
os._exit(0)
```

- [ ] **Step 2: Correr y confirmar que falla**

Run: `python tests/test_simulacro.py`
Expected: `AttributeError` (`disparar_simulacro` no existe) o `TypeError` (la señal todavía toma 3 argumentos).

- [ ] **Step 3: Implementar**

Cambiar `sabotaje_detectado = Signal(str, str, str)` a
`Signal(str, str, str, bool)`; en el único lugar que la emite
(`_exportar_evidencia_sabotaje`, al final), agregar el parámetro
`es_simulacro=False` a la firma del método y emitir
`self.sabotaje_detectado.emit(self.zona, ruta_video, ruta_foto, es_simulacro)`.
Nuevo método:

```python
def disparar_simulacro(self):
    threading.Thread(
        target=self._exportar_evidencia_sabotaje, args=(list(self._buffer),),
        kwargs={"es_simulacro": True}, daemon=True,
    ).start()
```

- [ ] **Step 4: Correr y confirmar que pasa**

Run: `python tests/test_simulacro.py`
Expected: imprime `OK: disparar_simulacro`, exit code 0.

- [ ] **Step 5: Correr el resto de la suite de Python para confirmar que la firma nueva de la señal no rompió nada**

Run: `python -u tests/test_sabotaje.py && python -u tests/test_api_service.py`
Expected: ambos `OK`.

- [ ] **Step 6: Commit**

```bash
git add app/services/camera_service.py tests/test_simulacro.py
git commit -m "feat: agrega CamaraThread.disparar_simulacro para la demo"
```

---

### Task 12: `MonitoreoController.disparar_simulacro(zona)`

**Files:**
- Modify: `app/controllers/monitoreo_controller.py`
- Test: Modify `tests/test_simulacro.py`

**Interfaces:**
- Consumes: `CamaraThread.disparar_simulacro()` (Task 11)
- Produces: `MonitoreoController.disparar_simulacro(self, zona) -> bool` (False si la zona no existe)

- [ ] **Step 1: Escribir las aserciones que fallan**

`_GuardarEvidenciaSabotajeThread.__init__` gana `tipo="Sabotaje",
severidad="Alta"` (con esos defaults, el llamado real de `_on_sabotaje` no
cambia); su `run()` usa esos valores en vez de los strings hardcodeados.
`_on_sabotaje` gana el 4º parámetro `es_simulacro` y lo traduce a
`tipo="Simulacro", severidad="Normal"` cuando es `True`. Agregar al final
de `tests/test_simulacro.py` (antes de `os._exit(0)`) una prueba de que
`_on_sabotaje` con `es_simulacro=True` efectivamente crea una incidencia
con `Tipo="Simulacro"` en la base (usando el patrón de datos sintéticos ya
usado en `tests/test_optimizacion_inicio.py`/`test_evidencia_sabotaje_sin_bloqueo.py`
para no depender de una base real — construir un `MonitoreoController` con
dobles de `usuario`/`camaras`/`obtener_turno_actual`, llamar a
`controller._on_sabotaje("zona1", "video.avi", "foto.jpg", True)`, esperar
la señal `listo` de `_GuardarEvidenciaSabotajeThread` con el mismo patrón
de `processEvents()`, y verificar con un stub de `incidencia_model.crear`
que el `tipo` recibido fue `"Simulacro"`, restaurando el original en un
`finally` como ya hace `test_evidencia_sabotaje_sin_bloqueo.py`).

- [ ] **Step 2: Correr y confirmar que falla**

Run: `python tests/test_simulacro.py`
Expected: `TypeError` (faltan argumentos) o el `tipo` capturado es `"Sabotaje"` en vez de `"Simulacro"`.

- [ ] **Step 3: Implementar**

`_GuardarEvidenciaSabotajeThread.__init__(self, zona, camara_info,
ruta_video, ruta_foto, id_usuario, id_turno, tipo="Sabotaje",
severidad="Alta", parent=None)`, guardando `self._tipo`/`self._severidad`
y usándolos en el `incidencia_model.crear(...)` de `run()` en vez de los
strings fijos. `_on_sabotaje(self, zona, ruta_video, ruta_foto,
es_simulacro=False)`: pasa `tipo="Simulacro" if es_simulacro else
"Sabotaje"`, `severidad="Normal" if es_simulacro else "Alta"` al construir
`_GuardarEvidenciaSabotajeThread`. Nuevo método público:

```python
def disparar_simulacro(self, zona):
    hilo = self.hilos_camara.get(zona)
    if hilo is None:
        return False
    self._activar_alarma()
    hilo.disparar_simulacro()
    return True
```

(Deliberadamente NO se agrega `zona` a `self._zonas_en_sabotaje`: ese set
solo se limpia cuando la cámara "se destapa" de verdad, y una zona
simulada nunca pasa por ese camino — agregarla la dejaría marcada como
"posible sabotaje" para siempre en el resumen. El costo aceptado es que el
mensaje de alarma en el escritorio no lista la zona simulada por nombre.)

- [ ] **Step 4: Correr y confirmar que pasa**

Run: `python tests/test_simulacro.py`
Expected: imprime `OK: disparar_simulacro` y el nuevo mensaje de la Tarea 12, exit code 0.

- [ ] **Step 5: Correr el resto de la suite**

Run: `python -u tests/test_sabotaje.py && python -u tests/test_evidencia_sabotaje_sin_bloqueo.py`
Expected: ambos `OK` (confirma que los defaults nuevos no cambiaron el camino real).

- [ ] **Step 6: Commit**

```bash
git add app/controllers/monitoreo_controller.py tests/test_simulacro.py
git commit -m "feat: MonitoreoController.disparar_simulacro distingue simulacro de sabotaje real"
```

---

### Task 13: `incidencia_model.contar_hoy()` excluye simulacros

**Files:**
- Modify: `app/models/incidencia_model.py`
- Test: Create `tests/test_contar_simulacros.py`

**Interfaces:**
- Produces: `contar_hoy(incluir_simulacros=False)`

- [ ] **Step 1: Escribir el test que falla**

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import inspect
from app.models import incidencia_model

firma = inspect.signature(incidencia_model.contar_hoy)
assert "incluir_simulacros" in firma.parameters, "contar_hoy debe aceptar incluir_simulacros"
assert firma.parameters["incluir_simulacros"].default is False

sql_fuente = inspect.getsource(incidencia_model.contar_hoy)
assert "Simulacro" in sql_fuente, "debe filtrar por Tipo <> 'Simulacro' cuando incluir_simulacros=False"
print("OK: contar_hoy excluye simulacros por defecto")
```

(Prueba sobre la firma/fuente, no contra una base real — consistente con
no depender de datos reales para esta verificación puntual.)

- [ ] **Step 2: Correr y confirmar que falla**

Run: `python tests/test_contar_simulacros.py`
Expected: `AssertionError` (el parámetro no existe todavía).

- [ ] **Step 3: Implementar**

```python
def contar_hoy(incluir_simulacros=False):
    filtro_tipo = "" if incluir_simulacros else " AND Tipo <> 'Simulacro'"
    fila = query_one(
        "SELECT COUNT(*) AS Total FROM cam.Incidencias "
        "WHERE CAST(FechaHora AS DATE) = CAST(SYSDATETIME() AS DATE)" + filtro_tipo
    )
    return fila["Total"] if fila else 0
```

- [ ] **Step 4: Correr y confirmar que pasa**

Run: `python tests/test_contar_simulacros.py`
Expected: imprime `OK: contar_hoy excluye simulacros por defecto`, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add app/models/incidencia_model.py tests/test_contar_simulacros.py
git commit -m "fix: contar_hoy no cuenta simulacros en el resumen por defecto"
```

---

### Task 14: Endpoint `POST /camaras/{zona}/simular-incidente`

**Files:**
- Modify: `app/services/api_service.py`
- Test: Modify `tests/test_api_service.py`

**Interfaces:**
- Consumes: `MonitoreoController.disparar_simulacro(zona) -> bool` (Task 12)
- Produces: `POST /camaras/{zona}/simular-incidente` → 200 `{"disparado": true}` si la zona existe; 404 si no; 401/503 igual que los demás

- [ ] **Step 1: Escribir las aserciones que fallan**

Agregar a `_MonitoreoFalso` en `tests/test_api_service.py` un
`disparar_simulacro(self, zona)` que devuelva `zona in self.hilos_camara`.
Agregar al test:

```python
r = requests.post(f"{BASE}/camaras/Cam-Ingreso-01/simular-incidente", headers=cabecera, timeout=3)
assert r.status_code == 200 and r.json() == {"disparado": True}, r.text

r = requests.post(f"{BASE}/camaras/Zona-Que-No-Existe/simular-incidente", headers=cabecera, timeout=3)
assert r.status_code == 404, r.text
```

- [ ] **Step 2: Correr y confirmar que falla**

Run: `python -u tests/test_api_service.py`
Expected: 404 (ruta no existe) en la primera aserción nueva.

- [ ] **Step 3: Implementar**

```python
@app.post("/camaras/{zona}/simular-incidente")
def simular_incidente(zona: str, authorization: str = Header(default=None)):
    _validar_token(authorization)
    if _monitoreo_controller is None:
        raise HTTPException(status_code=503, detail="El Centro de Monitoreo todavia no arranco.")
    if not _monitoreo_controller.disparar_simulacro(zona):
        raise HTTPException(status_code=404, detail="Camara no encontrada.")
    return {"disparado": True}
```

- [ ] **Step 4: Correr y confirmar que pasa**

Run: `python -u tests/test_api_service.py`
Expected: `OK: API ...`, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add app/services/api_service.py tests/test_api_service.py
git commit -m "feat: endpoint para disparar el simulacro de incidente desde el celular"
```

---

### Task 15: Ícono "alarma de simulacro"

**Files:**
- Create: `android_app/lib/widgets/icono_alarma.dart`

**Interfaces:**
- Produces: `class IconoAlarma extends StatelessWidget { final double tamano; final Color color; const IconoAlarma({super.key, this.tamano = 28, this.color = AppColors.acento}); }`

- [ ] **Step 1: Implementar** con `CustomPaint`: una campana de línea fina (cuerpo trapezoidal/semicírculo, badajo abajo) con un pequeño triángulo de alerta (signo de exclamación) superpuesto en una esquina — mismo trazo que el resto.
- [ ] **Step 2: Verificar**

Run: `cd android_app && flutter analyze lib/widgets/icono_alarma.dart`
Expected: solo el info preexistente.

- [ ] **Step 3: Commit**

```bash
git add android_app/lib/widgets/icono_alarma.dart
git commit -m "feat: icono de alarma para el simulacro de incidente"
```

---

### Task 16: Pantalla de simulación de incidente

**Files:**
- Create: `android_app/lib/screens/simulacro_screen.dart`
- Modify: `android_app/lib/api_client.dart` (agregar `Future<void> simularIncidente(String zona)`)

**Interfaces:**
- Consumes: `IconoAlarma` (Task 15), `ApiClient.getIncidencias`/`getResumen` (ya existentes)
- Produces: `class SimulacroScreen extends StatelessWidget { final ApiClient api; final String zona; const SimulacroScreen({super.key, required this.api, required this.zona}); }`; `ApiClient.simularIncidente(String zona) -> Future<void>` (POST, misma validación de 401 que `_get`)

- [ ] **Step 1:** en `api_client.dart`, agregar:

```dart
Future<void> simularIncidente(String zona) async {
  final respuesta = await http
      .post(_uri('/camaras/$zona/simular-incidente'), headers: _cabeceras)
      .timeout(const Duration(seconds: 8));
  if (respuesta.statusCode == 401) throw Exception('La sesion vencio, inicie sesion de nuevo.');
  if (respuesta.statusCode != 200) throw Exception('Error del servidor (${respuesta.statusCode}).');
}
```

- [ ] **Step 2:** `SimulacroScreen` con un botón grande "Mantené presionado para armar": `GestureDetector` con `onLongPressStart` iniciando un `TweenAnimationBuilder<double>` de 0 a 1 en 1.5s dibujando un `CircularProgressIndicator` alrededor del botón (color rojo/ámbar); `onLongPressEnd` o `onLongPressCancel` antes de completarse: el anillo retrocede a 0 en 200ms sin disparar nada. Al completarse el 1.5s: llama a `widget.api.simularIncidente(widget.zona)`.

- [ ] **Step 3:** al completarse la llamada (200 OK): destello rojo de toda la pantalla (`AnimatedOpacity` 0→0.4→0 en 300ms) y se muestran 3 pasos, cada uno apareciendo con `AnimatedSlide` desde la derecha + fundido, apenas se confirma:
  1. "Incidente simulado" — se marca de inmediato (el POST ya respondió 200).
  2. "Evidencia firmada con SHA-256" — sondeo de `api.getIncidencias(limite: 5)` cada 500ms hasta encontrar una fila con `tipo == "Simulacro"` y `zona == widget.zona` que no estaba en el primer sondeo.
  3. "Alarma activada" — sondeo de `api.getResumen()` cada 500ms hasta `alarmaSonando == true`.
  Cada paso confirmado agrega un ícono de tilde con un "pop" de escala
  (`TweenAnimationBuilder` 0.5→1.1→1.0). Si un paso no se confirma en 8s,
  se marca con un ícono de advertencia en vez de quedar esperando (cubre
  el Review Focus de la demo que nunca confirma).

- [ ] **Step 4: Verificar**

Run: `cd android_app && flutter analyze && flutter test`
Expected: solo infos preexistentes, todos los tests en verde.

- [ ] **Step 5: Commit**

```bash
git add android_app/lib/screens/simulacro_screen.dart android_app/lib/api_client.dart
git commit -m "feat: pantalla de simulacion de incidente con checklist confirmado de verdad"
```

---

## Feature D: Login por QR

### Task 17: `app/services/qr_service.py`

**Files:**
- Create: `app/services/qr_service.py`
- Test: Create `tests/test_qr_service.py`

**Interfaces:**
- Produces: `detectar_ip_lan() -> str`; `generar_qr_png_bytes(ip: str) -> bytes`

- [ ] **Step 1: Escribir el test que falla**

```python
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services import qr_service

ip = qr_service.detectar_ip_lan()
assert re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip), f"debe ser una IP valida, dio {ip!r}"

png = qr_service.generar_qr_png_bytes("192.168.1.10")
assert png[:8] == b"\x89PNG\r\n\x1a\n", "debe ser un PNG valido"
print("OK: qr_service")
```

- [ ] **Step 2: Correr y confirmar que falla**

Run: `python tests/test_qr_service.py`
Expected: `ModuleNotFoundError` — el archivo no existe.

- [ ] **Step 3: Implementar**

```python
import io
import json
import socket

import qrcode


def detectar_ip_lan():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def generar_qr_png_bytes(ip):
    imagen = qrcode.make(json.dumps({"ip": ip}))
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()
```

- [ ] **Step 4: Correr y confirmar que pasa**

Run: `python tests/test_qr_service.py`
Expected: imprime `OK: qr_service`, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add app/services/qr_service.py tests/test_qr_service.py
git commit -m "feat: generador de QR de login (ip detectada en LAN)"
```

---

### Task 18: QR visible en el login del escritorio

**Files:**
- Modify: `app/views/login_view.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `qr_service.detectar_ip_lan()`/`generar_qr_png_bytes()` (Task 17)
- Produces: `LoginView.set_codigo_qr(self, png_bytes)`

- [ ] **Step 1:** en `login_view.py`, agregar un `QLabel` de 110×110px (`self.lbl_qr`) con un título chico "Escaneá con la app CAM" encima, ubicado después del campo de clave y antes del botón "Ingresar" (o en una columna aparte si el ancho de 320px queda muy apretado — ancho fijo a criterio del que construye). Método:

```python
def set_codigo_qr(self, png_bytes):
    from PySide6.QtGui import QPixmap
    pixmap = QPixmap()
    pixmap.loadFromData(png_bytes)
    self.lbl_qr.setPixmap(pixmap.scaled(110, 110))
```

- [ ] **Step 2:** en `app/main.py`, después de `login_view = LoginView()` (línea 60), llamar a `set_codigo_qr` envuelto en `try/except` (igual que `api_service.iniciar_api`) para que una falla generando el QR nunca bloquee el login:

```python
try:
    from app.services import qr_service
    login_view.set_codigo_qr(qr_service.generar_qr_png_bytes(qr_service.detectar_ip_lan()))
except Exception:
    pass
```

- [ ] **Step 3: Verificar**

Run: `python -c "import app.main"` no debe lanzar error de sintaxis (smoke
test de import); y relanzar la app (`python app/main.py`) y confirmar a
simple vista que el login muestra el QR — esto lo confirma el usuario al
probar el APK/la app, no es parte del test automatizado.

- [ ] **Step 4: Commit**

```bash
git add app/views/login_view.py app/main.py
git commit -m "feat: muestra un codigo QR en el login para conectar el celular"
```

---

### Task 19: Dependencia y permiso de cámara en Android

**Files:**
- Modify: `android_app/pubspec.yaml`
- Modify: `android_app/android/app/src/main/AndroidManifest.xml`

- [ ] **Step 1:** `cd android_app && flutter pub add mobile_scanner`.
- [ ] **Step 2:** agregar `<uses-permission android:name="android.permission.CAMERA" />` en `AndroidManifest.xml`.
- [ ] **Step 3: Verificar**

Run: `cd android_app && flutter pub get && flutter analyze`
Expected: resuelve sin error; solo infos preexistentes.

- [ ] **Step 4: Commit**

```bash
git add android_app/pubspec.yaml android_app/pubspec.lock android_app/android/app/src/main/AndroidManifest.xml
git commit -m "feat: agrega mobile_scanner y permiso de camara para el login por QR"
```

---

### Task 20: Parser del QR + pantalla de escaneo con animaciones

**Files:**
- Create: `android_app/lib/qr_login.dart` (parser puro)
- Create: `android_app/lib/screens/qr_scan_screen.dart`
- Test: Create `android_app/test/qr_login_test.dart`

**Interfaces:**
- Produces: `String? parsearIpDeQr(String contenido)`; `class QrScanScreen extends StatelessWidget { const QrScanScreen({super.key}); }` (al escanear con éxito, hace `Navigator.pop(context, ip)`)

- [ ] **Step 1: Escribir el test que falla**

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:cam_app/qr_login.dart';

void main() {
  test('un QR valido de CAM devuelve la ip', () {
    expect(parsearIpDeQr('{"ip": "192.168.1.10"}'), '192.168.1.10');
  });
  test('un QR de cualquier otra cosa no rompe nada', () {
    expect(parsearIpDeQr('https://ejemplo.com'), isNull);
    expect(parsearIpDeQr('{"otracosa": 1}'), isNull);
    expect(parsearIpDeQr(''), isNull);
  });
}
```

- [ ] **Step 2: Correr y confirmar que falla**

Run: `cd android_app && flutter test test/qr_login_test.dart`
Expected: error de compilación, el archivo no existe.

- [ ] **Step 3: Implementar `parsearIpDeQr`**

```dart
import 'dart:convert';

String? parsearIpDeQr(String contenido) {
  try {
    final datos = jsonDecode(contenido);
    if (datos is Map && datos['ip'] is String) return datos['ip'] as String;
  } catch (_) {
    // QR de cualquier otra cosa: no es un error, simplemente no es de CAM
  }
  return null;
}
```

Cubre el Review Focus de QR ajeno a la app: cualquier contenido que no sea
el JSON esperado cae en el `catch` o en el `if` que no matchea, nunca
lanza.

- [ ] **Step 4: Correr y confirmar que pasa (parser)**

Run: `cd android_app && flutter test test/qr_login_test.dart`
Expected: `All tests passed!` (2 tests)

- [ ] **Step 5: Implementar `QrScanScreen`** con el paquete `mobile_scanner`:
  `MobileScanner(onDetect: (capture) { ... })`, por cada código leído prueba
  `parsearIpDeQr`; si da una IP, `Navigator.pop(context, ip)`.
  Animaciones: un marco cuadrado centrado con 4 esquinas dibujadas (puede
  reusar un `CustomPainter` simple con 4 trazos en L) y una línea
  horizontal que rebota de arriba a abajo dentro del marco en bucle
  (`TweenAnimationBuilder` 0→1→0, `AppColors.acento`). Al detectar un QR
  válido: las 4 esquinas cambian a verde por 300ms y el marco hace un
  "pop" de escala (1.0→1.08→1.0) antes de cerrar la pantalla.

- [ ] **Step 6: Verificar**

Run: `cd android_app && flutter analyze lib/qr_login.dart lib/screens/qr_scan_screen.dart`
Expected: solo el info preexistente.

- [ ] **Step 7: Commit**

```bash
git add android_app/lib/qr_login.dart android_app/lib/screens/qr_scan_screen.dart android_app/test/qr_login_test.dart
git commit -m "feat: parser de QR y pantalla de escaneo con animacion"
```

---

### Task 21: Wiring del QR en `LoginScreen`

**Files:**
- Modify: `android_app/lib/screens/login_screen.dart`

**Interfaces:**
- Consumes: `QrScanScreen` (Task 20)

- [ ] **Step 1:** agregar un botón/ícono "Escanear código QR" (usar el ícono QR nuevo descrito en el diseño: cuadrado con solo las 4 esquinas, mismo `CustomPainter` que ya usa `QrScanScreen` para su marco) junto al campo de IP; al tocarlo, `final ip = await Navigator.push<String>(context, MaterialPageRoute(builder: (_) => const QrScanScreen()));` y si `ip != null`, completar `_ipCtrl` con un efecto "máquina de escribir": un `Timer.periodic` cada ~25ms que agrega un carácter a la vez al `TextEditingController` hasta completar la IP (en vez de `_ipCtrl.text = ip` de una sola vez).
- [ ] **Step 2: Verificar**

Run: `cd android_app && flutter analyze && flutter test`
Expected: solo infos preexistentes, todos los tests en verde.

- [ ] **Step 3: Commit**

```bash
git add android_app/lib/screens/login_screen.dart
git commit -m "feat: boton de login por QR con efecto maquina de escribir"
```

---

## Task 22: Verificación final y entrega del APK

**Files:** ninguno nuevo.

- [ ] **Step 1:** Suite completa de Python: `for f in tests/test_*.py; do python -u "$f"; done` (o uno por uno) — todos en verde (se acepta el exit code 127 ya documentado de `test_evidencia_sabotaje_sin_bloqueo.py`, no es una regresión).
- [ ] **Step 2:** `cd android_app && flutter analyze` — solo los infos preexistentes de `material.dart`, cero errores/warnings nuevos.
- [ ] **Step 3:** `cd android_app && flutter test` — todo en verde.
- [ ] **Step 4:** `cd android_app && flutter build apk --debug`.
- [ ] **Step 5:** Verificar que `android_app/build/app/outputs/flutter-apk/app-debug.apk` existe y pesa más de 0 bytes.
- [ ] **Step 6:** Reiniciar el programa de escritorio (el proceso corriendo tiene código viejo) y entregar el APK al usuario explicando las 4 funciones nuevas y cómo probarlas en la demo.

---

## Self-Review

**1. Cobertura del spec:** máquina del tiempo (Tasks 1-5), comandos de voz (Tasks 6-10), simulación de incidente (Tasks 11-16), login por QR (Tasks 17-21), entrega (Task 22). Los 4 íconos (Tasks 4, 8, 15, 20) y las animaciones detalladas del spec están cada una en su task.

**2. Pasos:** cada paso de test fija nombre/aserciones exactas; cada paso de código fija firma y archivo exactos, con cuerpo solo donde el algoritmo no es obvio (generador finito de MJPEG, parser de voz, parser de QR, señal con el parámetro nuevo). Las animaciones se describen con el widget implícito exacto a usar y los tiempos/colores decididos en el spec, dejando solo el ensamblado de UI al que construye.

**3. Consistencia de tipos:** `CamaraThread.obtener_buffer_jpeg_brillante`/`disparar_simulacro` (Task 1/11) se usan igual en Tasks 2/12/14; `MonitoreoController.disparar_simulacro` (Task 12) se usa igual en Task 14; `ComandoVoz`/variantes (Task 7) se usan igual en Tasks 9-10; `parsearIpDeQr` (Task 20) se usa igual en Task 21; `MjpegView(finito, onTerminado)` (Task 3) se usa igual en Task 5.

**4. Review Focus:** los 5 puntos están cada uno cubierto por un test o un paso explícito (ver la lista, con la tarea entre paréntesis).

**5. Proporción:** 22 tareas para 4 funciones completas (escritorio + Android, con íconos y animaciones) es proporcional al spec; los bloques de código son firmas, tests, o el único algoritmo no obvio de cada tarea (generador finito, parsers, señal nueva) — no transcripciones de archivos enteros.
