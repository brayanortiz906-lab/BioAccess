# -*- coding: utf-8 -*-
"""
=======================================================================
 BioAccess Bridge Server  —  puente PC <-> Celular
=======================================================================
Servidor local (LAN) que interconecta el terminal de escritorio
(bioaccess.py / bioaccess.exe) con la app Android (BioAccess Mobile APK)
o con el navegador del celular.

  PC  <--- WebSocket --->  [ESTE SERVIDOR]  <--- WebSocket --->  CELULAR

- HTTP  : http://<ip-pc>:8080/mobile   -> interfaz movil (misma que el APK)
- WS    : ws://<ip-pc>:8080/ws?role=pc|phone&device=<nombre>
- UDP   : puerto 8089 -> autodescubrimiento desde el celular
- API   : /api/hello, /api/events, /api/state

Uso:
    python bioaccess_server.py                 (standalone)
    python bioaccess_server.py --port 8080
"""

import argparse
import asyncio
import json
import os
import secrets
import socket
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

if getattr(sys, "frozen", False):
    # Dentro del .exe: los recursos están en _MEIPASS, los datos van a %APPDATA%
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    DATA_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "BioAccess"
else:
    BASE_DIR = Path(__file__).resolve().parent
    DATA_DIR = BASE_DIR

try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    DATA_DIR = BASE_DIR

MOBILE_DIR = BASE_DIR / "mobile"
EVENTS_FILE = DATA_DIR / "bioaccess_events.json"

SERVER_NAME = "BioAccess PC"
VERSION = "2.0.1"
DEFAULT_PORT = 8080
DISCOVERY_PORT = 8089
DISCOVERY_MAGIC = "BIOACCESS_DISCOVER"

MAX_EVENTS = 400
REQUEST_TTL = 30          # segundos que vive una solicitud de huella
_PORT = DEFAULT_PORT      # puerto real en uso (lo ajusta main/EmbeddedServer)


# =====================================================================
#  Identidad de la PC y dispositivos vinculados (aprobación explícita)
# =====================================================================
IDENTITY_FILE = DATA_DIR / "pc_identity.json"
TRUSTED_FILE = DATA_DIR / "trusted_devices.json"
PAIR_NONCE_TTL = 300


