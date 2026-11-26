# CÓMO FUNCIONA EL SISTEMA DE CONEXIÓN (PC ↔ CELULAR) — explicado paso a paso

> Este archivo explica **solo la conexión** entre la terminal de la PC y el móvil:
> los cables por los que viajan los datos, qué archivo vivo toca y qué pasa
> si cambias algo. Está pensado para quien **no sabe nada** del tema.
>
> Si quieres la explicación del archivo simulador `sistema_simple.py`: ver `COMO_FUNCIONA.md`.
> Archivo del servidor real (con su código): `sistema simple\bioaccess_server.py`.
> Archivo de la terminal real (con su código): `sistema simple\bioaccess.py`.

---

## 1. La analogía de la vida real

Piensa en la conexión como **un edificio con 2 recepcionistas y un portero**:

- **La PC** (el jefe dentro del edificio) — pide cosas ("quien eres", "pon huella").
- **El servidor** (la central telefónica del edificio) — recibe los mensajes, decide a
  quién se los pasa y anota todo en un registro. **Está dentro de la propia PC.**
- **El celular** (el visitante) — responde con su información.

Ninguno de los dos se habla directo; **todo pasa por la central**:

```
┌───────────┐                          ┌──────────────────┐                          ┌───────────┐
│  PC       │  WebSocket (línea abierta)│  bioaccess_server│  WebSocket (línea abierta)│  CELULAR  │
│ (Terminal)│ ◄──────────────────────► │   (puerto 8080)  │ ◄──────────────────────► │   (APK o   │
│           │                           │                  │                            │   navegador)│
└───────────┘                          └──────────────────┘                          └───────────┘
```

La PC y el móvil nunca se escriben mutuamente por bytes sueltos: **se mandan TARJETAS JSON**.

Una tarjeta se ve así:

```json
{"type": "scan_request", "id": "a1b2c3d4", "ttl": 30, "from": "Terminal PC"}
```

El servidor mira la palabra `type` y sabe qué es: `scan_request` = "la PC pide huella".

---

## 2. Los 4 "caminos" por donde viajan los datos

| Camino | Puerto | Dirección típica | Qué se manda | ¿Cuándo se usa? |
|---|---|---|---|---|
| **HTTP (página web)** | 8080 (`/mobile/...`) | Servidor → celular | Los archivos de la app (HTML/CSS/JS) | Cada vez que el celular abre la app |
| **HTTP (API)** | 8080 (`/api/...`) | Celular/PC → servidor | Peticiones cortas (`preguntando un dato`) | Vinculación, consultar la lista de vinculados |
| **WebSocket** | 8080 (`/ws`) | Ambos sentidos, línea abierta | Tarjetas JSON en vivo | `scan_request`, `hello_ack`, `peer_joined`, `access_granted`… |
| **UDP (descubrimiento)** | **8089** | Celular → servidor | `BIOACCESS_DISCOVER` → **responde IP:puerto** | El móvil encuentra la PC sin QR |

(UDP = un grito por el edificio: "¿quién es BioAccess?". El servidor responde con su nombre, IP y puerto.)

---

## 3. Las CONSTANTES MÁGICAS (no tocar salvo que sepas lo que haces)

| Constante | Valor | Por qué no se cambia a la ligera |
|---|---|---|
| Puerto HTTP/WS | **8080** (o el siguiente libre) | Móvil y PC deben usarlo igual. Si cambias solo en un lado, el otro no lo encuentra. |
| Puerto UDP | **8089** | El móvil pregunta por este número; no es configurable desde el APK sin recompilar. |
| `DISCOVERY_MAGIC` | `"BIOACCESS_DISCOVER"` | El servidor solo responde a mensajes que empiecen por este texto. |
| Palabra mágica del localStorage | **`bioaccess_mobile_cfg_v2`** | Toda la configuración del celular vive bajo esta clave. |
| Esquema del deep link | `bioaccess://pair?ip=...&port=...&code=...` | El APK abre este enlace con el QR; si cambia, rompe el QR. |
| Roles de conexión | **`pc`** y **`phone`** | El servidor asigna permisos distintos según el rol. Nada más existe. |
| `PAIR_ALPHABET` | `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` (sin I/O/0/1) | Evita caracteres confundibles al leer el código a mano. |
| `PAIR_TTL` | 600 (10 minutos) | Tiempo de vida del código del QR. |
| `REQUEST_TTL` | 30 segundos | Tiempo de vida de una petición de huella sin responder. |
| `MAX_EVENTS` | 400 | Límite de eventos guardados en `bioaccess_events.json`. |

