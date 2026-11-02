# -*- coding: utf-8 -*-
"""アーセナルの全選手（ESPN の公開データ）を 1 つの squad.js にまとめる
  - 名簿（背番号・名前・ポジション・年齢・国・身長・体重）
  - 今季の数字（プレミア／全大会）＝出場・先発・ゴール・アシスト・シュート・枠内・警告・退場
  - 直近の試合ごとの数字（先発・ゴール・アシスト）
  - 日本語の名前は _道具/names_seed.json（無い選手は英語のまま）
使い方: python squad.py [出力先]   既定＝試作_選手画面_20261101/squad.js
"""
import os, sys, json, re, time, datetime, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "試作_選手画面_20261101", "squad.js")
TEAM = "359"
ROSTER = f"https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/teams/{TEAM}/roster"
OVERVIEW = "https://site.web.api.espn.com/apis/common/v3/sports/soccer/eng.1/athletes/{id}/overview"
NAT = {"Brazil": "ブラジル", "Ecuador": "エクアドル", "England": "イングランド", "France": "フランス", "Germany": "ドイツ",
       "Greece": "ギリシャ", "Italy": "イタリア", "Netherlands": "オランダ", "Northern Ireland": "北アイルランド",
       "Norway": "ノルウェー", "Spain": "スペイン", "Sweden": "スウェーデン", "Portugal": "ポルトガル", "Belgium": "ベルギー",
       "Japan": "日本", "Ghana": "ガーナ", "Nigeria": "ナイジェリア", "Poland": "ポーランド", "Ukraine": "ウクライナ",
       "Scotland": "スコットランド", "Wales": "ウェールズ", "Ireland": "アイルランド", "Argentina": "アルゼンチン", "Egypt": "エジプト"}
POS = {"G": "GK", "D": "DF", "M": "MF", "F": "FW"}


# 本番（5 分ごとの取り込み）では ARS_SQUAD_MAX_AGE_MIN 分より新しい名鑑があれば取り直さない（ESPN に 1 回 32 本頼むため。既定 180 分）
MAX_AGE = os.environ.get("ARS_SQUAD_MAX_AGE_MIN")
if MAX_AGE and os.path.exists(OUT):
    try:
        _m = re.search(r'const SQUAD_META = \{"updated": "([^"]+)"', open(OUT, encoding="utf-8").read())
        _age = (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))) - datetime.datetime.strptime(_m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=datetime.timezone(datetime.timedelta(hours=9)))).total_seconds() / 60
        if _age < float(MAX_AGE):
            print(f"名鑑は {_age:.0f} 分前の物を使う（{MAX_AGE} 分ごとに取り直す）")
            sys.exit(0)
    except Exception as ex:
        print("名鑑の古さが分からないので取り直す:", ex)


