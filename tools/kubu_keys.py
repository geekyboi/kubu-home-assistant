"""One-time fetch of your Kubu sensor keys from the Kubu cloud.

Usage: python kubu_keys.py you@example.com   (prompts for password)
Writes kubu_keys.json next to this script. Keep that file private.
"""

from __future__ import annotations

import getpass
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api-green.kubusmart.com"
FIELDS = (
    "sNo",
    "name",
    "devAlias",
    "dpKey",
    "type",
    "sensorClass",
    "productType",
    "fwVer",
    "hwRev",
)


def call(
    method: str, path: str, body: dict | None = None, token: str | None = None
) -> dict:
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(req, data=data, timeout=30) as r:
        return json.load(r)


def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else input("Kubu email: ")
    password = getpass.getpass("Kubu password: ")
    login = call("POST", "/oauth/login", {"email": email, "password": password})
    token = login["idToken"]
    homes = login.get("homes") or []
    if not homes:
        sys.exit(
            "Login worked but no homes came back. Send me the keys of the response (not the values)."
        )
    out = []
    for home in homes:
        q = urllib.parse.urlencode({"homeId": home["id"]})
        dash = call("GET", f"/view/rooms?{q}", token=token)
        for node in dash.get("bleNodes") or []:
            out.append({k: node.get(k) for k in FIELDS} | {"homeId": home["id"]})
    path = Path(__file__).with_name("kubu_keys.json")
    path.write_text(json.dumps(out, indent=2))
    print(f"Saved {len(out)} sensor(s) to {path}")
    for n in out:
        print(
            f"  {n['sNo']}  {n.get('devAlias') or n.get('name')}  type={n['type']} class={n['sensorClass']}"
        )


if __name__ == "__main__":
    main()
