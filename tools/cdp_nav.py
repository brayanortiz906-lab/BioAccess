"""Navega el WebView de la APK vía CDP y reporta eventos de carga/errores.

Uso:
    python tools/cdp_nav.py http://<IP-DE-TU-PC>:8080/mobile/index.html
    python tools/cdp_nav.py file:///android_asset/mobile/index.html
"""
import json
import sys
import time
import urllib.request

import websockets.sync.client


def main():
    url = sys.argv[1]
    with urllib.request.urlopen("http://127.0.0.1:9222/json/list", timeout=5) as r:
        page = json.loads(r.read().decode("utf-8"))[0]

    with websockets.sync.client.connect(page["webSocketDebuggerUrl"], open_timeout=10) as ws:
        for i, method in enumerate(["Page.enable", "Runtime.enable", "Log.enable"], start=1):
            ws.send(json.dumps({"id": i, "method": method}))
        ws.send(json.dumps({"id": 99, "method": "Page.navigate", "params": {"url": url}}))

        deadline = time.time() + 12
        while time.time() < deadline:
            try:
                msg = json.loads(ws.recv(timeout=2))
            except TimeoutError:
                continue
            m = msg.get("method", "")
            if m in ("Page.loadEventFired", "Page.frameNavigated", "Log.entryAdded",
                     "Page.javascriptDialogOpening", "Runtime.exceptionThrown"):
                print(json.dumps(msg, ensure_ascii=False)[:600])
            if m == "Page.loadEventFired":
                break

        ws.send(json.dumps({"id": 100, "method": "Runtime.evaluate", "params": {
            "expression": "JSON.stringify({title:document.title,href:location.href,len:document.body?document.body.innerHTML.length:-1,txt:document.body?document.body.innerText.slice(0,80):''})",
            "returnByValue": True}}))
        for _ in range(30):
            msg = json.loads(ws.recv(timeout=10))
            if msg.get("id") == 100:
                print("STATE:", json.dumps(msg.get("result"), ensure_ascii=False)[:1200])
                break


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
