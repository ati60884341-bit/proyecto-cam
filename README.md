# CAM — Sistema Inteligente de Videovigilancia y Auditoria

Software de escritorio (Python + PyQt6, arquitectura **MVC**) con base de datos
**SQL Server** (triggers de auditoria) para el proyecto "Sistema Inteligente de
Videovigilancia y Auditoria" (4 zonas: Ingreso, Patio, Estacionamiento, Pasillo).

## Estructura (MVC)

```
ProyectoCAM/
  db/                    scripts SQL Server (schema, triggers, seed)
  app/
    database/             conexion_bd.py: conexion a SQL Server (pyodbc)
    models/                Modelo: una clase/archivo por entidad (consultas SQL)
    views/                 Vista: pantallas PyQt6 (login, dashboard, tablas, etc.)
      UI/                   frames y dialogos reutilizables (QFrame, QDialog)
    controllers/           Controlador: logica que conecta vista <-> modelo
    services/              camara (QThread), sabotaje, voz, panico, fatiga, SHA-256
    main.py                punto de entrada
  evidencias/              fotos/videos capturados (se crea solo)
```

## 1. Base de datos

Requiere SQL Server (local, autenticacion de Windows). Ejecutar en orden:

```bash
sqlcmd -S localhost -E -C -i db/01_schema.sql
sqlcmd -S localhost -E -C -i db/02_triggers.sql
sqlcmd -S localhost -E -C -i db/03_seed.sql
```

Esto crea la base `bd_cam_seguridad`, el esquema `cam` y **5 triggers**:

| Trigger | Evento | Que hace |
|---|---|---|
| `trg_HistorialIncidencias` | AFTER UPDATE en Incidencias | Bitacora de cambios de estado/severidad |
| `trg_RegistroNuevaIncidencia` | AFTER INSERT en Incidencias | Si es tipo `Panico`, crea la alerta con bloqueo de borrado |
| `trg_BloqueoBorradoEvidencias` | INSTEAD OF DELETE en Evidencias | Cadena de custodia: bloquea el borrado si hay panico activo en la zona |
| `trg_EscalamientoSabotajeRepetido` | AFTER INSERT en Incidencias | 3+ sabotajes en 10 min en una zona -> incidencia critica automatica |
| `trg_CierreTurno` | AFTER UPDATE en Turnos | Al cerrar un turno, calcula y registra su duracion |

Puede probarlos con `db/04_test_triggers.sql`.

Para la pestana "NVR / DVR" (alta masiva de canales, ver seccion 4) corra
tambien `db/06_dispositivos_dvr.sql` una vez (agrega la tabla
`cam.DispositivosDVR` y dos columnas en `cam.Camaras`, no borra nada de lo
existente), y `db/07_capacidades_camara.sql` (agrega la columna `TienePTZ`).

Para los "Perfiles de sitio" y la "Bitacora de instalacion" de la misma
pestana (ver seccion 4) corra tambien `db/10_perfiles_sitio.sql` (agrega
`cam.PerfilesSitio`) y `db/11_bitacora_instalacion.sql` (agrega
`cam.BitacoraInstalacion`) — ninguna borra nada existente.

Para que el Centro de Monitoreo agrupe cada grabador como "DVR" o "NVR",
corra `db/12_tipo_grabador.sql` (agrega la columna `Tipo`; obligatoria: sin
ella la app no lista las camaras).

Si ya probo la app con los datos de ejemplo de `03_seed.sql` (zonas
Ingreso/Patio/Estacionamiento/Pasillo con camaras simuladas) y ahora va a
trabajar con camaras reales, corra `db/08_zonas_ejemplo.sql` y despues
`db/09_reactivar_webcam_pc.sql`: desactivan las 3 camaras RTSP de muestra
(IPs inventadas, sin borrarlas) y renombran sus zonas a "Zona de prueba
1-4" para que no choquen con los nombres reales que usted escriba despues,
agregan varias zonas genericas mas (Recepcion, Almacen, Oficina principal,
etc.), y dejan **activa** la webcam USB real de la PC ("Cam-Ingreso-01",
indice 0) — esa si funciona de verdad (deteccion de gesto/panico y
sabotaje la usan), no es una camara simulada como las otras 3.

