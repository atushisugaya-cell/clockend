# -*- coding: utf-8 -*-
"""試作の「選手」タブ用のデータ（11/1 菅谷様「リーグはおかしい・プレミア、カップ戦、CL の情報を入れたい・【選手】の方が良い」）
  読む物＝見本_20261030/data.js（自動取り込みの結果。読むだけ・書き替えない）と 試作の squad.js
  取る物＝ESPN：試合ごとの summary（先発・途中出場・得点・アシスト・シュート・警告・セーブ・失点・PK 戦）／次の試合（fixture）／CL の順位表
  書く物＝試作_選手画面_20261101/comps.js（const COMPS）
使い方: python comps_mock.py
"""
import json, re, os, sys, time, urllib.request, datetime as dt
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MOCK = os.path.join(ROOT, "試作_選手画面_20261101")
# 本番（GitHub の取り込み）では環境変数で置き場を替える。既定は試作のまま
DATA = os.environ.get("ARS_DATA_JS") or os.path.join(ROOT, "見本_20261030", "data.js")
SQUAD_JS = os.environ.get("ARS_SQUAD_JS") or os.path.join(MOCK, "squad.js")
OUT = os.environ.get("ARS_COMPS_OUT") or os.path.join(MOCK, "comps.js")
SUMMARY_DIR = os.path.join(ROOT, "_データ_自動", "summary")  # arsfetch.py と同じ控え（試合ごとの ESPN の summary）
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"}
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/"
JST = dt.timezone(dt.timedelta(hours=9))
# data.js の TEAMS に無いチーム（CL の順位表）の日本語名
JA_EXTRA = {
    "Paris Saint-Germain": "パリSG", "VfB Stuttgart": "シュトゥットガルト", "Barcelona": "バルセロナ", "Como": "コモ",
    "Club Brugge": "クラブ・ブルッヘ", "Sporting CP": "スポルティング", "AS Roma": "ローマ", "Atlético Madrid": "アトレティコ",
    "Shakhtar Donetsk": "シャフタール", "PSV Eindhoven": "PSV", "Villarreal": "ビジャレアル", "Internazionale": "インテル",
    "Galatasaray": "ガラタサライ", "LASK Linz": "LASK", "Feyenoord Rotterdam": "フェイエノールト", "Lens": "ランス",
    "Bodo/Glimt": "ボデ／グリムト", "AEK Athens": "AEKアテネ", "RB Leipzig": "ライプツィヒ", "Fenerbahce": "フェネルバフチェ",
    "Viking FK": "ヴァイキング", "FC Porto": "ポルト", "Slovan Bratislava": "スロヴァン・ブラチスラヴァ",
}


def jget(url):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r:
                return json.load(r)
        except Exception as ex:
            if i == 2:
                raise
            time.sleep(1.5)


def const(src, name):
    return json.loads(re.search(r"const %s = (.*?);\n" % name, src, re.S).group(1))


src = open(DATA, encoding="utf-8").read()
MATCHES, LINEUPS, TEAMS, NEXT, TABLE = (const(src, n) for n in ("MATCHES", "LINEUPS", "TEAMS", "NEXT", "TABLE"))
sq_src = open(SQUAD_JS, encoding="utf-8").read()
SQUAD = json.loads(re.search(r"const SQUAD = (.*?);\n", sq_src, re.S).group(1))
SQ_NOS = {p["no"] for p in SQUAD}
SEED = json.load(open(os.path.join(HERE, "names_seed.json"), encoding="utf-8"))
key_of_en = {v.get("en"): k for k, v in TEAMS.items() if v.get("en")}
key_of_en["Bayern München"] = "bayern"


def tkey(en):
    if en in key_of_en:
        return key_of_en[en]
    k = re.sub(r"[^a-z]", "", en.lower())[:12]
    TEAMS.setdefault(k, {"n": JA_EXTRA.get(en, en), "en": en})
    key_of_en[en] = k
    return k


