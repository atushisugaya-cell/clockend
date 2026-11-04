# -*- coding: utf-8 -*-
"""ポジション別の 6 角形（11/4 菅谷様「そのポジションに求められる能力値であるべき」→「A」）
  出どころ＝プレミアリーグ公式 Fantasy の JSON（bootstrap-static・鍵なし）。選手ごとの 影響力・創造性・脅威（Opta 由来の公式指標）、
  xG・xA・被 xG、セーブ・無失点、タックル・クリア/ブロック/インターセプト・リカバリー、ボーナス点（BPS）。
  作り＝軸はポジションごとに 6 つ（下の AXES）。値は 90 分あたりに直し、**プレミアの同じポジションの選手全員（出場 MIN 分以上）の中で何パーセンタイルか**（0〜100）。
       同点は半分ずつ数える（0 ばかりの軸で 0 の選手が 100 にならないように）。FBref の Scouting Report・Opta の radar と同じ考え方。
  出力＝_データ_自動/radar.json {"updated","src","league","min","pool":{"GKP":n,...},"p":{"<背番号>":{"pos","min","low","ax":[[名前, 値, 説明],×6]}}}
  60 分以内に取った物があれば取り直さない（ARS_RADAR_MAX_AGE_MIN）。名簿（squad.js の en）と名前で突き合わせる（injuries.py と同じ）
使い方: python radar.py [出力] [squad.js]
"""
import os, re, sys, json, unicodedata, urllib.request
from datetime import datetime, timezone
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_データ_自動", "radar.json")
SQUAD_JS = sys.argv[2] if len(sys.argv) > 2 else (os.environ.get("ARS_SQUAD_JS") or os.path.join(ROOT, "_データ_自動", "squad.js"))
MAX_AGE = int(os.environ.get("ARS_RADAR_MAX_AGE_MIN") or 60)
MIN = int(os.environ.get("ARS_RADAR_MIN") or 90)   # 比べる相手＝この分数以上プレミアに出た選手
URL = "https://fantasy.premierleague.com/api/bootstrap-static/"

if MAX_AGE and os.path.exists(OUT):
    try:
        prev = json.load(open(OUT, encoding="utf-8"))
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(prev["updated"])).total_seconds() / 60
        if age < MAX_AGE:
            print(f"6 角形は {age:.0f} 分前の物があるので取り直さない（{len(prev.get('p', {}))} 人）"); sys.exit(0)
    except Exception:
        pass


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", s.lower()).split()


def load_squad():
    try:
        src = open(SQUAD_JS, encoding="utf-8").read()
        return json.loads(re.search(r"const SQUAD = (.*?);\n", src, re.S).group(1))
    except Exception as ex:
        print("名簿が読めない:", ex); return []


F = lambda e, k: float(e.get(k) or 0)
def p90(e, k): return F(e, k) / max(F(e, "minutes"), 1) * 90

# 軸＝[名前, 計算, 説明]。全部「プレミアの同じポジションの中での位置」に直す
AXES = {
    "FWD": [["得点力", lambda e: p90(e, "goals_scored"), "ゴール（90 分あたり）"],
            ["脅威", lambda e: p90(e, "threat"), "公式の Threat 指標＝ゴールに近づいた度合い（90 分あたり）"],
            ["決定力", lambda e: (F(e, "goals_scored") - F(e, "expected_goals")) / max(F(e, "minutes"), 1) * 90, "ゴール − 期待値 xG（90 分あたり）。チャンスをどれだけ決めたか"],
            ["創造性", lambda e: p90(e, "creativity"), "公式の Creativity 指標＝チャンスを作った度合い（90 分あたり）"],
            ["影響力", lambda e: p90(e, "influence"), "公式の Influence 指標＝試合の流れに関わった度合い（90 分あたり）"],
            ["勝負強さ", lambda e: p90(e, "bps"), "ボーナス点の元になる BPS（90 分あたり）"]],
    "MID": [["創造性", lambda e: p90(e, "creativity"), "公式の Creativity 指標＝チャンスを作った度合い（90 分あたり）"],
            ["チャンス創出", lambda e: p90(e, "expected_assists"), "期待アシスト xA（90 分あたり）"],
            ["脅威", lambda e: p90(e, "threat"), "公式の Threat 指標＝ゴールに近づいた度合い（90 分あたり）"],
            ["影響力", lambda e: p90(e, "influence"), "公式の Influence 指標（90 分あたり）"],
            ["守備貢献", lambda e: (F(e, "clearances_blocks_interceptions") + F(e, "tackles") + F(e, "recoveries")) / max(F(e, "minutes"), 1) * 90, "クリア・ブロック・インターセプト＋タックル＋リカバリー（90 分あたり）"],
            ["ゴール関与", lambda e: (F(e, "goals_scored") + F(e, "assists")) / max(F(e, "minutes"), 1) * 90, "ゴール＋アシスト（90 分あたり）"]],
    "DEF": [["守備貢献", lambda e: p90(e, "clearances_blocks_interceptions"), "クリア・ブロック・インターセプト（90 分あたり）"],
            ["タックル", lambda e: p90(e, "tackles"), "タックル（90 分あたり）"],
            ["リカバリー", lambda e: p90(e, "recoveries"), "ボールを取り返した回数（90 分あたり）"],
            ["影響力", lambda e: p90(e, "influence"), "公式の Influence 指標（90 分あたり）"],
            ["攻撃の脅威", lambda e: p90(e, "threat"), "公式の Threat 指標＝セットプレーなどでゴールに近づいた度合い（90 分あたり）"],
            ["無失点", lambda e: p90(e, "clean_sheets"), "無失点の試合（90 分あたり）"]],
    "GKP": [["セーブ", lambda e: p90(e, "saves"), "セーブ（90 分あたり）"],
            ["無失点", lambda e: p90(e, "clean_sheets"), "無失点の試合（90 分あたり）"],
            ["防いだ失点", lambda e: (F(e, "expected_goals_conceded") - F(e, "goals_conceded")) / max(F(e, "minutes"), 1) * 90, "被 xG − 実際の失点（90 分あたり）。期待より何点防いだか"],
            ["飛び出し", lambda e: p90(e, "recoveries"), "リカバリー＝ペナルティエリアの外も含めてボールを拾った回数（90 分あたり）"],
            ["影響力", lambda e: p90(e, "influence"), "公式の Influence 指標（90 分あたり）"],
            ["勝負強さ", lambda e: p90(e, "bps"), "ボーナス点の元になる BPS（90 分あたり）"]],
}


