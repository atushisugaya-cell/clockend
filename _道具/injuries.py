# -*- coding: utf-8 -*-
"""ケガ・出場停止＝プレミアリーグ公式 Fantasy の JSON（bootstrap-static）から、アーセナルの選手の状態を取る（11/3 菅谷様 ⑩）
  出どころ＝https://fantasy.premierleague.com/api/bootstrap-static/（鍵なし・status i=ケガ d=疑問 s=出場停止・news「Thigh injury - Expected back 21 Nov」）
  出力＝_データ_自動/injuries.json {"updated", "src", "list":[{no, en, n, kind, en_text, ja, ret, ret_text, chance, since}]}
  60 分以内に取った物があれば取り直さない（ARS_INJ_MAX_AGE_MIN）。名簿（squad.js の en）と名前で突き合わせる
使い方: python injuries.py [出力] [squad.js]
"""
import os, re, sys, json, unicodedata, urllib.request
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_データ_自動", "injuries.json")
SQUAD_JS = sys.argv[2] if len(sys.argv) > 2 else (os.environ.get("ARS_SQUAD_JS") or os.path.join(ROOT, "_データ_自動", "squad.js"))
MAX_AGE = int(os.environ.get("ARS_INJ_MAX_AGE_MIN") or 60)
URL = "https://fantasy.premierleague.com/api/bootstrap-static/"

if MAX_AGE and os.path.exists(OUT):
    try:
        prev = json.load(open(OUT, encoding="utf-8"))
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(prev["updated"])).total_seconds() / 60
        if age < MAX_AGE:
            print(f"ケガ情報は {age:.0f} 分前の物があるので取り直さない（{len(prev.get('list', []))} 人）"); sys.exit(0)
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


PART = {"thigh": "太もも", "hamstring": "ハムストリング", "knee": "ひざ", "ankle": "足首", "calf": "ふくらはぎ", "back": "背中", "groin": "そけい部",
        "foot": "足", "hip": "股関節", "shoulder": "肩", "head": "頭", "achilles": "アキレス腱", "muscle": "筋肉", "toe": "つま先", "hand": "手",
        "wrist": "手首", "rib": "肋骨", "concussion": "脳しんとう", "illness": "体調不良", "ill": "体調不良", "knock": "打撲", "fitness": "コンディション",
        "virus": "体調不良", "quad": "太もも", "quadricep": "太もも", "adductor": "内転筋", "shin": "すね", "neck": "首", "face": "顔", "eye": "目", "finger": "指", "leg": "脚"}
MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def parse_date(txt, base):
    m = re.search(r"(\d{1,2}) ([A-Za-z]{3})", txt or "")
    if not m or m.group(2).lower() not in MON:
        return None
    d, mo = int(m.group(1)), MON[m.group(2).lower()]
    y = base.year + (1 if mo < base.month - 2 else 0)  # 年は無い＝更新日から見て 2 か月以上前の月なら翌年
    try:
        return f"{y}-{mo:02d}-{d:02d}"
    except Exception:
        return None


def to_ja(status, news):
    """FPL の英語の一文 → 日本語。分からない語はそのまま残す"""
    s = (news or "").strip()
    head, _, rest = s.partition(" - ")
    hl = head.lower()
    if status == "s" or hl.startswith("suspended"):
        d = re.search(r"until (\d{1,2} [A-Za-z]{3})", s)
        return "出場停止" + (f"（{d.group(1)} まで）" if d else ""), rest
    part = next((PART[k] for k in PART if re.search(rf"\b{k}", hl)), None)
    if "injury" in hl or "injured" in hl:
        what = (part + "のケガ") if part else head
    elif part:
        what = part
    else:
        what = head
    rl = rest.lower()
    if "expected back" in rl:
        d = re.search(r"back (\d{1,2} [A-Za-z]{3})", rest)
        tail = f"復帰の見込み {d.group(1)}" if d else "復帰の見込みあり"
    elif "unknown return" in rl:
        tail = "復帰日は未定"
    elif "chance of playing" in rl:
        pc = re.search(r"(\d+)%", rest)
        tail = f"次の試合に出る見込み {pc.group(1)}%" if pc else rest
    elif "suspended" in rl:
        d = re.search(r"until (\d{1,2} [A-Za-z]{3})", rest)
        tail = "出場停止" + (f"（{d.group(1)} まで）" if d else "")
    else:
        tail = rest
    jd = lambda s: re.sub(r"(\d{1,2}) ([A-Za-z]{3})\b", lambda m: f"{MON.get(m.group(2).lower(), '?')}/{int(m.group(1))}" if m.group(2).lower() in MON else m.group(0), s)
    return jd(what), jd(tail)


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (clockend.jp injury board)"})
    with urllib.request.urlopen(req, timeout=40) as r:
        j = json.load(r)
    ars = next(t["id"] for t in j["teams"] if t["short_name"] == "ARS")
    squad = load_squad()
    sq = [(p, set(norm(p.get("en", ""))), norm(p.get("en", ""))[-1:] ) for p in squad]
    out = []
    for e in j["elements"]:
        if e["team"] != ars or e["status"] not in ("i", "d", "s"):
            continue
        full = set(norm(e.get("first_name", "") + " " + e.get("second_name", ""))) | set(norm(e.get("web_name", "")))
        best, score = None, 0
        for p, toks, last in sq:
            ov = len(toks & full) + (1 if last and last[0] in full else 0)
            if ov > score:
                best, score = p, ov
        if not best or score < 1:
            print("名簿に無い:", e.get("web_name"), e.get("news")); continue
        news = e.get("news") or ""
        added = e.get("news_added") or ""
        try:
            base = datetime.fromisoformat(added.replace("Z", "+00:00"))
        except Exception:
            base = datetime.now(timezone.utc)
        what, tail = to_ja(e["status"], news)
        kind = {"s": "sus", "i": "inj", "d": "doubt"}[e["status"]]
        m_ret = re.search(r"(?:Expected back|until) (\d{1,2} [A-Za-z]{3})", news)
        ret = parse_date(m_ret.group(1), base) if m_ret else None
        out.append({"no": best["no"], "en": best.get("en"), "n": best.get("n"), "pos": best.get("pos"), "kind": kind,
                    "en_text": news, "ja": what, "ja2": tail, "ret": ret, "chance": e.get("chance_of_playing_next_round"),
                    "since": added[:10]})
    order = {"inj": 0, "doubt": 1, "sus": 2}
    out.sort(key=lambda x: (order[x["kind"]], x["ret"] or "9999", x["no"]))
    res = {"updated": datetime.now(timezone.utc).isoformat(), "src": "プレミアリーグ公式（Fantasy Premier League）", "list": out}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("書いた", OUT, len(out), "人")
    for x in out:
        print(f"  {x['no']:>2} {x['n']}: {x['ja']}・{x['ja2']}（{x['en_text']}・{x['since']}）")


if __name__ == "__main__":
    main()
