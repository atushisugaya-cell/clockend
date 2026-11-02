# -*- coding: utf-8 -*-
"""GitHub のサーバーから、取り込みの取り先がそれぞれ取れるかを試す（試し用・送らない）"""
import gzip, json, re, time, urllib.request, urllib.error
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
YT_COOKIE = {"Cookie": "CONSENT=YES+1; SOCS=CAI"}


def get(url, method="GET", headers=None, data=None):
    h = {"User-Agent": UA, "Accept-Encoding": "gzip", "Accept-Language": "ja,en"}
    h.update(headers or {})
    t = time.time()
    try:
        req = urllib.request.Request(url, headers=h, method=method, data=data)
        with urllib.request.urlopen(req, timeout=30) as r:
            code, body, final = r.status, r.read(), r.geturl()
    except urllib.error.HTTPError as e:
        code, body, final = e.code, e.read(), url
    except Exception as e:
        return None, str(e).encode(), url, time.time() - t
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return code, body, final, time.time() - t


def count_xml(body, tag):
    try:
        return len([e for e in ET.fromstring(body).iter() if e.tag.endswith(tag)])
    except Exception:
        return "読めない"


def check_json(b):
    j = json.loads(b)
    return f"試合 {len(j.get('events', []))}"


CHECKS = [
    ("ESPN 日程", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/teams/359/schedule", None, check_json),
    ("ESPN 順位", "https://site.api.espn.com/apis/v2/sports/soccer/eng.1/standings", None, lambda b: f"{len(b)} バイト"),
    ("YouTube RSS U-NEXT", "https://www.youtube.com/feeds/videos.xml?channel_id=UCMjvvElkdLRTgcTKklAUkSw", None, lambda b: f"動画 {count_xml(b, 'entry')}"),
    ("YouTube RSS WOWOW", "https://www.youtube.com/feeds/videos.xml?channel_id=UCJQj2lbG_3w8UrncJd7JZXw", None, lambda b: f"動画 {count_xml(b, 'entry')}"),
    ("YouTube RSS DAZN", "https://www.youtube.com/feeds/videos.xml?channel_id=UCoFLB_Gw_AoxUuuzKjXrc_Q", None, lambda b: f"動画 {count_xml(b, 'entry')}"),
    ("YouTube RSS 公式", "https://www.youtube.com/feeds/videos.xml?channel_id=UCpryVRk_VDudG8SHXgWcG0w", None, lambda b: f"動画 {count_xml(b, 'entry')}"),
    ("YouTube 一覧 U-NEXT", "https://www.youtube.com/channel/UCMjvvElkdLRTgcTKklAUkSw/videos", YT_COOKIE,
     lambda b: ("一覧あり" if b"ytInitialData" in b else "一覧なし") + ("・ロボット確認あり" if re.search(rb"not a bot|confirm you.re not", b) else "") + ("・同意画面" if b"consent.youtube.com" in b else "")),
    ("YouTube 縦動画 公式", "https://www.youtube.com/channel/UCpryVRk_VDudG8SHXgWcG0w/shorts", YT_COOKIE,
     lambda b: "一覧あり" if b"ytInitialData" in b else "一覧なし"),
    ("Google ニュース 日本語", "https://news.google.com/rss/search?q=%E3%82%A2%E3%83%BC%E3%82%BB%E3%83%8A%E3%83%AB&hl=ja&gl=JP&ceid=JP:ja", None, lambda b: f"記事 {count_xml(b, 'item')}"),
    ("Google ニュース 英語", "https://news.google.com/rss/search?q=Arsenal+FC&hl=en-GB&gl=GB&ceid=GB:en", None, lambda b: f"記事 {count_xml(b, 'item')}"),
    ("Arseblog", "https://arseblog.com/feed/", None, lambda b: f"記事 {count_xml(b, 'item')}"),
    ("予想 フットボールチャンネル", "https://www.footballchannel.jp/feed/", None, lambda b: f"記事 {count_xml(b, 'item')}"),
    ("予想 Sports Mole", "https://www.sportsmole.co.uk/football/arsenal/rss.xml", None, lambda b: f"記事 {count_xml(b, 'item')}"),
    ("予想 football.london", "https://www.football.london/arsenal-fc/?service=rss", None, lambda b: f"記事 {count_xml(b, 'item')}"),
    ("公開先 /_status", "https://clockend.atushisugaya.workers.dev/_status", None, lambda b: b[:80].decode("utf-8", "replace")),
]

ok = 0
for name, url, headers, judge in CHECKS:
    code, body, final, took = get(url, headers=headers)
    try:
        note = judge(body) if code == 200 else body[:120].decode("utf-8", "replace").replace("\n", " ")
    except Exception as e:
        note = f"読めない: {e}"
    good = code == 200 and "なし" not in note and "読めない" not in note
    ok += good
    moved = f"（転送先 {final[:60]}）" if final != url else ""
    print(f"{'○' if good else '×'} {name}: {code} {len(body)} バイト {took:.1f} 秒 {note}{moved}")

# 縦動画かどうかの見分け（/shorts/ID に HEAD を送り、転送されなければ縦動画）
code, body, final, took = get("https://www.youtube.com/shorts/gxQWpGIOl0s", method="HEAD")
print(f"{'○' if code == 200 else '×'} 縦動画の見分け: {code} 転送 {'あり' if final.rstrip('/').split('/')[-1] != 'gxQWpGIOl0s' else 'なし'}")

# 公開先への送信が Cloudflare に弾かれないか（わざと違う合言葉＝Worker が forbidden と答えれば通っている）
code, body, final, took = get("https://clockend.atushisugaya.workers.dev/_update", method="POST",
                              headers={"X-Update-Key": "probe-wrong-key-000000", "Content-Type": "application/javascript"}, data=b"probe")
txt = body[:80].decode("utf-8", "replace")
print(f"{'○' if txt == 'forbidden' else '×'} 公開先への送信の通り道: {code} {txt!r}（forbidden なら Worker まで届いている）")
print(f"\n取り先 {ok}/{len(CHECKS)} が取れた")
