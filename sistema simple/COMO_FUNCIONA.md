# CÓMO FUNCIONA `sistema_simple.py` — explicado con el CÓDIGO y para qué es cada línea

> Este es el documento TÉCNICO COMPLETO. En él está **el código real del archivo**, explicado
> bloque por bloque y casi línea por línea, indicando **qué pasa si se cambia o se borra cada parte**.
>
> - Cómo funciona la conexión PC ↔ celular (código del servidor y de los clientes): `COMO_FUNCIONA_CONEXION.md`

---

## 0. La regla de oro (antes que nada)

`sistema_simple.py` **NO es un sistema nuevo** y **NO es una copia distinta**.
Es el **mismo sistema BioAccess real**, guardado como una "copia congelada" dentro de
un solo archivo `.py`, junto al código que se encarga de sacarlo de su interior y arrancarlo.

Por eso:

- La apariencia y el flujo son **idénticos** a `bioaccess.py` + `bioaccess_server.py` + `mobile/`.
- Si editas un archivo del proyecto real (`bioaccess.py`, etc.), **el simulador seguirá viendo la versión vieja** del `_BUNDLE` hasta que lo regeneres (ver sección 6).
- El simulador **no es la APK** ni el EXE: es el mismo código abriendo ventanas en esta PC.

---

## 1. El código completo (con `_BUNDLE` resumido)

Las líneas larguísimas del `_BUNDLE` (la base64) se reducen a una sola línea
cada una para que se pueda leer (`…`). El resto es **el código exacto** del archivo.