Si otras laptops van a conectarse a esta base por red (no desde esta misma
PC), vea `db/05_acceso_red.sql` y la seccion 7 de este documento.

## 2. Dependencias de Python

```bash
pip install -r requirements.txt
```

Incluye: `pyodbc`, `PyQt6`, `opencv-python`, `pyttsx3`, `SpeechRecognition`,
`pyaudio`, `mediapipe`, `matplotlib`.

Si `pyaudio` o `mediapipe` no instalan en su equipo, la app sigue funcionando:
el asistente de voz y la deteccion de gesto se desactivan solos y quedan los
reemplazos manuales (campo de texto de comandos, boton "Simular Modo Panico").

## 3. Ejecutar

```bash
python app/main.py
```

Usuarios de demo (clave para ambos: `123456`):

- `admin` — rol Administrador (puede eliminar evidencias)
- `vigilante` — rol Vigilante

## 4. Guion de demo sugerido (en vivo ante el jurado)

1. **Login** con `vigilante` / `123456`.
2. **Centro de monitoreo**: la zona "Ingreso" usa la webcam real (camara 0);
   las otras 3 son RTSP simuladas (marcan "SIN SENAL", representando
   Hikvision/Dahua/Tapo del adaptador universal multimarca).
3. **Abrir turno** en la pestana "Turnos".
4. **Captura de evidencia**: clic en "Capturar evidencia" en Ingreso -> se
   guarda una foto, se firma SHA-256 y aparece en "Evidencias".
5. **Anti-sabotaje**: tapar la camara con la mano 2-3 segundos -> el marco se
   pone rojo, suena una alerta y se exporta automaticamente un video con los
   8 segundos previos + una foto del "culpable acercandose" (2s antes del
   bloqueo), ambos firmados SHA-256. Se crea una incidencia tipo `Sabotaje`.
6. **Comandos de voz**: activar el checkbox del microfono y decir
   *"patio ampliar"* o *"ingreso capturar"* (zona + accion, sin palabra de
   activacion; o usar el campo de texto manual si no hay microfono en la
   sala). Ver el manual completo de comandos en la seccion 5 de este
   documento, o con el boton "Ver manual de comandos" del panel derecho.
7. **Modo panico silencioso**: levantar una mano (o ambas) frente a la camara
   de Ingreso por 3 segundos — el panel muestra en vivo "mano detectada,
   sosteniendo X.Xs / 3.0s" (o usar el boton manual). No suena nada; se crea
   una alerta critica y queda bloqueado el borrado de evidencias de esa zona.
   Si la camara o la iluminacion no cooperan, use el boton manual.