def _load_json(path, default):
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _save_json(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def pc_identity():
    d = _load_json(IDENTITY_FILE, {})
    if not d.get("pc_id"):
        d["pc_id"] = str(uuid.uuid4())
        d["pc_secret"] = secrets.token_hex(32)
        _save_json(IDENTITY_FILE, d)
    return d


def trusted_devices():
    d = _load_json(TRUSTED_FILE, {"devices": []})
    if not isinstance(d, dict) or not isinstance(d.get("devices"), list):
        d = {"devices": []}
    return d


def save_trusted(d):
    _save_json(TRUSTED_FILE, d)


def find_trusted(device_id):
    for dev in trusted_devices()["devices"]:
        if dev.get("device_id") == device_id:
            return dev
    return None


def is_trusted(device_id, token):
    dev = find_trusted(device_id)
    if not dev:
        return False
    return secrets.compare_digest(str(dev.get("token", "")), str(token or ""))


def add_trusted(device_id, device_name, token):
    d = trusted_devices()
    # reemplaza si ya existía
    d["devices"] = [x for x in d["devices"] if x.get("device_id") != device_id]
    d["devices"].append({
        "device_id": device_id,
        "device_name": (device_name or "Celular")[:40],
        "token": token,
        "paired_at": datetime.now().isoformat(timespec="seconds"),
    })
    save_trusted(d)


def revoke_trusted(device_id):
    d = trusted_devices()
    before = len(d["devices"])
    d["devices"] = [x for x in d["devices"] if x.get("device_id") != device_id]
    save_trusted(d)
    return before != len(d["devices"])


# pending pair requests: request_id -> {device, device_id, code, ts, peer_id, accepted}
_PENDING_PAIRS = {}


def create_pending_pair(device, device_id, code):
    rid = str(uuid.uuid4())
    _PENDING_PAIRS[rid] = {
        "device": device, "device_id": device_id, "code": code,
        "ts": time.time(), "peer_id": None, "accepted": None,
        "pair_nonce": secrets.token_hex(8),
    }
    return rid


def get_pending(rid):
    p = _PENDING_PAIRS.get(rid)
    if p and (time.time() - p["ts"]) > 300:
        _PENDING_PAIRS.pop(rid, None)
        return None
    return p


def cleanup_pending():
    now = time.time()
    for rid in [r for r, p in _PENDING_PAIRS.items() if now - p["ts"] > 300]:
        _PENDING_PAIRS.pop(rid, None)





# =====================================================================
#  Utilidades
# =====================================================================
def now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


def local_ip() -> str:
    """IP de la PC en la LAN (la que debe escribir el celular)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"
    finally:
        s.close()


# =====================================================================
#  Código de emparejamiento (QR / PIN de 6 caracteres)
# =====================================================================
PAIR_TTL = 600          # el código del QR vive 10 minutos
_PAIR = {"code": "", "expires": 0.0, "used_by": ""}
PAIR_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def pair_code(refresh: bool = False) -> str:
    """Devuelve el código de emparejamiento vigente (lo crea si hace falta)."""
    now = time.time()
    if refresh or not _PAIR["code"] or now > _PAIR["expires"]:
        _PAIR["code"] = "".join(secrets.choice(PAIR_ALPHABET) for _ in range(6))
        _PAIR["expires"] = now + PAIR_TTL
        _PAIR["used_by"] = ""
    return _PAIR["code"]


def pair_payload(ip: str, port: int, name: str = SERVER_NAME) -> str:
    """URI que se dibuja dentro del QR (la escanea la APK)."""
    code = pair_code()
    pcid = pc_identity()["pc_id"]
    return f"bioaccess://pair?ip={ip}&port={port}&code={code}&name={name.replace(' ', '%20')}&pc={pcid}"


def verify_pair(code: str, device: str = "") -> Tuple[bool, str]:
    now = time.time()
    if not _PAIR["code"] or now > _PAIR["expires"]:
        return False, "codigo_expirado"
    if (code or "").strip().upper() != _PAIR["code"]:
        return False, "codigo_invalido"
    _PAIR["used_by"] = device or "celular"
    return True, "ok"


def load_events() -> List[dict]:
    try:
        if EVENTS_FILE.exists():
            with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data[-MAX_EVENTS:]
    except Exception:
        pass
    return []


def save_events(events: List[dict]) -> None:
    try:
        with open(EVENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(events[-MAX_EVENTS:], f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# =====================================================================
#  Hub de conexiones
# =====================================================================
class Peer:
    __slots__ = ("ws", "role", "device", "since", "id", "device_id", "token", "trusted")

    def __init__(self, ws: WebSocket, role: str, device: str):
        self.ws = ws
        self.role = role
        self.device = device
        self.since = time.time()
        self.id = str(uuid.uuid4())[:8]
        self.device_id = ""
        self.token = ""
        self.trusted = False

    def info(self) -> dict:
        return {"role": self.role, "device": self.device, "id": self.id,
                "since": int(self.since), "device_id": self.device_id,
                "trusted": self.trusted}


class Hub:
    """Registro de clientes conectados + difusión de mensajes."""

    def __init__(self) -> None:
        self.peers: Dict[str, Peer] = {}
        self.lock = threading.Lock()
        self.events: List[dict] = load_events()
        self.pending: Optional[dict] = None      # solicitud activa
        self.last_token: Optional[str] = None

    # ---------------- conexiones ----------------
    def add(self, peer: Peer) -> None:
        with self.lock:
            self.peers[peer.id] = peer

    def remove(self, peer_id: str) -> Optional[Peer]:
        with self.lock:
            return self.peers.pop(peer_id, None)

    def by_role(self, role: str) -> List[Peer]:
        with self.lock:
            return [p for p in self.peers.values() if p.role == role]

    def peer_list(self) -> List[dict]:
        with self.lock:
            return [p.info() for p in self.peers.values()]

    # ---------------- mensajería ----------------
    async def send(self, peer: Peer, payload: dict) -> None:
        try:
            await peer.ws.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass

    async def broadcast(self, payload: dict, role: Optional[str] = None,
                        exclude: Optional[str] = None) -> None:
        targets = self.by_role(role) if role else list(self.peers.values())
        for p in targets:
            if exclude and p.id == exclude:
                continue
            await self.send(p, payload)

    async def log(self, text: str, level: str = "info", to_all: bool = True) -> None:
        entry = {"t": now_str(), "text": text, "level": level}
        self.events.append(entry)
        save_events(self.events)
        if to_all:
            await self.broadcast({"type": "log", "ts": entry["t"],
                                  "text": text, "level": level})

    # ---------------- estado ----------------
    def state(self) -> dict:
        return {
            "server": SERVER_NAME,
            "version": VERSION,
            "ip": local_ip(),
            "port": globals().get("_PORT", DEFAULT_PORT),
            "peers": self.peer_list(),
            "pending": self.pending,
            "events": self.events[-40:],
        }


HUB = Hub()


# =====================================================================
#  App FastAPI
# =====================================================================
app = FastAPI(title="BioAccess Bridge", version=VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/")
async def root():
    return RedirectResponse(url="/mobile/index.html")


@app.get("/api/hello")
async def api_hello():
    return {"name": SERVER_NAME, "version": VERSION,
            "ip": local_ip(), "port": globals().get("_PORT", DEFAULT_PORT), "ok": True}


@app.get("/api/state")
async def api_state():
    return HUB.state()


@app.get("/api/events")
async def api_events():
    return {"events": HUB.events}


@app.post("/api/request")
async def api_request(ttl: int = REQUEST_TTL):
    """Solicitud de huella lanzada por HTTP (para pruebas o integraciones)."""
    req = {"id": str(uuid.uuid4()), "ts": time.time(), "ttl": ttl, "from": SERVER_NAME}
    HUB.pending = req
    phones = HUB.by_role("phone")
    trusted = [ph for ph in phones if ph.trusted]
    if not trusted:
        if phones:
            await HUB.log("Solicitud rechazada: celular conectado pero no vinculado", "warn")
            return JSONResponse({"ok": False, "error": "sin_celular_vinculado"}, status_code=409)
        await HUB.log("Solicitud rechazada: ningun celular conectado", "warn")
        return JSONResponse({"ok": False, "error": "sin_celular"}, status_code=409)
    for ph in trusted:
        await HUB.send(ph, {"type": "scan_request", "id": req["id"], "ttl": ttl,
                            "from": SERVER_NAME})
    await HUB.log("Solicitud de huella enviada al celular", "warn")
    return {"ok": True, "id": req["id"]}


@app.get("/api/pair")
async def api_pair(refresh: bool = False):
    """Datos que van dentro del código QR de emparejamiento."""
    ip = local_ip()
    port = globals().get("_PORT", DEFAULT_PORT)
    code = pair_code(refresh=refresh)
    return {"ok": True, "ip": ip, "port": port, "code": code,
            "name": SERVER_NAME, "version": VERSION,
            "pc_id": pc_identity()["pc_id"],
            "expires": int(_PAIR["expires"]),
            "payload": pair_payload(ip, port)}


# Rate-limit simple para /api/pair/verify (por IP)
_PAIR_VERIFY_HITS = {}
PAIR_VERIFY_LIMIT = 5
PAIR_VERIFY_WINDOW = 60.0


def _rate_ok(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _PAIR_VERIFY_HITS.get(ip, []) if now - t < PAIR_VERIFY_WINDOW]
    if len(hits) >= PAIR_VERIFY_LIMIT:
        _PAIR_VERIFY_HITS[ip] = hits
        return False
    hits.append(now)
    _PAIR_VERIFY_HITS[ip] = hits
    return True


@app.get("/api/pair/verify")
async def api_pair_verify(code: str = "", device: str = "", device_id: str = "",
                         pair_nonce: str = "", request: Request = None):
    """La APK canjea el código del QR. No vincula automáticamente: crea una
    solicitud pendiente y pide aprobación explícita a la PC."""
    cleanup_pending()
    # rate-limit por IP
    client_ip = ""
    try:
        if request is not None and getattr(request, "client", None) is not None:
            client_ip = request.client.host
    except Exception:
        client_ip = ""
    if not _rate_ok(client_ip or "unknown"):
        return {"ok": False, "reason": "demasiados_intentos",
                "ip": local_ip(), "port": globals().get("_PORT", DEFAULT_PORT)}
    # validate code against the current pair code
    now = time.time()
    if not _PAIR["code"] or now > _PAIR["expires"] or (code or "").strip().upper() != _PAIR["code"]:
        return {"ok": False, "reason": "codigo_invalido_o_expirado",
                "ip": local_ip(), "port": globals().get("_PORT", DEFAULT_PORT)}
    rid = create_pending_pair(device or "Celular", device_id or "", code)
    pnd = get_pending(rid)
    if pair_nonce:
        pnd["pair_nonce"] = pair_nonce
    # notify connected PCs
    for pc in HUB.by_role("pc"):
        try:
            await HUB.send(pc, {"type": "pair_request", "request_id": rid,
                                "device": device or "Celular", "device_id": device_id,
                                "ts": now_str()})
        except Exception:
            pass
    await HUB.log(f"Solicitud de vinculación: {device or 'Celular'}", "warn")
    return {"ok": True, "pending": True, "request_id": rid,
            "pair_nonce": pnd["pair_nonce"],
            "pc_id": pc_identity()["pc_id"],
            "ip": local_ip(), "port": globals().get("_PORT", DEFAULT_PORT)}


@app.post("/api/pair/decision")
async def api_pair_decision(request_id: str = "", accept: bool = False):
    """La PC aprueba o rechaza una vinculación pendiente."""
    pnd = get_pending(request_id)
    if not pnd:
        return JSONResponse({"ok": False, "reason": "solicitud_expirada_o_inexistente"}, status_code=404)
    pnd["accepted"] = bool(accept)
    if not accept:
        # notify phone
        for ph in HUB.by_role("phone"):
            if ph.device_id == pnd["device_id"] or not pnd["device_id"]:
                try:
                    await HUB.send(ph, {"type": "pair_result", "request_id": request_id,
                                        "ok": False, "reason": "rechazado_por_pc"})
                except Exception:
                    pass
        _PENDING_PAIRS.pop(request_id, None)
        await HUB.log(f"Vinculación rechazada: {pnd['device']}", "warn")
        return {"ok": True, "accepted": False}

    # accept: generate token
    token = secrets.token_hex(32)
    add_trusted(pnd["device_id"] or str(uuid.uuid4()), pnd["device"], token)
    dev_id = pnd["device_id"] or find_trusted(None) and ""
    # find the actual device_id stored
    tr = trusted_devices()["devices"][-1]
    dev_id = tr["device_id"]
    # notify phone
    for ph in HUB.by_role("phone"):
        if (not pnd["device_id"]) or ph.device_id == pnd["device_id"]:
            try:
                await HUB.send(ph, {"type": "pair_result", "request_id": request_id,
                                    "ok": True, "token": token,
                                    "pc_id": pc_identity()["pc_id"],
                                    "pair_nonce": pnd["pair_nonce"]})
            except Exception:
                pass
            ph.trusted = True
            ph.token = token
            ph.device_id = dev_id
    _PENDING_PAIRS.pop(request_id, None)
    await HUB.log(f"Dispositivo vinculado: {pnd['device']}", "ok")
    return {"ok": True, "accepted": True, "device_id": dev_id, "token": token}


@app.get("/api/pair/trusted")
async def api_pair_trusted():
    return {"devices": trusted_devices()["devices"]}


@app.get("/api/pair/pending")
async def api_pair_pending():
    cleanup_pending()
    out = []
    for rid, pnd in _PENDING_PAIRS.items():
        out.append({"request_id": rid, "device": pnd.get("device"),
                    "device_id": pnd.get("device_id"), "ts": pnd.get("ts")})
    return {"pending": out}


@app.post("/api/pair/revoke")
async def api_pair_revoke(device_id: str = ""):
    ok = revoke_trusted(device_id)
    # disconnect trusted peers with that device_id
    for ph in list(HUB.by_role("phone")):
        if ph.device_id == device_id:
            ph.trusted = False
            ph.token = ""
            try:
                await HUB.send(ph, {"type": "pair_revoked"})
            except Exception:
                pass
    if ok:
        await HUB.log(f"Dispositivo revocado: {device_id}", "warn")
    return {"ok": ok}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, role: str = "phone", device: str = "Desconocido",
                     device_id: str = "", token: str = ""):
    await ws.accept()
    role = role if role in ("pc", "phone") else "phone"
    peer = Peer(ws, role, device[:40] or "Desconocido")
    peer.device_id = (device_id or "")[:64]
    peer.token = (token or "")[:128]
    if role == "phone" and peer.device_id:
        peer.trusted = is_trusted(peer.device_id, peer.token)
    HUB.add(peer)

    await HUB.send(peer, {
        "type": "hello_ack",
        "server": SERVER_NAME, "version": VERSION,
        "ip": local_ip(), "port": globals().get("_PORT", DEFAULT_PORT),
        "pc_id": pc_identity()["pc_id"],
        "you": peer.info(), "peers": HUB.peer_list(),
        "pc_name": next((p.device for p in HUB.by_role("pc")), None),
        "trusted": peer.trusted,
    })
    await HUB.broadcast({"type": "peer_joined", "role": peer.role,
                         "device": peer.device, "id": peer.id,
                         "trusted": peer.trusted,
                         "device_id": peer.device_id},
                        exclude=peer.id)
    await HUB.log(("Terminal PC conectado: " if role == "pc" else "Celular conectado: ") + peer.device,
                  "info" if role == "phone" else "ok", to_all=False)
    await HUB.broadcast({"type": "log",
                         "text": ("Terminal PC conectado" if role == "pc" else "Celular conectado: " + peer.device),
                         "level": "ok" if role == "pc" else "info",
                         "ts": now_str()}, exclude=peer.id)

    # si el celular entra y hay una solicitud viva, se la reenviamos (solo si esta vinculado)
    if role == "phone" and peer.trusted and HUB.pending and (time.time() - HUB.pending["ts"]) < HUB.pending["ttl"]:
        await HUB.send(peer, {"type": "scan_request", "id": HUB.pending["id"],
                              "ttl": HUB.pending["ttl"], "from": SERVER_NAME})

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            await handle_message(peer, msg)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        HUB.remove(peer.id)
        await HUB.broadcast({"type": "peer_left", "role": peer.role,
                             "device": peer.device, "id": peer.id})
        await HUB.broadcast({"type": "log", "level": "warn", "ts": now_str(),
                             "text": ("Terminal PC desconectado" if peer.role == "pc"
                                      else "Celular desconectado: " + peer.device)})


async def handle_message(peer: Peer, msg: dict) -> None:
    mtype = msg.get("type", "")

    # ---------------- handshake ----------------
    if mtype == "hello":
        peer.device = str(msg.get("device") or peer.device)[:40]
        await HUB.send(peer, {"type": "hello_ack", "server": SERVER_NAME,
                              "version": VERSION, "ip": local_ip(),
                              "port": globals().get("_PORT", DEFAULT_PORT), "you": peer.info(),
                              "peers": HUB.peer_list()})
        await HUB.broadcast({"type": "peer_joined", "role": peer.role,
                             "device": peer.device, "id": peer.id}, exclude=peer.id)
        return

    # ---------------- solicitud de vinculacion por WS (desde QR) ----------------
    if mtype == "pair_request" and peer.role == "phone":
        code = (msg.get("code") or "").strip().upper()
        device = (msg.get("device") or peer.device or "Celular")[:40]
        device_id = (msg.get("device_id") or peer.device_id or "")[:64]
        print(f"[PAIR_WS] recibido code={code} device={device} device_id={device_id} expected={_PAIR.get('code')}", flush=True)
        # validate code
        now = time.time()
        if not _PAIR["code"] or now > _PAIR["expires"] or code != _PAIR["code"]:
            print("[PAIR_WS] codigo invalido o expirado", flush=True)
            await HUB.send(peer, {"type": "pair_result", "ok": False,
                                  "reason": "codigo_invalido_o_expirado"})
            await HUB.log("Vinculacion WS rechazada: codigo invalido", "warn")
            return
        print("[PAIR_WS] codigo valido, creando pending", flush=True)
        rid = create_pending_pair(device, device_id, code)
        pnd = get_pending(rid)
        pn = msg.get("pair_nonce")
        if pn:
            pnd["pair_nonce"] = pn
        # notify connected PCs
        pcs = HUB.by_role("pc")
        print(f"[PAIR_WS] PCs conectados: {len(pcs)}", flush=True)
        for pc in pcs:
            try:
                await HUB.send(pc, {"type": "pair_request", "request_id": rid,
                                    "device": device, "device_id": device_id,
                                    "ts": now_str()})
                print(f"[PAIR_WS] enviado pair_request a PC {pc.device}", flush=True)
            except Exception as e:
                print(f"[PAIR_WS] error enviando a PC: {e}", flush=True)
        await HUB.log(f"Solicitud de vinculacion (WS): {device}", "warn")
        await HUB.send(peer, {"type": "pair_pending", "request_id": rid})
        await HUB.send(peer, {"type": "pair_pending", "request_id": rid})
        return

    # ---------------- PC pide huella ----------------
    if mtype == "scan_request":
        if peer.role != "pc":
            await HUB.send(peer, {"type": "error", "error": "solo_pc_puede_solicitar"})
            return
        ttl = int(msg.get("ttl") or REQUEST_TTL)
        req = {"id": str(uuid.uuid4()), "ts": time.time(), "ttl": ttl,
               "from": peer.device}
        HUB.pending = req
        trusted_phones = [ph for ph in HUB.by_role("phone") if ph.trusted]
        if not trusted_phones:
            if HUB.by_role("phone"):
                await HUB.send(peer, {"type": "scan_result", "id": req["id"], "ok": False,
                                      "error": "sin_celular_vinculado", "method": "none"})
                await HUB.log("Solicitud fallida: celular conectado pero no vinculado", "warn")
            else:
                await HUB.send(peer, {"type": "scan_result", "id": req["id"], "ok": False,
                                      "error": "sin_celular", "method": "none"})
                await HUB.log("Solicitud fallida: ningun celular conectado", "err")
            HUB.pending = None
            return
        for ph in trusted_phones:
            await HUB.send(ph, {"type": "scan_request", "id": req["id"], "ttl": ttl,
                                "from": peer.device})
        await HUB.send(peer, {"type": "scan_pending", "id": req["id"], "ttl": ttl,
                              "phones": len(trusted_phones)})
        await HUB.log("Solicitud de huella enviada al celular vinculado", "warn")
        return

    # ---------------- celular avanza ----------------
    if mtype == "scan_progress":
        if peer.role == "phone" and peer.trusted:
            await HUB.broadcast({"type": "scan_progress",
                                 "id": msg.get("id"),
                                 "progress": msg.get("progress", 0)},
                                role="pc")
        return

    # ---------------- celular responde ----------------
    if mtype == "scan_result":
        if peer.role == "phone" and not peer.trusted:
            await HUB.log("scan_result ignorado: celular no vinculado", "warn")
            return
        ok = bool(msg.get("ok"))
        token = uuid.uuid4().hex[:12].upper() if ok else None
        if ok:
            HUB.last_token = token
        HUB.pending = None
        result = {"type": "scan_result", "id": msg.get("id"), "ok": ok,
                  "method": msg.get("method", "fingerprint"),
                  "device": peer.device, "ts": now_str(),
                  "token": token}
        await HUB.broadcast(result, role="pc")
        await HUB.broadcast({"type": "access_granted" if ok else "access_denied",
                             "token": token, "device": peer.device}, role="phone",
                            exclude=peer.id)
        if ok:
            await HUB.log("HUELLA AUTENTICADA · acceso concedido (token " + token + ")", "ok")
        else:
            await HUB.log("HUELLA RECHAZADA por el celular", "err")
        return

    # ---------------- cancelaciones ----------------
    if mtype in ("scan_cancel", "cancel"):
        HUB.pending = None
        await HUB.broadcast({"type": "scan_cancel", "id": msg.get("id"),
                             "reason": msg.get("reason", "cancelado"),
                             "device": peer.device},
                            exclude=peer.id)
        await HUB.log("Solicitud cancelada por " + peer.device, "warn")
        return

    if mtype == "ping":
        await HUB.send(peer, {"type": "pong", "ts": time.time()})
        return

    if mtype == "log":
        await HUB.log(str(msg.get("text", ""))[:200], msg.get("level", "info"))
        return


# =====================================================================
#  Autodescubrimiento UDP (el celular pregunta "¿quién es BioAccess?")
# =====================================================================
def start_discovery_responder(port: int) -> Optional[socket.socket]:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except Exception:
            pass
        sock.bind(("", DISCOVERY_PORT))
        sock.settimeout(1.0)
    except Exception:
        return None

    payload = json.dumps({"name": SERVER_NAME, "ip": local_ip(), "port": port,
                          "version": VERSION}).encode("utf-8")

    def loop() -> None:
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                txt = data.decode("utf-8", "ignore").strip()
                if txt.startswith(DISCOVERY_MAGIC):
                    sock.sendto(payload, addr)
            except socket.timeout:
                continue
            except OSError:
                return
            except Exception:
                continue

    threading.Thread(target=loop, daemon=True).start()
    return sock


# =====================================================================
#  Servidor embebido (lo usa bioaccess.py)
# =====================================================================
class EmbeddedServer:
    """Arranca uvicorn en un hilo daemon dentro de la app de escritorio."""

    def __init__(self, host: str = "0.0.0.0", port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.thread: Optional[threading.Thread] = None
        self.server = None
        self._sock = None

    def start(self) -> bool:
        global _PORT
        _PORT = self.port
        try:
            import uvicorn
        except Exception:
            return False
        cfg = uvicorn.Config(app, host=self.host, port=self.port,
                             log_level="warning", access_log=False)
        self.server = uvicorn.Server(cfg)

        def run() -> None:
            try:
                asyncio.run(self.server.serve())
            except Exception:
                pass

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        self._sock = start_discovery_responder(self.port)
        for _ in range(40):
            time.sleep(0.05)
            try:
                s = socket.create_connection(("127.0.0.1", self.port), timeout=0.25)
                s.close()
                return True
            except Exception:
                continue
        return False

    def stop(self) -> None:
        try:
            if self.server:
                self.server.should_exit = True
        except Exception:
            pass
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass


def mount_static() -> None:
    if MOBILE_DIR.is_dir():
        app.mount("/mobile", StaticFiles(directory=str(MOBILE_DIR), html=True), name="mobile")


mount_static()


def main() -> None:
    global DEFAULT_PORT, SERVER_NAME, _PORT
    ap = argparse.ArgumentParser(description="BioAccess Bridge Server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--name", default=SERVER_NAME)
    args = ap.parse_args()

    DEFAULT_PORT = args.port
    SERVER_NAME = args.name
    _PORT = args.port

    print("=" * 66)
    print("  BIOACCESS BRIDGE SERVER v" + VERSION)
    print("=" * 66)
    print("  IP de la PC   : " + local_ip())
    print("  Puerto        : " + str(args.port))
    print("  Movil (web)   : http://%s:%d/mobile   (en el celular)" % (local_ip(), args.port))
    print("  WebSocket     : ws://%s:%d/ws" % (local_ip(), args.port))
    print("  Descubrimiento: UDP %d" % DISCOVERY_PORT)
    print("=" * 66)
    print("  Abre esta IP:PUERTO en la APK BioAccess Mobile, o escanea el QR")
    print("  que muestra el terminal de escritorio.")
    print("=" * 66)

    import uvicorn
    start_discovery_responder(args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