```python
# -*- coding: utf-8 -*-                                       # (1) Le dice a Python que el archivo viene en UTF-8 (tildes)
"""                                                            # (2) Docstring: explicar qué es y cómo usarlo
sistema_simple.py  -  BioAccess completo en UNA sola PC (archivo unico e independiente)

Este es un archivo AUTOCONTENIDO: no necesita bioaccess.py ni la carpeta mobile/.
Al ejecutarse, extrae los modulos reales del proyecto en una carpeta temporal
y los usa tal cual (apariencia y flujo 100% identicos al sistema real).

Uso:
  - En Spyder: abrir este archivo y pulsar Run (F5).
  - En consola: python sistema_simple.py
"""
import sys, os, base64, tempfile, subprocess                # (3) Herramientas básicas: interfaz, sistema, base64, temp, pip

# --- 1) Auto-instalacion de dependencias ---               # (4) BLOQUE 1: instalar lo que falta
_REQUIRED = ["PyQt6", "PyQt6-WebEngine", "fastapi", "uvicorn[standard]",
             "websockets", "qrcode"]                        # (5) 6 paquetes imprescindibles

def _ensure_deps():                                         # (6) Función que instala lo que falta
    modmap = {"pyqt6": "PyQt6", "pyqt6_webengine": "PyQt6.QtWebEngineWidgets",
              "fastapi": "fastapi", "uvicorn": "uvicorn",
              "websockets": "websockets", "qrcode": "qrcode"}   # (7) nombre pip -> módulo de importación
    for pkg in _REQUIRED:                                   # (8) Repite por cada paquete
        mod = pkg.split("[")[0].replace("-", "_").lower()    # (9) "uvicorn[standard]" -> "uvicorn"
        import_name = modmap.get(mod, mod)                 # (10) Busca el nombre de módulo, si no está usa el mismo
        try:
            __import__(import_name.split(".")[0])           # (11) Intenta importar la parte principal (p.ej. "PyQt6")
        except ImportError:                                 # (12) Si falta…
            print("[auto-install] instalando " + pkg + " ...")   # (13) Aviso por consola
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg,
                                  "--quiet", "--disable-pip-version-check"])   # (14) pip install automático

_ensure_deps()                                             # (15) ¡Se llama INMEDIATAMENTE al abrir el archivo!

# --- 2) Extraer bundle embebido ---                        # (16) BLOQUE 2: sacar los 5 archivos reales de adentro
_BUNDLE = {                                                # (17) Diccionario: clave = ruta, valor = contenido en base64
    'bioaccess.py': "…(base64 del archivo bioaccess.py real, ~129 KB de texto)…",      # (18) Terminal de la PC
    'bioaccess_server.py': "…(base64 del servidor real, ~44 KB de texto)…",            # (19) Puente PC↔celular
    'mobile/index.html': "…(base64 del HTML real del móvil)…",                          # (20) Pantalla del "celular"
    'mobile/app.css': "…(base64 del CSS real del móvil)…",                              # (21) Estilos del "celular"
    'mobile/app.js': "…(base64 del JavaScript real del móvil)…",                        # (22) Lógica del "celular"
}

_EXTRACT_DIR = os.path.join(tempfile.gettempdir(), "bioaccess_simple_bundle")   # (23) Carpeta: %TEMP%\bioaccess_simple_bundle
os.makedirs(_EXTRACT_DIR, exist_ok=True)                                      # (24) Crearla si no existe
_HERE = os.path.dirname(os.path.abspath(__file__))                            # (25) Carpeta donde está ESTE archivo .py
for rel, data in _BUNDLE.items():                                             # (26) Para cada uno de los 5 archivos…
    dst = os.path.join(_EXTRACT_DIR, rel.replace("/", os.sep))                 # (27) Construye la ruta destino (con \ en Windows)
    os.makedirs(os.path.dirname(dst), exist_ok=True)                           # (28) Crea las subcarpetas (mobile/) si falta
    local = os.path.join(_HERE, rel.replace("/", os.sep))                      # (29) MIRA AL LADO: ¿existe el archivo junto al .py?
    if os.path.exists(local):                                                  # (30) Si existe copia local abierta…
        with open(local, "rb") as fin, open(dst, "wb") as fout:                # (31) …cópialo tal cual
            fout.write(fin.read())                                             # (32) (copia local SIEMPRE gana)
    else:                                                                      # (33) Si no existe junto al .py…
        with open(dst, "wb") as f:
            f.write(base64.b64decode(data))                                    # (34) …decodífícalo del base64 del _BUNDLE

if _EXTRACT_DIR not in sys.path:                                             # (35) BLOQUE 3: preparar la importación
    sys.path.insert(0, _EXTRACT_DIR)                                         # (36) Poner la carpeta extraída la PRIMERA en la lista de Python

# --- 3) Importar sistema real extraido ---                                  # (37) Ahora sí importar
import bioaccess                                                              # (38) ¡EL REAL! (el que acabamos de extraer/copiar)
import json                                                                   # (39) Para leer respuestas JSON (vincular)
import urllib.request                                                         # (40) Para llamadas HTTP GET al servidor
import urllib.parse                                                           # (41) Para escapar parámetros de URL (quote)
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton   # (42) Interfaz gráfica
from PyQt6.QtCore import QUrl, QTimer                                        # (43) Dirección URL y temporizador
from PyQt6.QtWebEngineWidgets import QWebEngineView                          # (44) Navegador embebido (para simular el móvil)

def main():                                                                  # (45) BLOQUE 4: toda la app vive dentro de main()
    app = QApplication(sys.argv)                                             # (46) Aplicación gráfica Qt
    app.setApplicationName("BioAccess Simulador")

    pc = bioaccess.SuperCustomBio()                                          # (47) ¡Crea la TERMINAL GRANDE REAL!
    pc.setWindowTitle("BioAccess - Terminal PC (simulador)")                 # (48) Cambia solo el título de la ventana
    pc.show()                                                                # (49) Muéstrala

    port = getattr(pc, "server_port", 8080) or 8080                          # (50) Puerto real del servidor embebido dentro de la terminal
    base = "http://127.0.0.1:%d" % port                                      # (51) URL base del servidor en ESTA PC

    mob = QMainWindow()                                                       # (52) Ventana del "celular simulado"
    mob.setWindowTitle("BioAccess Mobile (simulador PC)")                    # (53) Título
    mob.resize(420, 780)                                                     # (54) Tamaño de celular
    view = QWebEngineView()                                                  # (55) Navegador embebido (= APK del celular)
    mob.setCentralWidget(view)                                               # (56) Pone el navegador como contenido principal

    # ---------------- Ventana auxiliar del simulador ----------------       # (57) BLOQUE 5: ayuda de la simulación (NO es BioAccess)
    # No forma parte de BioAccess: ayuda a vincular el móvil simulado
    # (sin cámara ni huella reales). La vinculación sigue el flujo
    # normal: código -> /api/pair/verify -> ACEPTAR en la PC.
    helper = QMainWindow()                                                    # (58) Ventana extra cyberpunk
    helper.setWindowTitle("// AYUDA SIMULADOR (no es BioAccess)")             # (59) DEJA CLARO que no es BioAccess
    helper.setFixedSize(390, 250)                                             # (60) Tamaño fijo pequeño
    hw = QWidget()
    hw.setStyleSheet("background:#050b18; color:#b8e4ff; font-family:Consolas,monospace;")  # (61) Estilo cyberpunk
    lay = QVBoxLayout(hw)                                                     # (62) Layout vertical
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(8)
    titulo = QLabel("// SIMULADOR - VINCULACION EXPRESS")                     # (63) Título de la ayuda
    titulo.setStyleSheet("color:#22d3ff; font-size:13px; font-weight:bold; letter-spacing:2px;")
    lay.addWidget(titulo)
    info = QLabel(                                                            # (64) Instrucciones "pulsa VINCULAR…"
        "El movil del simulador usa el mismo codigo que la APK.\n"
        "Para que la PC le pida la huella debe vincularse UNA vez:\n"
        "1) Pulsa VINCULAR.  2) En la PC pulsa ACEPTAR."
    )
    info.setWordWrap(True)                                                    # (65) Texto se ajusta al ancho
    info.setStyleSheet("color:#8fb8d8; font-size:11px; line-height:150%;")
    lay.addWidget(info)
    btn = QPushButton("1)  VINCULAR CELULAR (1 CLIC)")                        # (66) EL BOTÓN DE VINCULAR (la parte clave)
    btn.setFixedHeight(38)
    btn.setStyleSheet(                                                        # (67) Botón cyan con borde
        "QPushButton{background:#0b2a3a; border:1px solid #22d3ff; border-radius:6px;"
        "color:#22d3ff; font-weight:bold; font-size:12px; letter-spacing:1px;}"
        "QPushButton:hover{background:#10364a;}"
    )
    lay.addWidget(btn)
    status = QLabel("... cargando movil ...")                                 # (68) Etiqueta de estado (VINCULADO / sin vincular)
    status.setWordWrap(True)
    status.setStyleSheet("color:#ff9a1f; font-size:11px;")
    lay.addWidget(status)
    helper.setCentralWidget(hw)                                               # (69) Activación de la ventana auxiliar
    helper.show()

    state = {"phase": 0, "did": None, "paired": None, "sent": False}          # (70) Memoria de la simulación (fase, deviceId, ¿vinculado?)

    def set_status(txt, ok=None):                                             # (71) Pinta el estado: verde/rojo/naranja según "ok"
        color = "#2dffb0" if ok is True else ("#ff3b5c" if ok is False else "#ff9a1f")
        status.setStyleSheet("color:%s; font-size:11px;" % color)
        status.setText(txt)

    def _read_state():                                                        # (72) Lee la memoria del "celular" (localStorage) con JS
        js = (                                                                # (73) JavaScript: lee bioaccess_mobile_cfg_v2
            "(function(){try{var c=JSON.parse(localStorage.getItem('bioaccess_mobile_cfg_v2')||'{}');"
            "return JSON.stringify({d:c.deviceId||'',t:!!c.token});}catch(e){return '{}'}})()"
        )

        def cb(res):                                                          # (74) ¿Qué hacer cuando llegue la respuesta?
            try:
                o = json.loads(res or "{}")
            except Exception:
                o = {}
            state["did"] = o.get("d") or state["did"]                         # (75) Guardar el deviceId del celular
            paired = bool(o.get("t"))                                         # (76) ¿Tiene token guardado? → vinculado
            state["paired"] = paired
            if paired:
                state["sent"] = False
                set_status("VINCULADO - la PC ya puede pedir la huella.", True)
            elif not state["sent"]:
                set_status("Sin vincular - pulsa VINCULAR.", None)

        view.page().runJavaScript(js, cb)                                     # (77) Lanzar el JS dentro del navegador embebido

    def _on_load_finished(ok):                                                # (78) Se dispara cuando termina de cargar la página del móvil
        if state["phase"] == 0:                                               # (79) Fase 0: "la página acaba de cargar por primera vez"
            state["phase"] = 1
            fix = (                                                           # (80) JS que ARREGLA la configuración del "celular":
                "(function(){try{var k='bioaccess_mobile_cfg_v2';"            #    la PC del móvil la pone en 127.0.0.1 (misma máquina)
                "var c=JSON.parse(localStorage.getItem(k)||'{}');"
                "c.ip='127.0.0.1';c.port='%d';" % port +
                "localStorage.setItem(k,JSON.stringify(c));return 'ok';}"
                "catch(e){return String(e);}})()"
            )

            def _done(_):                                                     # (81) Después del arreglo…
                view.reload()                                                #     recargamos la página para que reintente con la IP arreglada

            view.page().runJavaScript(fix, _done)
        elif state["phase"] == 1:                                             # (82) Fase 1: segundo recargado → ya podemos leer el estado
            state["phase"] = 2
            _read_state()

    view.loadFinished.connect(_on_load_finished)                             # (83) Conectar el evento "página cargada" a _on_load_finished
    view.setUrl(QUrl("http://127.0.0.1:%d/mobile/index.html" % port))        # (84) Cargar el móvil REAL (el mismo que la APK)
    mob.show()                                                               # (85) Mostrar la ventana del celular

    def _pair():                                                             # (86) LA FUNCIÓN DEL BOTÓN VINCULAR
        did = state.get("did")
        if not did:
            set_status("Espera a que cargue el movil...", False)             # (87) Aún no terminó de cargar
            return
        try:
            import bioaccess_server as bs                                    # (88) Importar el servidor real
            code = bs.pair_code(refresh=True)                               # (89) Pedir el código de 6 caracteres del QR
            url = (                                                           # (90) Construir la llamada a /api/pair/verify
                base + "/api/pair/verify?code=" + urllib.parse.quote(code)
                + "&device=" + urllib.parse.quote("Navegador")
                + "&device_id=" + urllib.parse.quote(did)
            )
            with urllib.request.urlopen(url, timeout=5) as r:                 # (91) Llamada HTTP al servidor (como si lo hiciera la APK)
                data = json.loads(r.read().decode())
            if data.get("ok"):                                                # (92) ¿El servidor la aceptó?
                state["sent"] = True
                set_status(
                    "SOLICITUD ENVIADA.\n"
                    "En la PC se abre 'VINCULAR NUEVO CELULAR'\n"
                    "-> pulsa ACEPTAR.  Codigo: " + code,
                    True,
                )                                                              # (93) ¡Listo! En la PC aparece el diálogo ACEPTAR
            else:
                set_status("Error del servidor: " + str(data.get("reason")), False)
        except Exception as e:
            set_status("Error: %s" % e, False)

    btn.clicked.connect(_pair)                                               # (94) Conectar el botón a _pair

    poll = QTimer()                                                          # (95) Temporizador para leer el estado cada 1.5 s
    poll.timeout.connect(_read_state)
    poll.start(1500)

    def _quit():                                                            # (96) Limpieza al cerrar: apagar el servidor embebido
        try:
            if getattr(pc, "server", None):
                pc.server.stop()
        except Exception:
            pass
        app.quit()

    pc.destroyed.connect(_quit)                                              # (97) Si se cierra la terminal PC, se cierra todo
    sys.exit(app.exec())                                                     # (98) Arrancar el bucle gráfico (¡aquí el archivo "espera" hasta que cierres todo!)

if __name__ == "__main__":                                                    # (99) Solo si lo ejecutas (no si lo importan)
    main()                                                                   # (100) Y finalmente, arrancar
```