7b. **Agregar una camara de cualquier marca**: en la pestana "Camaras",
   complete zona, nombre, marca (Hikvision/Dahua/Tapo/WebcamUSB/Generico),
   tipo de conexion (RTSP o USB) y la URL/indice, y pulse "Agregar camara".
   La camara arranca en caliente y aparece de inmediato en el Centro de
   Monitoreo (sin reiniciar la app), demostrando el adaptador universal
   multimarca. Para quitar una, selecciónela en la tabla (el boton "Quitar
   camara seleccionada" se activa) y confirme: la camara deja de transmitir
   y su recuadro **desaparece por completo** del Centro de Monitoreo (no
   queda ningun rastro, ni placeholder de "camara quitada") y de la lista
   de "Camaras" (puede agregar una nueva para esa zona de inmediato, que
   arma un recuadro nuevo desde cero).

   **Conectar un DVR/NVR Hikvision o Dahua:** al elegir esa marca con
   conexion RTSP aparece un "Asistente de conexion al DVR" (IP, puerto,
   usuario, clave, canal y calidad) que arma la URL RTSP solo — no hace
   falta escribirla ni saber su formato. Antes de agregarla, use **"Probar
   conexion"**: intenta abrir el canal y avisa si conecto o que falla (red,
   credenciales, numero de canal), sin tener que ir al Centro de Monitoreo
   ni abrir VLC. El DVR debe estar en la misma red (WiFi o UTP al mismo
   router/switch) que esta PC, con el servicio RTSP habilitado en su
   configuracion de red (puerto por defecto `554`).

   **Un DVR/NVR entero de una sola vez (pestana "NVR / DVR"):** la pestana
   "Camaras" agrega una camara a la vez; si lo que tiene es un grabador con
   varios canales (un DVR para camaras analogicas, o un NVR para camaras
   IP — cada canal es una camara conectada al grabador), use la pestana
   "NVR / DVR" en vez: registre el grabador UNA sola vez (nombre, marca,
   IP, usuario, clave y **cuantos canales tiene**) y pulse "Registrar y
   detectar todos los canales". El sistema prueba cada canal (igual que
   hace el software del fabricante — iVMS-4200 de Hikvision, SmartPSS de
   Dahua — al "buscar" camaras) y agrega solo una camara por cada uno que
   responda, cada una en su propia zona (`<Nombre> Canal N`), visibles de
   inmediato en el Centro de Monitoreo. Si despues conecta canales nuevos
   al mismo grabador, seleccionelo en la tabla y pulse "Detectar canales
   nuevos" (salta los que ya tiene, no los duplica). "Quitar grabador y
   sus camaras" detiene todas sus camaras en vivo y las marca inactivas de
   una sola vez (solo Administrador).

   **Checklist de red al entrar por primera vez:** la primera vez en cada
   sesion que se abre la pestana "NVR / DVR" aparece un dialogo con 3
   casillas (cable UTP puesto, esta PC en la misma red, internet portatil
   en otro adaptador) que hay que marcar antes de poder seguir — evita
   perder tiempo armando una conexion que la red ni siquiera deja llegar.
   Tiene un boton para abrir el manual ilustrado completo.

   **Columna "En esta red":** la tabla de grabadores registrados compara
   la IP de cada uno contra las redes activas de esta PC (mismo calculo
   que el panel "Mi red") y marca en rojo los que estan en otra subred —
   util cuando el DVR usa DHCP y el router le reasigno otra IP distinta a
   la guardada.

   **Perfiles de sitio:** si ya se instalo antes en un taller/cliente,
   el combo "Perfil de sitio" precarga su IP, puerto, marca y usuario
   tipicos (no la clave, esa se escribe a mano cada vez); "Guardar datos
   de abajo como perfil nuevo" lo crea a partir de lo que haya en el
   formulario. Se guarda en la base central (`cam.PerfilesSitio`), visible
   para todo el equipo.

   **Bitacora de instalacion compartida:** al seleccionar un grabador en
   la tabla, el panel de abajo muestra sus notas (`cam.BitacoraInstalacion`)
   y deja agregar una nueva — para que el siguiente tecnico no repita un
   diagnostico que otro ya hizo (ej. "este DVR necesita el puerto 8000, no
   el 554"). Las notas quedan ligadas al usuario y la fecha, y las ve todo
   el equipo, no solo quien las escribio.

   **Camaras USB/integradas en otra laptop:** el indice de la webcam no es
   siempre 0 (varia segun el equipo). Con conexion "USB" seleccionada,
   pulse **"Detectar camaras USB disponibles"**: prueba los indices 0 a 4
   y los lista con su resolucion para elegir el correcto, sin tener que
   adivinar ni probar uno por uno.
8. **Cadena de custodia**: en "Evidencias", como `admin`, intentar borrar una
   evidencia de Ingreso mientras el panico esta activo -> el trigger de SQL
   Server lo rechaza con el mensaje de cadena de custodia.
9. **Auditor de fatiga**: cada 90 segundos pide confirmacion; si se ignora
   15 segundos, suena una alerta y se registra la falta.
10. **Reportes**: graficos de incidencias por tipo y por zona.
11. **Alertas instantaneas a Telegram (efecto "wow" para el jurado)**: antes
    de empezar, configure el bot en la pestana "Alertas Telegram" (ver
    seccion 6) y muestre el QR para que el jurado se una desde su celular.
    Cuando tape la camara o active el modo panico, la foto + firma SHA-256
    le llega al instante a su propio telefono.
12. **Manuales ilustrados**: la pestana **"Manuales"** trae tres guias con
    diagramas para quien recien usa el programa — "Conectar tus camaras"
    (IP/WiFi, DVR/NVR completo, USB), "Comandos de voz" y "Conectar la
    camara, el DVR y la red" (que cable va en cada puerto del DVR y como
    dejarlo en la misma red que la PC, antes de abrir el programa). Se
    abren en el navegador del sistema y funcionan **sin internet** (vienen
    guardadas dentro del programa, en `app/manuales/`). Cada una tambien tiene un
    "Copiar enlace" a su version web (publicada como Artifact), por si hay
    que compartirla con alguien que aun no tiene el programa instalado, o
    pedir que se le agregue contenido (ej. el usuario/clave real de un
    equipo a modo de ejemplo) sin editar el archivo a mano.

    **"Cámaras" vs. "NVR / DVR", cuándo usar cada una**: no son lo mismo.
    "Cámaras" agrega una cámara/canal a la vez (útil para una IP suelta, o
    sumar una cámara a un grabador que ya registró); "NVR / DVR" registra
    el grabador completo y agrega todos sus canales de una sola vez. El
    propio asistente de "Cámaras" avisa cuándo conviene usar la otra
    pestaña en su lugar.

