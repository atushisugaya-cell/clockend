# -*- coding: utf-8 -*-
"""
アーセナル ファンサイト 自動取り込み（試作・2026/10/31）

取り先（すべて鍵なし）
  - ESPN の公開データ：日程・結果・スタメン・得点者・順位・個人成績・リーグ全体の予定と結果
  - YouTube の RSS：U-NEXT フットボール／WOWOWサッカー official／DAZN Japan（ハイライト）、アーセナル公式（縦動画）
  - Google ニュースの RSS（日本語・英語）、Arseblog の RSS
  - 日本語の名前・見出しの訳：手元の claude（Claude Code）に頼む。無ければ英語のまま

出力
  - 見本_20261030/data.js  … index.html が読む（TEAMS・MATCHES・GOALS・SHORTS・NEWS・LINEUP など）
  - _データ_自動/state.json … 初めて見た時刻・名前と訳の控え（会話が終わっても残る）
  - _データ_自動/raw/        … 直近に取った生データ（確認用・毎回上書き）
  - _ログ/自動取り込み_YYYYMMDD.txt … 何が・いつ届いたか

使い方
  python arsfetch.py            … 1 回だけ取り込んで data.js を書く
  （繰り返しは 見本_20261030/自動取り込み.py から呼ぶ）
"""
import json, os, re, sys, time, gzip, shutil, subprocess, datetime as dt
import urllib.request, urllib.error, urllib.parse
import xml.etree.ElementTree as ET

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SAMPLE = os.path.join(ROOT, "見本_20261030")
STATE_DIR = os.path.join(ROOT, "_データ_自動")
RAW_DIR = os.path.join(STATE_DIR, "raw")
LOG_DIR = os.path.join(ROOT, "_ログ")
STATE_FILE = os.path.join(STATE_DIR, "state.json")
CLASSICS_FILE = os.path.join(HERE, "classics.json")
NAMES_SEED = os.path.join(HERE, "names_seed.json")
DATA_JS = os.path.join(SAMPLE, "data.js")

ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/"
ESPN2 = "https://site.api.espn.com/apis/v2/sports/soccer/"
ARS_ID = "359"
LEAGUES = [("pl", "eng.1"), ("cl", "uefa.champions"), ("cup", "eng.league_cup"), ("cup", "eng.fa")]
COMP_JA = {"eng.1": "プレミアリーグ", "uefa.champions": "チャンピオンズリーグ", "eng.league_cup": "カラバオカップ", "eng.fa": "FAカップ"}
ROUND_JA = {"First Round": "1回戦", "Second Round": "2回戦", "Third Round": "3回戦", "Fourth Round": "ラウンド16", "Fifth Round": "5回戦",
            "Round of 32": "ラウンド32", "Round of 16": "ラウンド16", "Quarterfinals": "準々決勝", "Quarter-finals": "準々決勝",
            "Semifinals": "準決勝", "Semi-finals": "準決勝", "Final": "決勝", "Knockout Round Play-offs": "プレーオフ", "Knockout Round Playoffs": "プレーオフ"}
CHANNELS = {  # 記号: (名前, チャンネル ID, 色)
    "un": ("U-NEXT フットボール", "UCMjvvElkdLRTgcTKklAUkSw", "#111"),
    "ww": ("WOWOWサッカー official", "UCJQj2lbG_3w8UrncJd7JZXw", "#B4002A"),
    "dz": ("DAZN Japan", "UCoFLB_Gw_AoxUuuzKjXrc_Q", "#0d0d0d"),
}
ARSENAL_CH = "UCpryVRk_VDudG8SHXgWcG0w"
PREF_CH = {"pl": "un", "cl": "ww", "cup": "dz"}
JST = dt.timezone(dt.timedelta(hours=9))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"

# ESPN の表示名 → (記号, 日本語, 略, 色, 題に出る呼び方, しま模様)
TEAMS = {
    "Arsenal": ("arsenal", "アーセナル", "ARS", "#EF0107", ["アーセナル"]),
    "Everton": ("everton", "エヴァートン", "EVE", "#1B3C8C", ["エヴァートン", "エバートン"]),
    "Nottingham Forest": ("forest", "フォレスト", "NFO", "#8E1220", ["フォレスト"]),
    "Leeds United": ("leeds", "リーズ", "LEE", "#1D428A", ["リーズ"]),
    "Brighton & Hove Albion": ("brighton", "ブライトン", "BHA", "#0057B8", ["ブライトン"], 1),
    "Sunderland": ("sunderland", "サンダーランド", "SUN", "#C8102E", ["サンダーランド"], 1),
    "Chelsea": ("chelsea", "チェルシー", "CHE", "#034694", ["チェルシー"]),
    "Aston Villa": ("villa", "アストン・ヴィラ", "AVL", "#670E36", ["アストン・ヴィラ", "アストンヴィラ", "ヴィラ", "ビラ"]),
    "Coventry City": ("coventry", "コヴェントリー", "COV", "#3FA9D6", ["コヴェントリー", "コベントリー"]),
    "Fleetwood Town": ("fleetwood", "フリートウッド", "FLE", "#A0121C", ["フリートウッド"]),
    "Bayern Munich": ("bayern", "バイエルン", "FCB", "#B4002A", ["バイエルン"]),
    "Lille": ("lille", "リール", "LIL", "#24216A", ["リール"]),
    "Tottenham Hotspur": ("tottenham", "トッテナム", "TOT", "#132257", ["トッテナム", "スパーズ"]),
    "Crystal Palace": ("palace", "パレス", "CRY", "#1B458F", ["クリスタル・パレス", "クリスタルパレス", "パレス"]),
    "Manchester City": ("mancity", "マンチェスター・C", "MCI", "#5BA4D8", ["マンチェスター・シティ", "マンチェスター・C", "マン・C", "マンC", "シティ"]),
    "Liverpool": ("liverpool", "リヴァプール", "LIV", "#C8102E", ["リヴァプール", "リバプール"]),
    "Brentford": ("brentford", "ブレントフォード", "BRE", "#C8102E", ["ブレントフォード"]),
    "Fulham": ("fulham", "フラム", "FUL", "#1a1a1a", ["フラム"]),
    "Newcastle United": ("newcastle", "ニューカッスル", "NEW", "#241F20", ["ニューカッスル"]),
    "Hull City": ("hull", "ハル", "HUL", "#F5A12D", ["ハル・シティ", "ハルシティ", "ハル"]),
    "Manchester United": ("manutd", "マンチェスター・U", "MUN", "#DA291C", ["マンチェスター・ユナイテッド", "マンチェスター・U", "マン・U", "マンU", "ユナイテッド"]),
    "AFC Bournemouth": ("bournemouth", "ボーンマス", "BOU", "#B50E12", ["ボーンマス"]),
    "Ipswich Town": ("ipswich", "イプスウィッチ", "IPS", "#0E3A8C", ["イプスウィッチ", "イプスウィッチ・タウン"]),
    "West Ham United": ("westham", "ウェストハム", "WHU", "#7A263A", ["ウェストハム", "ウェスト・ハム"]),
    "Wolverhampton Wanderers": ("wolves", "ウルブス", "WOL", "#FDB913", ["ウルブス", "ウォルバーハンプトン"]),
    "Leicester City": ("leicester", "レスター", "LEI", "#003090", ["レスター"]),
    "Southampton": ("southampton", "サウサンプトン", "SOU", "#D71920", ["サウサンプトン"]),
    "Burnley": ("burnley", "バーンリー", "BUR", "#6C1D45", ["バーンリー"]),
    "Napoli": ("napoli", "ナポリ", "NAP", "#12A0D7", ["ナポリ"]),
    "Slavia Prague": ("slavia", "スラヴィア・プラハ", "SLP", "#C8102E", ["スラヴィア", "スラビア"]),
    "Borussia Dortmund": ("dortmund", "ドルトムント", "BVB", "#D9B800", ["ドルトムント"]),
    "Real Madrid": ("realmadrid", "レアル・マドリー", "RMA", "#1C2B6B", ["レアル・マドリー", "レアル・マドリード", "R・マドリード", "レアル"]),
    "Real Betis": ("betis", "ベティス", "BET", "#0BB363", ["ベティス"]),
    "Sabah FK": ("sabah", "サバフ", "SAB", "#1D3A8A", ["サバフ", "サバー"]),
}
EXCLUDE_WORDS = ["女子", "ウィメンズ", "WSL", "U-17", "U-19", "U-21", "U-23", "U17", "U19", "U21", "U23", "全ゴール集", "プレー集", "プレビュー",
                 "見どころ", "予告", "ランキング", "ベストゴール", "スーパーゴール集", "名場面", "今週の", "振り返り", "ダイジェスト集", "ユース", "レジェンド"]
