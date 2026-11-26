"""Evalúa JavaScript dentro del WebView de la APK vía CDP (adb forward tcp:9222).

Uso:
    python tools/cdp_eval.py "document.body.innerText.slice(0,200)"
    python tools/cdp_eval.py --list
"""
import asyncio
import json
import sys
import urllib.request

import websockets.sync.client


def get_page():
    with urllib.request.urlopen("http://127.0.0.1:9222/json/list", timeout=5) as r:
        pages = json.loads(r.read().decode("utf-8"))
    return pages[0]


def main():
    args = sys.argv[1:]
    page = get_page()
    if not args or args[0] == "--list":
        print(json.dumps(page, indent=2, ensure_ascii=False))
        return

    expr = " ".join(args)
    with websockets.sync.client.connect(page["webSocketDebuggerUrl"], open_timeout=10) as ws:
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": expr, "returnByValue": True, "awaitPromise": True},
        }))
        for _ in range(20):
            msg = json.loads(ws.recv(timeout=15))
            if msg.get("id") == 1:
                break
    print(json.dumps(msg, indent=2, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
