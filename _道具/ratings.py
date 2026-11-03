# -*- coding: utf-8 -*-
"""メディアの採点＝試合後に各社が出す「Arsenal player ratings」の記事から、選手ごとの点を抜く（11/3 菅谷様 ⑫）
  出どころ＝Google News の RSS → Goal・Evening Standard・football.london・Daily Express・Daily Mail・Arseblog（11/3 に本文が取れることを確かめた 6 社）
  抜き方＝記事の本文を Claude に渡して {番号: 点} の JSON（名簿の番号で返させる＝表記ゆれに強い）。数字と媒体名・リンクだけ載せる（文は写さない）
  出力＝_データ_自動/ratings.json {match_id: {"opp", "d", "outlets":[{src, url, title, pub, r:{no:点}, mgr}], "avg":{no:点}, "n", "updated"}}
  直近 4 日の終わった試合だけ見る。同じ記事は 1 回だけ（url で控え）。Google News の復号は gnews.py（控えつき・1 件ずつ）
使い方: python ratings.py [出力] [comps.js] [squad.js]
"""
import os, re, sys, json, shutil, subprocess
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gnews
ROOT = os.path.dirname(HERE)
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_データ_自動", "ratings.json")
COMPS_JS = sys.argv[2] if len(sys.argv) > 2 else (os.environ.get("ARS_COMPS_OUT") or os.path.join(ROOT, "_データ_自動", "comps.js"))
SQUAD_JS = sys.argv[3] if len(sys.argv) > 3 else (os.environ.get("ARS_SQUAD_JS") or os.path.join(ROOT, "_データ_自動", "squad.js"))
MODEL = os.environ.get("ARS_MODEL") or "claude-opus-5-5"
DAYS = 4
# 媒体＝元の住所のドメインで選ぶ（Google News の source 名は揺れる）
OUTLETS = [("goal.com", "Goal"), ("standard.co.uk", "Evening Standard"), ("football.london", "football.london"),
           ("express.co.uk", "Express"), ("dailymail.", "Daily Mail"), ("arseblog", "Arseblog")]  # Daily Mail は .com と .co.uk の両方
# 媒体自身の RSS（住所がそのまま取れる＝Google の復号が要らない。11/3 に動いた物）。Google News は復号が 429 で止まることがあるので両方見る
FEEDS = ["https://www.football.london/arsenal-fc/?service=rss", "https://arseblog.news/feed/", "https://www.standard.co.uk/sport/football/arsenal/rss",
         "https://www.dailymail.co.uk/sport/football/index.rss"]


def const_of(path, name):
    src = open(path, encoding="utf-8").read()
    return json.loads(re.search(r"const %s = (.*?);\n" % name, src, re.S).group(1))