## 5. Manual de comandos de voz

Formato simple: diga la **zona** y luego la **accion** (en cualquier orden,
sin palabra de activacion). El campo de texto manual del dashboard acepta
las mismas frases, sin microfono. Zonas reconocidas: `ingreso`, `patio`,
`estacionamiento`, `pasillo`, cualquier zona nueva que haya agregado desde
la pestana "Camaras", y las que crea la pestana "NVR / DVR" (ver seccion
4). El reconocimiento usa espanol latino (`es-PE`) y no distingue tildes
(decir "deposito" o "depósito" da lo mismo).

**Zonas de un DVR/NVR, con nombres largos**: esas zonas se llaman
"`<Nombre del grabador>` Canal N" (ej. "DVR Patio Central Canal 3"). Repetir
el nombre completo del grabador por voz es incomodo, asi que si hay una
sola zona que termine en "Canal N", alcanza con decir `"canal N"` seguido
de la accion — ej. *"canal 3 ampliar"*.

**Si no reconoce bien**: el desplegable sobre la casilla de activar microfono
lista todos los dispositivos de entrada de audio detectados — elija su
microfono real en vez de "por defecto de Windows" (que puede quedarse
apuntando a un Bluetooth desconectado). Hable claro, cerca del microfono y
con el menor ruido de fondo posible. Al activar la casilla, abrir el
microfono puede tardar hasta 15-20 segundos en algunos equipos (negociacion
del driver de audio + hilos de camara activos); mientras tanto se muestra
"Conectando microfono...", es normal — espere a que diga "escuchando".

| Intencion | Frases de ejemplo |
|---|---|
| Ver una zona en pantalla completa | "`<zona>` ampliar" / "`<zona>` mostrar" / "`<zona>` pantalla completa" |
| Capturar evidencia | "`<zona>` capturar" / "`<zona>` foto" / "`<zona>` evidencia" |
| Acercar (zoom in) | "`<zona>` acercar" / "`<zona>` zoom" |
| Alejar (zoom out) | "`<zona>` alejar" |
| Restablecer el zoom | "`<zona>` zoom normal" / "`<zona>` quitar zoom" |
| Mover la camara (PTZ real) | "`<zona>` mover izquierda / derecha / arriba / abajo" / "`<zona>` girar izquierda" |
| Guardar posicion PTZ (preset 1-9) | "`<zona>` preset N guardar" / "`<zona>` preset N grabar" / "`<zona>` preset N memoriza" |
| Ir a una posicion PTZ guardada | "`<zona>` preset N" (sin verbo) |
| Vista general | "vista general" (no necesita zona) |

