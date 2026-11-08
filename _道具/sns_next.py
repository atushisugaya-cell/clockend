# -*- coding: utf-8 -*-
"""CLOCK END の SNS｜毎週月曜の「次の試合」の絵と投稿文を作り、公開先（clockend.jp）に置く（2026-11-08〜）。

11/8 菅谷様「A」＝次の試合を日本時間で知らせる絵を毎週自動で（結果は書かない・選手や公式の絵は使わない）。
流れ：
  月 9:00（日本時間）  CLOCK END の Worker の 5 分ごとの時計が、月曜 9 時台の最初の回だけ sns_next.yml を起動する
                       → この道具が data.js の COMPS.next から次の 3 試合を選び、絵（1080×1350）と投稿文を作って
                         公開先の /_sns へ送る（合言葉は data.js と同じ UPDATE_KEY）
                         ＝ https://clockend.jp/sns/next-YYYYMMDD.png と https://clockend.jp/sns/next.json
  月 10:30            社内ツール（sns-tool の Worker）の定時が next.json を読み、CLOCK END の X と Instagram に 20:00 で予約する

使い方：
  python sns_next.py                     … 公開中の data.js から作って送る（GitHub Actions）
  python sns_next.py --no-upload --out <フォルダ> [--data <data.js>] [--today 2026-11-09]   … 手元で作るだけ
絵を撮るブラウザ＝環境変数 CHROME（無ければ google-chrome → Edge の順に探す）。
"""
import argparse, base64, datetime, html, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
JST = datetime.timezone(datetime.timedelta(hours=9))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ClockendUploader/1.0"   # Python そのままだと Cloudflare が 1010 で弾く
SITE = "https://clockend.jp"
UPLOAD = os.environ.get("UPDATE_URL") or "https://clockend.atushisugaya.workers.dev"
WD = "月火水木金土日"
COMP_DOT = {"pl": "#3D195B", "cl": "#1B4DB5"}
IG_TAGS = "#アーセナル #arsenal #プレミアリーグ #海外サッカー #ファンサイト"   # 11/6 の開店告知と同じ 5 つ


