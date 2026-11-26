# BioAccess · PC (EXE) + Celular (APK) interconectados

Sistema de terminal biométrica cyberpunk. Ahora **la PC y el celular trabajan juntos**:
la PC pide la huella, el celular la captura (con su lector real si lo tiene) y la PC
recibe el token de acceso.

```
   PC  (bioaccess.exe / bioaccess.py)          CELULAR  (BioAccessMobile.apk)
   ──────────────────────────────────          ──────────────────────────────
     interfaz Qt  ──┐                            WebView cyberpunk  ──┐
                    │  WebSocket                                │  WebSocket
                    └──────────► SERVIDOR PUENTE ◄──────────────┘
                                 0.0.0.0:8080
                    + baliza UDP 8089 (botón BUSCAR PC)
```

---

## 1. Archivos

| Archivo | Para qué sirve |
|---|---|
| `bioaccess.exe` | App de escritorio **+ servidor de enlace incluido**. Se abre con doble clic. |
| `dist/BioAccessMobile.apk` | App del celular (Android 9.0+ / API 28). |
| `bioaccess.py` | Código fuente de la app de escritorio (PyQt6). |
| `bioaccess_server.py` | Servidor puente (FastAPI/uvicorn) + baliza UDP. |
| `mobile/` | Interfaz móvil (HTML/CSS/JS). Es la misma que va dentro del APK. |
| `android/` | Proyecto Android nativo (WebView + puente Java). |
| `android/build.ps1` | Compila el APK **sin Gradle** (aapt2 + javac + d8 + zipalign + apksigner). |
| `iniciar_bioaccess.bat` | Doble clic: abre la app de escritorio (y con ella el enlace). |
| `iniciar_servidor.bat` | Solo el servidor (para usar el celular por navegador, sin EXE). |
| `instalar_apk.bat` | Instala la APK por USB con `adb` y la abre. |
| `tools/selftest_bridge.py` | Prueba automática del protocolo PC ↔ celular. |
| `tools/smoketest_desktop.py` | Prueba automática de la ventana de escritorio. |
| `tools/make_icons.py` | Genera los iconos de la APK. |
| `tools/pack_apk.py` | Empaqueta el APK final (zip estándar + classes.dex). |
| `tools/cdp_eval.py`, `tools/cdp_nav.py` | Depuración del WebView de la APK por USB (CDP). |

---

## 2. Instalar la app en el celular

**Opción A — por USB (recomendada para la primera vez)**

1. En el celular: Ajustes → Acerca del teléfono → toca 7 veces "Número de compilación".
2. Ajustes → Opciones de desarrollador → activa **Depuración USB**.
3. Conecta el cable y ejecuta `instalar_apk.bat` (o `adb install -r dist\BioAccessMobile.apk`).

**Opción B — sin cable**

1. Copia `BioAccessMobile.apk` al celular (USB, Drive, WhatsApp, etc.).
2. Ábrelo y permite "Instalar apps de origen desconocido".

> El APK está firmado con un keystore de desarrollo (`android/bioaccess.keystore`,
> contraseña `bioaccess`). No necesita Play Store.

---

## 3. Vincular PC y celular (misma red WiFi)

1. Abre `bioaccess.exe` en la PC.
2. En la barra lateral izquierda verás: `[ ENLACE: ONLINE ]` e `IP: <IP-DE-TU-PC>:8080`.

**Vinculacion por QR (sin escribir la IP):** en la PC pulsa el boton naranja VINCULAR (QR) (o la IP en la barra lateral) -> aparece un codigo QR grande + un codigo de 6 caracteres (10 min). En el celular: AJUSTES -> ESCANEAR QR y apunta a la pantalla. Si el movil no tiene camara, tambien puedes pegar el payload ioaccess://pair?... manualmente. El codigo se verifica contra el servidor antes de vincular.

**Vinculacion por USB (primera vez, sin WiFi):** conecta el cable USB (depuración USB activa). En la PC ejecuta `adb reverse tcp:8080 tcp:8080` (el instalador lo hace automáticamente si instalas por USB). En el celular: AJUSTES -> VINCULAR POR USB -> ingresa el código de 6 caracteres que muestra la PC. El celular se conecta por localhost a la PC y solicita aprobación.
3. En el celular abre **BioAccess** → pestaña **AJUSTES**:
   - Pulsa **BUSCAR PC** (descubrimiento automático por UDP), o
   - escribe la IP que muestra la PC (ej. `<IP-DE-TU-PC>`) y puerto `8080` → **GUARDAR**.