def ask_json(prompt):
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        r = anthropic.Anthropic().beta.messages.create(model=MODEL, max_tokens=4000, output_config={"effort": "low"},
                                                        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                                                        messages=[{"role": "user", "content": prompt}])
        out = "".join(b.text for b in r.content if b.type == "text")
    else:
        exe = shutil.which("claude")
        if not exe:
            print("API の鍵も claude も無い"); return None
        r = subprocess.run([exe, "-p", "--tools", "", "--output-format", "text"], input=prompt, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300, cwd=os.path.join(ROOT, "_データ_自動"))
        out = r.stdout or ""
    m = re.search(r"\{.*\}", out, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except Exception:
        return None


def outlet_of(url):
    u = (url or "").lower()
    for dom, name in OUTLETS:
        if dom in u:
            return name
    return None


def is_arsenal_ratings(title):
    t = (title or "").lower()
    if "rating" not in t or "arsenal" not in t:
        return False
    i = t.find("player ratings")
    if i < 0:
        i = t.find("ratings")
    return "arsenal" in t[max(0, i - 24):i]  # 「Arsenal player ratings」＝相手側の「Liverpool player ratings vs Arsenal」は外す


def main():
    now = datetime.now(timezone.utc)
    C = const_of(COMPS_JS, "COMPS")
    squad = const_of(SQUAD_JS, "SQUAD")
    try:
        R = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        R = {}
    targets = []
    for m in C.get("matches", []):
        d = datetime.fromisoformat(m["d"].replace("Z", "+00:00"))
        if d < now and (now - d) < timedelta(days=DAYS):
            targets.append((m, d))
    if not targets:
        print("直近の試合がない"); return
    items = []
    for f in FEEDS:  # 媒体の RSS を先に（住所がそのまま）
        items += [it for it in gnews.feed(f) if is_arsenal_ratings(it["title"])]
    n_feed = len(items)
    try:
        items += gnews.search('"Arsenal player ratings"', f"{DAYS}d")
    except Exception as ex:
        print("Google News が読めない:", ex)
    print(f"媒体の RSS {n_feed} 件・Google News を足して {len(items)} 件")
    roster = "\n".join(f"{p['no']}: {p.get('en')}" for p in sorted(squad, key=lambda p: p["no"]) if p.get("no"))
    changed = False
    for m, d in targets:
        rec = R.setdefault(m["id"], {"opp": m["a"] if m["h"] == "arsenal" else m["h"], "d": m["d"], "outlets": [], "avg": {}, "n": 0, "updated": None})
        seen = {o.get("link") for o in rec["outlets"]} | {o.get("url") for o in rec["outlets"]}
        for it in items:
            try:
                pub = datetime.fromisoformat(it["pub"])
            except Exception:
                continue
            # 採点の記事は試合中に作って更新する媒体がある（football.london は pubDate がキックオフ前）＝4 時間前から 60 時間後まで
            if not (d - timedelta(hours=4) <= pub <= d + timedelta(hours=60)) or not is_arsenal_ratings(it["title"]):
                continue
            if it["link"] in seen:
                continue
            name = outlet_of(it["srcurl"])
            if not name:
                continue
            if any(o["src"] == name for o in rec["outlets"]):
                continue  # 同じ媒体は 1 本だけ
            url = gnews.resolve(it["link"])
            if not url or outlet_of(url) != name:
                print(f"  {name}: 住所が取れない／違う（{url}）"); continue
            text = gnews.article_text(url, 12000)
            if len(text) < 400:
                print(f"  {name}: 本文が取れない（{len(text)} 字）"); continue
            prompt = ("次はアーセナルの試合後の『選手採点（player ratings）』の記事の本文です。アーセナルの選手だけ、10 点満点の採点を抜き出してください。\n"
                      "決まり：選手は下の名簿の番号で返す（表記ゆれは名簿と照らして判断）・相手チームの選手は入れない・採点が N/A や無い選手は入れない・本文に無い点は作らない・"
                      "小数はそのまま（7.5 など）・監督（Arteta）の採点があれば manager に。Arseblog の記事では『Arseblog』の点を使い『Users』（読者投票）は使わない。"
                      "JSON だけを返し、説明やコードブロックは不要です。\n"
                      "形式: {\"players\": {\"番号\": 点, ...}, \"manager\": 点または null}\n\n名簿:\n" + roster + "\n\n本文:\n" + text)
            res = ask_json(prompt)
            pl = (res or {}).get("players") if isinstance(res, dict) else None
            if not isinstance(pl, dict):
                print(f"  {name}: 返事が読めない"); continue
            r = {}
            for k, v in pl.items():
                try:
                    no, val = int(k), float(v)
                except Exception:
                    continue
                if 0 < val <= 10 and any(p["no"] == no for p in squad):
                    r[str(no)] = round(val, 1)
            if len(r) < 7:
                print(f"  {name}: 抜けた人数が少ない（{len(r)}）"); continue
            mgr = res.get("manager")
            try:
                mgr = round(float(mgr), 1) if mgr is not None else None
            except Exception:
                mgr = None
            rec["outlets"].append({"src": name, "url": url, "link": it["link"], "title": it["title"], "pub": it["pub"], "r": r, "mgr": mgr})
            seen.add(it["link"]); changed = True
            print(f"  {name}: {len(r)} 人")
        # 平均
        s, c = {}, {}
        for o in rec["outlets"]:
            for no, v in o["r"].items():
                s[no] = s.get(no, 0) + v; c[no] = c.get(no, 0) + 1
        rec["avg"] = {no: round(s[no] / c[no], 1) for no in s}
        rec["cnt"] = c
        rec["n"] = len(rec["outlets"])
        rec["updated"] = now.isoformat()
    if changed or not os.path.exists(OUT):
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("書いた", OUT, {k: v["n"] for k, v in R.items()})
    else:
        print("新しい採点の記事はない", {k: v["n"] for k, v in R.items()})


if __name__ == "__main__":
    main()
