# Carpeta `mobile/` (copia para mostrar)

Esta carpeta contiene **copias abiertas** de los 3 archivos reales del celular:

| Archivo | Qué contiene |
|---|---|
| `index.html` | La estructura de la app del celular (vistas, HUD, botones) |
| `app.css` | El estilo cyberpunk (colores, HUD, botones) |
| `app.js` | La lógica: WebSocket con la PC, huella, vinculación, PIN, historial |

## ¿Y el sistema simple?
`sistema_simple.py` ahora **usa estos archivos primero** (cuando existen aquí mismo).
Si esta carpeta se borra o se mueve el `.py` solo, el simulador vuelve a usar lo que tiene adentro en base64 (`_BUNDLE`) como antes.

## IMPORTANTE: no editar sin sincronizar
Si cambias algo aquí, el sistema seguirá usando **esta copia** (no la del repositorio).
Si quieres que el cambio llegue también al `.py` autocontenido, regenera el bundle con `regen_bundle.py` (en `C:\Users\Mugen\.local\share\opencode\shell\`) después de copiar los archivos.

## ¿Por qué existe?
Solo para que puedas **abrir y mostrar el código** (las funciones, la estructura y los estilos) cuando lo necesites, sin tener que "descongelar" el base64.