def pct(v, pool):
    """同点は半分ずつ＝(下の数 + 同じ数/2) / 全体"""
    if not pool:
        return 0
    less = sum(1 for x in pool if x < v - 1e-9); eq = sum(1 for x in pool if abs(x - v) <= 1e-9)
    return round(100 * (less + eq / 2) / len(pool))


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (clockend.jp player radar)"})
    with urllib.request.urlopen(req, timeout=40) as r:
        j = json.load(r)
    ars = next(t["id"] for t in j["teams"] if t["short_name"] == "ARS")
    types = {t["id"]: t["singular_name_short"] for t in j["element_types"]}   # 1 GKP 2 DEF 3 MID 4 FWD
    squad = load_squad()
    sq = [(p, set(norm(p.get("en", ""))), norm(p.get("en", ""))[-1:]) for p in squad]
    # 比べる相手＝ポジションごと・出場 MIN 分以上の全選手の、軸ごとの値
    pools = {}
    for e in j["elements"]:
        pos = types.get(e["element_type"])
        if pos not in AXES or F(e, "minutes") < MIN:
            continue
        pools.setdefault(pos, [[] for _ in AXES[pos]])
        for i, (_, fn, _) in enumerate(AXES[pos]):
            pools[pos][i].append(fn(e))
    out, seen = {}, set()
    for e in j["elements"]:
        if e["team"] != ars:
            continue
        pos = types.get(e["element_type"])
        if pos not in AXES:
            continue
        full = set(norm(e.get("first_name", "") + " " + e.get("second_name", ""))) | set(norm(e.get("web_name", "")))
        best, score = None, 0
        for p, toks, last in sq:
            ov = len(toks & full) + (1 if last and last[0] in full else 0)
            if ov > score:
                best, score = p, ov
        if not best or score < 1 or best["no"] in seen:
            print("名簿に無い（か重複）:", e.get("web_name")); continue
        seen.add(best["no"])
        mins = int(F(e, "minutes"))
        ax = [[name, pct(fn(e), pools.get(pos, [[]] * 6)[i]) if mins else 0, desc] for i, (name, fn, desc) in enumerate(AXES[pos])]
        out[str(best["no"])] = {"pos": pos, "min": mins, "low": mins < MIN, "ax": ax}
    res = {"updated": datetime.now(timezone.utc).isoformat(), "src": "プレミアリーグ公式（Fantasy Premier League）",
           "league": "プレミアリーグ", "min": MIN, "pool": {k: len(v[0]) for k, v in pools.items()}, "p": out}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("書いた", OUT, len(out), "人・比べる相手", res["pool"])
    for no, v in sorted(out.items(), key=lambda kv: int(kv[0])):
        print(f"  {int(no):>2} {v['pos']} {v['min']:>4}分 " + " ".join(f"{n}{x}" for n, x, _ in v["ax"]) + ("（出場が少ない＝目安）" if v["low"] else ""))


if __name__ == "__main__":
    main()