---

## 4. La vinculación, contada como la verías en pantalla

### Escenario A (QR desde la terminal)

```
PC:                                           Celular:                          Servidor:
abre “VINCULAR” → dibuja QR
     con código 6 letras + payload
     bioaccess://pair?ip=...&code=...
                          ──── escanea ────►
                                         GET /api/pair/verify?code=ABC123&device=Celular&device_id=dev-123
                                                                            ── crea "pending" con id rid
                                                                            ── avisa a la PC: "pair_request rid…"
                                         ◄── {"ok": true, "pending": true, "request_id": rid}
     ◄───────────────── pair_request (WS)
     2 segundos después: diálogo ACEPTAR / RECHAZAR
     pulsa ACEPTAR
     POST /api/pair/decision?request_id=rid&accept=true
                                                                            ── genera token
                                                                            ── guarda en trusted_devices.json
                                         ◄────────────── pair_result {ok:true, token}
     VINCULADO ✅
```

### Escenario B (código escrito a mano / AYUDA SIMULADOR)

- El celular (o el 1 clic de la ventana AYUDA SIMULADOR) llama a la misma URL `/api/pair/verify`
  con el código del QR (o el que la ventana leyó del servidor).
- El resto es idéntico: el servidor crea el "pending", la PC ve el diálogo, ACEPTAR → token.

### ¿Qué pasa en la VERDAD cuando "ACEPTAR"?

1. El servidor genera un **token** (64 caracteres aleatorios) con `secrets.token_hex(32)`.
2. Guarda en `%APPDATA%\BioAccess\trusted_devices.json` un registro con `device_id`, `device_name`, `token`, `paired_at`.
3. Se lo manda al celular vía WebSocket en la tarjeta `pair_result {"ok": true, "token": …}`.
4. El celular **guarda** el token bajo `bioaccess_mobile_cfg_v2` en su `localStorage`.
5. Cada reconexión del móvil lleva `?role=phone&device_id=…&token=…` y el servidor responde `peer.trusted = True` si coinciden.

---

## 5. Cada FUNCIÓN del servidor (`bioaccess_server.py`), para qué sirve y qué pasa si se cambia

> Tamaño del archivo: ~864 líneas. Aquí está explicado lo IMPORTANTE con los números de línea
> donde vive (tal como está en el disco hoy).

### 5.1 Utilidades y ficheros (líneas 76–102)

| Función | Qué hace | ¿Qué pasa si se cambia/borra? |
|---|---|---|
| `_load_json(path, default)` | Lee un JSON del disco; si algo falla, devuelve `default` nunca rompe. | Borrarlo → el sistema **muere al arrancar** (no puede leer identidad ni vinculados). |
| `_save_json(path, data)` | Escribe un JSON bonito en disco. | Romperlo → el servidor **no recuerda vinculados** (pierde la vinculación al reiniciar). |
| `pc_identity()` | Crea/carga `pc_identity.json` con `pc_id` y `pc_secret` (únicos de la PC). | Borrar → perder la identidad de la PC (el móvil no sabrá si habla con la misma PC). |
| `trusted_devices()` | Carga la lista de celulares vinculados; si el formato es inválido, devuelve `{"devices": []}`. | Sin la comprobación `isinstance`, **un trusted_devices.json roto dejaría vacío la lista y los celulares dejarían de ser confiables sin aviso**. |

### 5.2 Dispositivos vinculados (líneas 111–148)

