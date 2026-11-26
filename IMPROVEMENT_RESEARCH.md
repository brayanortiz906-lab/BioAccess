# BioAccess — Investigación de mejoras necesarias

> Fecha: 07/11/2026 · Proyecto: `C:\Users\Mugen\Documents\TRABAJOS UNIVERDAD PASCUAL\MATEMATICAS_DISCRETAS`
> Base: análisis del código fuente (bioaccess.py 1892 lín, bioaccess_server.py 789, mobile/app.js 998, MainActivity.java 454, installer.py 242), README, build scripts y pruebas existentes.

## 1. Resumen ejecutivo

BioAccess es un sistema **funcional y demostrable** (selftest + smoke test pasan, flujo PC↔celular completo, QR recién corregido, builds EXE/APK/installer regenerados). Sin embargo, para pasar de **prototipo/demo** a **producto robusto y mantenible**, se identifican **~40 mejoras** agrupadas en 8 ejes. Las 5 de mayor impacto:

1. **Seguridad**: todo el tráfico PC↔celular es HTTP/WS en claro y el túnel público expone el servidor completo; emparejamiento con código de 6 chars reutilizable y sin rate-limit.
2. **Persistencia de configuración en EXE**: `bioaccess_config.json` se guarda en `_MEIPASS` (temporal) → se pierde al cerrar.
3. **Monolito de 1892 líneas** en un solo archivo (`bioaccess.py`) sin tests unitarios.
4. **minSdk inconsistente** (README dice Android 6.0 / API 23, código usa 28).
5. **Sin cifrado ni rotación de tokens** (`trusted_devices.json` en claro, contiene dispositivo de prueba).

## 2. Estado actual (fortalezas)

| Aspecto | Estado |
|---|---|
| Protocolo PC↔celular | Funcional, probado (`selftest_bridge.py` PASS) |
| Emparejamiento QR + PIN 6 chars | Funcional tras corrección de cámara y conexión WS |
| Biometría real Android | `BiometricPrompt` (minSdk 28) |
| Descubrimiento UDP | Funcional (puerto 8089) |
| Builds reproducibles | EXE/APK/installer con scripts documentados |
| UI cyberpunk | Pulida, audio sintético, HUD canvas |
| Historial local móvil | Persistente en localStorage |
| Túnel público (serveo/localtunnel) | Operativo con headers bypass |

## 3. Hallazgos por eje

### 3.1 Seguridad (prioridad ALTA)
| # | Hallazgo | Evidencia | Riesgo |
|---|---|---|---|
| S1 | Tráfico LAN en claro (HTTP/WS) | `bioaccess_server.py`, `mobile/app.js` `ws://` | Sniffing en WiFi compartida |
| S2 | CORS `allow_origins=["*"]` + sin rate-limit | `bioaccess_server.py` | Abuso de endpoints de pairing |
| S3 | Código de 6 chars reutilizable, sin invalidación tras uso ni límite de intentos | `pair_code`, `verify_pair` | Fuerza bruta |
| S4 | Tokens en `trusted_devices.json` en claro, sin rotación | `trusted_devices.json` | Robo de identidad si se accede al disco |
| S5 | `pc_secret` generado pero no usado en el protocolo | `pc_identity.json` | Identidad no verificada |
| S6 | Túnel público expone servidor completo (solo aprobación de dispositivo) | `_start_tunnel` | Superficie de ataque remota |
| S7 | `trusted_devices.json` contaminado con `test-device-001` | repo actual | Datos de prueba en producción |

**Mejoras necesarias:**
- TLS opcional en LAN (certificado autofirmado + pinning en APK) o, mínimo, firma HMAC de mensajes con `pc_secret`.
- Rate-limit en `/api/pair/verify` (ej. 5 intentos/min por IP).
- Invalidar código tras uso exitoso; regenerar automáticamente.
- Cifrar `trusted_devices.json` at-rest (DPAPI en Windows, Keystore en Android) o al menos HMAC de tokens.
- Usar `pc_secret` para firmar `hello_ack` / `pair_result`.
- Limpiar dispositivos de prueba del repo y en installer.

### 3.2 Arquitectura y persistencia (prioridad ALTA)
| # | Hallazgo | Evidencia |
|---|---|---|
| A1 | `CONFIG_FILE` en `__file__` (temp `_MEIPASS` en frozen) → config se pierde | `bioaccess.py:31` |
| A2 | `DEFAULT_CONFIG.copy()` superficial (dicts anidados compartidos) | `_reset_settings` |
| A3 | Servidor usa `%APPDATA%\BioAccess`, escritorio no | inconsistencia |
| A4 | `EmbeddedServer.start()` puede reportar éxito si UDP responder falla | `bioaccess_server.py` |
| A5 | Dos fuentes de verdad para `mobile/` (raíz + assets) con copia manual | build.ps1 / installer.spec |
| A6 | `bioaccess.py` monolítico (1892 lín, UI+red+config+audio+HUD) | todo el archivo |
| A7 | Sin separación de capas (UI, dominio, infraestructura) | - |