def slug_of(m):
    if m["k"] == "pl":
        return "eng.1"
    if m["k"] == "cl":
        return "uefa.champions"
    return "eng.fa" if "FA" in m.get("lab", "") else "eng.league_cup"


season = [m for m in MATCHES if m.get("k") in ("pl", "cl", "cup") and m.get("eid") and m["d"] >= "2026-07-01"]
season.sort(key=lambda m: m["d"])
done = [m for m in season if m.get("hs") is not None]
out_matches, lu, games, ps, extra = [], {}, {}, {}, {}


def bump(no, comp, **kw):
    d = ps.setdefault(str(no), {}).setdefault(comp, {"app": 0, "st": 0, "sub": 0, "g": 0, "a": 0, "sh": 0, "sog": 0, "yc": 0, "sv": 0, "gc": 0, "cs": 0})
    for k, v in kw.items():
        d[k] += v


def summary_of(m):
    """終わった試合の summary は控えから読む（無ければ取って控える）"""
    fn = os.path.join(SUMMARY_DIR, f"{m['eid']}.json")
    if os.path.exists(fn):
        try:
            return json.load(open(fn, encoding="utf-8"))
        except Exception:
            pass
    j = jget(f"{ESPN}{slug_of(m)}/summary?event={m['eid']}")
    os.makedirs(SUMMARY_DIR, exist_ok=True)
    json.dump(j, open(fn, "w", encoding="utf-8"), ensure_ascii=False)
    time.sleep(0.3)
    return j


for m in done:
    s = summary_of(m)
    r = next((r for r in s.get("rosters", []) if r["team"].get("displayName") == "Arsenal"), None)
    if not r:
        print("アーセナルの名簿が無い:", m["id"]); continue
    comp = m["k"]
    xi_lu = LINEUPS.get(m["id"], {}).get("xi", [])
    ins, bench, ev = [], [], {}
    opp_goals = m["as"] if m["h"] != "arsenal" else m["hs"]
    opp_goals = m["hs"] if m["a"] == "arsenal" else m["as"]
    for p in r.get("roster", []):
        no = int(p.get("jersey") or 0)
        stt = {x.get("name"): x.get("value") or 0 for x in p.get("stats", [])}
        played = bool(p.get("starter") or p.get("subbedIn"))
        if no not in SQ_NOS:
            en_ = p["athlete"].get("displayName")
            ja_ = SEED.get(en_) or [next((x["n"] for x in xi_lu if x["no"] == no), en_), en_]
            extra[str(no)] = {"n": ja_[0], "f": ja_[1], "en": en_,
                              "pos": {"G": "GK", "D": "DF", "M": "MF", "F": "FW"}.get(((p.get("position") or {}).get("abbreviation") or "M")[:1], "MF")}
        if not played:
            bench.append(no); continue
        if p.get("subbedIn"):
            ins.append(no)
        g, a = int(stt.get("totalGoals", 0)), int(stt.get("goalAssists", 0))
        if g or a:
            ev[str(no)] = ["g"] * g + ["as"] * a
        isgk = (p.get("position") or {}).get("abbreviation") == "G"
        bump(no, comp, app=1, st=1 if p.get("starter") else 0, sub=1 if p.get("subbedIn") else 0, g=g, a=a,
             sh=int(stt.get("totalShots", 0)), sog=int(stt.get("shotsOnTarget", 0)), yc=int(stt.get("yellowCards", 0)),
             sv=int(stt.get("saves", 0)) if isgk else 0, gc=int(stt.get("goalsConceded", 0)) if isgk else 0,
             cs=1 if (isgk and p.get("starter") and not p.get("subbedOut") and opp_goals == 0) else 0)
        games.setdefault(str(no), []).append({"id": m["id"], "st": 1 if p.get("starter") else 0, "sub": 1 if p.get("subbedIn") else 0, "g": g, "a": a})
    lu[m["id"]] = {"fm": r.get("formation") or LINEUPS.get(m["id"], {}).get("fm"),
                   "xi": [[x["no"], x["x"], x["y"]] for x in xi_lu], "in": ins, "bench": sorted(bench), "ev": ev}
    print(f'{m["d"][:10]} {m["lab"]:<18} 先発 {len(xi_lu)}・途中 {len(ins)}・得点/アシスト {sum(len(v) for v in ev.values())}')