NEWS_JUNK = ["ガンダム", "アーセナルベース", "ARSENAL BASE", "Arsenal Base", "vietnam", "ベトナム語", "ASB"]
NEWS_JUNK_SRC = ["vietnam.vn", "vn.", "newsbreak", "msn.com"]
NAT_JA = {"England": "イングランド", "Spain": "スペイン", "Norway": "ノルウェー", "Brazil": "ブラジル", "Sweden": "スウェーデン", "Italy": "イタリア",
          "Netherlands": "オランダ", "Ecuador": "エクアドル", "Germany": "ドイツ", "Greece": "ギリシャ", "Ireland": "アイルランド", "Republic of Ireland": "アイルランド",
          "France": "フランス", "Belgium": "ベルギー", "Portugal": "ポルトガル", "Japan": "日本", "Ghana": "ガーナ", "Ukraine": "ウクライナ", "Poland": "ポーランド",
          "Scotland": "スコットランド", "Wales": "ウェールズ", "Denmark": "デンマーク", "Argentina": "アルゼンチン", "Uruguay": "ウルグアイ", "Colombia": "コロンビア",
          "Nigeria": "ナイジェリア", "Senegal": "セネガル", "Egypt": "エジプト", "USA": "アメリカ", "United States": "アメリカ", "Croatia": "クロアチア",
          "Switzerland": "スイス", "Austria": "オーストリア", "Czech Republic": "チェコ", "Czechia": "チェコ", "Hungary": "ハンガリー", "Serbia": "セルビア",
          "Morocco": "モロッコ", "Ivory Coast": "コートジボワール", "Côte d'Ivoire": "コートジボワール", "Cameroon": "カメルーン", "Mali": "マリ", "Turkey": "トルコ",
          "Türkiye": "トルコ", "Slovakia": "スロバキア", "Slovenia": "スロベニア", "Australia": "オーストラリア", "South Korea": "韓国", "Korea Republic": "韓国",
          "Canada": "カナダ", "Mexico": "メキシコ", "Chile": "チリ", "Paraguay": "パラグアイ", "Jamaica": "ジャマイカ", "Northern Ireland": "北アイルランド",
          "Algeria": "アルジェリア", "DR Congo": "コンゴ民主共和国", "Congo DR": "コンゴ民主共和国", "Guinea": "ギニア", "Gabon": "ガボン", "Burkina Faso": "ブルキナファソ",
          "Israel": "イスラエル", "Iran": "イラン", "Georgia": "ジョージア", "Romania": "ルーマニア", "Bosnia and Herzegovina": "ボスニア・ヘルツェゴビナ",
          "Albania": "アルバニア", "Kosovo": "コソボ", "North Macedonia": "北マケドニア", "Finland": "フィンランド", "Iceland": "アイスランド",
          "New Zealand": "ニュージーランド", "South Africa": "南アフリカ", "Tunisia": "チュニジア", "Angola": "アンゴラ", "Cape Verde": "カーボベルデ",
          "Venezuela": "ベネズエラ", "Peru": "ペルー", "Costa Rica": "コスタリカ", "Honduras": "ホンジュラス", "Panama": "パナマ", "Iraq": "イラク",
          "Saudi Arabia": "サウジアラビア", "Qatar": "カタール", "Uzbekistan": "ウズベキスタン", "China": "中国", "Indonesia": "インドネシア", "Philippines": "フィリピン",
          "Azerbaijan": "アゼルバイジャン", "Armenia": "アルメニア", "Belarus": "ベラルーシ", "Bulgaria": "ブルガリア", "Montenegro": "モンテネグロ",
          "Cyprus": "キプロス", "Luxembourg": "ルクセンブルク", "Zimbabwe": "ジンバブエ", "Zambia": "ザンビア", "Curaçao": "キュラソー", "Suriname": "スリナム"}
VENUE_JA = {"Emirates Stadium": "エミレーツ・スタジアム", "Anfield": "アンフィールド", "Old Trafford": "オールド・トラフォード", "Etihad Stadium": "エティハド・スタジアム",
            "Stamford Bridge": "スタンフォード・ブリッジ", "Tottenham Hotspur Stadium": "トッテナム・ホットスパー・スタジアム", "St. James' Park": "セント・ジェームズ・パーク",
            "Villa Park": "ヴィラ・パーク", "London Stadium": "ロンドン・スタジアム", "Goodison Park": "グディソン・パーク", "Hill Dickinson Stadium": "ヒル・ディキンソン・スタジアム",
            "Elland Road": "エランド・ロード", "Craven Cottage": "クレイヴン・コテージ", "Selhurst Park": "セルハースト・パーク", "Gtech Community Stadium": "Gテック・コミュニティ・スタジアム",
            "Vitality Stadium": "ヴァイタリティ・スタジアム", "The City Ground": "シティ・グラウンド", "City Ground": "シティ・グラウンド", "Stadium of Light": "スタジアム・オブ・ライト",
            "American Express Stadium": "アメックス・スタジアム", "Amex Stadium": "アメックス・スタジアム", "Coventry Building Society Arena": "コヴェントリー・ビルディング・ソサエティ・アリーナ",
            "MKM Stadium": "MKM スタジアム", "Portman Road": "ポートマン・ロード", "Allianz Arena": "アリアンツ・アレーナ", "Signal Iduna Park": "ジグナル・イドゥナ・パルク",
            "Santiago Bernabéu": "サンティアゴ・ベルナベウ", "Estadio Santiago Bernabéu": "サンティアゴ・ベルナベウ", "Fortuna Arena": "エデン・アレーナ", "Eden Arena": "エデン・アレーナ",
            "Estadio Benito Villamarín": "ベニート・ビジャマリン", "Highbury Stadium": "ハイベリー・スタジアム", "Stadio Diego Armando Maradona": "スタディオ・ディエゴ・アルマンド・マラドーナ"}

_log_lines = []
_t_run = None


# ---------------------------------------------------------------- 小道具
def now():
    return dt.datetime.now(dt.timezone.utc)


def jst_str(t=None):
    t = t or now()
    return t.astimezone(JST).strftime("%m/%d %H:%M")


def log(msg, star=False):
    line = f"{dt.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')} {'★ ' if star else ''}{msg}"
    _log_lines.append(line)
    print(line, flush=True)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, f"自動取り込み_{dt.datetime.now(JST).strftime('%Y%m%d')}.txt"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def fetch(url, timeout=30, retries=2, headers=None):
    h = {"User-Agent": UA, "Accept-Encoding": "gzip", "Accept-Language": "ja,en"}
    if headers:
        h.update(headers)
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if data[:2] == b"\x1f\x8b":
                data = gzip.decompress(data)
            return data
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def jget(url, raw_name=None):
    data = fetch(url)
    if raw_name:
        try:
            os.makedirs(RAW_DIR, exist_ok=True)
            open(os.path.join(RAW_DIR, raw_name), "wb").write(data)
        except Exception:
            pass
    return json.loads(data)


def iso(s):
    """ESPN の '2026-11-01T16:30Z' を '2026-11-01T16:30:00Z' に"""
    if not s:
        return s
    s = s.replace("+00:00", "Z")
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z$", s):
        s = s[:-1] + ":00Z"
    return s


def parse_iso(s):
    s = iso(s)
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def parse_rfc822(s):
    try:
        from email.utils import parsedate_to_datetime
        d = parsedate_to_datetime(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.astimezone(dt.timezone.utc)
    except Exception:
        return None


def to_iso(d):
    return d.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt_views(n):
    try:
        n = int(n)
    except Exception:
        return ""
    if n >= 10000:
        return f"{n // 10000}万"
    return f"{n:,}"


def load_state():
    st = {"first_seen": {}, "names": {}, "tr": {}, "shorts": {}, "videos": {}, "runs": 0, "notes": []}
    try:
        st.update(json.load(open(STATE_FILE, encoding="utf-8")))
    except Exception:
        pass
    try:
        seed = json.load(open(NAMES_SEED, encoding="utf-8"))
        for k, v in seed.items():
            st["names"].setdefault(k, v)
    except Exception:
        pass
    try:  # 見本 v1 に手で入れていた動画（RSS からはもう消えている分）
        vs = json.load(open(os.path.join(HERE, "videos_seed.json"), encoding="utf-8"))
        for k, v in vs.items():
            st["videos"].setdefault(k, v)
            st["first_seen"].setdefault(k, v.get("fs"))
    except Exception:
        pass
    return st


def save_state(st):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_FILE)


# ---------------------------------------------------------------- チーム
_team_cache = {}


def team(name, abbr=None):
    """ESPN の表示名 → 記号。未登録のチームは英語のまま登録して知らせる"""
    if name in TEAMS:
        return TEAMS[name][0]
    if name not in _team_cache:
        key = re.sub(r"[^a-z0-9]", "", name.lower())[:12] or "team"
        _team_cache[name] = key
        TEAMS[name] = (key, name, (abbr or name[:3]).upper(), "#555", [])
        log(f"未登録のチーム（英語のまま載せます）: {name}")
    return _team_cache[name]