**Mejoras necesarias:**
- Unificar rutas de datos: todo bajo `%APPDATA%\BioAccess` (config, identity, trusted, events) tanto en dev como frozen.
- Deep-copy en `_reset_settings`.
- Verificar arranque UDP y propagar error.
- Modularizar `bioaccess.py` en paquetes: `ui/`, `net/`, `config/`, `audio/`, `hud/`.
- Single source of truth para `mobile/` (symlink/copia en build, no duplicar).

### 3.3 Calidad de código y mantenibilidad (prioridad MEDIA)
| # | Hallazgo | Evidencia |
|---|---|---|
| Q1 | Sin tests unitarios (solo smoke/selftest de integración) | `tools/` |
| Q2 | APIs Android deprecadas (`Camera`, `BiometricPrompt.Builder` sin `CryptoObject`) | `QrScanActivity.java` |
| Q3 | minSdk inconsistente (README 23 vs código 28) | manifest + build.ps1 |
| Q4 | Historial de escritorio con eventos ficticios hardcodeados | `_create_history_view` |
| Q5 | `isSecureHost()` trata cualquier hostname con letras como túnel HTTPS → `localhost` falla | `mobile/app.js` |
| Q6 | QR matrix renderizado con `FastTransformation` (puede perder nitidez) | `bioaccess.py` |
| Q7 | Sin linting/formatting configurado (ruff/black, eslint) | - |
| Q8 | Sin CI/CD (builds manuales) | - |

**Mejoras necesarias:**
- Añadir tests unitarios para `parseQrPayload`, `pair_code`, `verify_pair`, `lan_ip`, config load/save.
- Migrar cámara a CameraX o al menos `Camera2` con rotación correcta; biometría con `CryptoObject`.
- Decidir minSdk definitivo (28 recomendado por BiometricPrompt) y actualizar README.
- Reemplazar historial ficticio por datos reales del servidor.
- Corregir `isSecureHost()` para reconocer `localhost`/`.local` como HTTP.
- Configurar ruff + black + eslint + pre-commit.
- Pipeline CI (GitHub Actions) para builds EXE/APK.

### 3.4 UX y funcionalidad (prioridad MEDIA)
| # | Hallazgo | Impacto |
|---|---|---|
| U1 | Vinculación QR requiere aprobación manual en PC (fricción) | Alto para uso frecuente |
| U2 | Sin recuperación si se pierde el celular (revocación existe pero no documentada en UI) | Medio |
| U3 | Sin modo offline / caché del historial en PC | Bajo |
| U4 | Sin notificación push cuando la PC solicita huella (solo si app abierta) | Medio |
| U5 | Sin multi-usuario / perfiles en PC | Bajo (fuera de alcance actual) |
| U6 | Sin internacionalización (todo en español) | Bajo |
| U7 | Sin accesibilidad (contraste, tamaño de fuente, screen reader) | Medio |
| U8 | Sin actualización automática del EXE/APK | Medio |
| U9 | Túnel: serveo/localtunnel inestables, sin fallback robusto | Medio |

**Mejoras necesarias:**
- Opción "confiar automáticamente en dispositivos de la misma red" (opt-in) para reducir fricción.
- Documentar y mejorar flujo de revocación + re-vinculación.
- Notificaciones Android (Foreground Service) para solicitudes de huella con app en background.
- Auto-update via GitHub Releases (WinSparkle / in-app updater).
- Mejorar túnel: opción de Cloudflare Tunnel o ngrok con authtoken.

### 3.5 Rendimiento (prioridad BAJA-MEDIA)
| # | Hallazgo | Impacto |
|---|---|---|
| P1 | `bioaccess.py` carga PyQt6 + servidor en un proceso → ~70 MB EXE | Arranque lento |
| P2 | WS síncrono con `websocket` legacy en `BridgeClient` | Latencia |
| P3 | QR decode en hilo por frame sin throttling → CPU alta | Batería móvil |
| P4 | Historial móvil en localStorage sin límite de tamaño | Crecimiento |
| P5 | Sin compresión de assets en APK (zipalign OK pero sin shrink) | Tamaño |

**Mejoras necesarias:**
- Throttle de frames en `QrScanActivity` (decodificar cada N frames, no todos).
- Limitar historial móvil a N entradas (ej. 200) con rotación.
- Evaluar split del servidor en proceso separado (opcional).
- Habilitar R8/ProGuard en build (si se migra a Gradle) o mantener manual.

