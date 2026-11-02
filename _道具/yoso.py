# -*- coding: utf-8 -*-
"""記者の予想スタメンを集める（11/1 菅谷様「記者の予想、いい」）
  出どころ＝直の RSS 3 本（フットボールチャンネル／Sports Mole／football.london）。Google ニュースは転送先が解けないので使わない。
  やること＝次の相手の名前が入った「予想スタメン／predicted」の記事を拾う → 記事を読んで 11 人（名簿と照合）と布陣を抜く → _データ_自動/yoso.json
  写すのは「出典・題・11 人の並び」と「記事の要点（AI が自分の言葉で 2〜3 行にまとめた物）」だけ。本文は載せない。
  要点は手元の Claude（claude -p・取り込みのニュースと同じ呼び方）で作り、記事ごとに 1 回だけ（_データ_自動/yoso_sum.json に保存）。
  要点には過去の試合の結果（勝ち負け・スコア・敗退など）を書かない＝結果を知らずにハイライトを見たい人のサイトのため（11/1 菅谷様「各記事を要約して下に表示」）。
使い方: python yoso.py [相手の英語名] [相手の日本語名]    例: python yoso.py Liverpool リヴァプール
"""
import os, sys, re, json, html, shutil, subprocess, datetime as dt, urllib.request, xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "_データ_自動", "yoso.json")
SUM_CACHE = os.path.join(ROOT, "_データ_自動", "yoso_sum.json")
ITEM_CACHE = os.path.join(ROOT, "_データ_自動", "yoso_items.json")  # 記事ごとに抜いた 11 人（同じ記事を何度も読みに行かない）
# 本番（GitHub の取り込み）では環境変数で置き場を替える。既定は試作のまま
DATA_JS = os.environ.get("ARS_DATA_JS") or os.path.join(ROOT, "見本_20261030", "data.js")
SQUAD_JS = os.environ.get("ARS_SQUAD_JS") or os.path.join(ROOT, "試作_選手画面_20261101", "squad.js")
DAYS_BEFORE = 4  # 次の試合の何日前から予想を探すか
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36", "Accept-Language": "ja,en;q=0.8"}
FEEDS = [
    ("フットボールチャンネル", "ja", "https://www.footballchannel.jp/feed/"),
    ("Sports Mole", "en", "https://www.sportsmole.co.uk/football/arsenal/rss.xml"),
    ("football.london", "en", "https://www.football.london/arsenal-fc/?service=rss"),
]
JST = dt.timezone(dt.timedelta(hours=9))


def get(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=timeout) as r:
        return r.read()


def items(url):
    root = ET.fromstring(get(url))
    out = []
    for it in root.findall("./channel/item"):
        out.append({"title": html.unescape((it.findtext("title") or "").strip()), "link": (it.findtext("link") or "").strip(), "pub": it.findtext("pubDate") or ""})
    return out


def text_of(url, lang):
    """記事の本文の文字だけ（フットボールチャンネルは /2/ /3/ /4/ の続きのページも読む）"""
    pages = [url]
    if "footballchannel.jp" in url:
        base = url.rstrip("/")
        pages += [f"{base}/{i}/" for i in range(2, 6)]
    buf = []
    for p in pages:
        try:
            b = get(p).decode("utf-8", "replace")
        except Exception:
            break
        b = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", b, flags=re.S)
        # 本文らしい所：フットボールチャンネルは entry-content、ほかは <p>
        m = re.search(r'class="[^"]*(entry-content|article-body|article__body|content-body)[^"]*"[^>]*>(.*?)(<footer|<div class="[^"]*(related|share|tags))', b, re.S)
        body = m.group(2) if m else b
        t = html.unescape(re.sub(r"<[^>]+>", " ", body))
        buf.append(re.sub(r"\s+", " ", t))
    return " ".join(buf)