| Función | Qué hace | ¿Qué pasa si se cambia/borra? |
|---|---|---|
| `find_trusted(device_id)` | Busca el dispositivo por su ID. | Borrarlo → imposible comprobar si un celular es confiable. |
| `is_trusted(device_id, token)` | **Chequeo central**: exige device_id y luego compara el token (con `secrets.compare_digest`, resistente a ataques de tiempo). | Cambiar la comparación a `==` normal → abre la puerta a un atacante midiendo tiempos. |
| `add_trusted(device_id, name, token)` | Agrega/reemplaza el dispositivo en el fichero (si ya existía ese `device_id`, lo sustituye). | Sin reemplazar por `device_id`, un mismo celular podría **duplicarse** en la lista. |
| `revoke_trusted(device_id)` | Borra el dispositivo de la lista. | Usada por `/api/pair/revoke` (botón "olviar" de la PC). |

### 5.3 Solicitudes pendientes (líneas 150–176)

| Función | Qué hace | ¿Qué pasa si se cambia/borra? |
|---|---|---|
| `create_pending_pair(device, device_id, code)` | Crea la solicitud "pendiente" que la PC verá como diálogo **VINCULAR NUEVO CELULAR**. Devuelve un `request_id` (UUID). | Sin ella **la PC no recibe la solicitud** y nunca abre el diálogo. |
| `get_pending(rid)` | Devuelve la solicitud si sigue vigente (< 300 s), si no, la purga. | Error en la comparación de tiempo → solicitudes caducan tarde o nunca. |
| `cleanup_pending()` | Limpieza por antigüedad de solicitudes. | Sin ella la PC mostraría avisos falsos de celulares viejos. |

### 5.4 Código de emparejamiento (líneas 206–236)

| Función | Qué hace | ¿Qué pasa si se cambia/borra? |
|---|---|---|
| `pair_code(refresh=False)` | Devuelve el código de 6 caracteres vigente; con `refresh=True` crea uno **nuevo**. | Sin `refresh=True` el mismo código se **agotaría por caducar** y NADIE podría vincular sin acordarse de refrescarlo. |
| `pair_payload(ip, port, name)` | Construye el texto que va **dentro** del QR: `bioaccess://pair?ip=...&port=...&code=...&pc_id=...` | Si cambias el formato de la URI, **el QR deja de abrir** con la APK (el APK espera este texto exacto). |
| `verify_pair(code, device)` | Comprueba que el código sea válido y correcto; guarda "used_by". | El servidor usa esta misma validación con `create_pending_pair` (parecida en `/api/pair/verify`). |

### 5.5 Historial de eventos (líneas 238–255)

| Función | Qué hace |
|---|---|
| `load_events()` / `save_events(events)` | Carga/guarda `bioaccess_events.json` (máx. 400 entradas). El log de la app usa esto. |
| `now_str()` | "13:45:22". |

### 5.6 `Peer` y `Hub` (líneas 261–343)

| Pieza | Qué hace |
|---|---|
| `Peer` | Objeto que representa a UN conectado (PC o celular). Tiene `ws`, `role`, `device`, `device_id`, `token`, `trusted`, `since`, `id`. |
| `Hub` | El registro de todos los conectados + difusor. Tiene `add/remove/by_role/peer_list/send/broadcast/log/state`. |
| `HUB.log()` | Además de guardar, **DIFUNDE** la línea de log a todos (para que la PC la pinte). |
| `state()` | Devuelve el "estado global" para `/api/state` (peers, pending, eventos). |

### 5.7 La API HTTP (líneas 354–540)