def teams_js():
    out = {}
    for name, t in TEAMS.items():
        d = {"n": t[1], "s": t[2], "c": t[3], "en": name}
        if len(t) > 5 and t[5]:
            d["sh"] = 1
        out[t[0]] = d
    return out


def aliases(key):
    for name, t in TEAMS.items():
        if t[0] == key:
            return list(t[4]) + [name]
    return []


# ---------------------------------------------------------------- claude（名前と訳）
# GitHub Actions では ANTHROPIC_API_KEY（リポジトリの Secrets）で API に頼む。手元の PC は claude（Claude Code）に頼む
CLAUDE_MODEL = os.environ.get("ARS_MODEL") or "claude-opus-5-5"


def claude_api_text(prompt):
    import anthropic
    r = anthropic.Anthropic().beta.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
    )
    if r.stop_reason == "refusal":
        raise RuntimeError(f"断られた: {getattr(r.stop_details, 'category', None)}")
    return "".join(b.text for b in r.content if b.type == "text")


def claude_json(prompt, timeout=240):
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            out = claude_api_text(prompt).strip()
            m = re.search(r"\{.*\}", out, re.S)
            if not m:
                log(f"API の返事に JSON が無い: {out[:120]}")
                return None
            return json.loads(m.group(0))
        except Exception as e:
            log(f"API に頼めなかった: {type(e).__name__}: {str(e)[:200]}")
            return None
    exe = shutil.which("claude")
    if not exe:
        log("claude が見つからないので、訳は英語のままにします")
        return None
    try:
        r = subprocess.run([exe, "-p", "--tools", "", "--output-format", "text"], input=prompt, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=STATE_DIR)
        out = (r.stdout or "").strip()
        m = re.search(r"\{.*\}", out, re.S)
        if not m:
            log(f"claude の返事に JSON が無い: {out[:120]}")
            return None
        return json.loads(m.group(0))
    except Exception as e:
        log(f"claude に頼めなかった: {e}")
        return None


def ensure_names(st, names):
    """英語の選手名の一覧 → st['names'] に [姓, フルネーム] を足す"""
    need = sorted({n for n in names if n and n not in st["names"]})
    if not need:
        return
    log(f"名前の日本語表記を claude に頼む: {len(need)} 人")
    prompt = ("次の英語のサッカー選手名を、日本のサッカー報道で一般的なカタカナ表記にしてください。"
              "JSON だけを返し、説明やコードブロックは不要です。形式は {\"English Name\": [\"姓だけ\", \"フルネーム\"]}。"
              "複合姓の区切りは「＝」（例: ルイス＝スケリー）、名と姓の間は「・」。\n名前: " + ", ".join(need))
    res = claude_json(prompt)
    ok = 0
    if isinstance(res, dict):
        for k, v in res.items():
            if k in need and isinstance(v, list) and len(v) >= 2:
                st["names"][k] = [str(v[0]), str(v[1])]
                ok += 1
    if isinstance(res, dict):  # 頼めなかった時（鍵が無い・claude が無い）は控えず、次の回に聞き直す
        for n in need:
            st["names"].setdefault(n, [n, n])
    log(f"名前の表記: {ok}/{len(need)} 人分を受け取った")


def ja_name(st, en, full=False):
    v = st["names"].get(en)
    if not v:
        return en
    return v[1] if full else v[0]


# ---------------------------------------------------------------- ESPN
def score_of(x):
    sc = x.get("score")
    if isinstance(sc, dict):
        sc = sc.get("value", sc.get("displayValue"))
    try:
        return int(float(sc))
    except Exception:
        return None


def espn_events(st):
    """アーセナルの全試合（今季・終わった分と予定）"""
    evs = {}
    for k, lg in LEAGUES:
        for q in ("", "?fixture=true"):
            try:
                j = jget(f"{ESPN}{lg}/teams/{ARS_ID}/schedule{q}", f"sched_{lg}{'_fix' if q else ''}.json")
            except Exception as e:
                if lg != "eng.fa":
                    log(f"ESPN の日程が取れない {lg}{q}: {e}")
                continue
            for e in j.get("events", []):
                c = e["competitions"][0]
                comps = c["competitors"]
                home = next(x for x in comps if x["homeAway"] == "home")
                away = next(x for x in comps if x["homeAway"] == "away")
                stt = c.get("status", {}).get("type", {})
                notes = c.get("notes") or []
                evs[e["id"]] = {
                    "eid": e["id"], "k": k, "lg": lg, "d": iso(e["date"]),
                    "hname": home["team"]["displayName"], "aname": away["team"]["displayName"],
                    "h": team(home["team"]["displayName"], home["team"].get("abbreviation")),
                    "a": team(away["team"]["displayName"], away["team"].get("abbreviation")),
                    "hs": score_of(home), "as": score_of(away),
                    "hwin": home.get("winner"), "awin": away.get("winner"),
                    "state": stt.get("state"), "completed": bool(stt.get("completed")), "detail": stt.get("shortDetail"),
                    "round": (e.get("seasonType") or {}).get("name"), "note": (notes[0].get("headline") if notes else None),
                    "venue": (c.get("venue") or {}).get("fullName"),
                }
    out = sorted(evs.values(), key=lambda x: x["d"])
    # 節の番号（リーグは何試合目か）
    n = {"eng.1": 0, "ucl": 0}
    for e in out:
        if e["lg"] == "eng.1":
            n["eng.1"] += 1
            e["rn"] = n["eng.1"]
            e["lab"] = f"プレミアリーグ 第{e['rn']}節"
        elif e["lg"] == "uefa.champions":
            if (e["round"] or "").startswith("League"):
                n["ucl"] += 1
                e["rn"] = n["ucl"]
                e["lab"] = f"チャンピオンズリーグ 第{e['rn']}節"
            else:
                e["lab"] = "チャンピオンズリーグ " + ROUND_JA.get(e["round"] or "", e["round"] or "")
        else:
            e["lab"] = COMP_JA.get(e["lg"], e["lg"]) + " " + ROUND_JA.get(e["round"] or "", e["round"] or "")
        e["lab"] = e["lab"].strip()
        opp = e["a"] if e["h"] == "arsenal" else e["h"]
        e["id"] = f"{opp}-{e['d'][5:7]}{e['d'][8:10]}"
        # アーセナルから見た結果
        if e["completed"]:
            mine, theirs = (e["hs"], e["as"]) if e["h"] == "arsenal" else (e["as"], e["hs"])
            if mine is None or theirs is None:
                e["r"] = "D"
            else:
                e["r"] = "W" if mine > theirs else ("L" if mine < theirs else "D")
            m = re.search(r"win (\d+)[-–](\d+) on penalties", e["note"] or "")
            if m:
                winner_is_ars = (e["note"] or "").startswith("Arsenal")
                e["pk"] = f"{m.group(1)}-{m.group(2)}"
                e["r"] = "W" if winner_is_ars else "L"
    return out


def espn_summary(e, force=False):
    fn = os.path.join(STATE_DIR, "summary", f"{e['eid']}.json")
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    fresh = os.path.exists(fn) and (now() - dt.datetime.fromtimestamp(os.path.getmtime(fn), dt.timezone.utc)) < dt.timedelta(hours=12)
    ended_recently = (now() - parse_iso(e["d"])) < dt.timedelta(hours=8)
    if os.path.exists(fn) and fresh and not ended_recently and not force:
        return json.load(open(fn, encoding="utf-8"))
    try:
        j = jget(f"{ESPN}{e['lg']}/summary?event={e['eid']}")
        json.dump(j, open(fn, "w", encoding="utf-8"), ensure_ascii=False)
        return j
    except Exception as ex:
        log(f"試合の中身が取れない {e['id']}: {ex}")
        if os.path.exists(fn):
            return json.load(open(fn, encoding="utf-8"))
        return None


def goals_from_summary(st, e, summ, jersey_of):
    goals = []
    for k in summ.get("keyEvents", []) or []:
        if not k.get("scoringPlay") or k.get("shootout"):
            continue
        text = (k.get("text") or "")
        parts = [p.get("athlete", {}).get("displayName") for p in k.get("participants", [])]
        tname = (k.get("team") or {}).get("displayName")
        tkey = team(tname) if tname else None
        g = {"t": re.sub(r"'", "", (k.get("clock") or {}).get("displayValue", "")), "team": tkey}
        if parts:
            g["s"] = ja_name(st, parts[0])
            if tkey == "arsenal" and jersey_of.get(parts[0]):
                g["sno"] = jersey_of[parts[0]]
            g["_s_en"] = parts[0]
        if len(parts) > 1 and parts[1]:
            g["a"] = ja_name(st, parts[1])
            if tkey == "arsenal" and jersey_of.get(parts[1]):
                g["ano"] = jersey_of[parts[1]]
            g["_a_en"] = parts[1]
        low = text.lower()
        if "penalty" in low:
            g["pen"] = 1
        if "own goal" in low:
            g["og"] = 1
            g["s"] = (g.get("s") or "") + "（OG）"
        if "header" in low or "Header" in (k.get("type") or {}).get("text", ""):
            g["hd"] = 1
        if "corner" in low:
            g["ck"] = 1
        if "free kick" in low:
            g["fk"] = 1
        goals.append(g)
    return goals


