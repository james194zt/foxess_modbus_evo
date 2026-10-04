#!/usr/bin/env python3
"""Dump the raw Fox Cloud mode-scheduler JSON for an inverter.

Read-only: only calls the scheduler "get" endpoints, never "set"/"enable".

Usage:
    export FOX_API_KEY=...            # e.g. in ~/.bashrc
    python3 scripts/fox_cloud_scheduler_dump.py [DEVICE_SN] [--label NAME]

DEVICE_SN can also come from FOX_SN. If neither is set, the devices on the account are listed.
Each run is printed and saved to fox_scheduler_<label>_<timestamp>.json in the current directory.
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

BASE = "https://www.foxesscloud.com"
# Fox returns these errnos when an API version isn't available for the device; try the next one.
_FALLBACK_ERRNOS = {41200, 41203, 40256, 41811}


class FoxError(Exception):
    def __init__(self, message: str, errno: int | None = None) -> None:
        super().__init__(message)
        self.errno = errno


def _post(api_key: str, path: str, body: dict) -> object:
    ts = str(round(time.time() * 1000))
    # Same as the plant app: md5(path + "\r\n" + token + "\r\n" + timestamp) with literal \r\n.
    signature = hashlib.md5(rf"{path}\r\n{api_key}\r\n{ts}".encode()).hexdigest()
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "token": api_key,
            "signature": signature,
            "timestamp": ts,
            "lang": "en",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as err:
        raise FoxError(f"HTTP {err.code} from {path}") from err
    errno = data.get("errno", 0)
    if errno not in (0, None):
        raise FoxError(f"{data.get('msg') or 'Fox Cloud error'} (errno {errno}) from {path}", int(errno))
    # Fox rate-limits the Open API; keep consecutive calls apart.
    time.sleep(1.1)
    return data.get("result")


def _first_working(api_key: str, paths: list[str], body: dict) -> dict:
    last: FoxError | None = None
    for path in paths:
        try:
            return {"endpoint": path, "result": _post(api_key, path, body)}
        except FoxError as err:
            last = err
            if err.errno not in _FALLBACK_ERRNOS:
                break
    return {"endpoint": None, "error": str(last)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("device_sn", nargs="?", default=os.environ.get("FOX_SN"))
    parser.add_argument("--label", default="dump", help="name for the saved file, e.g. before / after_mode_change")
    args = parser.parse_args()

    api_key = os.environ.get("FOX_API_KEY", "").strip()
    if not api_key:
        print("FOX_API_KEY is not set (add `export FOX_API_KEY=...` to ~/.bashrc, then `source ~/.bashrc`).")
        return 1

    if not args.device_sn:
        devices = _post(api_key, "/op/v0/device/list", {"currentPage": 1, "pageSize": 50})
        rows = devices.get("data", []) if isinstance(devices, dict) else devices or []
        print("No device SN given. Devices on this account:")
        for row in rows:
            print(f"  deviceSN={row.get('deviceSN')}  type={row.get('deviceType')}  station={row.get('stationName')}")
        print("Re-run with one of the deviceSNs above (or set FOX_SN).")
        return 1

    body = {"deviceSN": args.device_sn.strip()}
    output = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "label": args.label,
        "deviceSN": body["deviceSN"],
        "schedule": _first_working(
            api_key,
            [f"/op/{v}/device/scheduler/get" for v in ("v3", "v2", "v1", "v0")],
            body,
        ),
        "flag": _first_working(
            api_key,
            [f"/op/{v}/device/scheduler/get/flag" for v in ("v1", "v0")],
            body,
        ),
    }

    text = json.dumps(output, indent=2)
    print(text)
    filename = f"fox_scheduler_{args.label}_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"\nSaved to {filename}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
