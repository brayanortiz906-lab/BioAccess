/* ===================================================================
   BioAccess Mobile v2.0 — lógica del cliente
   Funciona en: APK Android (WebView + puente nativo) y navegador móvil.
   Protocolo: WebSocket JSON contra bioaccess_server.py (PC)
   =================================================================== */
'use strict';

/* ------------------------------------------------------------------
   0. PUENTE NATIVO (Android) — opcional
   ------------------------------------------------------------------ */
const ANDROID = (typeof window.BioAndroid !== 'undefined') ? window.BioAndroid : null;
const IS_APK  = !!ANDROID;

/* ------------------------------------------------------------------
   1. CONFIGURACIÓN
   ------------------------------------------------------------------ */
const CFG_KEY = 'bioaccess_mobile_cfg_v2';
const LOG_KEY = 'bioaccess_mobile_log_v2';

const DEFAULT_CFG = {
  ip: (location.protocol === 'http:' && location.hostname) ? location.hostname : '192.168.1.50',
  port: (location.protocol === 'http:' && location.port) ? location.port : '8080',
  device: IS_APK ? 'Celular BioAccess' : 'Navegador',
  auto: true,
  sens: 50,
  time: 3,
  biometric: true,
  haptic: true,
  audio: true,
  vol: 70,
  pin: '',
  pinOnStart: false,
  pinPerRequest: false,
  deviceId: '',
  token: '',
  pcId: '',
  enrolled: false
};

// ---- protocolo adaptativo: LAN (http/ws) vs tunel publico (https/wss) ----
function isTunnelHost(ip) {
  ip = (ip || '').toLowerCase();
  // dominios de tuneles publicos conocidos => HTTPS/WSS
  return /(\.serveo\.net|\.loca\.lt|\.ngrok\.io|\.ngrok-free\.app|\.trycloudflare\.com|\.localtunnel\.me|\.lhr\.life|\.serveo\.cc)$/i.test(ip);
}
function isSecureHost() {
  const ip = (CFG.ip || '').trim().toLowerCase();
  if (!ip) return false;
  // hosts locales / LAN => HTTP/WS (no TLS)
  if (ip === 'localhost' || ip === '127.0.0.1' || ip === '::1') return false;
  if (ip.endsWith('.local') || ip.endsWith('.lan') || ip.endsWith('.home') || ip.endsWith('.localdomain')) return false;
  // IP numerica (IPv4/IPv6) => LAN => HTTP/WS
  if (/^[\d.:]+$/.test(ip)) return false;
  // puerto explicito 443/https => tunel publico
  if (CFG.port === '443' || CFG.port === '' || CFG.port === 443) return true;
  // dominio de tunel conocido => HTTPS/WSS
  if (isTunnelHost(ip)) return true;
  // cualquier otro hostname (ej. nombre de PC con letras) => intentar HTTP primero
  // (los tuneles reales usan los sufijos anteriores o el puerto 443)
  return false;
}
function httpProto() { return isSecureHost() ? 'https://' : 'http://'; }
function wsProto()   { return isSecureHost() ? 'wss://'   : 'ws://';   }
function hostPort()  { const p = (CFG.port || '').toString().trim(); return p ? (':' + p) : ''; }

let CFG = Object.assign({}, DEFAULT_CFG, readJSON(CFG_KEY) || {});
if (!CFG.deviceId) { CFG.deviceId = 'dev-' + Math.random().toString(36).slice(2) + Date.now().toString(36); saveCfg(); }
let LOG = readJSON(LOG_KEY) || [];

function readJSON(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } }
function writeJSON(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
function saveCfg() { writeJSON(CFG_KEY, CFG); }
function saveLog() { if (LOG.length > 200) LOG = LOG.slice(-200); writeJSON(LOG_KEY, LOG); }

const $ = (id) => document.getElementById(id);

/* ------------------------------------------------------------------
   2. AUDIO (sintético, sin archivos)
   ------------------------------------------------------------------ */
let actx = null;
function beep(freq, ms, type) {
  if (!CFG.audio) return;
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    if (actx.state === 'suspended') actx.resume();
    const o = actx.createOscillator(), g = actx.createGain();
    o.type = type || 'square';
    o.frequency.value = freq;
    g.gain.value = Math.max(0.0001, (CFG.vol / 100) * 0.16);
    o.connect(g); g.connect(actx.destination);
    const t = actx.currentTime;
    o.start(t); g.gain.exponentialRampToValueAtTime(0.0001, t + ms / 1000);
    o.stop(t + ms / 1000 + 0.02);
  } catch (e) {}
}
const S = {
  start:   () => { beep(400, 40); setTimeout(() => beep(600, 40), 55); setTimeout(() => beep(800, 50), 110); },
  ok:      () => { beep(523, 70); setTimeout(() => beep(659, 70), 80); setTimeout(() => beep(784, 110), 160); },
  fail:    () => { beep(300, 70); setTimeout(() => beep(200, 130), 85); },
  click:   () => beep(1000, 22, 'sine')
};

/* ------------------------------------------------------------------
   3. VIBRACIÓN
   ------------------------------------------------------------------ */
function vibrate(pattern) {
  if (!CFG.haptic) return;
  try {
    if (ANDROID && ANDROID.vibrate) ANDROID.vibrate(pattern);
    else if (navigator.vibrate) navigator.vibrate(pattern);
  } catch (e) {}
}

/* ------------------------------------------------------------------
   4. TOAST
   ------------------------------------------------------------------ */
let toastTimer = null;
function toast(msg, kind) {
  const el = $('toast');
  el.textContent = msg;
  el.className = 'toast show' + (kind ? ' ' + kind : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = 'toast'; }, 2200);
}

/* ------------------------------------------------------------------
   5. LOG / HISTORIAL
   ------------------------------------------------------------------ */