def lineup_from_summary(st, e, summ, roster):
    """アーセナルのスタメン・控え・この試合の活躍"""
    r = next((r for r in summ.get("rosters", []) if r["team"].get("id") == ARS_ID or r["team"].get("displayName") == "Arsenal"), None)
    if not r:
        return None
    fm = r.get("formation") or "4-2-3-1"
    starters = [p for p in r.get("roster", []) if p.get("starter")]
    bench = [p for p in r.get("roster", []) if not p.get("starter")]
    if len(starters) != 11:
        log(f"スタメンが 11 人でない（{len(starters)} 人）: {e['id']}")

    def depth(ab):
        a = (ab or "").upper()
        if a == "G":
            return 0
        if a.startswith("AM"):
            return 4
        if a in ("F", "CF", "ST", "S", "F-L", "F-R", "LW", "RW", "FW", "LF", "RF"):
            return 5
        if a.startswith("DM"):
            return 2
        if a.startswith("M") or a.startswith("CM") or a in ("LM", "RM"):
            return 3
        return 1

    def side(ab):
        a = (ab or "").upper()
        if a in ("LB", "LWB", "LM", "LW", "LF"):
            return 0
        if a.endswith("-L"):
            return 1
        if a in ("RB", "RWB", "RM", "RW", "RF"):
            return 4
        if a.endswith("-R"):
            return 3
        return 2

    gk = [p for p in starters if (p.get("position") or {}).get("abbreviation") == "G"]
    field = [p for p in starters if p not in gk]
    field.sort(key=lambda p: (depth((p.get("position") or {}).get("abbreviation")), side((p.get("position") or {}).get("abbreviation")), p.get("formationPlace") or 99))
    rows = [int(x) for x in re.findall(r"\d+", fm)]
    if sum(rows) != len(field):
        groups = {}
        for p in field:
            groups.setdefault(min(depth((p.get("position") or {}).get("abbreviation")), 5), []).append(p)
        rows = [len(groups[k]) for k in sorted(groups)]
    YS = {1: [40], 2: [70, 25], 3: [72, 42, 14], 4: [72, 52, 32, 12], 5: [74, 58, 42, 27, 12], 6: [76, 62, 48, 35, 23, 11]}
    XS = {1: [50], 2: [34, 66], 3: [17, 50, 83], 4: [13, 37, 63, 87], 5: [10, 30, 50, 70, 90], 6: [8, 25, 42, 58, 75, 92]}
    ys = YS.get(len(rows), [72, 52, 32, 12][:len(rows)])
    placed, i = [], 0
    for ri, cnt in enumerate(rows):
        row = field[i:i + cnt]
        i += cnt
        row.sort(key=lambda p: (side((p.get("position") or {}).get("abbreviation")), p.get("formationPlace") or 99))
        xs = XS.get(len(row), [50] * len(row))
        for xi_, p in enumerate(row):
            placed.append((p, xs[xi_], ys[ri]))
    for p in gk:
        placed.append((p, 50, 90))

    stats_of = {a["id"]: a for a in roster.get("athletes", [])}

    def pinfo(p, x=None, y=None):
        a = p["athlete"]
        ra = stats_of.get(a["id"], {})
        stt = {}
        for c in ((ra.get("statistics") or {}).get("splits") or {}).get("categories", []):
            for s in c.get("stats", []):
                stt[s["name"]] = s.get("value", s.get("displayValue"))
        pos = (ra.get("position") or p.get("position") or {}).get("abbreviation", "")
        pg = {"G": "GK", "D": "DF", "M": "MF", "F": "FW"}.get(pos[:1].upper(), pos)
        d = {"no": int(p.get("jersey") or ra.get("jersey") or 0), "n": ja_name(st, a["displayName"]), "f": ja_name(st, a["displayName"], full=True),
             "p": pg, "age": ra.get("age"), "nat": NAT_JA.get(ra.get("citizenship") or "", ra.get("citizenship") or ""),
             "st": [int(stt.get("appearances") or 0), int(stt.get("totalGoals") or 0), int(stt.get("goalAssists") or 0)], "en": a["displayName"]}
        if x is not None:
            d["x"], d["y"] = x, y
        if pos == "G":
            d["gk"] = 1
        if p.get("subbedIn"):
            d["in"] = 1
        return d

    xi = [pinfo(p, x, y) for p, x, y in placed]
    # 前から並べる（見た目の順）
    xi.sort(key=lambda d: (d["y"], d["x"]))
    bn = [pinfo(p) for p in bench]
    bn.sort(key=lambda d: (0 if d.get("in") else 1, d["no"]))
    allp = xi + bn
    mx = [max([p["st"][0] for p in allp] + [1]), max([p["st"][1] for p in allp] + [1]), max([p["st"][2] for p in allp] + [1])]
    return {"match": e["id"], "fm": fm, "xi": xi, "bench": bn, "max": mx}


def lineup_mini(lu):
    """シアターの上に横向きで出す分（先発 11 人だけ・結果は含めない）"""
    return {"fm": lu["fm"], "xi": [dict({"no": p["no"], "n": p["n"], "x": p["x"], "y": p["y"]}, **({"gk": 1} if p.get("gk") else {})) for p in lu["xi"]]}


def attach_events(lineup, goals):
    byname = {}
    for p in lineup["xi"] + lineup["bench"]:
        byname[p["en"]] = p
    for g in goals:
        if g.get("team") != "arsenal":
            continue
        t = g["t"] + "分"
        s = byname.get(g.get("_s_en"))
        if s:
            d = "PKでゴール" if g.get("pen") else ("ヘディングでゴール" if g.get("hd") else ("コーナーキックからゴール" if g.get("ck") else ("フリーキックでゴール" if g.get("fk") else "ゴール")))
            s.setdefault("ev", []).append({"k": "g", "t": t, "d": d})
        a = byname.get(g.get("_a_en"))
        if a and s:
            a.setdefault("ev", []).append({"k": "as", "t": t, "d": f"{s['n']}のゴールをアシスト"})


def espn_standings():
    j = jget(f"{ESPN2}eng.1/standings", "standings.json")
    rows = []
    for en in j["children"][0]["standings"]["entries"]:
        s = {x["name"]: x for x in en["stats"]}
        g = lambda k: int(float(s[k]["value"])) if k in s and s[k].get("value") is not None else int(s[k]["displayValue"]) if k in s else 0
        gd = g("pointDifferential")
        rows.append([team(en["team"]["displayName"], en["team"].get("abbreviation")), g("gamesPlayed"), g("wins"), g("ties"), g("losses"), (f"+{gd}" if gd > 0 else str(gd)), g("points"), g("rank")])
    rows.sort(key=lambda r: r[7])
    return [r[:7] for r in rows]


def espn_leaders(st, lg="eng.1", raw="stats.json", n=9):
    """得点王・アシスト王（ESPN の statistics）。lg＝eng.1（プレミア）／uefa.champions（CL）／eng.league_cup（カラバオ杯）（11/4 PC 版の右の欄で大会を切り替える）"""
    j = jget(f"{ESPN}{lg}/statistics", raw)
    cats = {c["name"]: c for c in j.get("stats", [])}
    out = {}
    for key, cname in (("SCORERS", "goalsLeaders"), ("ASSISTS", "assistsLeaders")):
        rows = []
        for L in (cats.get(cname) or {}).get("leaders", [])[:n]:
            a = L["athlete"]
            apps = 0
            for s in (a.get("statistics") or []):
                if s.get("name") == "appearances":
                    apps = int(float(s.get("value") or s.get("displayValue") or 0))
            tn = (a.get("team") or {}).get("displayName") or ""
            rows.append([a["displayName"], team(tn, (a.get("team") or {}).get("abbreviation")) if tn else "arsenal", int(float(L.get("value") or 0)), apps])
        out[key] = rows
    return out


def pl_round_window(d):
    """その試合が入る節の日付の範囲（金〜月／火〜木）"""
    wd = d.weekday()  # 月=0
    if wd in (4, 5, 6, 0):
        start = d - dt.timedelta(days=(wd - 4) % 7)
        days = 4
    else:
        start = d - dt.timedelta(days=wd - 1)
        days = 3
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    return [start + dt.timedelta(days=i) for i in range(days)]


