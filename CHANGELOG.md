# Changelog — BioAccess

## v1.1.0 (2026-11-27)
### Mejoras
- Página web rehecha como terminal BioAccess (sidebar, panel central, diagnóstico, scrollspy, responsive).
- Logo de huella del sistema integrado en header/sidebar y favicon.
- Seguridad: control plane con `pc_secret`, tokens en SHA-256, código de emparejamiento de un solo uso, CORS endurecido, rate-limit.
- Emparejamiento móvil: auto-reparación de IP guardada, vinculación por QR/código/USB.
- Simulador portable actualizado al sistema real.

### Parches
- Corregido estado de enlace PC/celular (muestra "SIN VINCULAR" cuando no está vinculado).
- Corregido flujo de huella: `scan_request` solo se envía a celulares vinculados.
- Corregido QR de PC (alto contraste) y lector móvil (enfoque, antorcha, pegar).
- Corregida configuración persistente en `%APPDATA%\BioAccess`.

## v1.0.0 (2026-11-12)
- Versión inicial: terminal PC, app móvil, servidor embebido, APK, instalador y simulador.