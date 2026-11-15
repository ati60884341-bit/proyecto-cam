# Instrucciones de proyecto — CAM

CAM es una app de escritorio (PySide6) para monitoreo de cámaras DVR/NVR: video en vivo, detección de sabotaje, alarmas/sirena, alertas por Telegram/WhatsApp y evidencia.

## Skills que se usan por defecto aquí

- **ponytail** — modo "dev senior perezoso": para cualquier cambio de código, el cambio más chico que resuelve la tarea completa. Nada de refactors, abstracciones o validaciones de más. Es el enfoque por defecto en este repo.
- **superpowers** (flujo de trabajo):
  - `systematic-debugging` antes de proponer un arreglo para cualquier bug (como los de sabotaje/alarma/freeze que ya se arreglaron).
  - `brainstorming` antes de construir una funcionalidad nueva o grande (ej. radar de cámaras, auditoría de contraseñas).
  - `verification-before-completion` antes de reportar cualquier tarea como terminada — probar de verdad (smoke test, app corriendo), no solo asumir.
  - `writing-plans` / `executing-plans` para cambios de varios pasos.
- **ui-ux-pro-max** — para cualquier trabajo visual: pantallas PySide6 (Inicio, Monitoreo, formularios), iconos, paleta de colores, tipografía, layout en pantalla completa.

## Nota sobre "modo caveman"

`caveman` no queda prendido por defecto en el proyecto: es un interruptor de conversación. Decir "modo caveman" o "habla simple" lo activa para esa sesión y sigue activo hasta que se pida lo contrario. No se deja siempre activo porque simplifica demasiado las explicaciones técnicas (diagnósticos de bugs, por ejemplo).