def load_names():
    seed = json.load(open(os.path.join(HERE, "names_seed.json"), encoding="utf-8"))
    sq_path = SQUAD_JS
    squad = []
    if os.path.exists(sq_path):
        s = open(sq_path, encoding="utf-8").read()
        squad = json.loads(re.search(r"const SQUAD = (.*?);\n", s, re.S).group(1))
    by_no = {}
    for p in squad:
        en = p["en"]; ja = seed.get(en, [p["n"], p["f"]])
        sur = en.split()[-1]
        keys_en = {sur, en}
        if sur == "Magalhães": keys_en |= {"Gabriel", "Magalhaes"}
        if sur == "Lewis-Skelly": keys_en |= {"Lewis Skelly"}
        if sur == "Guimarães": keys_en |= {"Guimaraes", "Bruno Guimaraes"}
        if sur == "Ødegaard": keys_en |= {"Odegaard"}
        if sur == "Gyökeres": keys_en |= {"Gyokeres"}
        if sur == "Hincapié": keys_en |= {"Hincapie"}
        if sur == "Zubimendi": keys_en |= {"Zubimendi"}
        keys_ja = {ja[0], ja[1]}
        if ja[0] == "ガブリエウ": keys_ja |= {"ガブリエル"}
        if ja[0] == "ギェケレシュ": keys_ja |= {"ヨケレス", "ギョケレス"}
        if ja[0] == "ルイス＝スケリー": keys_ja |= {"ルイス・スケリー", "ルイス=スケリー", "スケリー"}
        by_no[p["no"]] = {"en": keys_en, "ja": keys_ja, "pos": p["pos"], "n": ja[0]}
    return by_no


def match_name(tok, lang, names):
    tok = tok.strip(" .,;:>\u3000")
    if not tok: return None
    for no, d in names.items():
        for k in (d["en"] if lang == "en" else d["ja"]):
            if k and (tok == k or tok.endswith(k) or k.endswith(tok)):
                return no
    return None


def layout(groups):
    """[[GK],[DF…],[MF…],[AM…],[FW…]] の並びから、ピッチの座標（x% y%）を付ける。先頭が GK・最後が FW"""
    rows = [g for g in groups if g]
    n = len(rows)
    ys = {1: [90], 2: [90, 20], 3: [90, 72, 20], 4: [90, 72, 45, 15], 5: [90, 72, 52, 32, 12], 6: [90, 74, 58, 42, 26, 10]}[min(n, 6)]
    out = []
    for i, g in enumerate(rows):
        k = len(g)
        for j, no in enumerate(g):
            x = 50 if k == 1 else round(13 + (100 - 26) * j / (k - 1))
            out.append({"no": no, "x": x, "y": ys[i]})
    fm = "-".join(str(len(g)) for g in rows[1:])
    return out, fm


def extract_xi(text, lang, names):
    """記事の中の「予想 XI」の行を狙って 11 人を取る。取れなければ出現順の 11 人（rough）"""
    if lang == "en":
        for m in re.finditer(r"(?:predicted|possible|likely|probable)\s+(?:Arsenal\s+)?(?:starting\s+)?(?:XI|lineup|line-up|team)\s*(?:vs\.?\s*[A-Za-z ]+)?\s*:\s*([^.>\n]{20,260})", text, re.I):
            seg = m.group(1)
            groups = [[match_name(t, lang, names) for t in part.split(",")] for part in seg.split(";")]
            groups = [[no for no in g if no] for g in groups]
            flat = [no for g in groups for no in g]
            if len(flat) >= 9:
                pos, fm = layout(groups)
                return flat[:11], fm, pos, "line"
    else:
        # フットボールチャンネル：4 ページ目の「アーセナル予想フォーメーション ▽GK 1 ダビド・ラヤ ▽DF 12 … ▽MF … ▽FW …」＝背番号で取れる
        for m in re.finditer(r"アーセナル予想フォーメーション(.*?)(?:【次ページ】|【関連記事】|football|$)", text):
            seg = m.group(1)
            groups = []
            for part in re.split(r"▽", seg)[1:]:
                nos = [int(x) for x in re.findall(r"(?<![\d-])(\d{1,2})\s+[ァ-ヴー＝・]", part)]
                groups.append([n for n in nos if n in names])
            flat = [no for g in groups for no in g]
            if len(flat) >= 9:
                # 図は GK/DF/MF/FW の 4 段しか無いので、本文の「布陣は4-2-3-1」があればその段数で並べ直す
                fp = [x for x in re.findall(r"布陣は\s*([3-5]-[1-5]-[1-5](?:-[1-4])?)", text[m.start()-2500:m.start()] if m.start() > 2500 else text[:m.start()])]
                fm2 = fp[-1] if fp else None
                if fm2 and sum(int(x) for x in fm2.split("-")) == len(flat) - 1 and len(flat) == 11:
                    sizes = [1] + [int(x) for x in fm2.split("-")]
                    groups, i = [], 0
                    for k in sizes: groups.append(flat[i:i+k]); i += k
                pos, fm = layout(groups)
                return flat[:11], fm, pos, "figure"
        # 文章の形：「布陣は4-2-3-1。GKは…。DFラインは右から…。ボランチは…。2列目は…。最前線には…」
        for m in re.finditer(r"布陣は\s*([3-5]-[1-5]-[1-5](?:-[1-4])?)[。．](.{0,600}?)(?:【次ページ】|$)", text):
            fm = m.group(1); body = m.group(2)
            found = []
            for no, d in names.items():
                p = min((body.find(k) for k in d["ja"] if k and body.find(k) >= 0), default=-1)
                if p >= 0: found.append((p, no))
            found.sort()
            flat = [no for _, no in found][:11]
            if len(flat) >= 9:
                sizes = [1] + [int(x) for x in fm.split("-")]
                groups, i = [], 0
                for k in sizes: groups.append(flat[i:i+k]); i += k
                pos, _ = layout(groups)
                return flat, fm, pos, "prose"
    # 最後の手：出現順
    found = []
    for no, d in names.items():
        keys = d["en"] if lang == "en" else d["ja"]
        p = min((text.find(k) for k in keys if k and text.find(k) >= 0), default=-1)
        if p >= 0: found.append((p, no))
    found.sort()
    return [no for _, no in found[:11]], None, [], "rough"


