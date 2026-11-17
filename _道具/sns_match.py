# -*- coding: utf-8 -*-
"""CLOCK END の SNS｜試合の日の 5 つの出来事（決まり帳 v1.1 の 1〜5）を見つけて、絵と文を作り、公開先の /_sns に置く（2026-11-14〜）。

流れ（GitHub の fetch.yml の 5 分ごとの取り込みの最後に 1 回・出来事が無ければ何もしない）：
  ① 取り込みが作った data.js から、近い試合と出来事を探す
      eve       明日の試合    … キックオフの日（日本時間）の前の日の 16:00〜19:40 の最初の回 → 20:00 に出す
      lineup    公式スタメン  … キックオフの 110 分前〜2 分前。ESPN の試合の中身にアーセナルの先発 11 人が出た最初の回 → すぐ出す
      ft        試合終了の合図… MATCHES にその試合の結果が入った最初の回（キックオフから 6 時間以内）→ すぐ出す（X の文だけ）
      highlight ハイライト到着… MATCHES にハイライトの動画が付いた最初の回 → すぐ出す。キックオフから 50 時間（試合終了から約 48 時間）を
                               過ぎていたら「遅れた」印を付ける＝社内ツールは出さずに【要対応】
      ratings   メディアの採点… 試合終了（キックオフ＋2 時間）から 10 時間で 2 社以上・12 時間で 1 社以上。ハイライトが届いてから → すぐ出す
  ② 「もう作ったか」は公開先で確かめる（https://clockend.jp/sns/ev-<試合>-<出来事>.json があれば作らない＝2 回出さない）
  ③ 絵（sns_cards.py の型・1080×1350）と文を作り、番人（結果の言葉）に通して、絵 → json の順に /_sns へ送る
     番人が止めた時も json は送る（blocked に言葉）＝社内ツールが【要対応】を出す。黙って止まらない
  ④ 公開先（CLOCK END の Worker）は ev-*.json を受け取ったら、社内ツール（sns-tool の ClockendHook）に絵ごと渡す
     ＝社内ツールが Buffer に予約（X・Instagram）し、困った時とハイライトが届いた時はカレンダー「SNS運用」へ
対象＝キックオフが SNS_MATCH_SINCE（既定 2026-11-20）より後の試合だけ（前の試合の出来事を今さら出さない）。

使い方：
  python sns_match.py --data 見本_20261030/data.js                         … 本番（GitHub）
  python sns_match.py --data <data.js> --now 2026-11-21T17:00:00+09:00 --no-upload --out <フォルダ> [--since 2026-11-01] [--only eve,lineup]
     --no-upload の時は公開先を見に行かない（作った物は --out に置くだけ）
"""
import argparse, base64, datetime as dt, html, json, math, os, re, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sns_cards as C   # noqa: E402

JST = dt.timezone(dt.timedelta(hours=9))
UTC = dt.timezone.utc
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ClockendUploader/1.0"   # Python そのままだと Cloudflare が 1010 で弾く
SITE = "https://clockend.jp"
UPLOAD = os.environ.get("UPDATE_URL") or "https://clockend.atushisugaya.workers.dev"
SINCE_DEFAULT = "2026-11-20T00:00:00Z"
WD = "月火水木金土日"
TAGS_PL = "#アーセナル #arsenal #プレミアリーグ #海外サッカー #ファンサイト"
TAGS_CL = "#アーセナル #arsenal #チャンピオンズリーグ #海外サッカー #ファンサイト"
STRIPES = {"newcastle", "brentford", "sunderland", "southampton", "stoke", "sheffieldutd", "juventus", "barcelona", "inter", "acmilan", "atleticomadrid", "athleticbilbao", "psv", "feyenoord", "betis"}
KIND_JA = {"eve": "明日の試合", "lineup": "公式スタメン", "ft": "試合終了の合図", "highlight": "ハイライト到着", "ratings": "メディアの採点"}

# ---- 番人（決まり帳の共通の決まり「結果は書かない」）＝社内ツールの clockend_match.js と同じ言葉 ----
GUARD = re.compile(r"\d\s*[-–−]\s*\d|勝利|勝ち|敗|負け|引き分け|ドロー|逆転|完封|撃破|首位|連勝|連敗|制し|白星|黒星|(?<!ウーデ)(?<!エデ)ゴール(?!キーパー)|得点|スコア")