for m in season:
    o = {k: m.get(k) for k in ("id", "k", "lab", "d", "h", "a", "hs", "as", "pk", "r")}
    o["done"] = m.get("hs") is not None
    out_matches.append(o)

# これからの試合（大会ごとに 3 つまで）
nxt = {}
count = {"pl": sum(1 for m in done if m["k"] == "pl"), "cl": sum(1 for m in done if m["k"] == "cl")}
for comp, slug in (("pl", "eng.1"), ("cl", "uefa.champions"), ("cup", "eng.league_cup"), ("cup", "eng.fa")):
    try:
        d = jget(f"{ESPN}{slug}/teams/359/schedule?fixture=true")
    except Exception as ex:
        print("予定が取れない", slug, ex); continue
    n = 0
    for e in d.get("events", []):
        c = e["competitions"][0]
        if (c.get("status") or {}).get("type", {}).get("completed"):
            continue
        hc = next(x for x in c["competitors"] if x.get("homeAway") == "home")
        ac = next(x for x in c["competitors"] if x.get("homeAway") == "away")
        h, a = tkey(hc["team"]["displayName"]), tkey(ac["team"]["displayName"])
        if comp in count:
            count[comp] += 1
            lab = ("プレミアリーグ 第%d節" if comp == "pl" else "チャンピオンズリーグ 第%d節") % count[comp]
        else:
            lab = "FAカップ" if slug == "eng.fa" else "カラバオカップ"
        nxt.setdefault(comp, []).append({"id": f"{h if h != 'arsenal' else a}-{e['date'][5:7]}{e['date'][8:10]}", "k": comp, "lab": lab, "d": e["date"], "h": h, "a": a, "done": False})
        n += 1
        if n >= 3:
            break
    time.sleep(0.3)

# CL の順位表（36 チーム）
cl_table = []
try:
    stj = jget("https://site.api.espn.com/apis/v2/sports/soccer/uefa.champions/standings")
    ent = ((stj.get("children") or [stj])[0].get("standings") or {}).get("entries", [])
    for e in ent:
        v = {x["name"]: x.get("value") for x in e["stats"]}
        cl_table.append([tkey(e["team"]["displayName"]), int(v.get("rank") or 0), int(v.get("gamesPlayed") or 0), int(v.get("wins") or 0),
                         int(v.get("ties") or 0), int(v.get("losses") or 0), int(v.get("pointDifferential") or 0), int(v.get("points") or 0)])
    cl_table.sort(key=lambda r: r[1])
except Exception as ex:
    print("CL の順位表が取れない", ex)

used = {m["h"] for m in out_matches} | {m["a"] for m in out_matches} | {x["h"] for v in nxt.values() for x in v} | {x["a"] for v in nxt.values() for x in v} | {r[0] for r in cl_table} | {r[0] for r in TABLE}
COMPS = {
    "updated": dt.datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
    "matches": out_matches, "next": nxt, "lu": lu, "games": games, "ps": ps, "extra": extra,
    "pl_table": TABLE, "cl_table": cl_table,
    "teams": {k: {"n": TEAMS[k]["n"]} for k in used if k in TEAMS},
}
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("// 「選手」タブの大会ごとのデータ（_道具/comps_mock.py が作る・data.js と ESPN から）\n")
    f.write("const COMPS = " + json.dumps(COMPS, ensure_ascii=False) + ";\n")
print("書いた", OUT, "試合", len(out_matches), "次", {k: len(v) for k, v in nxt.items()}, "CL表", len(cl_table), "名簿外", sorted(extra, key=int))