function addLog(text, level) {
  const now = new Date();
  const ts = now.toTimeString().slice(0, 8);
  LOG.push({ t: ts, text, level: level || 'info' });
  saveLog();
  renderLog();
}
function renderLog() {
  const ul = $('histList');
  if (!LOG.length) { ul.innerHTML = '<li class="empty">// SIN EVENTOS REGISTRADOS</li>'; return; }
  const frag = document.createDocumentFragment();
  for (let i = LOG.length - 1; i >= 0; i--) {
    const e = LOG[i];
    const li = document.createElement('li');
    li.className = e.level || 'info';
    li.innerHTML = '<span class="t">[' + e.t + ']</span><span>' + escapeHtml(e.text) + '</span>';
    frag.appendChild(li);
  }
  ul.innerHTML = '';
  ul.appendChild(frag);
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ------------------------------------------------------------------
   6. WEBSOCKET — enlace con la PC
   ------------------------------------------------------------------ */
const Net = {
  ws: null,
  state: 'off',            // off | connecting | on
  retry: 0,
  timer: null,
  server: null,
  pcName: null,
  send(obj) {
    if (this.ws && this.ws.readyState === 1) {
      try { this.ws.send(JSON.stringify(obj)); return true; } catch (e) {}
    }
    return false;
  },
  url() { return wsProto() + CFG.ip.trim() + hostPort() +
    '/ws?role=phone&device=' + encodeURIComponent(CFG.device) +
    '&device_id=' + encodeURIComponent(CFG.deviceId) +
    '&token=' + encodeURIComponent(CFG.token || ''); },
  connect() {
    if (this.state === 'connecting' || this.state === 'on') return;
    clearTimeout(this.timer);
    this.state = 'connecting';
    setConn('wait', 'CONECTANDO');
    let ws;
    try { ws = new WebSocket(this.url()); } catch (e) { this.state = 'off'; this.scheduleRetry(); return; }
    this.ws = ws;
    const guard = setTimeout(() => { try { ws.close(); } catch (e) {} }, 6000);

    ws.onopen = () => {
      clearTimeout(guard);
      this.state = 'on'; this.retry = 0; this.fails = 0;
      setConn('on', 'ONLINE');
      this.send({ type: 'hello', role: 'phone', device: CFG.device, app: 'mobile', version: '2.0' });
      if (window._pendingPair) {
        const pp = window._pendingPair;
        window._pendingPair = null;
        addLog('WS conectado. Enviando pair_request con codigo ' + pp.code, 'warn');
        setTimeout(() => {
          try { this.send({ type: 'pair_request', code: pp.code, device: pp.device, device_id: pp.device_id }); addLog('pair_request enviado', 'info'); }
          catch (e) { addLog('Error enviando pair_request: ' + e.message, 'err'); }
        }, 300);
        $('discoverHint').textContent = '> ESPERANDO APROBACIÓN EN LA PC...';
      } else {
        addLog('Conectado a la PC ' + CFG.ip + ':' + CFG.port, 'ok');
      }
      toast('PC CONECTADA');
      S.click();
    };
    ws.onmessage = (ev) => {
      let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
      handleMessage(m);
    };
    ws.onerror = () => { setConn('', (this.state === 'on') ? 'ONLINE' : 'SIN SEÑAL'); };
    ws.onclose = () => {
      const was = this.state;
      this.state = 'off'; this.ws = null;
      setConn('', 'OFFLINE');
      $('peerBanner').classList.remove('show');
      if (was === 'on') addLog('Enlace con la PC perdido', 'warn');
      // autorreparacion: con varios fallos seguidos, buscar la PC en la red
      this.fails = (this.fails || 0) + 1;
      if (CFG.auto && this.fails >= 4 && (this.autoDisc || 0) < 3) {
        this.fails = 0;
        this.autoDisc = (this.autoDisc || 0) + 1;
        addLog('No se alcanza la PC guardada. Buscando en la red local...', 'warn');
        toast('BUSCANDO PC EN LA RED...', 'warn');
        try { discover(); } catch (e) {}
      }
      this.scheduleRetry();
    };
  },
  scheduleRetry() {
    clearTimeout(this.timer);
    if (!CFG.auto) return;
    this.retry = Math.min(this.retry + 1, 6);
    const delay = [800, 1500, 3000, 5000, 8000, 12000][this.retry - 1] || 12000;
    this.timer = setTimeout(() => this.connect(), delay);
  },
  disconnect() {
    CFG.auto = false; saveCfg(); $('chkAuto').checked = false;
    clearTimeout(this.timer);
    if (this.ws) { try { this.ws.close(); } catch (e) {} }
    this.ws = null; this.state = 'off';
    setConn('', 'OFFLINE');
  }
};

function setConn(cls, text) {
  const chip = $('connChip');
  chip.className = 'status-chip' + (cls ? ' ' + cls : '');
  $('connText').textContent = text;
}

/* ------------------------------------------------------------------
   7. PROTOCOLO
   ------------------------------------------------------------------ */
const Pending = { id: null, ttl: 30, from: null };

function handleMessage(m) {
  switch (m.type) {
    case 'hello_ack':
      Net.server = m.server || 'BioAccess PC';
      Net.pcName = m.pc_name || null;
      if (m.peers) {
        const pc = m.peers.filter(p => p.role === 'pc');
        if (pc.length) { $('connText').textContent = 'PC ✓'; }
      }
      showDevInfo();
      break;

    case 'peer_joined':
      if (m.role === 'pc') { addLog('Terminal de escritorio conectado', 'ok'); toast('TERMINAL PC EN LINEA'); showDevInfo(); }
      break;

    case 'peer_left':
      if (m.role === 'pc') { addLog('Terminal de escritorio desconectado', 'warn'); showDevInfo(); }
      break;

    case 'scan_request': {
      Pending.id = m.id;
      Pending.ttl = m.ttl || 30;
      Pending.from = m.from || 'PC';
      $('peerBanner').classList.add('show');
      $('pbText').textContent = 'TOCA EL SENSOR PARA AUTORIZAR';
      $('scanHint').textContent = '> SOLICITUD DE LA PC // ' + Pending.from + ' DESEA TU HUELLA_';
      addLog('Solicitud de huella recibida de la PC', 'warn');
      S.start(); vibrate([0, 60, 60, 60]);
      switchView('scan');
      Hud.set('req');
      break;
    }

    case 'scan_cancel': {
      Pending.id = null;
      $('peerBanner').classList.remove('show');
      $('scanHint').textContent = '> SOLICITUD CANCELADA POR LA PC_';
      addLog('La PC canceló la solicitud', 'err');
      S.fail(); Hud.reset();
      break;
    }

    case 'pair_result':
      if (m.ok) {
        CFG.token = m.token || CFG.token;
        CFG.pcId = m.pcId || m.pc_id || CFG.pcId;
        saveCfg();
        addLog('Dispositivo vinculado a la PC', 'ok');
        toast('VINCULADO A LA PC');
        Net.state = 'off'; Net.connect();
      } else {
        addLog('Vinculacion rechazada: ' + (m.reason || 'desconocido'), 'err');
        toast('VINCULACION RECHAZADA', 'err');
      }
      break;

    case 'pair_revoked':
      CFG.token = '';
      saveCfg();
      addLog('Vinculacion revocada por la PC', 'warn');
      toast('VINCULACION REVOCADA', 'err');
      Net.state = 'off'; Net.connect();
      break;

    case 'pair_request':
      // solo la PC recibe esto; el celular no hace nada
      break;

    case 'log':
      addLog(m.text, m.level || 'info');
      break;

    case 'ack':
      break;
  }
}

/* ------------------------------------------------------------------
   8. HUD (canvas) — réplica del sensor del escritorio
   ------------------------------------------------------------------ */
const Hud = {
  cvs: null, ctx: null, w: 0, h: 0, dpr: 1,
  rot: 0, prog: 0, disp: 0, holding: false, mode: 'idle',
  lastT: 0,
  init() {
    this.cvs = $('hud');
    this.ctx = this.cvs.getContext('2d');
    this.resize();
    window.addEventListener('resize', () => this.resize());
    requestAnimationFrame((t) => this.frame(t));
  },
  resize() {
    const r = this.cvs.getBoundingClientRect();
    this.dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    this.w = Math.max(200, r.width); this.h = Math.max(200, r.height);
    this.cvs.width = Math.round(this.w * this.dpr);
    this.cvs.height = Math.round(this.h * this.dpr);
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
  },
  set(mode) { this.mode = mode; },
  reset() { this.prog = 0; this.mode = 'idle'; this.holding = false; this.tag('ESCANEAR'); },
  tag(t) { $('hudTag').textContent = t; },

  frame(t) {
    const dt = this.lastT ? Math.min((t - this.lastT) / 1000, 0.05) : 0.016;
    this.lastT = t;
    this.rot = (this.rot + 42 * dt) % 360;

    if (this.holding && this.prog < 1) {
      const step = dt / Math.max(0.8, CFG.time);
      this.prog = Math.min(1, this.prog + step);
      if (this.prog >= 1) this.complete();
    } else if (!this.holding && this.prog > 0 && this.mode !== 'done') {
      this.prog = Math.max(0, this.prog - dt * 1.6);
    }
    this.disp += (this.prog - this.disp) * 0.16;

    this.draw();
    requestAnimationFrame((tt) => this.frame(tt));
  },

  draw() {
    const c = this.ctx, w = this.w, h = this.h;
    if (!c) return;
    c.clearRect(0, 0, w, h);
    const cx = w / 2, cy = h / 2;
    const r = Math.min(w, h) / 2 - 10;
    const coreR = r * 0.78;

    // rejilla interna
    c.save();
    c.strokeStyle = 'rgba(34,211,255,.10)';
    c.lineWidth = 1;
    for (let x = cx - r; x <= cx + r; x += 20) { c.beginPath(); c.moveTo(x, cy - r); c.lineTo(x, cy + r); c.stroke(); }
    for (let y = cy - r; y <= cy + r; y += 20) { c.beginPath(); c.moveTo(cx - r, y); c.lineTo(cx + r, y); c.stroke(); }
    c.restore();

    // disco base
    c.beginPath(); c.arc(cx, cy, coreR, 0, Math.PI * 2);
    c.fillStyle = 'rgba(2,8,22,.94)'; c.fill();
    c.strokeStyle = 'rgba(34,211,255,.32)'; c.lineWidth = 1.2; c.stroke();

    // marcas exteriores
    c.save(); c.translate(cx, cy);
    c.strokeStyle = 'rgba(34,211,255,.45)';
    for (let i = 0; i < 72; i++) {
      const len = (i % 6 === 0) ? 7 : 3;
      c.beginPath(); c.moveTo(0, -r); c.lineTo(0, -r + len); c.stroke();
      c.rotate(Math.PI / 36);
    }
    c.restore();

    // anillo naranja giratorio
    c.save(); c.translate(cx, cy); c.rotate(this.rot * Math.PI / 180);
    c.setLineDash([6, 8]); c.strokeStyle = 'rgba(255,154,31,.75)'; c.lineWidth = 1.5;
    c.beginPath(); c.arc(0, 0, r - 10, 0, Math.PI * 2); c.stroke();
    c.restore();

    // huella
    c.save(); c.translate(cx, cy); c.scale(0.78, 0.78);
    this.fingerprint(c);
    c.restore();

    // láser
    c.save();
    c.beginPath(); c.arc(cx, cy, coreR, 0, Math.PI * 2); c.clip();
    const lt = (Math.sin(this.rot * 0.04) + 1) / 2;
    const smooth = lt * lt * (3 - 2 * lt);
    const yLaser = (cy - coreR) + (coreR * 2 * smooth);
    const g = c.createLinearGradient(0, yLaser - 10, 0, yLaser + 10);
    g.addColorStop(0, 'rgba(34,211,255,0)');
    g.addColorStop(0.5, 'rgba(34,211,255,.9)');
    g.addColorStop(1, 'rgba(34,211,255,0)');
    c.fillStyle = g; c.fillRect(cx - coreR, yLaser - 10, coreR * 2, 20);
    c.restore();

    // arco de progreso
    if (this.disp > 0.01) {
      const done = this.disp >= 0.99;
      c.save(); c.translate(cx, cy); c.rotate(-Math.PI / 2);
      c.strokeStyle = done ? '#2dffb0' : '#ff9a1f';
      c.lineWidth = 5; c.lineCap = 'round';
      c.shadowColor = done ? 'rgba(45,255,176,.9)' : 'rgba(255,154,31,.9)';
      c.shadowBlur = 14;
      c.beginPath(); c.arc(0, 0, r - 5, 0, Math.PI * 2 * this.disp); c.stroke();
      c.restore();
    }

    // etiqueta de estado
    const pct = Math.round(this.prog * 100);
    if (this.mode === 'done') this.tag('✓ VALIDADO');
    else if (this.holding) this.tag(pct + '%');
    else if (this.mode === 'req') this.tag('SOLICITUD');
    else this.tag('ESCANEAR');

    $('meterFill').style.width = Math.round(this.disp * 100) + '%';
    $('meterLabel').textContent = 'PROGRESO: ' + Math.round(this.disp * 100) + '%';
  },

  /** huella realista: arcos superiores + curvas inferiores (igual que el EXE) */
  fingerprint(c) {
    const rMax = 70, nTop = 13;
    c.lineCap = 'round';
    for (let k = 0; k < nTop; k++) {
      const w = 62 - k * 4.4;
      const ry = w * 1.04 + 1;
      const ye = (k < 4) ? Math.sqrt(Math.max(0, rMax * rMax - w * w)) - 4 : 46 - (k - 3) * 0.9;
      c.beginPath();
      c.moveTo(-w, ye);
      c.lineTo(-w, 0);
      c.ellipse(0, 0, w, ry, 0, Math.PI, Math.PI * 2, false);
      c.lineTo(w, ye);
      if (k % 2 === 1) { c.setLineDash([5, 4]); c.strokeStyle = 'rgba(34,211,255,.86)'; }
      else { c.setLineDash([]); c.strokeStyle = 'rgba(34,211,255,.94)'; }
      c.lineWidth = 2.2;
      c.stroke();
    }
    c.setLineDash([]);
    c.strokeStyle = 'rgba(34,211,255,.78)';
    for (let k = 0; k < 4; k++) {
      const y0 = 52 + k * 5.4;
      const hw = Math.sqrt(Math.max(0, rMax * rMax - y0 * y0)) - 3;
      c.beginPath();
      c.moveTo(-hw, y0);
      c.quadraticCurveTo(0, y0 + 9, hw, y0);
      c.stroke();
    }
  },

  complete() {
    this.mode = 'done';
    S.ok();
    vibrate([0, 40, 50, 40, 50, 90]);
    const wasReq = !!Pending.id;
    if (wasReq) {
      const id = Pending.id;
      Pending.id = null;
      Net.send({ type: 'scan_result', id, ok: true, method: 'fingerprint', device: CFG.device, ts: Date.now() });
      addLog('Huella validada y enviada a la PC', 'ok');
      $('scanHint').textContent = '> ✓ HUELLA ENVIADA. ACCESO CONCEDIDO EN LA PC_';
      $('peerBanner').classList.remove('show');
      toast('ACCESO CONCEDIDO');
      setTimeout(() => Hud.reset(), 1800);
    } else {
      addLog('Huella validada localmente (sin solicitud)', 'ok');
      $('scanHint').textContent = '> ✓ HUELLA VALIDADA (LOCAL)_';
      toast('HUELLA VALIDADA');
      setTimeout(() => Hud.reset(), 1500);
    }
  }
};

/* ------------------------------------------------------------------
   9. FONDO ANIMADO (grid + partículas + scanlines)
   ------------------------------------------------------------------ */
const BG = {
  cvs: null, ctx: null, w: 0, h: 0, parts: [], scanY: 0, dpr: 1,
  init() {
    this.cvs = $('bg'); this.ctx = this.cvs.getContext('2d');
    this.resize();
    window.addEventListener('resize', () => this.resize());
    for (let i = 0; i < 70; i++) this.parts.push(this.newPart());
    requestAnimationFrame(() => this.frame());
  },
  newPart() {
    return {
      x: Math.random(), y: Math.random(),
      vx: (Math.random() - 0.5) * 0.0006, vy: (Math.random() - 0.5) * 0.0006,
      s: 1 + Math.random() * 1.6, b: 0.4 + Math.random() * 0.6,
      p: Math.random() * Math.PI * 2, ps: 0.03 + Math.random() * 0.05
    };
  },
  resize() {
    this.dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.w = window.innerWidth; this.h = window.innerHeight;
    this.cvs.width = Math.round(this.w * this.dpr);
    this.cvs.height = Math.round(this.h * this.dpr);
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
  },
  frame() {
    const c = this.ctx, w = this.w, h = this.h;
    c.fillStyle = '#01040a'; c.fillRect(0, 0, w, h);

    // grid en perspectiva
    const vx = w / 2, vy = h * 0.25;
    c.strokeStyle = 'rgba(34,211,255,.07)'; c.lineWidth = 1;
    const n = 24;
    for (let i = -n; i <= n; i++) {
      c.beginPath(); c.moveTo(vx + i * (w / n), h); c.lineTo(vx, vy); c.stroke();
    }
    for (let i = 1; i <= 16; i++) {
      const t = i / 16;
      const y = vy + (h - vy) * Math.pow(t, 1.4);
      const xl = vx - (vx * Math.pow(t, 0.65));
      const xr = vx + ((w - vx) * Math.pow(t, 0.65));
      c.beginPath(); c.moveTo(xl, y); c.lineTo(xr, y); c.stroke();
    }

    // partículas
    for (const p of this.parts) {
      p.x += p.vx; p.y += p.vy; p.p += p.ps;
      if (p.x < 0) p.x = 1; if (p.x > 1) p.x = 0;
      if (p.y < 0) p.y = 1; if (p.y > 1) p.y = 0;
      const a = p.b * (0.5 + 0.5 * Math.sin(p.p));
      const px = p.x * w, py = p.y * h;
      c.fillStyle = 'rgba(34,211,255,' + (a * 0.18).toFixed(3) + ')';
      c.beginPath(); c.arc(px, py, p.s * 3, 0, Math.PI * 2); c.fill();
      c.fillStyle = 'rgba(34,211,255,' + (a * 0.55).toFixed(3) + ')';
      c.beginPath(); c.arc(px, py, p.s / 2, 0, Math.PI * 2); c.fill();
    }

    // scanline vertical
    this.scanY = (this.scanY + 1.4) % h;
    c.strokeStyle = 'rgba(34,211,255,.12)'; c.lineWidth = 2;
    c.beginPath(); c.moveTo(0, this.scanY); c.lineTo(w, this.scanY); c.stroke();
    c.strokeStyle = 'rgba(0,0,0,.16)'; c.lineWidth = 1;
    for (let y = 0; y < h; y += 4) { c.beginPath(); c.moveTo(0, y); c.lineTo(w, y); c.stroke(); }

    requestAnimationFrame(() => this.frame());
  }
};

/* ------------------------------------------------------------------
   10. CONTROL DEL ESCANEO (táctil / huella real)
   ------------------------------------------------------------------ */
const Scan = {
  active: false,

  start() {
    if (Hud.mode === 'done') return;
    const hasBio = (CFG.biometric && ANDROID && ANDROID.hasBiometric && ANDROID.hasBiometric());
    if (hasBio && !CFG.enrolled) {
      addLog('Primer uso: registra tu huella para este dispositivo', 'warn');
      $('scanHint').textContent = '> REGISTRA TU HUELLA: apoya el dedo en el lector_';
      Hud.set('idle'); Hud.tag('REGISTRAR');
      const prev = window.onBiometricResult;
      window.onBiometricResult = (ok, msg) => {
        window.onBiometricResult = prev;
        if (ok) {
          CFG.enrolled = true; saveCfg();
          addLog('Huella registrada en este dispositivo', 'ok');
          toast('HUELLA REGISTRADA');
          this.realStart();
        } else {
          Hud.reset(); S.fail();
          $('scanHint').textContent = '> REGISTRO CANCELADO_';
          addLog('Registro de huella cancelado', 'err');
        }
      };
      try { ANDROID.authenticate(); } catch (e) { Hud.reset(); }
      return;
    }
    if (CFG.pinPerRequest && Pending.id) {
      askPin('CONFIRMAR HUELLA', () => this.realStart());
      return;
    }
    this.realStart();
  },

  realStart() {
    if (this.active) return;
    this.active = true;
    $('btnScan').classList.add('pressed');
    S.start();
    vibrate(45);

    // ¿huella real disponible?
    if (CFG.biometric && ANDROID && ANDROID.hasBiometric && ANDROID.hasBiometric()) {
      Hud.set(Pending.id ? 'req' : 'local');
      $('scanHint').textContent = '> APOYA TU DEDO EN EL LECTOR_';
      Hud.holding = true;             // animación mientras el sistema pide la huella
      try { ANDROID.authenticate(); } catch (e) { Hud.holding = false; }
      return;
    }

    // modo simulado: mantener presionado
    Hud.mode = Pending.id ? 'req' : 'local';
    Hud.holding = true;
    $('scanHint').textContent = '> CAPTURANDO HUELLA... NO SUELTES_';
    if (Pending.id) Net.send({ type: 'scan_progress', id: Pending.id, progress: 0.05 });
  },

  stop() {
    if (!this.active) return;
    this.active = false;
    $('btnScan').classList.remove('pressed');
    if (Hud.prog > 0 && Hud.prog < 1) {
      Hud.holding = false;
      Hud.mode = 'idle';
      S.fail();
      $('scanHint').textContent = '> ESCANEO CANCELADO. INTENTE DE NUEVO._';
      if (Pending.id) Net.send({ type: 'scan_cancel', id: Pending.id, reason: 'released' });
    } else if (Hud.prog >= 1) {
      Hud.holding = false;
    }
  }
};

/** callback desde Java (BiometricPrompt / FingerprintManager) */
window.onBiometricResult = function (ok, msg) {
  Scan.active = false;
  $('btnScan').classList.remove('pressed');
  Hud.holding = false;
  if (ok) {
    if (CFG.biometric && !CFG.enrolled) { CFG.enrolled = true; saveCfg(); }
    Hud.prog = 0.999;
    Hud.complete();
  } else {
    Hud.reset();
    S.fail(); vibrate([0, 90, 60, 90]);
    $('scanHint').textContent = '> HUELLA NO RECONOCIDA: ' + (msg || 'ERROR') + '_';
    addLog('Huella no reconocida (' + (msg || 'error') + ')', 'err');
    if (Pending.id) Net.send({ type: 'scan_result', id: Pending.id, ok: false, method: 'biometric', device: CFG.device });
  }
};

/* ------------------------------------------------------------------
   11. PIN
   ------------------------------------------------------------------ */
let pinCb = null;
function askPin(title, cb) {
  if (!CFG.pin) { cb && cb(); return; }
  pinCb = cb || null;
  $('pinMsg').textContent = '';
  $('pinInput').value = '';
  $('pinModal').classList.add('show');
  setTimeout(() => $('pinInput').focus(), 120);
}
function closePin() {
  $('pinModal').classList.remove('show');
  pinCb = null;
}
function confirmPin() {
  const v = $('pinInput').value.trim();
  if (v === CFG.pin) {
    const cb = pinCb;
    $('pinModal').classList.remove('show');
    pinCb = null;
    S.click();
    if (cb) cb();
  } else {
    $('pinMsg').textContent = '⚠ PIN INCORRECTO';
    $('pinInput').value = '';
    S.fail(); vibrate([0, 60, 40, 60]);
  }
}

/* ------------------------------------------------------------------
   12. VISTAS
   ------------------------------------------------------------------ */
function switchView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const v = $('view-' + name);
  if (v) v.classList.add('active');
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.view === name));
  if (name === 'hist') renderLog();
}