def espn_round(e, ars_events):
    """アーセナルの試合 e が入る節の、リーグ全体の試合"""
    d = parse_iso(e["d"])
    out, seen = [], set()
    for day in pl_round_window(d):
        try:
            j = jget(f"{ESPN}eng.1/scoreboard?dates={day.strftime('%Y%m%d')}", f"sb_{day.strftime('%Y%m%d')}.json")
        except Exception as ex:
            log(f"節の試合が取れない {day.date()}: {ex}")
            continue
        for ev in j.get("events", []):
            if ev["id"] in seen:
                continue
            seen.add(ev["id"])
            c = ev["competitions"][0]
            home = next(x for x in c["competitors"] if x["homeAway"] == "home")
            away = next(x for x in c["competitors"] if x["homeAway"] == "away")
            stt = c.get("status", {}).get("type", {})
            f = {"d": iso(ev["date"]), "h": team(home["team"]["displayName"], home["team"].get("abbreviation")), "a": team(away["team"]["displayName"], away["team"].get("abbreviation"))}
            if stt.get("completed"):
                f["hs"], f["as"] = score_of(home), score_of(away)
            elif stt.get("state") == "in":
                f["live"] = 1
                f["hs"], f["as"] = score_of(home), score_of(away)
            if "arsenal" in (f["h"], f["a"]):
                me = next((x for x in ars_events if x["eid"] == ev["id"]), None)
                if me:
                    f["m"] = me["id"]
            out.append(f)
    out.sort(key=lambda f: f["d"])
    return out


# ---------------------------------------------------------------- YouTube
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "media": "http://search.yahoo.com/mrss/"}


# GitHub のサーバーからは YouTube の RSS が 404 になる（11/2 の試し）＝ARS_SKIP_RSS=1 で取りに行かず、チャンネルのページだけで拾う
SKIP_RSS = os.environ.get("ARS_SKIP_RSS") == "1"


def yt_feed(cid):
    if SKIP_RSS:
        raise RuntimeError("RSS は使わない設定")
    data = fetch(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}")
    root = ET.fromstring(data)
    out = []
    for e in root.findall("a:entry", NS):
        stt = e.find("media:group/media:community/media:statistics", NS)
        out.append({"v": e.findtext("yt:videoId", namespaces=NS), "t": e.findtext("a:title", namespaces=NS) or "",
                    "p": iso(e.findtext("a:published", namespaces=NS) or ""), "views": int(stt.get("views")) if stt is not None and stt.get("views") else None})
    return out


def yt_channel_scrape(cid):
    """RSS は新しい 15 本しか出ないので、チャンネルの動画一覧（約 30 本）も見る。壊れたら黙って空"""
    try:
        html = fetch(f"https://www.youtube.com/channel/{cid}/videos", headers={"Cookie": "CONSENT=YES+1; SOCS=CAI"}).decode("utf-8", "replace")
        j = None
        dec = json.JSONDecoder()
        pos = 0
        while j is None:
            i = html.find("ytInitialData", pos)
            if i < 0:
                break
            k = html.find("{", i)
            try:
                j, _ = dec.raw_decode(html[k:k + 3000000])
            except Exception:
                pos = i + 13
        if j is None:
            log("チャンネルの一覧の形が読めない（RSS だけで続ける）")
            return []
        out = []

        def views_of(txt):
            mm = re.search(r"([\d.,]+)\s*(万|億)?\s*(回|views)", txt.replace(",", ""))
            if not mm:
                return None
            try:
                return int(float(mm.group(1)) * (10000 if mm.group(2) == "万" else 100000000 if mm.group(2) == "億" else 1))
            except Exception:
                return None

        def texts(o, acc):
            if isinstance(o, dict):
                if "content" in o and isinstance(o["content"], str):
                    acc.append(o["content"])
                if "simpleText" in o and isinstance(o["simpleText"], str):
                    acc.append(o["simpleText"])
                if "accessibilityLabel" in o and isinstance(o["accessibilityLabel"], str):
                    acc.append(o["accessibilityLabel"])
                for v in o.values():
                    texts(v, acc)
            elif isinstance(o, list):
                for v in o:
                    texts(v, acc)
            return acc

        def walk(o):
            if isinstance(o, dict):
                if "videoRenderer" in o:  # 古い形
                    vr = o["videoRenderer"]
                    title = "".join(r.get("text", "") for r in (vr.get("title") or {}).get("runs", []))
                    out.append({"v": vr.get("videoId"), "t": title, "p": None, "views": views_of((vr.get("viewCountText") or {}).get("simpleText") or ""),
                                "rel": (vr.get("publishedTimeText") or {}).get("simpleText")})
                elif "lockupViewModel" in o:  # 今の形
                    lv = o["lockupViewModel"]
                    vid = lv.get("contentId")
                    md = (lv.get("metadata") or {}).get("lockupMetadataViewModel") or {}
                    title = ((md.get("title") or {}).get("content")) or ""
                    tx = texts(md.get("metadata"), [])
                    views = next((views_of(t) for t in tx if views_of(t) is not None), None)
                    rel = next((t for t in tx if re.search(r"前$|ago$", t.strip())), None)
                    if vid and title:
                        out.append({"v": vid, "t": title, "p": None, "views": views, "rel": rel})
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(j)
        return out
    except Exception as ex:
        log(f"チャンネルの一覧が読めない（RSS だけで続ける）: {ex}")
        return []


def yt_channel_shorts(cid):
    """チャンネルの「ショート」のタブ（shortsLockupViewModel）から縦動画を拾う。RSS が 404 の時の代わり。公開時刻は無い"""
    try:
        html = fetch(f"https://www.youtube.com/channel/{cid}/shorts", headers={"Cookie": "CONSENT=YES+1; SOCS=CAI"}).decode("utf-8", "replace")
        dec = json.JSONDecoder()
        pos, j = 0, None
        while j is None:
            i = html.find("ytInitialData", pos)
            if i < 0:
                break
            k = html.find("{", i)
            try:
                j, _ = dec.raw_decode(html[k:k + 4000000])
            except Exception:
                pos = i + 13
        if j is None:
            return []

        def find_key(o, key):
            if isinstance(o, dict):
                if key in o:
                    return o[key]
                for v in o.values():
                    r = find_key(v, key)
                    if r is not None:
                        return r
            elif isinstance(o, list):
                for v in o:
                    r = find_key(v, key)
                    if r is not None:
                        return r
            return None

        out = []

        def walk(o):
            if isinstance(o, dict):
                if "shortsLockupViewModel" in o:
                    sl = o["shortsLockupViewModel"]
                    vid = find_key(sl.get("onTap"), "videoId")
                    om = sl.get("overlayMetadata") or {}
                    title = (om.get("primaryText") or {}).get("content") or ""
                    vt = (om.get("secondaryText") or {}).get("content") or ""
                    mm = re.search(r"([\d.,]+)\s*(万|億)?", vt.replace(",", ""))
                    views = None
                    if mm:
                        try:
                            views = int(float(mm.group(1)) * (10000 if mm.group(2) == "万" else 100000000 if mm.group(2) == "億" else 1))
                        except Exception:
                            views = None
                    if vid and title:
                        out.append({"v": vid, "t": title, "p": None, "views": views})
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(j)
        return out
    except Exception as ex:
        log(f"ショートの一覧が読めない: {ex}")
        return []


def rel_to_time(rel):
    """「3 時間前」などを UTC のおおよその時刻に"""
    if not rel:
        return None
    m = re.search(r"(\d+)\s*(分|時間|日|週間|か月|ヶ月|年|minute|hour|day|week|month|year)", rel)
    if not m:
        return None
    n = int(m.group(1))
    u = m.group(2)
    sec = {"分": 60, "minute": 60, "時間": 3600, "hour": 3600, "日": 86400, "day": 86400, "週間": 604800, "week": 604800,
           "か月": 2592000, "ヶ月": 2592000, "month": 2592000, "年": 31536000, "year": 31536000}.get(u, 86400)
    return now() - dt.timedelta(seconds=n * sec)


def collect_videos(st):
    """3 社の動画を集めて state['videos'] に足す（初めて見た時刻つき）"""
    newly = []
    for ch, (nm, cid, _c) in CHANNELS.items():
        items = []
        try:
            items = yt_feed(cid)
        except Exception as ex:
            if not SKIP_RSS:
                log(f"{nm} の RSS が取れない: {ex}")
        extra = yt_channel_scrape(cid)
        seen = {x["v"] for x in items}
        for x in extra:
            if x["v"] and x["v"] not in seen:
                seen.add(x["v"])
                items.append(x)
        for x in items:
            if not x.get("v"):
                continue
            rec = st["videos"].get(x["v"]) or {}
            if not rec:
                rec = {"ch": ch, "t": x["t"], "p": x.get("p") or (to_iso(rel_to_time(x.get("rel"))) if x.get("rel") else None), "views": x.get("views"), "fs": to_iso(now())}
                st["videos"][x["v"]] = rec
                st["first_seen"][x["v"]] = rec["fs"]
                if "アーセナル" in x["t"]:
                    newly.append((ch, x["v"], x["t"], rec["p"]))
            else:
                if x.get("views") is not None:
                    rec["views"] = x["views"]
                if x.get("p") and not rec.get("p"):
                    rec["p"] = x["p"]
                if x.get("t"):
                    rec["t"] = x["t"]
    for ch, v, t, p in newly:
        if st["runs"] > 0:
            log(f"新しいアーセナルの動画 [{CHANNELS[ch][0]}] {v} 公開 {jst_str(parse_iso(p)) if p else '?'}｜{t}", star=True)
    return newly