---

## 2. Bloque por bloque, y qué pasa si lo tocas

### Bloque 1 — Auto-instalación (líneas 15–33)

| Parte | Qué hace |
|---|---|
| `_REQUIRED` | Lista los 6 paquetes imprescindibles. |
| `modmap` | Traduce "nombre de `pip`" → "nombre de `import`" (`PyQt6-WebEngine` → `PyQt6.QtWebEngineWidgets`). |
| `_ensure_deps()` | Intenta `import` de cada paquete; si falla, lo instala con `pip install` automáticamente. |
| `_ensure_deps()` al momento | **Importante**: se ejecuta INMEDIATAMENTE, antes de extraer el bundle. Si algo falta, lo instala solo. |

**¿Qué pasa si lo modificas?**

| Cambio | Consecuencia |
|---|---|
| Borrar `_ensure_deps()` | En una PC nueva que no tenga las cosas instaladas, el archivo **falla al abrir con ImportError**. |
| Quitar un paquete de `_REQUIRED` | Ese paquete NO se instalará solo; el usuario tendrá que instalarlo a mano. |
| Cambiar `--quiet` | El usuario verá el texto de instalación de pip (solo cambia estética de la consola). |

### Bloque 2 — El `_BUNDLE` (líneas 36–42)

| Parte | Qué hace |
|---|---|
| Dict `{ruta: base64}` | Los 5 archivos reales del sistema, codificados para vivir dentro del `.py`. |
| Las 5 claves | `bioaccess.py`, `bioaccess_server.py`, `mobile/index.html`, `mobile/app.css`, `mobile/app.js` |
| Base64 | A–Z a–z 0–9 `+` `/` `=`: texto seguro para guardarlo dentro de Python sin que se rompa por comillas, tildes o CRLF. |