4. Cuando conecte, la PC muestra `CELULAR: <nombre del equipo>` y el celular `ENLACE: ONLINE`.

**Vinculacion por QR (sin escribir la IP):** en la PC pulsa el boton naranja VINCULAR (QR) (o la IP en la barra lateral) -> aparece un codigo QR grande + un codigo de 6 caracteres (10 min). En el celular: AJUSTES -> ESCANEAR QR y apunta a la pantalla. Si el movil no tiene camara, tambien puedes pegar el payload ioaccess://pair?... manualmente. El codigo se verifica contra el servidor antes de vincular.

### Flujo de uso

| Paso | PC | Celular |
|---|---|---|
| 1 | Botón **PEDIR HUELLA AL CELULAR** | Suena/vibra y aparece "SOLICITUD DE LA PC" |
| 2 | El HUD muestra "CELULAR" y el % de avance | Mantén pulsado el sensor (o usa el lector real si el móvil tiene huella) |
| 3 | `✓ HUELLA VALIDADA. ACCESO CONCEDIDO. TOKEN 44D47F97554D` | `✓ VALIDADO` + registro en HISTORIAL |
| 4 | El token queda en el historial de ambos | El historial se guarda en el teléfono |

Si no hay celular conectado, la PC avisa `⚠ NO HAY CELULAR VINCULADO` (no es un error).

---

## 4. Firewall de Windows

La primera vez Windows preguntará por `bioaccess.exe`: **permitir en redes privadas**.
Si no aparece el aviso, abre estos puertos (PowerShell **como administrador**):

```powershell
New-NetFirewallRule -DisplayName "BioAccess TCP 8080" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "BioAccess UDP 8089" -Direction Inbound -Protocol UDP -LocalPort 8089 -Action Allow -Profile Private
```

---

## 5. Uso sin instalar la APK

El servidor también sirve la interfaz móvil por HTTP. Desde el navegador del celular:

```
http://IP_DE_LA_PC:8080/mobile/index.html
```

(o simplemente `http://IP_DE_LA_PC:8080`). Sirve para probar; la APK añade vibración,
huella real, descubrimiento automático y arranque sin escribir la URL.

---

## 6. Recompilar

**APK** (no requiere Gradle ni Android Studio, solo el SDK):

```powershell
powershell -ExecutionPolicy Bypass -File android\build.ps1
# salida: dist\BioAccessMobile.apk (firmada)
```

**EXE** (PyInstaller, incluye el servidor y la carpeta `mobile/`):

```powershell
python -m PyInstaller --noconfirm --clean bioaccess.spec
# salida: dist\bioaccess.exe
```

**Pruebas**

```powershell
$env:PYTHONIOENCODING="utf-8"
python tools\selftest_bridge.py      # protocolo PC <-> celular
python tools\smoketest_desktop.py    # ventana Qt en modo offscreen
```

---

## 7. Protocolo (para extenderlo)

| Mensaje | Dirección | Contenido |
|---|---|---|
| `hello` / `hello_ack` | ambos | identificación, versión, peers |
| `peer_joined` / `peer_left` | servidor → todos | quién entra o sale |
| `scan_request` | PC → servidor → celular | `{id, ttl, from}` |
| `scan_pending` | servidor → PC | solicitud aceptada/en cola |
| `scan_progress` | celular → PC | `{id, progress: 0..1}` |
| `scan_result` | celular → PC | `{id, ok, token?, error?, device}` |
| `scan_cancel` | cualquiera | cancela la solicitud |
| `access_granted` / `access_denied` | servidor → celular | confirmación final |

- HTTP: `GET /api/hello`, `GET /api/state`, `GET /api/events`, `POST /api/request?ttl=30`.
- WebSocket: `ws://IP:8080/ws?role=pc|phone&device=<nombre>`.
- Descubrimiento: UDP `8089`, enviar `BIOACCESS_DISCOVER`, responde JSON `{name,ip,port,version}`.

---

## 8. Problemas típicos

| Síntoma | Causa / solución |
|---|---|
| `ENLACE: OFFLINE` en la PC | El puerto 8080 está ocupado por otro programa, o el firewall lo bloquea. |
| El celular no encuentra la PC ("BUSCAR PC") | Redes distintas (una en WiFi y otra en datos), o el router aísla clientes. Escribe la IP a mano. |
| `NO HAY CELULAR VINCULADO` | La APK no está conectada; revisa IP/puerto en AJUSTES. |
| La huella real no aparece | El móvil no tiene lector; usa mantener pulsado el sensor en pantalla. |
| Cambié de red WiFi | La IP de la PC cambia: vuelve a pulsar BUSCAR PC. |