def guard_hit(s):
    m = GUARD.search(str(s or ""))
    return m.group(0) if m else None


def x_weight(s):
    """X の数え方（日本語・絵文字は 2・URL は 23）"""
    urls = re.findall(r"https?://\S+", s)
    s = re.sub(r"https?://\S+", "", s)
    return sum(1 if ord(c) <= 0x10FF else 2 for c in s) + 23 * len(urls)


# ---------------------------------------------------------------- data.js
def load_data(path):
    src = open(path, encoding="utf-8").read() if path else get(SITE + "/data.js").decode("utf-8")
    out = {}
    for line in src.split("\n"):
        m = re.match(r"^const\s+([A-Za-z_0-9]+)\s*=\s*(.*?);?\s*$", line)
        if not m:
            continue
        try:
            out[m.group(1)] = json.loads(m.group(2))
        except Exception:
            pass
    return out


def ptime(s):
    s = str(s).replace("Z", "+00:00")
    if re.search(r"T\d{2}:\d{2}\+", s):
        s = s.replace("+", ":00+", 1)
    return dt.datetime.fromisoformat(s).astimezone(UTC)


def matches_of(D):
    """試合の一覧（id → 中身）。予定＝COMPS.next・NEXT、終わった・進行中＝MATCHES（結果 r・動画 v・live）"""
    out = {}
    for k, lst in ((D.get("COMPS") or {}).get("next") or {}).items():
        for m in lst or []:
            out.setdefault(m["id"], {"id": m["id"], "k": m.get("k") or k, "lab": m.get("lab") or "", "ko": ptime(m["d"]), "h": m["h"], "a": m["a"]})
    n = D.get("NEXT")
    if n and n.get("id"):
        out.setdefault(n["id"], {"id": n["id"], "k": "pl" if "プレミア" in (n.get("lab") or "") else "cl" if "チャンピオンズ" in (n.get("lab") or "") else "cup",
                                 "lab": n.get("lab") or "", "ko": ptime(n["d"]), "h": n["h"], "a": n["a"]})
    for m in D.get("MATCHES") or []:
        if m.get("k") == "old" or not m.get("d"):
            continue
        cur = out.setdefault(m["id"], {"id": m["id"], "k": m.get("k"), "lab": m.get("lab") or "", "ko": ptime(m["d"]), "h": m["h"], "a": m["a"]})
        if m.get("k") != "pre":
            cur["k"] = m.get("k") or cur["k"]
        cur["live"] = bool(m.get("live"))
        cur["done"] = m.get("r") is not None and not m.get("live")
        cur["v"] = m.get("v")
        cur["eid"] = m.get("eid")
    teams = D.get("TEAMS") or {}
    for m in out.values():
        opp = m["a"] if m["h"] == "arsenal" else m["h"]
        m["opp"] = opp
        m["opp_n"] = (teams.get(opp) or {}).get("n") or opp
        m["home_n"] = (teams.get(m["h"]) or {}).get("n") or m["h"]
        m["away_n"] = (teams.get(m["a"]) or {}).get("n") or m["a"]
    return out


def when(t):
    t = t.astimezone(JST)
    return "%d/%d（%s）%d:%02d" % (t.month, t.day, WD[t.weekday()], t.hour, t.minute)


def joke(t):
    h = t.astimezone(JST).hour
    return "夜ふかし確定です！" if h < 5 else "早起き確定です！" if h < 9 else "仕事終わりに間に合います！" if h >= 19 else "予定を空けておきましょう！"


def tags(m):
    return TAGS_CL if m.get("k") == "cl" else TAGS_PL


def comp_en(lab):
    m = re.match(r"プレミアリーグ 第(\d+)節", lab or "")
    if m:
        return "PREMIER LEAGUE ・ MATCHWEEK " + m.group(1)
    m = re.match(r"チャンピオンズリーグ 第(\d+)節", lab or "")
    if m:
        return "CHAMPIONS LEAGUE ・ MATCHDAY " + m.group(1)
    return lab or ""


def reply(kind, label="サイトはこちらです。"):
    return "%s\n%s/?utm_source=x&utm_medium=social&utm_campaign=%s" % (label, SITE, kind)