Ejemplos: *"patio ampliar"*, *"ingreso capturar"*, *"estacionamiento acercar"*,
*"patio mover derecha"*, *"patio preset 1 guardar"*, *"patio preset 1"*,
*"canal 3 ampliar"*.

**Mover la camara y los presets** solo funcionan con camaras RTSP de motor
Pan/Tilt que soporten ONVIF (como la Tapo C510W): usan el mismo
usuario/clave de la "Cuenta de camara" (RTSP) configurados en la app Tapo,
contra el puerto ONVIF 2020. Si la camara no tiene motor, o el
puerto/credenciales no son correctos, el sistema lo informa en la bitacora
de eventos sin interrumpir el resto de la app. Los presets quedan grabados
**en la propia camara** (no en esta base de datos): un preset guardado con
una marca/modelo PTZ puede no ser compatible con otra.

**Importante — el PTZ se declara por CAMARA, no por marca.** Al agregar una
camara (pestana "Camaras") o un grabador (pestana "NVR / DVR") hay una
casilla "tiene motor PTZ": una misma marca vende tanto domos PTZ como
camaras fijas, asi que el programa nunca asume la capacidad por marca —
solo ofrece mover/presets en las camaras donde usted marco que si tienen
motor. Esta es la base para que, mas adelante, cada camara pueda tener su
propio set de funciones (en vez de un comportamiento fijo igual para
todas, como en el software propio de cada fabricante).

El boton **"Ver manual de comandos"** del dashboard refleja esto: la
seccion de mover/presets solo aparece (y lista las zonas exactas donde
funciona) si al menos una camara registrada ahora mismo tiene el motor
marcado; si no, explica que falta marcarlo en vez de listar comandos que
no van a hacer nada. Se recalcula solo cada vez que se agrega o se quita
una camara.

El zoom es digital (recorta y escala la imagen en vivo), de x1.0 a x3.0 en
pasos de x0.5, y se aplica tanto al recuadro de la zona como a su vista
ampliada si esta abierta; la evidencia y la deteccion de sabotaje siempre
usan la imagen original sin recortar.

El **modo panico silencioso** deliberadamente NO es un comando de voz (para
no delatar al operador frente a un asaltante): se activa con el gesto de
mano(s) arriba 3 segundos frente a la camara de Ingreso, o con el boton
manual "Simular Modo Panico".

## 6. Alertas instantaneas a Telegram

Cuando el sistema detecta un sabotaje o activa el modo panico, puede enviar
de inmediato la foto de evidencia + su firma SHA-256 a un chat/canal de
Telegram — ideal para que el jurado reciba la alerta en su propio celular
durante la demo en vivo, sin tocar nada.

**Paso 1: crear el bot (2 minutos, gratis)**
1. Abra Telegram y busque el usuario oficial `@BotFather`.
2. Envie el comando `/newbot`, elija un nombre y un usuario para su bot
   (debe terminar en "bot", ej. `CentinelaFeriaBot`).
3. BotFather le entrega un **Token** (una cadena larga tipo
   `123456789:AAH...`). Guardelo.

**Paso 2: conseguir el Chat ID**
- Para un chat de prueba: hablele a su bot primero (busquelo por su usuario
  y envie cualquier mensaje), luego visite en el navegador
  `https://api.telegram.org/bot<SU_TOKEN>/getUpdates` y busque el campo
  `"chat":{"id": ...}` en la respuesta — ese numero es el Chat ID.