/* ------------------------------------------------------------------
   13. DESCUBRIMIENTO DE LA PC
   ------------------------------------------------------------------ */
function discover() {
  $('discoverHint').textContent = '> BUSCANDO EN LA RED LOCAL...';
  const done = (ip, port, name) => {
    if (!ip) { $('discoverHint').textContent = '> NO SE ENCONTRÓ NINGUNA PC. ESCRIBE LA IP MANUALMENTE.'; toast('PC NO ENCONTRADA', 'err'); return; }
    CFG.ip = ip; if (port) CFG.port = String(port);
    $('inpIp').value = CFG.ip; $('inpPort').value = CFG.port;
    saveCfg();
    $('discoverHint').textContent = '> ENCONTRADA: ' + (name || 'BioAccess PC') + ' @ ' + ip + ':' + CFG.port;
    toast('PC ENCONTRADA');
    Net.state = 'off'; Net.connect();
  };

  if (ANDROID && (ANDROID.discoverAsync || ANDROID.discover)) {
    let finished = false;
    // callback que invoca el lado Java cuando termina el UDP broadcast
    window.onDiscoverResult = (raw) => {
      if (finished) return;
      finished = true;
      let o = {};
      try { o = JSON.parse(raw || '{}'); } catch (e) { o = {}; }
      done(o.ip, o.port, o.name);
    };
    try {
      if (ANDROID.discoverAsync) ANDROID.discoverAsync();
      else window.onDiscoverResult(ANDROID.discover());
    } catch (e) {
      $('discoverHint').textContent = '> ERROR DE RED: ' + e.message;
    }
    // red de seguridad: si el nativo no responde en 4s, avisa
    setTimeout(() => {
      if (finished) return;
      finished = true;
      $('discoverHint').textContent = '> NO SE ENCONTRÓ NINGUNA PC. ESCRIBE LA IP MANUALMENTE.';
      toast('PC NO ENCONTRADA', 'err');
    }, 4000);
    return;
  }

  // fallback navegador: probar la IP configurada y el origen actual
  const candidates = [];
  if (CFG.ip) candidates.push(CFG.ip);
  if (location.hostname && location.hostname !== 'localhost') candidates.push(location.hostname);
  let i = 0;
  const probe = () => {
    if (i >= candidates.length) { done(null); return; }
    const ip = candidates[i++];
    const secure = isTunnelHost(ip) || (CFG.port === '443' || CFG.port === '' || CFG.port === 443);
    const url = (secure ? 'https://' : 'http://') + ip + (CFG.port ? (':' + CFG.port) : '') + '/api/hello';
    fetch(url, { cache: 'no-store', headers: { 'Bypass-Tunnel-Reminder': 'true' } })
      .then(r => r.json())
      .then(j => done(ip, j.port || CFG.port, j.name))
      .catch(() => probe());
  };
  probe();
}