# ---------------------------------------------------------------- 選手・予想・ケガ・採点
def players(D):
    P = {}
    for p in D.get("SQUAD") or []:
        P[int(p["no"])] = {"n": p.get("n") or p.get("en"), "pos": p.get("pos") or ""}
    for no, x in ((D.get("COMPS") or {}).get("extra") or {}).items():
        P.setdefault(int(no), {"n": x.get("n"), "pos": x.get("pos") or "MF"})
    return P


def kana(s):
    for a, b in (("ヴァ", "バ"), ("ヴィ", "ビ"), ("ヴェ", "ベ"), ("ヴォ", "ボ"), ("ヴ", "ブ"), ("・", ""), ("＝", ""), ("=", ""), (" ", "")):
        s = s.replace(a, b)
    return s


def prediction(D, m, P):
    """記者の予想（YOSO）→ 2 社以上が選んだ選手で 11 人。布陣は一番多い物。返り値＝(xi, n, 社名の並び, 全員が 2 社以上か) か None（2 社未満）"""
    Y = D.get("YOSO") or {}
    if kana((Y.get("opp") or {}).get("ja") or "") != kana(m["opp_n"]):
        return None
    items, seen = [], set()
    for it in Y.get("items") or []:
        if it.get("src") in seen or len(it.get("xi") or []) < 11 or len(it.get("pos") or []) < 11:
            continue
        seen.add(it["src"])
        items.append(it)
    if len(items) < 2:
        return None
    votes = Counter(int(no) for it in items for no in set(it["xi"][:11]))
    fm = Counter(it.get("fm") for it in items).most_common(1)[0][0]
    base = max([it for it in items if it.get("fm") == fm], key=lambda it: sum(votes[int(no)] for no in it["xi"][:11]))
    slots = [dict(p) for p in base["pos"][:11]]
    used = {int(p["no"]) for p in slots}
    pool = [no for no, v in votes.most_common() if v >= 2 and no not in used]
    grp = lambda no: (P.get(no) or {}).get("pos") or ""
    all2 = True
    for p in slots:
        if votes[int(p["no"])] >= 2:
            continue
        alt = next((no for no in pool if grp(no) == grp(int(p["no"]))), None)
        if alt is None:
            all2 = False
            continue
        pool.remove(alt)
        p["no"] = alt
    xi = [{"no": int(p["no"]), "n": (P.get(int(p["no"])) or {}).get("n") or str(p["no"]), "x": p["x"], "y": p["y"],
           "p": "GK" if grp(int(p["no"])) == "GK" else None} for p in slots]
    return xi, len(items), "・".join(it["src"] for it in items), all2


def injuries(D, m):
    """ケガ・出場停止（4 人まで）。キックオフより前に戻る人・出られそうな人（75% 以上）は外す"""
    ko_day = m["ko"].astimezone(JST).date().isoformat()
    out = []
    for p in (D.get("INJ") or {}).get("list") or []:
        if p.get("ret") and p["ret"] < ko_day:
            continue
        if p.get("chance") is not None and p["chance"] >= 75:
            continue
        what = re.sub(r"(の)?(ケガ|負傷)$", "", p.get("ja") or "").strip()
        if p.get("kind") == "sus":
            out.append(("出場停止", p.get("n") or ""))
        elif p.get("kind") == "doubt":
            out.append(("出場微妙", "%s（%s）" % (p.get("n"), what) if what else p.get("n") or ""))
        else:
            out.append(("ケガ", "%s（%s）" % (p.get("n"), what) if what else p.get("n") or ""))
    return out[:4]


def ratings_of(D, m, P):
    R = (D.get("MRATE") or {}).get(m["id"]) or {}
    outs = R.get("outlets") or []
    by = {}
    for o in outs:
        for no, v in (o.get("r") or {}).items():
            if v is not None:
                by.setdefault(int(no), []).append(float(v))
    need = max(1, math.ceil(len(outs) / 2))
    rows = [((P.get(no) or {}).get("n") or str(no), round(sum(v) / len(v), 1)) for no, v in by.items() if len(v) >= need]
    rows.sort(key=lambda r: -r[1])
    return len(outs), "・".join(o.get("src") or "" for o in outs), rows