| Endpoint | Qué hace | Si modificas algo aquí… |
|---|---|---|
| `GET /` | Redirige al móvil en `/mobile/index.html`. | Cambia este redirige → el móvil no abre la app. |
| `GET /api/hello` | "¿Quién eres?" → nombre, versión, IP, puerto. | La rutina de autodescubrimiento del móvil y el depurador lo usan. |
| `GET /api/state` / `GET /api/events` | Estado global / historial. | El dashboard de la PC los pinta. |
| `POST /api/request` | Lanza una solicitud de huella **via HTTP**. | La versión "de prueba" del pedido; la normal viene por WS. |
| `GET /api/pair` | Devuelve el payload del QR (ip, puerto, código, `pc_id`, expiración). | Si cambias este JSON, el QR se desincroniza. |
| `_rate_ok(ip)` | Rate-limit: máximo **5 intentos/minuto por IP** en `/api/pair/verify`. | Sin esto, cualquiera puede probar códigos infinitos. |
| `GET /api/pair/verify` | Chequea código + **crea solicitud pendiente** + avisa a la PC (máx. 5/min por IP). | El contrato más sensible de todo: el QR entero pasa por aquí. |
| `POST /api/pair/decision` | **Acepta/rechaza**. Acepta → token → guarda vinculado → avisa al celular. | Es el "botón ACEPTAR" real; romperlo rompe la vinculación. |
| `GET /api/pair/trusted` / `/api/pair/pending` / `POST /api/pair/revoke` | Lista vinculados / pendientes / revocar. | La PC los consulta cada 2 segundos para detectar solicitudes y administrar. |

### 5.8 El WebSocket `/ws` (líneas 542–730)             # corazón de todo

**Handshake:** al conectar, el celular manda `?role=phone&device=Nombre&device_id=...&token=...`.

- Si `role=phone` y tiene `device_id`, el servidor comprueba `is_trusted(device_id, token)`:
  - **True** → `peer.trusted = True` (el celular es de confianza).
  - **False** → se conecta igual, pero **NO recibirá `scan_request`**.

**Tarjetas JSON que entiende (vía `handle_message`):**

| `type` | Quién la envía | Qué hace el servidor |
|---|---|---|
| `hello` | PC / celular | Devuelve `hello_ack` con yo y la lista de peers (con **trusted**). |
| `pair_request` | celular (WS, desde el QR) | Valida el código, crea `pending`, avisa a la PC → `pair_pending`. |
| `scan_request` | **solo** la PC (`role=='pc'`) | Crea solicitud → solo a celulares **vinculados** manda `scan_request`. Si no hay vinculados → responde a la PC `scan_result {ok:false, error:'sin_celular_vinculado'}` (o `'sin_celular'`). |
| `scan_progress` | celular | Difunde el progreso a la PC (0–100). |
| `scan_result` | celular | Genera token de acceso (12 hex), lo registra y difunde `scan_result` + `access_granted` / `access_denied`. |
| `scan_cancel` / `cancel` | cualquiera | Cancela la solicitud pendiente y avisa a todos. |
| `ping` | cualquiera | Responde `pong` (mantener la línea viva). |
| `log` | cualquiera | Anota y difunde una línea al resto. |

### 5.9 UDP descubrimiento (líneas 735–766)

- El celular grita `BIOACCESS_DISCOVER` por UDP 8089.
- El servidor escucha y responde `{name, ip, port, version}`.
- Si este bloque se borra, el móvil **ya no encuentra la PC automáticamente**, pero el QR la fija a mano en la configuración del móvil.
- El hilo `loop()` es daemon (muere solo cuando el proceso principal muere).

### 5.10 El servidor embebido (líneas 772–830)

| Pieza | Qué hace |
|---|---|
| `EmbeddedServer` | Arranca uvicorn en un hilo **daemon dentro de la terminal de la PC**. Lo usa `bioaccess.py` al abrir la app. |
| `start()` | Arranca uvicorn + cierra el "readiness check" TCP a 127.0.0.1:puerto (40 intentos × 0.05 s). |
| `stop()` | Orden de apagado: `server.should_exit = True` + cerrar el socket UDP. |
| `mount_static()` | Monta la carpeta `mobile/` en `/mobile` (desde aquí se ve el celular). |

---

## 6. El lado PC (`bioaccess.py`) — funciones de conexión

Todas las funciones abajo son las que la terminal usa para "hablar":

