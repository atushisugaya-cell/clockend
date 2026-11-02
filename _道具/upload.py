# -*- coding: utf-8 -*-
"""GitHub Actions から公開先（Cloudflare の Worker）へ data.js を送る。
合言葉はリポジトリの Secrets の UPDATE_KEY（鍵だけでも upload.json の中身まるごとでも読める）"""
import json, os, sys, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_JS = os.path.join(os.path.dirname(HERE), "見本_20261030", "data.js")
URL = os.environ.get("UPDATE_URL") or "https://clockend.atushisugaya.workers.dev"


def update_key():
    raw = (os.environ.get("UPDATE_KEY") or "").strip()
    if raw.startswith("{"):
        try:
            return str(json.loads(raw).get("key") or "").strip()
        except Exception:
            return ""
    return raw.strip('"')


def main():
    key = update_key()
    if not key:
        print("UPDATE_KEY が無いので送らない")
        return 1
    body = open(DATA_JS, "rb").read()
    req = urllib.request.Request(URL.rstrip("/") + "/_update", data=body, method="POST",
                                 headers={"X-Update-Key": key, "Content-Type": "application/javascript; charset=utf-8",
                                          # Python そのままの名乗りだと Cloudflare が 1010 で弾くので、ブラウザ風に名乗る
                                          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ClockendUploader/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print("公開先へ送った:", r.read().decode("utf-8", "replace"))
        return 0
    except urllib.error.HTTPError as e:
        print("公開先へ送れなかった:", e.code, e.read()[:200].decode("utf-8", "replace"))
        return 1


if __name__ == "__main__":
    sys.exit(main())