- Para un canal/grupo: agregue el bot como administrador del canal/grupo y
  use el mismo metodo (`getUpdates`) o un bot auxiliar como `@userinfobot`.

**Paso 3: configurar en la app**
1. Inicie sesion y vaya a la pestana **"Alertas Telegram"**.
2. Pegue el **Bot Token** y el **Chat ID**, y el usuario del bot (sin `@`).
3. Pulse **"Guardar configuracion"**, luego **"Enviar mensaje de prueba"**
   para confirmar que llega.
4. Pulse **"Generar QR"**: aparece un codigo QR hacia `https://t.me/<su_bot>`
   — proyectelo o imprimalo para que el jurado lo escanee con la camara de
   su celular y se una al chat del bot antes de la demo.

A partir de ahi, cada sabotaje detectado o activacion del modo panico envia
automaticamente la foto + hash SHA-256 a ese chat, sin intervencion manual.
Si no configura Telegram, el resto de la app funciona exactamente igual (el
envio simplemente se omite y queda registrado en la bitacora).

## 7. Generar el instalador (.exe) para llevar el programa a otra PC

Para no depender de instalar Python ni las librerias en cada laptop, el
programa se empaqueta con **PyInstaller** y se distribuye como instalador
con **Inno Setup**.

**Paso 1: generar la carpeta del programa**

```bash
venv\Scripts\pip install pyinstaller
venv\Scripts\pyinstaller.exe CAM.spec
```