def pick_video(st, e):
    """試合 e に合うハイライトを 3 社の動画から選ぶ"""
    opp = e["a"] if e["h"] == "arsenal" else e["h"]
    als = aliases(opp)
    k0 = parse_iso(e["d"])
    cands = []
    for v, rec in st["videos"].items():
        t = rec.get("t") or ""
        if "アーセナル" not in t or "ハイライト" not in t:  # 予告（「〇〇 v アーセナル 🕰️ キックオフ」）を拾わないよう、ハイライトの字を必須に
            continue
        if any(w in t for w in EXCLUDE_WORDS):
            continue
        if not any(a in t for a in als):
            continue
        p = parse_iso(rec["p"]) if rec.get("p") else None
        if p and not (k0 - dt.timedelta(hours=2) <= p <= k0 + dt.timedelta(days=8)):
            continue
        score = 0
        if "ハイライト" in t:
            score += 10
        if rec["ch"] == PREF_CH.get(e["k"]):
            score += 5
        if p:
            score += 1
        cands.append((score, p or now(), v, rec))
    if not cands:
        return None
    cands.sort(key=lambda c: (-c[0], c[1]))
    return cands[0][2], cands[0][3]


PREVIEW_EXCLUDE = ["女子", "ウィメンズ", "WSL", "U-17", "U-19", "U-21", "U-23", "U17", "U19", "U21", "U23", "全ゴール集", "プレー集", "ランキング",
                   "ベストゴール", "名場面", "ハイライト", "振り返り", "ダイジェスト"]


def pick_preview(st, e):
    """試合 e の予告（試合前の宣伝の短い動画）。結果と関係ないのでサムネをそのまま見せる"""
    opp = e["a"] if e["h"] == "arsenal" else e["h"]
    als = aliases(opp)
    k0 = parse_iso(e["d"])
    cands = []
    for v, rec in st["videos"].items():
        t = rec.get("t") or ""
        if "アーセナル" not in t or any(w in t for w in PREVIEW_EXCLUDE) or not any(a in t for a in als):
            continue
        p = parse_iso(rec["p"]) if rec.get("p") else None
        if not p or not (k0 - dt.timedelta(days=6) <= p <= k0 + dt.timedelta(hours=2)):
            continue
        score = 5 if rec["ch"] == PREF_CH.get(e["k"]) else 0
        cands.append((score, p, v, rec))
    if not cands:
        return None
    cands.sort(key=lambda c: (c[0], c[1]), reverse=True)  # 配信元の優先 → 新しい順
    return cands[0][2], cands[0][3]


def attach_preview(st, e, m):
    pv = pick_preview(st, e)
    if not pv:
        return
    v, rec = pv
    m["pv"], m["pvch"], m["pvw"], m["pvt"] = v, rec["ch"], fmt_views(rec.get("views")), rec.get("t") or ""
    if st["runs"] > 0 and v not in st.setdefault("pv_seen", {}):
        st["pv_seen"][v] = to_iso(now())
        log(f"予告動画が見つかった: {e['lab']} {e['hname']} vs {e['aname']} → {CHANNELS[rec['ch']][0]} {v}｜{m['pvt'][:60]}", star=True)


def collect_shorts(st):
    try:
        items = yt_feed(ARSENAL_CH)
    except Exception as ex:
        if not SKIP_RSS:
            log(f"アーセナル公式の RSS が取れない: {ex}（ショートのタブから拾う）")
        items = yt_channel_shorts(ARSENAL_CH)[:15]  # RSS が 404 の時の代わり（11/1 に全チャンネル 404 になった）
        for x in items:
            st["shorts"][x["v"]] = True  # ショートのタブにある物は縦動画と分かっている
        if not items:
            return []
    out = []
    for x in items:
        v = x["v"]
        if v not in st["shorts"]:
            # /shorts/ID が 200 なら縦動画、転送されれば普通の動画
            try:
                class NoRedir(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self, *a, **k):
                        return None
                op = urllib.request.build_opener(NoRedir)
                req = urllib.request.Request(f"https://www.youtube.com/shorts/{v}", method="HEAD", headers={"User-Agent": UA})
                r = op.open(req, timeout=20)
                st["shorts"][v] = (r.status == 200)
            except urllib.error.HTTPError as he:
                st["shorts"][v] = (he.code == 200)
            except Exception:
                st["shorts"][v] = False
            if st["shorts"][v] and st["runs"] > 0:
                log(f"新しい縦動画 {v}｜{x['t']}", star=True)
        if st["shorts"][v]:
            out.append(x)
    return out


# ---------------------------------------------------------------- ニュース
def rss_items(url, raw_name=None):
    data = fetch(url)
    if raw_name:
        try:
            os.makedirs(RAW_DIR, exist_ok=True)
            open(os.path.join(RAW_DIR, raw_name), "wb").write(data)
        except Exception:
            pass
    root = ET.fromstring(data)
    out = []
    for it in root.findall("./channel/item"):
        src = it.find("source")
        ce = it.find("{http://purl.org/rss/1.0/modules/content/}encoded")
        desc = it.findtext("description") or ""
        out.append({"title": (it.findtext("title") or "").strip(), "link": it.findtext("link") or "", "pub": parse_rfc822(it.findtext("pubDate") or ""),
                    "src": (src.text if src is not None else None), "srcurl": (src.get("url") if src is not None else ""),
                    "desc": re.sub(r"<[^>]+>", "", (ce.text if ce is not None and ce.text else desc)).strip()})
    return out


CAT_RULES = [
    ("wm", ["女子", "ウィメンズ", "WSL", "Women", "women's", "Arsenal Women"]),
    ("inj", ["ケガ", "怪我", "負傷", "離脱", "出場停止", "復帰", "欠場", "injur", "suspend", "ban ", "banned", "fitness", "ruled out", "return"]),
    ("tr", ["移籍", "獲得", "契約", "加入", "関心", "売却", "放出", "延長", "レンタル", "補強", "狙う", "争奪", "アタック", "ステップアップ", "退団", "transfer", "sign", "contract", "deal", "bid", "linked", "target"]),
]


def categorize(title):
    for c, words in CAT_RULES:
        if any(w.lower() in title.lower() for w in words):
            return c
    return "mt"


def news_match_link(title, pub, matches):
    """見出しが直近の試合の結果を含みそうなら、その試合の id"""
    if not pub:
        return None
    for m in matches:
        if m["k"] == "old":
            continue
        k0 = parse_iso(m["d"])
        if not (k0 - dt.timedelta(hours=3) <= pub <= k0 + dt.timedelta(hours=96)):
            continue
        opp = m["a"] if m["h"] == "arsenal" else m["h"]
        if any(a in title for a in aliases(opp)) or re.search(r"採点|rating|勝利|勝ち|敗|負け|引き分け|ドロー|撃破|PK|完封|逆転|劇的|beat|win|loss|lose|draw|\d\s?[-–−]\s?\d", title, re.I):
            return m["id"]
    return None