**¿Qué pasa si lo modificas?**

| Cambio | Consecuencia |
|---|---|
| Desordenar una coma del dict | **Error de sintaxis** → el archivo ni arranca. |
| Borrar una clave (p.ej. `mobile/app.js`) | El simulador abre pero **el móvil se ve muerto o en blanco**. |
| Editar los archivos junto al .py (carpeta `sistema simple\`) | **Funciona** (gana la copia local, ver Bloque 3). |
| Editar SOLO el base64 a mano | ❌ **Nunca.** Base64 editado a mano se corrompe. Se regenera con `regen_bundle.py`. |

### Bloque 3 — Extracción a una carpeta temporal (líneas 44–59)

| Parte | Qué hace |
|---|---|
| `_EXTRACT_DIR` | `%TEMP%\bioaccess_simple_bundle` — carpeta temporal donde se escriben los 5 archivos. |
| `_HERE` | **Carpeta donde vive ESTE .py** (no la de los archivos del proyecto). |
| Bucle `for rel, data in _BUNDLE.items()` | Por cada archivo: crea ruta destino, crea subcarpetas (`mobile/`) y escribe el contenido. |
| `if os.path.exists(local)` | **¡Novedad clave!** Si hay una copia abierta al lado (ej. `sistema simple\bioaccess.py`), **la copia local gana**. Si no, decodifica el base64 del bundle. |
| `sys.path.insert(0, _EXTRACT_DIR)` | Caja fuerte: Python buscará los módulos reales DENTRO de la carpeta extraída, no en el repositorio. |

**¿Qué pasa si lo modificas?**

| Cambio | Consecuencia |
|---|---|
| Borrar el `_EXTRACT_DIR` | El archivo **no puede crear los .py** → no arranca. |
| Borrar `sys.path.insert` | Python importa `bioaccess` del repositorio en vez del extraído (o lo encuentra y luego tendrías un sistema de 2 versiones distintas mezcladas). |
| Cambiar la copia local en `sistema simple\` a algo roto | La función **copia el error** a la carpeta temporal → el simulador arranca roto. |
| Meterse los archivos al `_EXTRACT_DIR` y olvidarse de regenerar el bundle | En OTRA PC (sin las copias locales) **vuelve a ser el de antes**. |

### Bloque 4 — Importar el sistema real (líneas 61–68)

| Parte | Qué hace |
|---|---|
| `import bioaccess` | **El real.** Crea la terminal de la PC (`SuperCustomBio`) con servidor embebido en el puerto 8080 (o el libre). |
| `QWebEngineView` | Navegador embebido: es el "celular" (carga `mobile/index.html` exactamente igual que la APK). |
| `json`, `urllib.request`, `urllib.parse` | Para la vinculación del móvil simulado (Llamada HTTP `/api/pair/verify`). |

### Bloque 5 — `main()` y la app (líneas 70–224)

**Las 3 ventanas que aparecen:**

1. `pc = bioaccess.SuperCustomBio()` → **la terminal de la PC REAL** (fondo cyberpunk, HUD, botón de huella).
2. `mob` → **el "celular" simulado** (420×780, navegador cargando `/mobile/index.html` del servidor que arrancó la terminal).
3. `helper` → **la AYUDA SIMULADOR** (cyberpunk): solo existe en el simulador; la APK no la tiene.

| Función / línea | Qué hace | Qué pasa si se cambia o borra |
|---|---|---|
| `port = getattr(pc, "server_port", 8080)` | Descubre el puerto real (8080 o el libre si 8080 está ocupado). | Borrarlo → la ventana móvil no encuentra el servidor. |
| `view.setUrl(QUrl("http://127.0.0.1:%d/mobile/index.html" % port))` | La pantalla del "celular" carga el móvil real. | Cambiar el puerto → el móvil no encuentra al servidor. |
| `state` dict | Memoria del simulador (fase, deviceId, ¿vinculado?). | Borrarlo → las funciones `_read_state`, `_pair`, `_on_load_finished` rompen. |
| `_read_state()` | Pide al móvil (via JS) el `localStorage` `bioaccess_mobile_cfg_v2`: deviceId y si tiene token → pinta VINCULADO. | Borrarlo → el botón "VINCULADO" nunca se muestra. |
| `_on_load_finished()` | Al cargar la página del móvil: **fase 0** = arregla la IP del móvil a 127.0.0.1 y recarga; **fase 1** = lee el estado. | Borrar la fase 0 → el móvil intenta conectar a la IP vieja (<IP-DE-TU-PC>) y falla. |
| `_pair()` | **El botón VINCULAR**: llama `/api/pair/verify` como si fuera la APK → la PC abre el diálogo ACEPTAR → al aceptar, la PC da el token. | Borrado → no se puede vincular desde el simulador. |
| `poll = QTimer()` cada 1500 ms | Cada 1.5 s vuelve a mirar si el móvil ya tiene token. | Borrarlo → el estado se queda desactualizado |
| `pc.destroyed.connect(_quit)` | Cerrar la terminal PC apaga el servidor embebido y cierra todo. | Borrarlo → el servidor queda vivo en un hilo invisible (proceso zombie). |
| `if __name__ == "__main__"` | Ejecutar la app solo si se lanza el archivo (no si alguien lo importa). | Borrado → al importarlo desde consola/otro archivo arranca solo una app gráfica. |

---

## 3. Diagrama mental de qué pasa cuando pulsas F5

```
F5
 │
 ├─► 1) _ensure_deps()  → ¿PyQt6, fastapi, uvicorn…? Si falta algo lo instala solo.
 ├─► 2) Copia las 5 piezas reales (local > bundle) a %TEMP%\bioaccess_simple_bundle
 ├─► 3) sys.path ← la carpeta extraída
 ├─► 4) import bioaccess (¡la versión REAL que acabamos de copiar!)
 ├─► 5) main()
 │     ├─► SuperCustomBio()                  → Ventana 1: TERMINAL PC + servidor (puerto real)
 │     ├─► QWebEngineView → /mobile/index.html → Ventana 2: EL "CELULAR" (420x780)
 │     └─► Ventana 3: // AYUDA SIMULADOR
 │
 └─► Tú pulsas "1) VINCULAR CELULAR (1 CLIC)"
       ├─► _pair() → GET /api/pair/verify?code=XXXX → el servidor crea "pending"
       ├─► La terminal PC detecta la pendiente (poll cada 2 s) → diálogo ACEPTAR
       ├─► Tú pulsas ACEPTAR en la PC → /api/pair/decision → token + registro trusted_devices.json
       ├─► El "celular" recibe el token → lo guarda → "VINCULADO"
       └─► La PC ya puede pedir huella → huella → ACCESO CONCEDIDO
