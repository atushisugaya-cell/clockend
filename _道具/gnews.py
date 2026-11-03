# -*- coding: utf-8 -*-
"""Google News の RSS と、記事の住所の復号・本文の取り出し（11/3・採点 ratings.py と要約 arsfetch.py で使う）
  - search(q, when="3d") → [{title, link, pub(iso), src, srcurl}]
  - resolve(link) → 元の記事の住所（news.google.com/rss/articles/<id> を復号）。控え＝_データ_自動/gnews_cache.json
  - article_text(url) → 本文の文字（JSON-LD の articleBody を優先・無ければ段落の区切りで改行して札を外す）
  注意：復号は /articles/<id> の HTML → batchexecute への POST（11/3 調べ）。1 時間に 85 回ほどで 429 になるので、控えを必ず使い 1 件ずつ
"""
import os, re, json, time, html as htmlmod, urllib.request, urllib.parse, urllib.error
from xml.etree import ElementTree as ET
from email.utils import parsedate_to_datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "_データ_自動", "gnews_cache.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
      "Accept-Language": "en-GB,en;q=0.9"}


def _get(url, timeout=30, data=None, headers=None):
    h = dict(UA); h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, (e.read() if e.fp else b"")


def search(q, when="3d"):
    """Google News の検索 RSS。q は英語の検索語（"Arsenal player ratings" のように引用符つきで）"""
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(f"{q} when:{when}") + "&hl=en-GB&gl=GB&ceid=GB:en"
    code, body = _get(url)
    if code != 200:
        raise RuntimeError(f"Google News RSS {code}")
    out = []
    for it in ET.fromstring(body).findall(".//item"):
        src = it.find("source")
        try:
            pub = parsedate_to_datetime(it.findtext("pubDate") or "").isoformat()
        except Exception:
            pub = ""
        out.append({"title": (it.findtext("title") or "").strip(), "link": it.findtext("link") or "", "pub": pub,
                    "src": (src.text if src is not None else "") or "", "srcurl": (src.get("url") if src is not None else "") or ""})
    return out


def feed(url):
    """媒体自身の RSS（住所がそのまま＝復号が要らない）。[{title, link, pub, src, srcurl}]・取れない時は []"""
    try:
        code, body = _get(url)
        if code != 200:
            return []
        out = []
        for it in ET.fromstring(body).findall(".//item"):
            try:
                pub = parsedate_to_datetime(it.findtext("pubDate") or "").isoformat()
            except Exception:
                pub = ""
            out.append({"title": (it.findtext("title") or "").strip(), "link": (it.findtext("link") or "").strip(), "pub": pub, "src": url, "srcurl": url})
        return out
    except Exception as ex:
        print(f"gnews: feed が読めない {url[:60]} {type(ex).__name__}")
        return []


def _load():
    try:
        return json.load(open(CACHE, encoding="utf-8"))
    except Exception:
        return {}


def _save(c):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    tmp = CACHE + ".tmp"
    json.dump(c, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, CACHE)


BUDGET = {"left": int(os.environ.get("ARS_GNEWS_BUDGET") or 8), "stopped": False}  # 1 回の実行で復号する数の上限。429 が出たらその回は止める


def resolve(link):
    """news.google.com の記事の住所 → 元の記事の住所。復号できない時は None（1 時間は聞き直さない）"""
    m = re.search(r"news\.google\.com/(?:rss/)?articles/([^?&#]+)", link or "")
    if not m:
        return link
    art = m.group(1)
    cache = _load()
    got = cache.get(art)
    if got and (got.get("url") or time.time() - got.get("t", 0) < 3600):
        return got.get("url")
    if BUDGET["stopped"] or BUDGET["left"] <= 0:
        return None  # 控えには書かない＝次の回に聞く
    BUDGET["left"] -= 1
    url = None
    try:
        code, body = _get(f"https://news.google.com/articles/{art}")
        if code == 429:
            BUDGET["stopped"] = True
            print("gnews: 429＝この回の復号はここまで（次の回に続きを聞く）")
            return None
        h = body.decode("utf-8", "replace")
        sg = re.search(r'data-n-a-sg="([^"]+)"', h); ts = re.search(r'data-n-a-ts="(\d+)"', h)
        if code == 200 and sg and ts:
            req = [["Fbv4je", f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{art}",{ts.group(1)},"{sg.group(1)}"]']]
            payload = ("f.req=" + urllib.parse.quote(json.dumps([req]))).encode()
            code2, body2 = _get("https://news.google.com/_/DotsSplashUi/data/batchexecute", data=payload,
                                headers={"content-type": "application/x-www-form-urlencoded;charset=UTF-8"})
            if code2 == 200:
                txt = body2.decode("utf-8", "replace")
                parts = txt.split("\n\n")
                chunk = json.loads(parts[1] if len(parts) > 1 else parts[0].lstrip(")]}'\n"))
                for res in chunk:
                    if isinstance(res, list) and len(res) > 2 and isinstance(res[2], str):
                        try:
                            u = json.loads(res[2])[1]
                            if isinstance(u, str) and u.startswith("http"):
                                url = u; break
                        except Exception:
                            pass
        else:
            print(f"gnews: /articles が {code}（sg {bool(sg)} ts {bool(ts)}）")
    except Exception as ex:
        print(f"gnews: 復号に失敗 {type(ex).__name__}: {str(ex)[:120]}")
    cache[art] = {"url": url, "t": time.time()}
    _save(cache)
    return url


_TAG_BREAK = re.compile(r"</(p|h[1-6]|li|div|tr|blockquote|strong|b)>|<br\s*/?>", re.I)


def _strip(html_src):
    s = re.sub(r"<(script|style|noscript|svg|nav|header|footer)[^>]*>.*?</\1>", " ", html_src, flags=re.S | re.I)
    s = _TAG_BREAK.sub("\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = htmlmod.unescape(s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def _ld_body(html_src):
    for m in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html_src, re.S | re.I):
        try:
            d = json.loads(htmlmod.unescape(m.group(1)).strip())
        except Exception:
            continue
        stack = [d]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if isinstance(x.get("articleBody"), str) and len(x["articleBody"]) > 200:
                    return htmlmod.unescape(x["articleBody"])
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)
    return None


def article_text(url, limit=20000):
    """記事の本文。取れない時は空の文字"""
    if not url:
        return ""
    code, body = _get(url)
    if code != 200:
        print(f"gnews: 記事が {code} {url[:80]}")
        return ""
    h = body.decode("utf-8", "replace")
    text = (_ld_body(h) or _strip(h))[:limit]
    # Arseblog の採点は iframe（arseblog-ratings.vercel.app）の中＝そちらを先頭に足す（ページ本体が長くて切れないように）
    m = re.search(r'src="(https://arseblog-ratings\.vercel\.app/[^"]+)"', h)
    if m:
        code2, body2 = _get(m.group(1))
        if code2 == 200:
            text = _strip(body2.decode("utf-8", "replace"))[:limit // 2] + "\n" + text
    return text[:limit]


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    items = search('"Arsenal player ratings"', "3d")
    print(len(items), "件")  # 題は出さない（結果が入っていることがある）
    for it in items[:8]:
        print(it["pub"], "|", it["src"], "|", it["srcurl"])