def collect_news(st, matches):
    items = []
    for lang, url, raw in (("ja", "https://news.google.com/rss/search?q=%E3%82%A2%E3%83%BC%E3%82%BB%E3%83%8A%E3%83%AB&hl=ja&gl=JP&ceid=JP:ja", "news_ja.xml"),
                           ("en", "https://news.google.com/rss/search?q=Arsenal+FC&hl=en-GB&gl=GB&ceid=GB:en", "news_en.xml"),
                           ("blog", "https://arseblog.com/feed/", "arseblog.xml")):
        try:
            for it in rss_items(url, raw):
                it["lang"] = lang
                items.append(it)
        except Exception as ex:
            log(f"ニュースが取れない {lang}: {ex}")
    out, seen = [], set()
    cutoff = now() - dt.timedelta(days=4)
    for it in sorted(items, key=lambda x: x["pub"] or dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc), reverse=True):
        t = it["title"]
        if not t or not it["pub"] or it["pub"] < cutoff:
            continue
        host = (urllib.parse.urlparse(it["srcurl"] or "").hostname or "").lower()
        if any(j.lower() in t.lower() for j in NEWS_JUNK) or any(j in host for j in NEWS_JUNK_SRC) or host.endswith(".vn"):
            continue
        src = it["src"] or ("Arseblog" if it["lang"] == "blog" else "")
        # Google ニュースの題は「見出し - 出典」
        t = re.sub(r"\s+-\s+[^-]{1,40}$", "", t) if it["lang"] != "blog" else t
        if it["lang"] == "ja" and "アーセナル" not in t:
            continue
        if it["lang"] == "en" and "arsenal" not in t.lower():
            continue
        key = re.sub(r"[\s　「」『』【】!！?？・…、。,.:：\-－—–]", "", t)[:22]
        if key in seen:
            for o in out:
                if o["_key"] == key:
                    o["more"] = o.get("more", 0) + 1
            continue
        seen.add(key)
        n = {"h": t, "s": src, "t": to_iso(it["pub"]), "c": categorize(t), "_key": key, "link": it["link"]}
        if it["lang"] != "ja":
            n["ov"] = 1
            n["lang"] = "英語・音声" if t.lower().startswith("arsecast") else "英語"
            n["_desc"] = (it["desc"] or "")[:400]
            n["_en"] = t
        m = news_match_link(t, it["pub"], matches)
        if m:
            n["m"] = m
        out.append(n)
    ja = [n for n in out if not n.get("ov")][:22]
    ov = [n for n in out if n.get("ov")][:8]
    out = sorted(ja + ov, key=lambda n: n["t"], reverse=True)
    # 英語の見出しの訳と要点（控えがある物はそのまま）。11/3＝記事の冒頭（gnews.py で住所を復号して本文を取る）から要点を書く・v2
    #   古い控え（v2 でない・fail でない）は 1 回だけ作り直す＝「新加入選手」のようにぼかした要約を、本文の名前で言い直すため
    need = [n for n in out if n.get("ov") and (n["link"] not in st["tr"] or (st["tr"][n["link"]].get("v") != 2 and not st["tr"][n["link"]].get("fail")))][:8]
    if need:
        log(f"英語の見出し {len(need)} 本の訳と要点を claude に頼む（本文の冒頭つき）")
        try:
            import gnews
        except Exception:
            gnews = None
        for n in need:
            body = ""
            if gnews:
                try:
                    u = gnews.resolve(n["link"])
                    body = gnews.article_text(u, 6000) if u else ""
                except Exception as ex:
                    log(f"本文が取れない: {type(ex).__name__}: {str(ex)[:100]}")
            n["_body"] = re.sub(r"\s+", " ", body)[:1500] or n["_desc"][:300]
        lines = "\n".join(f"[{i}] 見出し: {n['_en']}\n    本文の冒頭: {n['_body'] or '（なし）'}" for i, n in enumerate(need))
        prompt = ("次はアーセナル（サッカー）に関する英語の記事の見出しと本文の冒頭です。それぞれについて、(1) 見出しの自然な日本語訳、"
                  "(2) 見出しと本文から分かることだけを使った 1〜2 文の要点（ですます調・推測で事実を足さない・選手名は日本の報道の表記）を書いてください。"
                  "見出しが『新加入選手』『あのスター』のようにぼかしている時は、本文にある名前・金額・日付で、読んだ人の『誰？いくら？いつ？』に答えてください。"
                  "要点の中で一番大事な語（選手名・金額・日付など）を 1 つだけ ⟪ ⟫ で囲んでください。試合の結果（スコア・勝ち負け）は書かないでください。"
                  "JSON だけを返し、説明やコードブロックは不要です。形式: {\"0\": {\"h\": \"訳\", \"sum\": \"要点\"}, \"1\": ...}\n\n" + lines)
        res = claude_json(prompt)
        for i, n in enumerate(need):
            v = (res or {}).get(str(i)) if isinstance(res, dict) else None
            if isinstance(v, dict) and v.get("h"):
                st["tr"][n["link"]] = {"h": v["h"], "sum": v.get("sum", ""), "v": 2}
            elif isinstance(res, dict):  # 返事はあったのに訳が無い物は英語のまま載せ、毎回聞き直さない（頼めなかった時は次の回に聞き直す）
                st["tr"][n["link"]] = {"h": n["_en"], "sum": "", "fail": 1, "v": 2}
    for n in out:
        if n.get("ov"):
            tr = st["tr"].get(n["link"])
            if tr:
                n["h"], n["sum"] = tr["h"], tr.get("sum", "")
            else:
                n["sum"] = ""
        for k in ("_key", "_desc", "_en", "_body"):
            n.pop(k, None)
    return out


# ---------------------------------------------------------------- 縦動画の題の訳と試合の結びつけ
def shorts_js(st, shorts, matches, goals_by_match):
    need = [x for x in shorts if x["v"] not in st["tr"]]
    if need:
        log(f"縦動画の題 {len(need)} 本の訳を claude に頼む")
        lines = "\n".join(f"{x['v']}: {x['t']}" for x in need)
        prompt = ("次はアーセナル公式 YouTube の短い動画の題（英語・大文字）です。それぞれ、日本語の自然な一文（句点で終える・15〜30 字・選手名は日本の報道の表記・絵文字は外す）にしてください。"
                  "JSON だけを返し、説明やコードブロックは不要です。形式: {\"動画ID\": \"日本語の題\"}\n" + lines)
        res = claude_json(prompt)
        if isinstance(res, dict):
            for x in need:
                v = res.get(x["v"])
                if isinstance(v, str) and v:
                    st["tr"][x["v"]] = {"ja": v}
    out = []
    for x in shorts[:10]:
        d = {"v": x["v"], "ja": (st["tr"].get(x["v"]) or {}).get("ja") or x["t"], "en": x["t"], "vw": fmt_views(x.get("views"))}
        p = parse_iso(x["p"]) if x.get("p") else None
        if p:
            for m in matches:
                if m["k"] == "old":
                    continue
                k0 = parse_iso(m["d"])
                if not (k0 <= p <= k0 + dt.timedelta(hours=96)):
                    continue
                opp = m["a"] if m["h"] == "arsenal" else m["h"]
                names = [g.get("_s_en", "") for g in goals_by_match.get(m["id"], []) if g.get("team") == "arsenal"]
                surnames = [n.split()[-1].lower() for n in names if n]
                tl = x["t"].lower()
                if any(a.lower() in tl for a in aliases(opp) if a.isascii()) or any(s and s in tl for s in surnames):
                    d["m"] = m["id"]
                    break
        out.append(d)
    return out