/* ------------------------------------------------------------------
   13b. VINCULACIÓN POR CÓDIGO QR
   ------------------------------------------------------------------ */
function scanQr() {
  $('discoverHint').textContent = '> ABRIENDO CÁMARA...';
  if (ANDROID && ANDROID.scanQr) {
    window.onQrResult = (raw) => {
      let o = {};
      try { o = JSON.parse(raw || '{}'); } catch (e) { o = {}; }
      if (!o || !o.ok) {
        $('discoverHint').textContent = '> ESCANEO CANCELADO O FALLIDO.';
        toast('QR NO LEÍDO', 'err');
        return;
      }
      pairFromQr(o);
    };
    try { ANDROID.scanQr(); }
    catch (e) { $('discoverHint').textContent = '> ERROR: ' + e.message; }
    return;
  }
  // Fallback navegador: pegar el payload manualmente
  const val = prompt('Pega aquí el payload del QR (bioaccess://pair?...)');
  if (val) pairFromQr({ ok: true, payload: val });
  else $('discoverHint').textContent = '> CANCELADO.';
}

function parseQrPayload(raw) {
  // acepta URI bioaccess://pair?... o JSON
  if (!raw) return null;
  let s = String(raw).trim();
  try { const o = JSON.parse(s); if (o && (o.ip || o.payload)) return o; } catch (e) {}
  const m = s.match(/bioaccess:\/\/pair\?([^\s]+)/i);
  if (m) {
    const params = new URLSearchParams(m[1]);
    return { ip: params.get('ip'), port: params.get('port'), code: params.get('code'),
             name: params.get('name'), pc: params.get('pc') };
  }
  // intenta como query suelta
  try { const p = new URLSearchParams(s); if (p.has('ip')) return { ip: p.get('ip'), port: p.get('port'), code: p.get('code'), name: p.get('name'), pc: p.get('pc') }; } catch (e) {}
  return null;
}