# ---------------------------------------------------------------- ESPN（公式スタメン）
def official_lineup(m, log_dir):
    """ESPN の試合の中身にアーセナルの先発 11 人が出ていれば、取り込みと同じ形（arsfetch.lineup_from_summary）で返す"""
    import arsfetch as A
    A.LOG_DIR = log_dir or A.LOG_DIR
    lgs = {"pl": ["eng.1"], "cl": ["uefa.champions"]}.get(m.get("k"), ["eng.league_cup", "eng.fa"])
    for lg in lgs:
        eid = m.get("eid")
        if not eid:
            for q in ("?fixture=true", ""):
                try:
                    j = A.jget(f"{A.ESPN}{lg}/teams/{A.ARS_ID}/schedule{q}")
                except Exception:
                    continue
                for e in j.get("events", []):
                    if abs((ptime(A.iso(e["date"])) - m["ko"]).total_seconds()) < 20 * 60:
                        eid = e["id"]
                        break
                if eid:
                    break
        if not eid:
            continue
        summ = A.jget(f"{A.ESPN}{lg}/summary?event={eid}")
        lu = A.lineup_from_summary(A.load_state(), {"id": m["id"]}, summ, {"athletes": []})
        if lu and len(lu.get("xi") or []) == 11:
            return lu
        return None
    return None


# ---------------------------------------------------------------- 絵
_faces = None


def faces():
    global _faces
    if _faces is None:
        try:
            s = get(SITE + "/sprites.js").decode("utf-8")
            i = s.find("{", s.find("const SPRITES"))
            _faces = json.JSONDecoder().raw_decode(s[i:])[0]
        except Exception as ex:
            print("ドット絵の顔が読めない（背番号の丸で出す）:", ex)
            _faces = {}
    return _faces


def with_faces(xi):
    F = faces()
    return [dict(p, face=(F.get(str(p["no"])) or {}).get("face")) for p in xi]


def crest():
    return "data:image/png;base64," + base64.b64encode(open(os.path.join(HERE, "sns_crest.png"), "rb").read()).decode()