```

---

## 4. Preguntas de defensa de proyecto (respuestas listas)

| Si te preguntan… | Respuesta |
|---|---|
| ¿Y por qué no es un EXE? | Porque un EXE es el paso **siguiente** (PyInstaller). Aquí demuestro el código puro corriendo en una sola PC. |
| ¿Dónde está el código de verdad? | En los 5 archivos que están dentro del `_BUNDLE` (o junto al `.py` en `sistema simple\`). Este archivo es solo el **lanzador**. |
| ¿Por qué base64? | Porque meter texto de Tildes/EOF/comillas dentro de un string de Python rompe; base64 es el único lenguaje que no se rompe. |
| ¿Puede usar un archivo que no sea base64? | En realidad **sí**: las copias locales lo pisan. Si están junto al .py, ni hace falta el base64 para desarrollar. |
| ¿El simulador graba en el registro de Windows o en el Vault? | No; usa `%TEMP%` (se puede borrar sin miedo) y `%APPDATA%\BioAccess` (ahí viven `pc_identity.json`, `trusted_devices.json`, `bioaccess_events.json`, `bioaccess_config.json`). |
| ¿Y el QR / huella rigen igual? | Sí: el código pasa por el mismo camino que la APK (misma llamada `/api/pair/verify`, mismo flujo de ACEPTAR). |
| ¿Por qué la ayuda dice "no es BioAccess"? | Porque la APK **no tiene** esa ventana; es solo un atajo para quien no tiene cámara. |

---

## 5. Regenerar el `_BUNDLE`

Cada vez que cambies los archivos reales del proyecto:

```
python "C:\Users\Mugen\.local\share\opencode\shell\regen_bundle.py"
```

(escribe el dict `_BUNDLE` a partir de `bioaccess.py`, `bioaccess_server.py`, `mobile\index.html`,
`mobile\app.css`, `mobile\app.js` del proyecto raíz).

Sin regenerar, en otra PC el simulador **vuelve al sistema viejo**.

---

## 6. Cosas que NO hace (para que no prometa de más)

- No instala nada en el sistema (no es instalador; sus únicas escrituras son `%TEMP%` y `%APPDATA%\BioAccess`).
- No compila ni empaqueta (no es PyInstaller).
- No configura USB ni activa ADB.
- No puede vincularse desde otra red (usa 127.0.0.1 por defecto).
- No actualiza el `_BUNDLE` solo.
- No añade huella real (es un botón de mantener pulsado).