Esto crea `dist\ProyectoCAM\` (unos 400 MB: incluye PyQt6, OpenCV, mediapipe
y el resto de dependencias). Pruebe que arranca con
`dist\ProyectoCAM\ProyectoCAM.exe` antes de seguir.

**Paso 2: armar el instalador**

1. Instale [Inno Setup](https://jrsoftware.org/isdl.php) (gratis) en esta PC
   de desarrollo (no en la PC destino).
2. Abra `installer.iss` con Inno Setup y pulse "Compile" (o
   `iscc installer.iss` por linea de comandos). Genera
   `installer_output\ProyectoCAM_Setup.exe`.
3. Ese `ProyectoCAM_Setup.exe` es el unico archivo que se lleva a la otra
   PC/laptop: lo ejecuta, elige una carpeta (por defecto no pide ser
   administrador) y queda listo con acceso directo en el escritorio.

**Lo que la PC destino necesita tener instalado aparte** (no viaja dentro
del `.exe` porque son componentes del sistema, no paquetes de Python):

- **ODBC Driver 18 for SQL Server** (lo usa `pyodbc` para hablar con SQL
  Server) — <https://go.microsoft.com/fwlink/?linkid=2278537>.
- **Visual C++ Redistributable x64** (lo usan OpenCV/mediapipe) —
  <https://aka.ms/vs/17/release/vc_redist.x64.exe>. La mayoria de PCs con
  Windows 10/11 actualizado ya lo tiene.

`installer.iss` tiene comentada la seccion para que el propio instalador
descargue/instale esos dos automaticamente (descomentarla una vez que
tenga los `.exe`/`.msi` oficiales guardados en una carpeta `prereqs\`).

**Base de datos:** el instalador NO incluye SQL Server. Lo recomendado es
tener **un solo** SQL Server central (puede ser SQL Server Express, gratis)
en una PC del local, y que las demas laptops solo lleven el `.exe`
conectandose por red. Por defecto la app usa autenticacion de Windows
(`Trusted_Connection`, solo sirve si la app corre en la misma PC que el SQL
Server, o en el mismo dominio). Para conectarse desde otra laptop por red,
corra una vez `db/05_acceso_red.sql` en el servidor (trae los pasos previos
que hay que hacer a mano: habilitar autenticacion mixta en el SQL Server y
el puerto 1433 en el Firewall) y defina estas variables de entorno en cada
laptop antes de abrir `ProyectoCAM.exe`:

```bash
set CAM_DB_SERVER=192.168.1.X
set CAM_DB_NAME=bd_cam_seguridad
set CAM_DB_USER=cam_app
set CAM_DB_PASSWORD=la_clave_que_puso_en_05_acceso_red.sql
```

**Actualizaciones:** el `.exe` es una foto fija del codigo al momento de
compilarlo. Cada cambio en `app/` requiere repetir el Paso 1 y el Paso 2 y
reinstalar en cada laptop; los cambios de esquema de base de datos (carpeta
`db/`) se corren aparte, una sola vez contra el SQL Server central, sin
tocar el `.exe`.

## 8. Radar de camaras (deteccion automatica en la red)

La pestana **"Radar de camaras"** busca equipos encendidos en la misma red
sin que haga falta saber su IP de antemano — el mismo mecanismo que usan
las herramientas propias de cada fabricante (SADP de Hikvision, ConfigTool
de Dahua): no agrega ninguna dependencia nueva, usa `onvif-zeep` (ya
incluido) mas la libreria estandar de Python.

**Como funciona:**
1. **WS-Discovery** (el estandar ONVIF de "busqueda" en la red): manda una
   sonda por multicast UDP y escucha durante unos segundos. Cualquier
   camara/grabador con ONVIF habilitado responde con su IP.
2. Por cada IP que respondio, se consulta ONVIF directo al equipo
   (`GetDeviceInformation`): la **marca y el modelo son reales** — el
   propio dispositivo se identifica, no es una adivinanza.
3. Se cuentan las fuentes de video del equipo (`GetVideoSources`): 1 sola
   → se estima "camara individual"; mas de 1 → se estima "grabador
   DVR/NVR" con esa cantidad de canales.
4. Con la casilla **"Escaneo completo"** marcada, ademas se revisan las 254
   direcciones de la red por el puerto 554 (RTSP) — mas lento (hasta un
   minuto) pero encuentra equipos con ONVIF apagado; estos quedan con
   marca/modelo "Desconocidos" salvo que un reintento de ONVIF directo si
   funcione.

**Algunas marcas piden usuario/clave hasta para identificarse**: a
diferencia de Hikvision/Dahua (que suelen responder `GetDeviceInformation`
sin credenciales), las camaras Tapo exigen autenticacion ONVIF incluso para
esa consulta de solo lectura — sin eso, el radar las encuentra (responden
en el puerto 554 o 2020) pero quedan como "Desconocida". Por eso la
pestana tiene campos opcionales de **usuario/clave** (use la "Cuenta de
camara" de esa marca, no la de la app del celular) que se usan en todo el
escaneo, y un boton **"Reintentar con estas credenciales"** por fila: vuelve
a consultar solo ese equipo con lo que haya en esos campos, sin repetir
todo el escaneo — util cuando un hallazgo quedo "Desconocida" por pedir
autenticacion.

**Importante — esto es deteccion "de buena fe", no infalible**: la marca y
el modelo vienen del propio equipo (confiables), pero "camara suelta" vs
"grabador" es una ESTIMACION por cantidad de canales, no una garantia en
todas las marcas/firmwares. Al seleccionar un hallazgo y pulsar **"Usar en
Camaras"** o **"Usar en NVR / DVR"**, el programa cambia de pestana con la
IP y la marca ya precargadas — pero el usuario/clave y el nombre los
confirma el usuario; el radar nunca inventa ni guarda credenciales.

## 9. Notas

- Las URLs RTSP de Patio/Estacionamiento/Pasillo en `db/03_seed.sql` son de
  ejemplo (IPs ficticias). Reemplacelas por las de camaras reales
  (Hikvision/Dahua/Tapo) en la tabla `cam.Camaras` para que transmitan en vivo.
- La contrasena de los usuarios de demo es `123456` (SHA-256 almacenado).
- La ventana principal y la vista ampliada de una zona se achican solas si
  la laptop tiene una pantalla chica (ej. 1366x768, muy comun), para que
  siempre entren completas sin tapar la barra de tareas de Windows.