### 3.6 Compatibilidad y despliegue (prioridad MEDIA)
| # | Hallazgo | Impacto |
|---|---|---|
| C1 | Build Android manual (aapt2/javac/d8) frágil y no estándar | Mantenimiento |
| C2 | Keystore de desarrollo con contraseña pública (`bioaccess`) | Seguridad de firma |
| C3 | Sin firma de código del EXE (SmartScreen warning) | Adopción |
| C4 | Installer en tkinter (básico, sin uninstaller) | UX |
| C5 | Sin soporte macOS/Linux (PyQt6 es portable pero builds no) | Alcance |
| C6 | Python 3.14 en dev (bleeding edge) vs 3.11+ declarado | Compatibilidad |

**Mejoras necesarias:**
- Migrar build Android a Gradle (o mantener manual pero documentar toolchain exacta).
- Generar keystore de producción seguro y documentar rotación.
- Firmar EXE con certificado (o al menos documentar SmartScreen).
- Añadir uninstaller al installer (o migrar a Inno Setup / WiX).
- Validar en Python 3.11 LTS y fijar versión en CI.

### 3.7 Observabilidad y operación (prioridad BAJA)
| # | Hallazgo |
|---|---|
| O1 | Logs solo en UI y `bioaccess_events.json`; sin rotación ni niveles |
| O2 | Sin métricas de uso (cuántas huellas, fallos, latencia) |
| O3 | Sin crash reporting |
| O4 | Sin health-check endpoint estructurado |

**Mejoras necesarias:** logging estructurado (JSON) con rotación, endpoint `/api/health`, telemetría opt-in.

## 4. Roadmap priorizado

### Fase 1 — Estabilización (1-2 semanas)
- [ ] Persistir config en `%APPDATA%\BioAccess` (A1)
- [ ] Deep-copy defaults (A2)
- [ ] Limpiar `trusted_devices.json` de datos de prueba (S7)
- [ ] Rate-limit + invalidación de código (S3)
- [ ] Corregir `isSecureHost()` (Q5)
- [ ] Actualizar README minSdk (Q3)
- [ ] Throttle de frames QR (P3)

### Fase 2 — Calidad (2-4 semanas)
- [ ] Modularizar `bioaccess.py` (A6/A7)
- [ ] Tests unitarios (Q1) + CI básico
- [ ] ruff/black/eslint + pre-commit (Q7)
- [ ] Historial real en PC (Q4)
- [ ] Migrar cámara a CameraX (Q2)
- [ ] Cifrado at-rest de tokens (S4)

### Fase 3 — Seguridad y despliegue (4-8 semanas)
- [ ] TLS opcional / HMAC de mensajes (S1, S5)
- [ ] Firma de código EXE (C3)
- [ ] Auto-update (U8)
- [ ] Notificaciones Android en background (U4)
- [ ] Migrar build Android a Gradle (C1)
- [ ] Uninstaller (C4)

### Fase 4 — Producto (8+ semanas)
- [ ] Internacionalización (U6)
- [ ] Accesibilidad (U7)
- [ ] Soporte multi-plataforma (C5)
- [ ] Métricas y crash reporting (O2, O3)

## 5. Quick wins (≤ 1 día cada uno)

1. Mover `CONFIG_FILE` a `%APPDATA%\BioAccess\bioaccess_config.json`.
2. `copy.deepcopy(DEFAULT_CONFIG)` en `_reset_settings`.
3. Eliminar `test-device-001` de `trusted_devices.json`.
4. Añadir `device_id` a `/api/pair/verify` (ya hecho).
5. Corregir `isSecureHost()` para localhost/`.local`.
6. Limitar historial móvil a 200 entradas.
7. Throttle QR: decodificar cada 3er frame.
8. Actualizar README (minSdk 28, puertos, flujo QR).

## 6. Riesgos si no se actúa

- **Pérdida de configuración en EXE** → usuarios reconfiguran cada arranque (ya reportable).
- **Tráfico en claro en WiFi corporativa** → bloqueo por políticas de seguridad.
- **Código de pairing fuerza-bruteable** → vinculación no autorizada.
- **Monolito sin tests** → regresiones silenciosas al agregar features.
- **Build manual frágil** → dificultad para onboarding de nuevos devs.

## 7. Métricas de éxito sugeridas

| Métrica | Objetivo |
|---|---|
| Config persiste entre reinicios del EXE | 100% |
| Latencia scan_request → respuesta móvil | < 2 s en LAN |
| Tasa de éxito de emparejamiento QR | > 95% |
| Cobertura de tests unitarios | > 60% en módulos de red/config |
| Tamaño EXE | < 80 MB |
| Tiempo de arranque EXE | < 5 s |

---

**Conclusión:** el sistema es sólido como prototipo/demo y el flujo principal funciona. Para convertirlo en producto, la prioridad inmediata es **persistencia de config (A1)** y **seguridad del pairing (S3, S4)**; luego **modularización + tests (A6, Q1)** para sostener el desarrollo. El resto puede escalonarse por fases sin bloquear el uso actual.