| Función (línea aprox.) | Qué hace | ¿Y si se cambia/borra? |
|---|---|---|
| `class BridgeClient(QThread)` (740) | Hilo de fondo que vive en WebSocket con el servidor; cola de envío `_outbox`; bucle `while self._running`. | Borrarlo → la PC **no puede mandar tarjetas** al celular. |
| `BridgeClient.send()` (757) | Envía cualquier tarjeta por la cola; el bucle `run()` la agarra. | Si se rompe `_outbox`, los mensajes se quedan en la cola sin llegar. |
| `SuperCustomBio.__init__` (822) | Arranca `EmbeddedServer` embebido al abrir la terminal. | Si no arranca el servidor, la PC abre la ventana pero **nunca contacta con el celular**. |
| `_poll_pending_pairs()` (1458) | Cada **2 segundos** llama `GET /api/pair/pending` y, si hay solicitud nueva, abre el diálogo **VINCULAR NUEVO CELULAR** (ACEPTAR / RECHAZAR). | Sin esto, la PC **nunca muestra** el diálogo de vinculación, aunque el celular la pida. |
| `_on_net_message()` (1531) | Recibe las tarjetas del servidor y pinta la UI: `hello_ack` → `net_peer`; `peer_joined`/`peer_left` → registro del celular; `pair_request` → replica del diálogo; `scan_result ok` → ACCESO CONCEDIDO / denegado. | Sin esto, la terminal muestra el mundo pero **no reacciona** a nada. |
| `_request_fingerprint()` (1693) | Envía la tarjeta `scan_request`. | Sin ella la PC no puede pedir la huella. |
| `_show_pair_dialog()` (1706) | Dibuja el QR (`bioaccess://pair?...`) y el código de 6 caracteres. | Sin él no se ve el QR de vinculación. |
| `_show_trusted_devices_dialog()` (1789) | Lista de celulares vinculados con opción de **Revocar** (usa `/api/pair/revoke`). | Sin él no hay forma de "olviar" un celular desde la PC. |

---

## 7. El lado celular (`mobile/app.js`) — funciones de conexión

| Pieza | Qué hace | ¿Y si se cambia? |
|---|---|---|
| `CFG_KEY = 'bioaccess_mobile_cfg_v2'` | Nombre del cajón (localStorage) donde vive `{ip, port, device, deviceId, token, ...}`. | Cambiar el nombre → **el APK queda "ciego"** (no lee su config vieja, hay que re-vincular). |
| `DEFAULT_CFG` | Valores por defecto. | Cambiar `ip` por defecto → comportamiento esperado: el simulador lo sobreescribe a 127.0.0.1. |
| `Net.connect()` → `ws://host:port/ws?role=phone&device_id=…&token=…` | **Conexión principal**. Envia `hello` tras abrir. | Cambiar los nombres de query params (`role`, `device_id`, `token`) → el servidor no identifica al celular y lo marca como "no confiable". |
| `Net.onclose` → contador `fails` | Tras **4 fallos consecutivos** llama a `discover()` para auto-reparar una PC antigua guardada. | Sin esto, un celular apuntando a una IP vieja se queda sin conexión eterna hasta que el usuario re-configura. |
| `pairFromQr()` / `pairByUsb()` | Flujo de vinculación: `GET /api/pair/verify` (nativo o fetch) → luego WebSocket + `pair_request`. | Cambiar la URL o el nombre `/api/pair/verify` → **el QR deja de funcionar**. |
| `Net.onmessage('pair_result')` | Guarda el `token` en `localStorage` y marca el celular como vinculado. | Sin ella, el celular pediría vinculación una y otra vez. |
| `Hud` + fingerprint | Pintan el progreso de huella y, en Android real, disparan el sensor. | No afectan a la conexión; solo a la UX de huella. |
| `_autoDiscover()` | Al abrir la app, si está configurada a una IP buena, se conecta; si no, pregunta por UDP (APK). | Sin esto requiere QR o configuración manual cada vez. |

---

## 8. ¿Qué SE PUEDE cambiar? ¿Y qué NO?