SPOIL = re.compile(r"(?<![\d\-－–])\d+\s*[-－–対]\s*\d+(?!\s*[-－–]?\s*\d)|敗退|敗れ|負け|勝利し|勝った|引き分け|ドロー|PK|逆転|完勝|完敗|大勝|惨敗")


def summarize(title, text, names, lang):
    """記事の要点を日本語 2〜3 行で。結果の言葉が入った行は捨てる。API の鍵も claude も無ければ None"""
    exe = shutil.which("claude")
    if not exe and not os.environ.get("ANTHROPIC_API_KEY"):
        print("claude が見つからないので要点は作らない"); return None
    table = "、".join(sorted({f"{sorted(d['en'], key=len)[-1]}={d['n']}" for d in names.values()}))
    prompt = f"""あなたはアーセナルのファンサイトの編集者です。下の「予想スタメンの記事」を読んで、アーセナルについての要点を日本語で 2〜3 行にまとめてください。
決まり:
- 記事の文をそのまま訳したり写したりしない。自分の言葉で短く（1 行 45 字まで・です・ます は使わず体言止めか「〜の見込み」）。
- 1 行が 20 字を超える時は、途中に読点「、」を 1 つ入れる（画面ではそこで折り返すため）。
- 書くのは、出られない選手（ケガ・出場停止・コンディション）、先発の読みの理由（入れ替え・復帰・起用の変化）、布陣の狙い、など。
- 前の試合や過去の試合の結果（勝ち負け・スコア・敗退・PK・引き分け）は絶対に書かない。結果を知らずにハイライトを見たい人のサイトです。
- 相手チームのことは書かない。アーセナルのことだけ。
- 選手名はこの表のカタカナに合わせる: {table}
返事は JSON だけ: {{"lines": ["…", "…"]}}

記事の題: {title}
記事（{'英語' if lang == 'en' else '日本語'}）:
{text[:7000]}
"""
    try:
        if os.environ.get("ANTHROPIC_API_KEY"):  # GitHub では取り込みと同じ API の頼み方
            import arsfetch
            j = arsfetch.claude_json(prompt)
            lines = (j or {}).get("lines", []) if isinstance(j, dict) else []
            if j is None:
                return None
        else:
            r = subprocess.run([exe, "-p", "--tools", "", "--output-format", "text"], input=prompt, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=300, cwd=os.path.join(ROOT, "_データ_自動"))
            m = re.search(r"\{.*\}", r.stdout or "", re.S)
            lines = json.loads(m.group(0)).get("lines", []) if m else []
    except Exception as ex:
        print("要点を作れなかった:", ex); return None
    keep = [x.strip() for x in lines if x and x.strip() and not SPOIL.search(x)]
    drop = [x for x in lines if x and SPOIL.search(x)]
    if drop:
        print("   結果の言葉が入った行を捨てた:", drop)
    return keep[:3] or None


def kana_norm(s):
    for a, b in (("ヴァ", "バ"), ("ヴィ", "ビ"), ("ヴェ", "ベ"), ("ヴォ", "ボ"), ("ヴ", "ブ"), ("・", ""), ("＝", ""), ("=", ""), (" ", "")):
        s = s.replace(a, b)
    return s