function pairFromQr(o) {
  // intenta extraer payload de cualquier campo posible
  let raw = (o && (o.payload || o.result || o.text || o.raw)) || '';
  if (!raw && typeof o === 'string') raw = o;
  const p = parseQrPayload(raw) || (o || {});
  // fallback: buscar URI bioaccess en todo el objeto serializado
  if (!p.ip) {
    try {
      const m = JSON.stringify(o || {}).match(/bioaccess:\/\/pair\?[^\s"']+/i);
      if (m) { const pp = parseQrPayload(m[0]); if (pp && pp.ip) Object.assign(p, pp); }
    } catch (e) {}
  }
  const ip = (p && p.ip) || o.ip;
  const port = (p && p.port) || o.port || '8080';
  const code = (p && p.code) || o.code || '';
  const name = (p && p.name) || o.name || 'BioAccess PC';
  const pc = (p && p.pc) || o.pc || '';
  if (!ip) { toast('QR SIN IP', 'err'); addLog('QR leído sin IP: ' + JSON.stringify(o).slice(0,200), 'err'); return; }
  $('discoverHint').textContent = '> VERIFICANDO CÓDIGO...';
  // verifica el código contra el servidor (si está disponible)
  const verify = () => {
    CFG.ip = ip; CFG.port = String(port); if (pc) CFG.pcId = pc; saveCfg();
    $('inpIp').value = CFG.ip; $('inpPort').value = CFG.port;
    $('discoverHint').textContent = '> VINCULADA: ' + name + ' @ ' + ip + ':' + port;
    toast('PC VINCULADA POR QR');
    addLog('Vinculación por QR con ' + name + ' (' + ip + ':' + port + ')', 'ok');
    Net.state = 'off'; Net.connect();
  };
  if (code) {
    CFG.ip = ip; CFG.port = String(port); if (pc) CFG.pcId = pc; saveCfg();
    $('inpIp').value = CFG.ip; $('inpPort').value = CFG.port;
    $('discoverHint').textContent = '> VERIFICANDO CÓDIGO EN LA PC...';
    toast('VERIFICANDO CÓDIGO');
    addLog('Vinculando por QR con ' + name + ' (' + ip + ':' + port + ')', 'warn');
    const verifyUrl = httpProto() + ip + (port ? (':' + port) : '') + '/api/pair/verify'
      + '?code=' + encodeURIComponent(code)
      + '&device=' + encodeURIComponent(CFG.device)
      + '&device_id=' + encodeURIComponent(CFG.deviceId || '');

    // Preferir HTTP nativo (bridge Android): evita mixed-content/CORS del WebView.
    const useNative = !!(ANDROID && ANDROID.httpGet);
    const handleOk = () => {
      addLog('Código válido. Esperando aprobación en la PC.', 'ok');
      $('discoverHint').textContent = '> CÓDIGO VÁLIDO. ESPERANDO APROBACIÓN EN LA PC...';
      toast('ESPERANDO APROBACIÓN DE LA PC');
      Net.state = 'off'; Net.connect();
    };
    const handleFail = (rsn) => {
      const r = rsn || 'codigo_invalido';
      addLog('Verificación falló: ' + r, 'err');
      toast('CÓDIGO INVÁLIDO O EXPIRADO', 'err');
      $('discoverHint').textContent = '> ' + r.toUpperCase().replace(/_/g,' ') + '_';
    };
    const fallbackWs = () => {
      addLog('HTTP falló. Intentando por WebSocket...', 'warn');
      toast('HTTP FALLÓ - INTENTANDO WS', 'err');
      window._pendingPair = { code: code, device: CFG.device, device_id: CFG.deviceId || '' };
      $('discoverHint').textContent = '> CONECTANDO POR WS PARA VINCULAR...';
      toast('ESPERANDO APROBACIÓN DE LA PC');
      Net.state = 'off'; Net.connect();
    };

    if (useNative) {
      addLog('Verificando por HTTP nativo: ' + verifyUrl, 'info');
      try {
        const raw = ANDROID.httpGet(verifyUrl);
        addLog('HTTP nativo respuesta: ' + String(raw).slice(0,200), 'info');
        let j = null; try { j = JSON.parse(raw); } catch (e) { j = null; }
        if (j && j.ok) handleOk();
        else handleFail(j && j.reason);
      } catch (e) {
        addLog('HTTP nativo error: ' + (e && e.message ? e.message : e), 'err');
        fallbackWs();
      }
    } else {
      const ctrl = new AbortController();
      const tmo = setTimeout(() => ctrl.abort(), 8000);
      fetch(verifyUrl, { cache: 'no-store', mode: 'cors', signal: ctrl.signal,
                         headers: { 'Bypass-Tunnel-Reminder': 'true' } })
        .then(r => r.json())
        .then(j => {
          clearTimeout(tmo);
          if (j && j.ok) handleOk();
          else handleFail(j && j.reason);
        })
        .catch(e => {
          clearTimeout(tmo);
          addLog('HTTP falló: ' + (e && e.name ? e.name + ': ' : '') + (e && e.message ? e.message : e), 'err');
          addLog('URL intentada: ' + verifyUrl, 'warn');
          fallbackWs();
        });
    }
  } else {
    verify();
  }
}

/* ------------------------------------------------------------------
   13c. VINCULACIÓN POR USB (cable)
   ------------------------------------------------------------------ */
function pairByUsb() {
  if (!(ANDROID && ANDROID.usbConnected && ANDROID.usbConnected())) {
    toast('CONECTA EL CABLE USB A LA PC', 'err');
    addLog('USB no detectado. Conecta el cable y activa depuración USB.', 'err');
    $('discoverHint').textContent = '> USB NO DETECTADO. CONECTA EL CABLE_';
    return;
  }
  const code = (prompt('Ingresa el código de 6 caracteres que muestra la PC (ventana VINCULAR CELULAR):') || '').trim().toUpperCase();
  if (!code) { $('discoverHint').textContent = '> CANCELADO.'; return; }
  // Conexión por localhost vía "adb reverse tcp:8080 tcp:8080" (el instalador lo configura).
  CFG.ip = '127.0.0.1'; CFG.port = '8080'; saveCfg();
  $('inpIp').value = CFG.ip; $('inpPort').value = CFG.port;
  window._pendingPair = { code: code, device: CFG.device, device_id: CFG.deviceId || '' };
  $('discoverHint').textContent = '> CONECTANDO POR USB...';
  toast('ESPERANDO APROBACIÓN DE LA PC');
  addLog('Vinculando por USB (localhost:8080) con código ' + code, 'warn');
  Net.state = 'off'; Net.connect();
  // si no conecta en 6s, avisar sobre adb reverse
  setTimeout(() => {
    if (Net.state !== 'on') {
      addLog('No se pudo conectar por USB. Asegúrate de ejecutar en la PC: adb reverse tcp:8080 tcp:8080', 'err');
      toast('USB: EJECUTA adb reverse EN LA PC', 'err');
      $('discoverHint').textContent = '> EJECUTA EN LA PC: adb reverse tcp:8080 tcp:8080_';
    }
  }, 6000);
}

// deep-link: otra app (o la cámara del sistema) abre bioaccess://pair?...
window.onPairUri = (uri) => { pairFromQr({ payload: uri }); };

/* ------------------------------------------------------------------
   14. AJUSTES — bind UI
   ------------------------------------------------------------------ */
function bindSettings() {
  $('inpIp').value = CFG.ip;
  $('inpPort').value = CFG.port;
  $('inpDevice').value = CFG.device;
  $('chkAuto').checked = !!CFG.auto;
  $('inpSens').value = CFG.sens; $('lblSens').textContent = CFG.sens + '%';
  $('inpTime').value = CFG.time; $('lblTime').textContent = CFG.time + 's';
  $('chkBiometric').checked = !!CFG.biometric;
  $('chkHaptic').checked = !!CFG.haptic;
  $('chkAudio').checked = !!CFG.audio;
  $('inpVol').value = CFG.vol; $('lblVol').textContent = CFG.vol + '%';
  $('chkPin').checked = CFG.pinOnStart;
  $('chkPinReq').checked = CFG.pinPerRequest;
  $('inpPin').value = CFG.pin;

  $('inpSens').oninput = e => { CFG.sens = +e.target.value; $('lblSens').textContent = CFG.sens + '%'; };
  $('inpTime').oninput = e => { CFG.time = +e.target.value; $('lblTime').textContent = CFG.time + 's'; };
  $('inpVol').oninput = e => { CFG.vol = +e.target.value; $('lblVol').textContent = CFG.vol + '%'; };
  $('chkBiometric').onchange = e => { CFG.biometric = e.target.checked; saveCfg(); };
  $('chkHaptic').onchange = e => { CFG.haptic = e.target.checked; saveCfg(); };
  $('chkAudio').onchange = e => { CFG.audio = e.target.checked; saveCfg(); };
  $('chkAuto').onchange = e => {
    CFG.auto = e.target.checked; saveCfg();
    if (CFG.auto) Net.connect(); else Net.disconnect();
  };
  $('btnDiscover').onclick = () => { S.click(); discover(); };
  $('btnQr').onclick = () => { S.click(); scanQr(); };
  $('btnUsb').onclick = () => { S.click(); pairByUsb(); };
  $('btnForget').onclick = () => {
    S.click();
    if (!confirm('¿Olvidar la vinculación con esta PC?')) return;
    CFG.token = ''; CFG.pcId = ''; CFG.enrolled = false; saveCfg();
    addLog('Vinculacion olvidada. Vuelve a escanear el QR.', 'warn');
    toast('VINCULACION OLVIDADA');
    Net.state = 'off'; Net.connect();
  };
  $('btnSave').onclick = () => {
    const oldIp = CFG.ip, oldPort = String(CFG.port);
    CFG.ip = $('inpIp').value.trim() || DEFAULT_CFG.ip;
    CFG.port = $('inpPort').value.trim() || '8080';
    CFG.device = $('inpDevice').value.trim() || 'Celular BioAccess';
    CFG.pinOnStart = $('chkPin').checked;
    CFG.pinPerRequest = $('chkPinReq').checked;
    CFG.pin = $('inpPin').value.trim();
    saveCfg();
    S.click();
    toast('CONFIGURACIÓN GUARDADA');
    addLog('Configuración actualizada (PC ' + CFG.ip + ':' + CFG.port + ')', 'info');
    // prueba HTTP antes de abrir el WebSocket: da un error claro si la PC no es alcanzable
    const probeUrl = httpProto() + CFG.ip + hostPort() + '/api/hello';
    fetch(probeUrl, { cache: 'no-store', mode: 'cors', headers: { 'Bypass-Tunnel-Reminder': 'true' } })
      .then(r => r.json())
      .then(j => {
        addLog('PC alcanzable: ' + (j.name || 'BioAccess PC') + ' v' + (j.version || '?'), 'ok');
        toast('PC ALCANZABLE');
        Net.state = 'off';
        if (Net.ws) { try { Net.ws.close(); } catch (e) {} Net.ws = null; }
        Net.connect();
      })
      .catch(e => {
        addLog('NO se puede alcanzar la PC en ' + probeUrl, 'err');
        toast('PC NO ALCANZABLE - revisa WiFi/firewall/IP', 'err');
        addLog('Verifica: 1) misma WiFi, 2) firewall Windows (TCP ' + CFG.port + '), 3) IP correcta (ipconfig en la PC)', 'warn');
      });
    showDevInfo();
  };
}

function showDevInfo() {
  const durable = (Net.server || '—');
  $('devInfo').innerHTML =
    'SERVIDOR: <b>' + escapeHtml(durable) + '</b><br>' +
    'PC: <b>' + escapeHtml(Net.pcName || 'sin identificar') + '</b><br>' +
    'DISPOSITIVO: <b>' + escapeHtml(CFG.device) + '</b><br>' +
    'ENLACE: <b>' + (Net.state === 'on' ? 'ONLINE' : 'OFFLINE') + '</b> · ws://' + escapeHtml(CFG.ip + ':' + CFG.port) + '<br>' +
    'MODO: <b>' + (IS_APK ? 'APK NATIVO' : 'NAVEGADOR') + '</b>';
}

/* ------------------------------------------------------------------
   15. ARRANQUE
   ------------------------------------------------------------------ */
function boot() {
  BG.init();
  Hud.init();
  bindSettings();
  renderLog();
  addLog('Sistema iniciado (' + (IS_APK ? 'APK' : 'navegador') + ')', 'info');

  // tabs
  document.querySelectorAll('.tab').forEach(t => {
    t.onclick = () => { switchView(t.dataset.view); S.click(); };
  });

  // escáner: mantener presionado
  const btn = $('btnScan');
  const down = (e) => { e.preventDefault(); Scan.start(); };
  const up = (e) => { e.preventDefault(); Scan.stop(); };

  btn.addEventListener('touchstart', down, { passive: false });
  btn.addEventListener('touchend', up, { passive: false });
  btn.addEventListener('touchcancel', up, { passive: false });
  btn.addEventListener('mousedown', down);
  btn.addEventListener('mouseup', up);
  btn.addEventListener('mouseleave', up);

  // tocar el propio sensor también escanea
  const hudCvs = $('hud');
  hudCvs.addEventListener('touchstart', down, { passive: false });
  hudCvs.addEventListener('touchend', up, { passive: false });

  // historial
  $('btnClearHist').onclick = () => {
    LOG = []; saveLog(); renderLog(); S.click();
    addLog('Historial limpiado', 'warn');
  };

  // pin modal
  $('pinOk').onclick = confirmPin;
  $('pinCancel').onclick = closePin;
  $('pinInput').addEventListener('keydown', e => { if (e.key === 'Enter') confirmPin(); });

  // primer toque habilita audio
  ['touchstart', 'mousedown'].forEach(ev =>
    document.addEventListener(ev, function once() {
      try { actx = actx || new (window.AudioContext || window.webkitAudioContext)(); } catch (e) {}
      document.removeEventListener(ev, once);
    }, { once: true })
  );

  // PIN de entrada
  if (CFG.pinOnStart && CFG.pin) askPin('DESBLOQUEAR', null);

  // conectar
  $('connChip').onclick = () => { Net.state = 'off'; if (Net.ws) { try { Net.ws.close(); } catch (e) {} Net.ws = null; } Net.connect(); };
  Net.connect();
  showDevInfo();
  setInterval(showDevInfo, 4000);

  // autodescubrimiento automatico si no hay IP conocida o es la IP por defecto
  if (CFG.auto) {
    const needDiscover = !CFG.ip || CFG.ip === '192.168.1.50' || CFG.ip === '127.0.0.1';
    setTimeout(() => {
      if (needDiscover) { try { discover(); } catch (e) {} }
    }, 1500);
    // reintento si sigue offline
    setTimeout(() => {
      if (Net.state !== 'on' && CFG.auto) { try { discover(); } catch (e) {} }
    }, 7000);
  }

  // progreso remoto -> enviar a la PC mientras se mantiene
  setInterval(() => {
    if (Hud.holding && Pending.id) {
      Net.send({ type: 'scan_progress', id: Pending.id, progress: +Hud.prog.toFixed(3) });
    }
  }, 120);
}

document.addEventListener('DOMContentLoaded', boot);