def jget(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def cm(s):
    m = re.match(r"(\d+)' *(\d+)\"", s or "")
    return round((int(m.group(1)) * 12 + int(m.group(2))) * 2.54) if m else None


def kg(s):
    m = re.match(r"(\d+) lbs", s or "")
    return round(int(m.group(1)) * 0.4536) if m else None


def stat_map(a):
    out = {}
    for c in (a.get("statistics") or {}).get("splits", {}).get("categories", []):
        for s in c.get("stats", []):
            out[s["name"]] = s.get("value")
    return out


names = json.load(open(os.path.join(HERE, "names_seed.json"), encoding="utf-8"))
try:  # 種に無い選手は、取り込みが Claude に頼んで控えた名前（_データ_自動/state.json）で補う
    for en_, v_ in json.load(open(os.path.join(ROOT, "_データ_自動", "state.json"), encoding="utf-8")).get("names", {}).items():
        if en_ not in names and isinstance(v_, list) and len(v_) >= 2 and v_[0] != en_:
            names[en_] = v_
except Exception:
    pass
roster = jget(ROSTER)
players = []
sample_printed = False
for a in roster["athletes"]:
    en = a["displayName"]
    ja = names.get(en) or [en.split()[-1], en]
    st = stat_map(a)
    p = {
        "id": a["id"], "no": int(a.get("jersey") or 0), "en": en, "n": ja[0], "f": ja[1],
        "pos": POS.get(a["position"]["abbreviation"], a["position"]["abbreviation"]),
        "age": a.get("age"), "nat": NAT.get(a.get("citizenship"), a.get("citizenship")),
        "h": cm(a.get("displayHeight")), "w": kg(a.get("displayWeight")),
        "all": {"app": int(st.get("appearances") or 0), "sub": int(st.get("subIns") or 0), "g": int(st.get("totalGoals") or 0),
                "a": int(st.get("goalAssists") or 0), "sh": int(st.get("totalShots") or 0), "sog": int(st.get("shotsOnTarget") or 0),
                "yc": int(st.get("yellowCards") or 0), "rc": int(st.get("redCards") or 0), "fc": int(st.get("foulsCommitted") or 0),
                "fa": int(st.get("foulsSuffered") or 0), "sv": int(st.get("saves") or 0), "gc": int(st.get("goalsConceded") or 0)},
        "inj": [{"status": i.get("status"), "d": (i.get("details") or {}).get("type") or i.get("shortComment") or i.get("longComment")} for i in (a.get("injuries") or [])],
        "comps": [], "last": [],
    }
    # 大会ごと・試合ごと
    try:
        o = jget(OVERVIEW.format(id=a["id"]))
        stt = o.get("statistics") or {}
        names_ = stt.get("names") or []
        for sp in stt.get("splits", []):
            row = dict(zip(names_, sp.get("stats", [])))
            p["comps"].append({"name": sp.get("displayName"), "slug": sp.get("leagueSlug"), "club": str(sp.get("teamId")) == TEAM,
                               "st": int(row.get("starts") or row.get("STRT") or 0), "g": int(row.get("totalGoals") or row.get("G") or 0),
                               "a": int(row.get("goalAssists") or row.get("A") or 0), "sh": int(row.get("totalShots") or row.get("SHOT") or 0),
                               "sog": int(row.get("shotsOnTarget") or row.get("SOG") or 0), "yc": int(row.get("yellowCards") or row.get("YC") or 0)})
        gl = o.get("gameLog") or {}
        evs = gl.get("events") or {}
        per = {}
        for block in gl.get("statistics") or []:
            labels = block.get("names") or block.get("labels") or []
            for e in block.get("events") or []:
                per[str(e.get("eventId"))] = dict(zip(labels, e.get("stats", [])))
        rows = []
        for eid, e in (evs.items() if isinstance(evs, dict) else []):
            if TEAM not in (str(e.get("homeTeamId")), str(e.get("awayTeamId"))):
                continue  # 代表の試合は外す（クラブの試合だけ）
            if not sample_printed:
                print("試合の例:", json.dumps({k: v for k, v in e.items() if k != "links"}, ensure_ascii=False)[:600])
                print("数字の例:", per.get(str(eid)))
                sample_printed = True
            r = per.get(str(eid), {})
            opp = e.get("opponent") or {}
            rows.append({"id": eid, "d": e.get("gameDate"), "opp": opp.get("displayName") or opp.get("name"), "oppAbbr": opp.get("abbreviation"),
                         "home": (e.get("atVs") == "vs"), "comp": e.get("leagueName") or e.get("leagueAbbreviation"),
                         "res": e.get("gameResult"), "sc": f'{e.get("homeTeamScore")}-{e.get("awayTeamScore")}' if e.get("homeTeamScore") is not None else None,
                         "st": 1 if str(r.get("appearances", "")).lower().startswith("start") else 0, "sub": 1 if str(r.get("appearances", "")).lower().startswith("sub") else 0, "g": int(r.get("totalGoals") or r.get("G") or 0),
                         "a": int(r.get("goalAssists") or r.get("A") or 0), "sh": int(r.get("totalShots") or r.get("SHOT") or 0),
                         "yc": int(r.get("yellowCards") or r.get("YC") or 0)})
        rows.sort(key=lambda r: r["d"] or "", reverse=True)
        p["last"] = rows[:6]
    except Exception as ex:
        print("  個別の取得に失敗:", en, ex)
    club = [c for c in p["comps"] if c.get("club")]
    p["all"]["g"] = sum(c["g"] for c in club) if club else p["all"]["g"]
    p["all"]["a"] = sum(c["a"] for c in club) if club else p["all"]["a"]
    p["all"]["st"] = sum(c["st"] for c in club)
    p["all"]["comps"] = len(club)
    pl = next((c for c in p["comps"] if c.get("slug") == "eng.1"), None)
    p["pl"] = pl or {"st": 0, "g": 0, "a": 0, "sh": 0, "sog": 0, "yc": 0}
    players.append(p)
    print(f'{p["no"]:>3} {p["n"]:<10} {p["pos"]} {p["age"]} {p["nat"]} {p["h"]}cm 全大会 {p["all"]["app"]}試合 {p["all"]["g"]}G {p["all"]["a"]}A / PL 先発{p["pl"]["st"]} {p["pl"]["g"]}G {p["pl"]["a"]}A / 直近{len(p["last"])}')
    time.sleep(0.3)

order = {"GK": 0, "DF": 1, "MF": 2, "FW": 3}
players.sort(key=lambda p: (order.get(p["pos"], 9), p["no"]))
meta = {"updated": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "src": "ESPN"}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("// アーセナルの全選手（ESPN の公開データ・_道具/squad.py が作る）\n")
    f.write("const SQUAD = " + json.dumps(players, ensure_ascii=False) + ";\n")
    f.write("const SQUAD_META = " + json.dumps(meta, ensure_ascii=False) + ";\n")
print("書いた", OUT, len(players), "人")