# ---------------------------------------------------------------- 本体
def run():
    global _log_lines
    _log_lines = []
    t0 = time.time()
    st = load_state()
    st["runs"] = int(st.get("runs") or 0)
    log(f"取り込み開始（{st['runs'] + 1} 回目）")

    # 1. 日程と結果
    events = espn_events(st)
    done = [e for e in events if e["completed"]]
    upcoming = [e for e in events if not e["completed"]]
    live = [e for e in events if e["state"] == "in"]
    log(f"今季の試合 {len(events)}（終了 {len(done)}・予定 {len(upcoming)}・進行中 {len(live)}）")
    for e in live:
        log(f"進行中: {e['hname']} {e['hs']} - {e['as']} {e['aname']}（{e['detail']}）", star=True)

    # 2. 選手の一覧（背番号・今季の成績）
    try:
        roster = jget(f"{ESPN}eng.1/teams/{ARS_ID}/roster", "roster.json")
    except Exception as ex:
        log(f"選手一覧が取れない: {ex}")
        roster = {"athletes": []}
    jersey_of = {a["displayName"]: int(a["jersey"]) for a in roster.get("athletes", []) if a.get("jersey")}

    # 3. 終わった試合の中身（得点者）
    summaries = {}
    for e in done:
        summaries[e["eid"]] = espn_summary(e)

    # 名試合（手で選んだ物）の中身も取る（スタメンを出すため）
    classics = {"matches": [], "goals": {}}
    try:
        classics = json.load(open(CLASSICS_FILE, encoding="utf-8"))
        for m in classics["matches"]:
            if m.get("eid"):
                summaries[m["eid"]] = espn_summary({"eid": m["eid"], "lg": m.get("lg", "eng.1"), "d": m["d"], "id": m["id"]})
    except Exception as ex:
        log(f"名試合の控えが読めない: {ex}")

    # 名前の日本語表記を先にそろえる
    names = set(jersey_of)
    for e in done + [m for m in classics["matches"] if m.get("eid")]:
        s = summaries.get(e["eid"]) or {}
        for k in s.get("keyEvents", []) or []:
            if k.get("scoringPlay"):
                for p in k.get("participants", []):
                    names.add(p.get("athlete", {}).get("displayName"))
        for r in s.get("rosters", []) or []:
            if r["team"].get("id") == ARS_ID:
                for p in r.get("roster", []):
                    names.add(p["athlete"]["displayName"])
    leaders = {}
    try:
        leaders = espn_leaders(st)
        for rows in leaders.values():
            for r in rows:
                names.add(r[0])
    except Exception as ex:
        log(f"得点王が取れない: {ex}")
    leaders2 = {}   # CL・カップ戦の得点王・アシスト王（11/4・PC 版の右の欄）＝{"cl": {"s": [...], "a": [...]}, "cup": {...}}
    for k2, lg2 in (("cl", "uefa.champions"), ("cup", "eng.league_cup")):
        try:
            d2 = espn_leaders(st, lg2, f"stats_{k2}.json", 10)
            leaders2[k2] = {"s": d2["SCORERS"], "a": d2["ASSISTS"]}
            for rows in d2.values():
                for r in rows:
                    names.add(r[0])
        except Exception as ex:
            log(f"{k2} の得点王が取れない: {ex}")
    ensure_names(st, names)
    for rows in leaders.values():
        for r in rows:
            r[0] = ja_name(st, r[0])
    for d2 in leaders2.values():
        for rows in d2.values():
            for r in rows:
                r[0] = ja_name(st, r[0])

    # 4. 動画
    collect_videos(st)

    # 5. 試合の一覧（見本の MATCHES）と得点
    matches, goals = [], {}
    for e in reversed(done):
        s = summaries.get(e["eid"]) or {}
        g = goals_from_summary(st, e, s, jersey_of)
        goals[e["id"]] = g
        m = {"id": e["id"], "k": e["k"], "lab": e["lab"], "d": e["d"], "h": e["h"], "a": e["a"], "hs": e["hs"], "as": e["as"], "r": e.get("r", "D"), "eid": e["eid"]}
        if e.get("pk"):
            m["pk"] = e["pk"]
        pv = pick_video(st, e)
        if pv:
            v, rec = pv
            m["v"], m["ch"], m["vw"] = v, rec["ch"], fmt_views(rec.get("views"))
            fs = st["first_seen"].get(v)
            if fs and st["runs"] > 0 and not rec.get("seed") and parse_iso(fs) > parse_iso(e["d"]) and not st.get("notes_done", {}).get(m["id"]):
                hours = (parse_iso(fs) - parse_iso(e["d"])).total_seconds() / 3600 - 1.9
                log(f"{e['lab']} {e['hname']} vs {e['aname']} のハイライトが載った: {CHANNELS[rec['ch']][0]} {v}（試合終了から約 {hours:.1f} 時間）", star=True)
                st.setdefault("notes_done", {})[m["id"]] = fs
                st["notes"].append({"t": fs, "x": f"{e['lab']}のハイライトが届いた（{CHANNELS[rec['ch']][0]}・試合終了から約 {hours:.1f} 時間）"})
        else:
            m["v"] = None
            if (now() - parse_iso(e["d"])) < dt.timedelta(days=10):
                log(f"ハイライト待ち: {e['lab']} {e['hname']} vs {e['aname']}")
        matches.append(m)
    # 予告（試合前の宣伝の動画）：終わったばかりの試合と進行中の試合には「予告を見る」の口として付け、これからの試合は先頭に札を出す
    for m in matches:
        if (now() - parse_iso(m["d"])) < dt.timedelta(days=4):
            e = next((x for x in done if x["id"] == m["id"]), None)
            if e:
                attach_preview(st, e, m)
    # 進行中・直前の試合も「結果はまだ」として先頭に出す
    for e in live:
        m = {"id": e["id"], "k": e["k"], "lab": e["lab"], "d": e["d"], "h": e["h"], "a": e["a"], "hs": None, "as": None, "r": None, "v": None, "live": 1, "eid": e["eid"]}
        attach_preview(st, e, m)
        matches.insert(0, m)
    for e in [x for x in upcoming if x["state"] != "in"][:2]:
        if (parse_iso(e["d"]) - now()) > dt.timedelta(days=8):
            continue
        m = {"id": e["id"], "k": "pre", "lab": e["lab"], "d": e["d"], "h": e["h"], "a": e["a"], "hs": None, "as": None, "r": None, "v": None, "eid": e["eid"]}
        attach_preview(st, e, m)
        if m.get("pv"):
            matches.insert(0, m)

    # 名試合（手で選んだ物）
    for m in classics["matches"]:
        matches.append({k: v for k, v in m.items() if k not in ("eid", "lg")})
    goals.update(classics.get("goals", {}))

    # 6. スタメン（リーグのタブ＝直近のプレミアリーグの試合／シアターの上＝試合ごとの先発 11 人）
    lineup, lineups, full = None, {}, {}
    for e in done + [m for m in classics["matches"] if m.get("eid")]:
        s = summaries.get(e["eid"])
        if not s:
            continue
        lu = lineup_from_summary(st, e, s, roster)
        if not lu or len(lu["xi"]) < 11:
            continue
        lineups[e["id"]] = lineup_mini(lu)
        full[e["id"]] = lu
    # リーグのタブ＝直近のプレミアリーグの試合。スタメンがまだ無ければ、その前の試合で代わりにする（画面が壊れないように）
    for e in reversed([x for x in done if x["lg"] == "eng.1"]):
        if e["id"] in full:
            lineup = full[e["id"]]
            attach_events(lineup, goals.get(e["id"], []))
            break
    if lineup is None:
        log("スタメンが 1 試合分も取れていない（リーグのタブは前回の data.js のまま）")

    # 7. 次の試合・順位・節
    nxt = None
    not_started = [e for e in upcoming if e["state"] != "in"]  # 進行中の試合は「次の試合」に出さない
    if not_started:
        e = not_started[0]
        nxt = {"lab": e["lab"], "d": e["d"], "h": e["h"], "a": e["a"], "venue": VENUE_JA.get(e["venue"] or "", e["venue"] or ""), "id": e["id"]}
    table = []
    try:
        table = espn_standings()[:6]
    except Exception as ex:
        log(f"順位が取れない: {ex}")
    pl = [e for e in events if e["lg"] == "eng.1"]
    cur = None
    for e in pl:
        if not e["completed"]:
            win = pl_round_window(parse_iso(e["d"]))
            if win[0] <= now() + dt.timedelta(days=5):
                cur = e
            break
    if cur is None:
        cur = next((e for e in reversed(pl) if e["completed"]), None)
    prev = next((e for e in reversed(pl) if cur and e["rn"] == cur["rn"] - 1), None)
    round_cur = {"n": cur["rn"], "list": espn_round(cur, events)} if cur else {"n": 0, "list": []}
    round_prev = {"n": prev["rn"], "list": espn_round(prev, events)} if prev else {"n": 0, "list": []}

    # 8. 縦動画・ニュース
    shorts = shorts_js(st, collect_shorts(st), matches, goals)
    if shorts:
        st["last_shorts"] = shorts
    elif st.get("last_shorts"):  # RSS が一時的に取れない時は前回の分を出す（縦動画のタブを空にしない）
        shorts = st["last_shorts"]
        log("縦動画が 0 本だったので前回の分を使う")
    news = collect_news(st, matches)
    if news:
        st["last_news"] = news
    elif st.get("last_news"):
        news = st["last_news"]
        log("ニュースが 0 本だったので前回の分を使う")

    # 9. 書き出し
    for gl in goals.values():
        for g in gl:
            for k in ("_s_en", "_a_en", "hd", "ck", "fk"):
                g.pop(k, None)
    st["runs"] += 1
    meta = {"updated": to_iso(now()), "runs": st["runs"], "notes": st["notes"][-8:], "took": round(time.time() - t0, 1),
            "live": [{"id": e["id"], "hs": e["hs"], "as": e["as"], "detail": e["detail"]} for e in live]}
    if nxt is None:  # 予定が無い時も画面が壊れないように
        nxt = {"lab": "次の試合は未定", "d": to_iso(now() + dt.timedelta(days=30)), "h": "arsenal", "a": "arsenal", "venue": "", "id": ""}
    ncats = [{"k": "all", "n": "すべて", "c": "#EF0107"}, {"k": "tr", "n": "移籍", "c": "#1E7BD8"}, {"k": "mt", "n": "試合", "c": "#12A150"},
             {"k": "inj", "n": "出場停止・ケガ", "c": "#E58A00"}, {"k": "ov", "n": "海外", "c": "#7B4BD1"}, {"k": "wm", "n": "女子", "c": "#D6337A"}]
    data = {"TEAMS": teams_js(), "CH": {k: {"n": v[0], "c": v[2]} for k, v in CHANNELS.items()}, "NCATS": ncats, "MATCHES": matches, "GOALS": goals, "NEXT": nxt, "TABLE": table,
            "ROUND_CUR": round_cur, "ROUND_PREV": round_prev, "SCORERS": leaders.get("SCORERS", []), "ASSISTS": leaders.get("ASSISTS", []), "LEADERS": leaders2,
            "SHORTS": shorts, "NEWS": news, "LINEUP": lineup, "LINEUPS": lineups, "META": meta}
    js = "// 自動取り込みが書いた物。手で直さない（次の取り込みで上書きされる）\n"
    for k, v in data.items():
        js += f"const {k} = {json.dumps(v, ensure_ascii=False)};\n"
    js += "MATCHES.forEach(m => { m.goals = GOALS[m.id] || []; });\n"
    tmp = DATA_JS + ".tmp"
    open(tmp, "w", encoding="utf-8").write(js)
    os.replace(tmp, DATA_JS)
    save_state(st)
    nv = sum(1 for m in matches if m.get("v"))
    log(f"data.js を書いた（試合 {len(matches)}・動画あり {nv}・縦動画 {len(shorts)}・ニュース {len(news)}・{meta['took']} 秒）")
    return data


if __name__ == "__main__":
    run()
