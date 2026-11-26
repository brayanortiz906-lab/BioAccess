# -*- coding: utf-8 -*-
"""
Autotest del puente BioAccess (sin GUI ni celular).
Simula: vinculación aprobada -> PC pide huella -> celular responde -> PC recibe token.

    python tools/selftest_bridge.py
"""
import json
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bioaccess_server import EmbeddedServer  # noqa: E402
from websockets.sync.client import connect  # noqa: E402

PORT = 8099
server = EmbeddedServer(port=PORT)
assert server.start(), "el servidor no arrancó"
print("[OK] servidor arriba en", PORT)

DEVICE_ID = "test-device-001"

pc = connect(f"ws://127.0.0.1:{PORT}/ws?role=pc&device=PC-Test", open_timeout=3, legacy=True)
phone = connect(f"ws://127.0.0.1:{PORT}/ws?role=phone&device=Celular-Test&device_id={DEVICE_ID}", open_timeout=3, legacy=True)
time.sleep(0.3)


def drain(ws):
    out = []
    while True:
        try:
            out.append(json.loads(ws.recv(timeout=0.15)))
        except TimeoutError:
            return out
        except Exception:
            return out


print("[PC] handshake:", [m["type"] for m in drain(pc)])
print("[PHONE] handshake:", [m["type"] for m in drain(phone)])

# 0) vincular el celular (aprobación explícita de la PC)
with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/pair", timeout=3) as r:
    code = json.loads(r.read().decode())["code"]
vr = json.loads(urllib.request.urlopen(
    f"http://127.0.0.1:{PORT}/api/pair/verify?code={code}&device=Celular-Test&device_id={DEVICE_ID}").read().decode())
assert vr.get("ok") and vr.get("pending"), vr
rid_pair = vr["request_id"]
data = urllib.parse.urlencode({"request_id": rid_pair, "accept": "true"}).encode()
req = urllib.request.Request(
    f"http://127.0.0.1:{PORT}/api/pair/decision?request_id={rid_pair}&accept=true",
    data=data, method="POST")
dr = json.loads(urllib.request.urlopen(req).read().decode())
assert dr.get("accepted") is True, dr
print("[OK] celular vinculado (token emitido)")

# 1) la PC solicita la huella
pc.send(json.dumps({"type": "scan_request", "ttl": 30}))
time.sleep(0.3)
pc_msgs = drain(pc)
ph_msgs = drain(phone)
assert any(m["type"] == "scan_pending" for m in pc_msgs), pc_msgs
assert any(m["type"] == "scan_request" for m in ph_msgs), ph_msgs
req_id = [m for m in ph_msgs if m["type"] == "scan_request"][0]["id"]
print("[OK] PC pidió huella, celular recibió la solicitud", req_id[:8])

# 2) el celular reporta progreso
for p in (0.25, 0.5, 0.75):
    phone.send(json.dumps({"type": "scan_progress", "id": req_id, "progress": p}))
time.sleep(0.25)
prog = [m for m in drain(pc) if m["type"] == "scan_progress"]
assert prog, "no llegó el progreso a la PC"
print("[OK] progreso recibido en la PC:", [m["progress"] for m in prog])

# 3) el celular valida la huella
phone.send(json.dumps({"type": "scan_result", "id": req_id, "ok": True,
                       "method": "biometric", "device": "Celular-Test"}))
time.sleep(0.3)
res = [m for m in drain(pc) if m["type"] == "scan_result"]
assert res and res[0]["ok"] and res[0]["token"], res
print("[OK] PC recibió ACCESO CONCEDIDO — token", res[0]["token"])

# 4) HTTP
with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/hello", timeout=3) as r:
    print("[OK] /api/hello ->", json.loads(r.read().decode())["name"])
with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/mobile/index.html", timeout=3) as r:
    body = r.read().decode("utf-8", "ignore")
    assert "BIO" in body and "ACCESS" in body
    print("[OK] /mobile/index.html servido (", len(body), "bytes )")

pc.close()
phone.close()
server.stop()
print("\nTODAS LAS PRUEBAS PASARON")