def load_data(path):
    if path:
        return open(path, encoding="utf-8").read()
    req = urllib.request.Request(SITE + "/data.js", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def const_json(js, name):
    m = re.search(r"const %s = (\{.*?\});\s*\n" % name, js, re.S)
    if not m:
        raise SystemExit("data.js に %s が無い" % name)
    return json.loads(m.group(1))


def pick(js, now, n=3):
    comps, teams = const_json(js, "COMPS"), const_json(js, "TEAMS")
    out = []
    for k, lst in (comps.get("next") or {}).items():
        for m in lst:
            if m.get("done"):
                continue
            t = datetime.datetime.fromisoformat(m["d"].replace("Z", "+00:00")).astimezone(JST)
            if t < now or t > now + datetime.timedelta(days=45):
                continue
            name = lambda key: (teams.get(key) or {}).get("n") or key
            out.append({"id": m["id"], "k": m.get("k") or k, "lab": m.get("lab") or "", "t": t, "h": name(m["h"]), "a": name(m["a"])})
    out.sort(key=lambda x: x["t"])
    return out[:n]


def when(t):
    return "%d/%d（%s）%d:%02d" % (t.month, t.day, WD[t.weekday()], t.hour, t.minute)


def opponent(m):
    return m["a"] if m["h"] == "アーセナル" else m["h"]


def x_weight(s):
    """X の数え方（日本語・絵文字は 2・URL は 23）"""
    urls = re.findall(r"https?://\S+", s)
    s = re.sub(r"https?://\S+", "", s)
    return sum(1 if ord(c) <= 0x10FF else 2 for c in s) + 23 * len(urls)


def captions(ms, today):
    """11/2 の決まり（記憶 clockend-captions-humor-heat-emoji）＝「！」で熱・かっこの中で笑いか呼びかけ・最後に COYG と ⚽️🔴⚪️・結果は書かない"""
    m0 = ms[0]
    days = (m0["t"].date() - today).days
    if days <= 0:
        head = "今日は試合の日！⚽️"
    elif days == 1:
        head = "いよいよ明日、試合です！⚽️"
    else:
        head = "次の試合まで、あと%d日！⚽️" % days
    h = m0["t"].hour
    joke = ("夜ふかし確定です！" if h < 5 else "早起き確定です！" if h < 9 else "仕事終わりに間に合います！" if h >= 19 else "予定を空けておきましょう！")
    body = "%sの%s戦から、日本時間で%d試合まとめました。%s（寝落ちしても大丈夫。結果は、見終わるまで伏せておきます）COYG！🔴⚪️" % (
        when(m0["t"]), opponent(m0), len(ms), joke)
    text = head + "\n" + body
    if x_weight(text) > 270:   # 無料の X は 280 まで
        text = head + "\n%sの%s戦から、日本時間で%d試合まとめました。COYG！🔴⚪️" % (when(m0["t"]), opponent(m0), len(ms))
    return {"x": text, "ig": text + "\n\n" + IG_TAGS,
            "reply": "サイトはこちらです。\n%s/?utm_source=x&utm_medium=social&utm_campaign=next" % SITE}


def alt_text(ms):
    return "アーセナル、次の%d試合（日本時間）。" % len(ms) + "、".join(
        "%s %s対%s（%s）" % (when(m["t"]), m["h"], m["a"], m["lab"]) for m in ms) + "。結果は書いていません。"


def render_html(ms):
    crest = "data:image/png;base64," + base64.b64encode(open(os.path.join(HERE, "sns_crest.png"), "rb").read()).decode()
    rows = []
    for m in ms:
        t = m["t"]
        rows.append(
            '    <div class="m"><div class="when"><b>%d.%02d</b><span>%s %d:%02d</span></div><div>'
            '<div class="who"><span>%s</span><span><em>VS</em>%s</span></div>'
            '<div class="comp"><i style="background:%s"></i>%s</div></div></div>'
            % (t.month, t.day, ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"][t.weekday()], t.hour, t.minute,
               html.escape(m["h"]), html.escape(m["a"]), COMP_DOT.get(m["k"], "#8A7A3A"), html.escape(m["lab"])))
    tpl = open(os.path.join(HERE, "sns_next.html"), encoding="utf-8").read()
    return tpl.replace("{{CREST}}", crest).replace("{{N}}", str(len(ms))).replace("{{ROWS}}", "\n".join(rows))


def browser():
    for c in [os.environ.get("CHROME"), shutil.which("google-chrome"), shutil.which("chromium"),
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
        if c and os.path.exists(c):
            return c
    raise SystemExit("絵を撮るブラウザが無い（CHROME を指定）")


def shoot(page_html, png):
    d = tempfile.mkdtemp(prefix="sns_next_")
    src = os.path.join(d, "page.html")
    open(src, "w", encoding="utf-8").write(page_html)
    cmd = [browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-sandbox", "--force-device-scale-factor=1",
           "--window-size=1080,1350", "--virtual-time-budget=15000", "--user-data-dir=" + os.path.join(d, "prof"),
           "--screenshot=" + png, "file:///" + src.replace("\\", "/").lstrip("/")]
    if os.path.exists(png):
        os.remove(png)
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    # Windows の Edge は撮り終える前に戻ってくる（裏で続く）＝絵が出来上がって大きさが止まるまで待つ
    last = -1
    for _ in range(120):
        size = os.path.getsize(png) if os.path.exists(png) else -1
        if size > 20000 and size == last:
            break
        last = size
        time.sleep(0.5)
    if not os.path.exists(png) or os.path.getsize(png) < 20000:
        raise SystemExit("絵が撮れなかった: " + (r.stderr or b"")[-600:].decode("utf-8", "replace"))
    shutil.rmtree(d, ignore_errors=True)


def update_key():
    raw = (os.environ.get("UPDATE_KEY") or "").strip()
    if raw.startswith("{"):
        try:
            return str(json.loads(raw).get("key") or "").strip()
        except Exception:
            return ""
    return raw.strip('"')


def put(name, body, ctype, key):
    req = urllib.request.Request(UPLOAD.rstrip("/") + "/_sns?name=" + name, data=body, method="POST",
                                 headers={"X-Update-Key": key, "Content-Type": ctype, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        print("送った:", name, r.read().decode("utf-8", "replace"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data"); ap.add_argument("--out"); ap.add_argument("--today"); ap.add_argument("--no-upload", action="store_true")
    a = ap.parse_args()
    now = datetime.datetime.now(JST)
    if a.today:
        now = datetime.datetime.fromisoformat(a.today + "T09:00:00+09:00")
    today = now.date()
    ms = pick(load_data(a.data), now)
    if not ms:
        print("次の試合が取り込みに無い（45 日以内）＝今週は作らない")
        return 0
    stamp = today.strftime("%Y%m%d")
    out = a.out or tempfile.mkdtemp(prefix="sns_next_out_")
    os.makedirs(out, exist_ok=True)
    png = os.path.join(out, "next-%s.png" % stamp)
    page = render_html(ms)
    open(os.path.join(out, "next-%s.html" % stamp), "w", encoding="utf-8").write(page)
    shoot(page, png)
    cap = captions(ms, today)
    meta = {"date": today.isoformat(), "image": "%s/sns/next-%s.png" % (SITE, stamp), "alt": alt_text(ms),
            "x": {"text": cap["x"], "reply": cap["reply"]}, "ig": {"text": cap["ig"]},
            "matches": [{"id": m["id"], "jst": m["t"].isoformat(), "home": m["h"], "away": m["a"], "lab": m["lab"]} for m in ms],
            "made": datetime.datetime.now(JST).isoformat(timespec="seconds")}
    js = json.dumps(meta, ensure_ascii=False, indent=1)
    open(os.path.join(out, "next.json"), "w", encoding="utf-8").write(js)
    print(js)
    print("X の数え方:", x_weight(cap["x"]), "・絵:", png, os.path.getsize(png), "バイト")
    if a.no_upload:
        return 0
    key = update_key()
    if not key:
        print("UPDATE_KEY が無いので送らない")
        return 1
    put("next-%s.png" % stamp, open(png, "rb").read(), "image/png", key)
    put("next.json", js.encode("utf-8"), "application/json; charset=utf-8", key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