def next_opp():
    """data.js の NEXT から次の相手（英語・日本語）と、キックオフまでの日数"""
    src = open(DATA_JS, encoding="utf-8").read()
    nxt = json.loads(re.search(r"const NEXT = (.*?);\n", src, re.S).group(1))
    teams = json.loads(re.search(r"const TEAMS = (.*?);\n", src, re.S).group(1))
    k = nxt["a"] if nxt.get("h") == "arsenal" else nxt.get("h")
    t = teams.get(k) or {}
    days = (dt.datetime.strptime(nxt["d"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) - dt.datetime.now(dt.timezone.utc)).total_seconds() / 86400
    return t.get("en") or k, t.get("n") or k, days


def write_out(out):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    if len(sys.argv) > 2:
        opp_en, opp_ja, days = sys.argv[1], sys.argv[2], 0
    else:
        opp_en, opp_ja, days = next_opp()
    if days > DAYS_BEFORE or opp_en == "arsenal":
        write_out({"opp": {"en": opp_en, "ja": opp_ja}, "updated": dt.datetime.now(JST).strftime("%Y-%m-%d %H:%M"), "items": []})
        print(f"次の試合（{opp_ja}）まで {days:.1f} 日＝予想はまだ探さない"); return
    names = load_names()
    res = []
    cache = json.load(open(SUM_CACHE, encoding="utf-8")) if os.path.exists(SUM_CACHE) else {}
    icache = json.load(open(ITEM_CACHE, encoding="utf-8")) if os.path.exists(ITEM_CACHE) else {}
    for src, lang, url in FEEDS:
        try:
            its = items(url)
        except Exception as ex:
            print(f"{src}: RSS が取れない {ex}"); continue
        for it in its:
            t = it["title"]
            if lang == "ja":
                # 表記ゆれ（スラヴィア／スラビア・ノッティンガム・フォレスト／ノッティンガム）に負けないよう、最初の語をゆるく比べる
                ok = ("予想スタメン" in t or "予想フォーメーション" in t) and "アーセナル" in t and kana_norm(opp_ja.split("・")[0]) in kana_norm(t)
            else:
                ok = ("predicted" in t.lower()) and "arsenal" in t.lower() and opp_en.lower() in t.lower()
            if not ok:
                continue
            got = icache.get(it["link"])
            if got and got.get("skip"):
                continue
            if got and cache.get(it["link"]) is not None:
                xi, fm, pos, how, text = got["xi"], got["fm"], got["pos"], got["how"], ""
            else:
                try:
                    text = text_of(it["link"], lang)
                except Exception as ex:
                    print(f"{src}: 記事が読めない {ex}"); continue
                xi, fm, pos, how = extract_xi(text, lang, names)
                if how == "rough" and len(xi) < 11:
                    icache[it["link"]] = {"skip": 1}
                    json.dump(icache, open(ITEM_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
                    continue  # 相手側の記事など、アーセナルの 11 人が無い物は捨てる
                icache[it["link"]] = {"xi": xi, "fm": fm, "pos": pos, "how": how}
                json.dump(icache, open(ITEM_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
            summ = cache.get(it["link"])
            if summ is None:
                summ = summarize(t, text, names, lang)
                if summ:
                    cache[it["link"]] = summ
                    json.dump(cache, open(SUM_CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            res.append({"src": src, "lang": lang, "title": t, "link": it["link"], "pub": it["pub"], "fm": fm, "xi": xi, "pos": pos, "how": how, "sum": summ or []})
            print(f"[{src}] {t[:60]}")
            print(f"   {how}・布陣 {fm}・先発 {[names[no]['n'] for no in xi]}")
            for x in (summ or []):
                print("   要点:", x)
    out = {"opp": {"en": opp_en, "ja": opp_ja}, "updated": dt.datetime.now(JST).strftime("%Y-%m-%d %H:%M"), "items": res}
    write_out(out)
    # 試作の画面用（const YOSO = …）
    mock = os.path.join(ROOT, "試作_選手画面_20261101", "yoso.js")
    if os.path.isdir(os.path.dirname(mock)):
        with open(mock, "w", encoding="utf-8", newline="\n") as f:
            f.write("// 記者の予想（_道具/yoso.py が作る）\n")
            f.write("const YOSO = " + json.dumps(out, ensure_ascii=False) + ";\n")
    print("書いた", OUT, len(res), "本")


if __name__ == "__main__":
    main()