| Sí puedes cambiar | Mejor no, o con mucho cuidado |
|---|---|
| El **nombre para mostrar** `SERVER_NAME` ("BioAccess PC") — cosmético | **Los nombres de las tarjetas** (`type`, `scan_request`…): el móvil y la PC deben hablar el mismo idioma exacto |
| El **tamaño de los textos** en la terminal/celular — estética | **El puerto 8080 / la ruta `/ws` / `/api`**: tienen que coincidir en servidor, terminal **y** APK |
| El mensaje "CELULAR VINCULADO"… — textos de UI | **La clave `bioaccess_mobile_cfg_v2`**: si cambia, todos los móviles vinculados dejan de ser reconocidos |
| El TTL del código del QR (`PAIR_TTL`), hasta 10 → 15 min | **`DISCOVERY_MAGIC` / el esquema `bioaccess://pair?`**: el APK espera exactamente esos textos |
| El `REQUEST_TTL` de 30 s | **El `token` / la estructura de `trusted_devices.json`** (`device_id`/`token`/`paired_at`) |
| El texto del código QR mostrado (p. ej. reemplazar por un logo) | Los **nombres de roles** `pc` / `phone` y los campos del handshake |

---

## 9. Errores típicos y cómo leerlos (la "caja negra de fallos")

| Texto que ves | Significado real | Qué hacer |
|---|---|---|
| `sin_celular` | La PC no ve **ningún** celular conectado | Abre la app en el móvil / pulsa CONECTAR |
| `sin_celular_vinculado` | Celular conectado pero **no** vinculado | Abre VINCULAR en el móvil y pulsa ACEPTAR en la PC |
| `codigo_invalido_o_expirado` | El código del QR es viejo (> 10 min) o está mal escrito | Pide un código nuevo pulsando VINCULAR de nuevo en la PC |
| `demasiados_intentos` | Más de 5 intentos en 1 minuto desde la misma IP | Espera 1 minuto o reinicia el servidor |
| `solicitud_expirada_o_inexistente` | La vinculación tardó > 5 min y caducó | Pulsa ACEPTAR/RECHAZAR o genera un código nuevo |
| `codigo_invalido_o_expirado` en la consola (`[PAIR_WS]`) | Igual, visto desde el servidor | Revisa fecha/hora del PC vs. celular |
| "Vista fija a 127.0.0.1…" (simulador) | El simulador ancla el móvil simulado a la misma máquina | Estático por diseño del simulador |
| `BUSCANDO PC EN LA RED...` | Auto-reparación tras 4 fallos seguidos | Espera; debería autoconectar a la PC correcta |

---

## 10. Si tuvieras que explicárselo a un grupo en 30 segundos

> "El sistema tiene 3 piezas: una **terminal** (la PC), una **central telefónica** dentro de la PC
> (el servidor `bioaccess_server.py`, que acepta WebSockets y HTTP en el puerto 8080, y grita por
> UDP en el 8089), y un **celular** (la APK o el navegador). El servidor exige que el celular esté
> **vinculado** (token guardado en el servidor); si no lo está, el celular se conecta pero la PC
> le dice `sin_celular_vinculado` y nunca le pide la huella. La vinculación es: el móvil pide con
> el código del QR, la PC ve el diálogo VINCULAR NUEVO CELULAR y el usuario pulsa ACEPTAR. A
> partir de ahí, cada vez que la PC pide huella (`scan_request`), solo los celulares **vinculados**
> la reciben, responden con el progreso y al final la terminal pinta **ACCESO CONCEDIDO**."

---

## 11. Guion de demo en vivo (5 pasos)

1. Abre `sistema_simple.py` (Spyder F5 o `python sistema_simple.py`).
2. Se abren **3 ventanas**: terminal PC, móvil simulado y AYUDA SIMULADOR.
3. Pulsa **"1) VINCULAR CELULAR (1 CLIC)"** en la AYUDA SIMULADOR.
4. En la terminal PC aparece **VINCULAR NUEVO CELULAR** → pulsa **ACEPTAR**.
5. El móvil muestra **VINCULADO**. Pulsa **MANTENER PULSADO** en el móvil hasta 100 % → la PC pinta **ACCESO CONCEDIDO**.