def browser():
    for c in [os.environ.get("CHROME"), shutil.which("google-chrome"), shutil.which("chromium"),
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
        if c and os.path.exists(c):
            return c
    raise SystemExit("絵を撮るブラウザが無い（CHROME を指定）")


_fonts_ok = False


def fonts():
    """GitHub の Ubuntu には日本語の字が無い＝Google Fonts が読めなかった時の控えに Noto CJK を入れる（絵を撮る回だけ・1 回）"""
    global _fonts_ok
    if _fonts_ok or not os.environ.get("GITHUB_ACTIONS"):
        return
    _fonts_ok = True
    subprocess.run("fc-list | grep -qi 'Noto Sans CJK' || sudo apt-get install -y -q fonts-noto-cjk > /dev/null", shell=True, timeout=180)


def shoot(page_html, png, h=1350):
    fonts()
    d = tempfile.mkdtemp(prefix="sns_match_")
    src = os.path.join(d, "page.html")
    open(src, "w", encoding="utf-8").write(page_html)
    cmd = [browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-sandbox", "--force-device-scale-factor=1",
           "--window-size=1080,%d" % h, "--virtual-time-budget=15000", "--user-data-dir=" + os.path.join(d, "prof"),
           "--screenshot=" + png, "file:///" + src.replace("\\", "/").lstrip("/")]
    if os.path.exists(png):
        os.remove(png)
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    last = -1
    for _ in range(120):   # Windows の Edge は撮り終える前に戻ってくる＝大きさが止まるまで待つ
        size = os.path.getsize(png) if os.path.exists(png) else -1
        if size > 20000 and size == last:
            break
        last = size
        time.sleep(0.5)
    if not os.path.exists(png) or os.path.getsize(png) < 20000:
        raise RuntimeError("絵が撮れなかった: " + (r.stderr or b"")[-400:].decode("utf-8", "replace"))
    shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------- 出来事
def make_event(kind, m, D, P, now, log_dir):
    """返り値＝(meta, [(絵の名前, html)]) か None（まだ作れない＝次の回にもう一度見る）"""
    eid = "ev-%s-%s" % (m["id"], kind)
    meta = {"v": 1, "kind": kind, "id": eid, "due": None, "late": False, "blocked": None, "notes": [],
            "match": {"id": m["id"], "lab": m["lab"], "ko": m["ko"].strftime("%Y-%m-%dT%H:%M:%SZ"), "opp": m["opp_n"], "home": m["home_n"], "away": m["away_n"], "k": m.get("k")},
            "made": now.astimezone(JST).isoformat(timespec="seconds")}
    pages, opp = [], m["opp_n"]
    if kind == "eve":
        pr = prediction(D, m, P)
        inj = injuries(D, m)
        side = "ホーム" if m["h"] == "arsenal" else "アウェイ"
        d = {"when": when(m["ko"]), "match": "%s vs %s" % (m["home_n"], m["away_n"]), "comp": "%s・%s" % (m["lab"], side), "inj": inj}
        hm = "%d:%02d" % (m["ko"].astimezone(JST).hour, m["ko"].astimezone(JST).minute)
        if pr:
            xi, n, src, all2 = pr
            d.update(xi=with_faces(xi), n=n, src=src)
            if not all2:
                d["xi_label"] = "（多くの社が選んだ並び）"
                meta["notes"].append("2 社以上がそろわない位置があり、その位置は 1 社の予想のまま")
            text = "いよいよ明日、%s戦！⚽️\n記者%d社の予想スタメンを1枚にまとめました。あなたの予想は？（日本時間%sキックオフ＝%s）COYG！🔴⚪️" % (opp, n, hm, joke(m["ko"]))
        else:
            meta["notes"].append("記者の予想が 2 社未満＝予想の欄を外した（決まり帳の「足りない時」）")
            what = "ケガと出場停止の情報も1枚にまとめました。" if inj else "日本時間の日時を1枚にまとめました。"
            text = "いよいよ明日、%s戦！⚽️\n日本時間%sキックオフ＝%s%sCOYG！🔴⚪️" % (opp, hm, joke(m["ko"]), what)
        pages.append((eid + ".png", C.card_html("eve", d, crest())))
        due = dt.datetime.combine(m["ko"].astimezone(JST).date() - dt.timedelta(days=1), dt.time(20, 0), JST)
        meta["due"] = due.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        meta["x"] = {"text": text, "reply": reply("eve"), "images": [eid + ".png"]}
        meta["ig"] = {"text": text + "\n\n" + tags(m), "images": [eid + ".png"]}
        meta["alt"] = "%s %s（日本時間）。%s。結果は書いていません。" % (when(m["ko"]), d["match"], d["comp"])
        meta["card"] = {k: v for k, v in d.items() if k != "xi"}
        meta["card"]["xi"] = [p["n"] for p in d.get("xi") or []]
    elif kind == "lineup":
        lu = official_lineup(m, log_dir)
        if not lu:
            return None
        pr = prediction(D, m, P)
        pred = {p["no"] for p in pr[0]} if pr else None
        xi = [{"no": p["no"], "n": p["n"], "x": p["x"], "y": p["y"], "p": "GK" if p.get("gk") else p.get("p")} for p in lu["xi"]]
        diff = [p["no"] for p in xi if pred is not None and p["no"] not in pred]
        left = max(1, int((m["ko"] - now).total_seconds() // 60))
        names = [p["n"] for p in xi if p["no"] in diff]
        if pred is None:
            sent = ""
            meta["notes"].append("記者の予想が 2 社未満＝予想との違いは書かない")
        elif names:
            sent = "予想と違ったのは%s%s。" % ("・".join(names[:3]), "ら%d人" % len(names) if len(names) > 3 else "")
        else:
            sent = "記者の予想どおり！"
        text = "公式スタメン、出ました！🔴⚪️\n%sキックオフまであと%d分！（寝落ちしても大丈夫。結果は伏せておきます）COYG！⚽️" % (sent, left)
        d = {"fm": lu["fm"], "xi": with_faces(xi), "diff": diff, "bench": [p["n"] for p in lu.get("bench") or []], "left": left, "pred": pred is not None}
        pages.append((eid + ".png", C.card_html("lineup", d, crest())))
        meta["x"] = {"text": text, "reply": reply("lineup"), "images": [eid + ".png"]}
        meta["ig"] = {"text": text + "\n\n" + tags(m), "images": [eid + ".png"]}
        # 説明に布陣（4-2-3-1）を入れない＝番人が「2-1」の形と見分けられない
        meta["alt"] = "%s %s の公式スタメン。結果は書いていません。" % (m["lab"], "%s vs %s" % (m["home_n"], m["away_n"]))
        meta["card"] = {"fm": lu["fm"], "xi": [p["n"] for p in xi], "diff": names, "left": left}
    elif kind == "ft":
        text = "%s戦、試合終了のホイッスル！⚽️\nここから数時間、タイムラインは危険地帯です。ハイライトが届いたら、結果を伏せてお知らせします。COYG！🔴⚪️" % opp
        meta["x"] = {"text": text, "reply": None, "images": []}
        meta["ig"] = None
    elif kind == "highlight":
        T = D.get("TEAMS") or {}
        side = lambda k: {"s": (T.get(k) or {}).get("s") or k[:3].upper(), "c": (T.get(k) or {}).get("c") or "#333333", "st": k in STRIPES}
        text = "ハイライト、届きました！⚽️\n%sの%s戦。結果は見終わるまで出ません。安心してどうぞ。（見終わったら、メディアの採点もサイトでどうぞ！）COYG！🔴⚪️" % (m["lab"], opp)
        d = {"home": side(m["h"]), "away": side(m["a"]), "comp": comp_en(m["lab"])}
        pages.append((eid + ".png", C.card_html("highlight", d, crest())))
        meta["x"] = {"text": text, "reply": reply("highlight"), "images": [eid + ".png"]}
        meta["ig"] = {"text": text + "\n\n" + tags(m), "images": [eid + ".png"]}
        meta["alt"] = "%s %s のハイライトが届きました。結果は書いていません。" % (m["lab"], "%s vs %s" % (m["home_n"], m["away_n"]))
        meta["cal"] = {"title": "【CLOCK END】ハイライト届きました（%s戦）" % opp, "desc": "結果の字は入れていません。\nhttps://clockend.jp/"}
        if (now - m["ko"]) > dt.timedelta(hours=50):
            meta["late"] = True
            meta["late_text"] = "お待たせしました！%s戦のハイライト、CLOCK END に届きました⚽️\n%sの%s戦。結果は見終わるまで出ません。安心してどうぞ。COYG！🔴⚪️" % (opp, m["lab"], opp)
    elif kind == "ratings":
        n, src, rows = ratings_of(D, m, P)
        if not rows:
            return None
        T = D.get("TEAMS") or {}
        tag = "%s v %s" % ((T.get(m["h"]) or {}).get("s") or m["h"], (T.get(m["a"]) or {}).get("s") or m["a"])
        text = "メディア%d社の採点、まとまりました！⚽️\nここから先は結果を含みます。まだの方は、ハイライトからどうぞ。COYG！🔴⚪️" % n
        pages.append((eid + ".png", C.card_html("rcover", {"tag": tag, "n": n, "src": src}, crest())))
        pages.append((eid + "-2.png", C.card_html("ravg", {"tag": tag, "n": n, "src": src, "rows": rows, "mvp": rows[0][0]}, crest())))
        meta["x"] = {"text": text, "reply": reply("ratings", "採点はこちらです（結果を含みます）。"), "images": [eid + ".png"]}
        meta["ig"] = {"text": text + "\n\n" + tags(m), "images": [eid + ".png", eid + "-2.png"]}
        meta["alt"] = "%s %s のメディアの採点（表紙は結果を含みますの案内）。" % (m["lab"], "%s vs %s" % (m["home_n"], m["away_n"]))
        meta["card"] = {"n": n, "src": src, "rows": len(rows)}
    # 番人：文（と、結果を含まないはずの絵の字）に結果の言葉があれば止める。採点の 2 枚目は表紙の後ろなので通さない
    texts = [meta["x"]["text"], meta["x"].get("reply") or "", (meta.get("ig") or {}).get("text") or "", meta.get("alt") or ""]
    if kind == "eve":
        texts += [meta["card"]["match"], meta["card"]["comp"]] + [t for _, t in meta["card"].get("inj") or []]
    hit = next((h for h in map(guard_hit, texts) if h), None)
    if hit:
        meta["blocked"] = hit
        pages = []
        for k in ("x", "ig"):
            if meta.get(k):
                meta[k]["images"] = []
    if x_weight(meta["x"]["text"]) > 280:
        meta["blocked"] = meta["blocked"] or "X の 280 を超えた（%d）" % x_weight(meta["x"]["text"])
    return meta, pages


def due_events(M, D, now, since, only):
    """いま作るべき出来事（作ったかどうかは見ない）＝[(kind, 試合)]"""
    out = []
    nj = now.astimezone(JST)
    for m in sorted(M.values(), key=lambda m: m["ko"]):
        if m["ko"] < since:
            continue
        ko = m["ko"]
        if (ko.astimezone(JST).date() - dt.timedelta(days=1)) == nj.date() and dt.time(16, 0) <= nj.time() < dt.time(19, 40):
            out.append(("eve", m))
        if ko - dt.timedelta(minutes=110) <= now < ko - dt.timedelta(minutes=2) and not m.get("done"):
            out.append(("lineup", m))
        if m.get("done") and now - ko < dt.timedelta(hours=6):
            out.append(("ft", m))
        if m.get("done") and m.get("v") and now - ko < dt.timedelta(days=7):
            out.append(("highlight", m))
        if m.get("done") and m.get("v") and now - ko < dt.timedelta(days=4):
            n = len(((D.get("MRATE") or {}).get(m["id"]) or {}).get("outlets") or [])
            ft = ko + dt.timedelta(hours=2)
            if (now >= ft + dt.timedelta(hours=10) and n >= 2) or (now >= ft + dt.timedelta(hours=12) and n >= 1):
                out.append(("ratings", m))
    return [(k, m) for k, m in out if not only or k in only]


# ---------------------------------------------------------------- 公開先
def get(url, method="GET", timeout=60):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def exists(name):
    """公開先にもう置いてあるか。True／False／None（分からない＝今回は作らない）"""
    try:
        get("%s/sns/%s?t=%d" % (SITE, name, time.time()), method="HEAD", timeout=20)
        return True
    except urllib.error.HTTPError as e:
        return False if e.code == 404 else None
    except Exception:
        return None


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
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data"); ap.add_argument("--out"); ap.add_argument("--now"); ap.add_argument("--since"); ap.add_argument("--only")
    ap.add_argument("--no-upload", action="store_true")
    a = ap.parse_args()
    now = ptime(a.now) if a.now else dt.datetime.now(UTC)
    since = ptime(a.since or os.environ.get("SNS_MATCH_SINCE") or SINCE_DEFAULT)
    only = set(a.only.split(",")) if a.only else None
    D = load_data(a.data)
    M, P = matches_of(D), players(D)
    todo = due_events(M, D, now, since, only)
    if not todo:
        print("試合の日の SNS：いまは出来事なし（%s）" % now.astimezone(JST).strftime("%m/%d %H:%M"))
        return 0
    out = a.out or tempfile.mkdtemp(prefix="sns_match_out_")
    os.makedirs(out, exist_ok=True)
    key = None if a.no_upload else update_key()
    if not a.no_upload and not key:
        print("UPDATE_KEY が無いので送らない")
        return 1
    for kind, m in todo:
        name = "ev-%s-%s" % (m["id"], kind)
        if not a.no_upload:
            ex = exists(name + ".json")
            if ex is not False:
                print("%s：%s" % (name, "もう作ってある" if ex else "公開先が確かめられない＝次の回に"))
                continue
        try:
            got = make_event(kind, m, D, P, now, out if a.no_upload else None)
        except Exception as ex:
            print("%s：作れなかった（次の回にもう一度）：%s" % (name, ex))
            continue
        if not got:
            print("%s：まだ材料がそろっていない（次の回にもう一度）" % name)
            continue
        meta, pages = got
        try:
            for fn, page in pages:
                open(os.path.join(out, fn.replace(".png", ".html")), "w", encoding="utf-8").write(page)
                shoot(page, os.path.join(out, fn))
        except Exception as ex:
            meta["blocked"] = meta["blocked"] or "絵が作れなかった：" + str(ex)[:160]
            pages = []
            for k in ("x", "ig"):
                if meta.get(k):
                    meta[k]["images"] = []
        js = json.dumps(meta, ensure_ascii=False, indent=1)
        open(os.path.join(out, name + ".json"), "w", encoding="utf-8").write(js)
        print("==== %s（%s）%s" % (name, KIND_JA[kind], "番人が止めた：" + meta["blocked"] if meta["blocked"] else ""))
        print(meta["x"]["text"])
        print("X の数え方:", x_weight(meta["x"]["text"]), "・絵:", ", ".join("%s %d バイト" % (fn, os.path.getsize(os.path.join(out, fn))) for fn, _ in pages) or "なし")
        if a.no_upload:
            continue
        for fn, _ in pages:
            print("送った:", put(fn, open(os.path.join(out, fn), "rb").read(), "image/png", key))
        print("送った:", put(name + ".json", js.encode("utf-8"), "application/json; charset=utf-8", key))
    return 0


if __name__ == "__main__":
    sys.exit(main())
