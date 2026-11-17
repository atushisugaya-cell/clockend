# -*- coding: utf-8 -*-
"""CLOCK END の試合の日の SNS の絵（決まり帳 v1.1・2026-11-10）。月曜の「次の 3 試合」（sns_next.html）と同じ色と字。
  種類＝eve（1 明日の試合）／lineup（2 公式スタメン）／highlight（4 ハイライト到着・reel=True で 1080×1920）／
        rcover（5 採点の表紙）／ravg（5 採点の 2 枚目・Instagram だけ）
  決まり：結果は絵に出さない（スコア・得点者・勝ち負け）。rcover は「結果を含みます」の表紙。ravg だけが結果を含む（表紙の後ろ）。
  使い方：html = card_html(kind, data, crest_src) → 画面なしの Chrome／Edge で 1080×1350（reel は 1080×1920）で撮る。
"""
import html as _h

FONT = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Noto+Sans+JP:wght@500;700;900&family=Anton&display=swap" rel="stylesheet">')

BASE = """
:root{--red:#DB0007;--bg:#0B0E14;--line:#2A3242;--cyan:#36D6FF;--text:#F2F4F8;--sub:#9AA3B5;--gold:#F6D66E;
  --num:"Barlow Condensed","Noto Sans JP","Noto Sans CJK JP",sans-serif;--disp:"Anton","Barlow Condensed",sans-serif;
  --grain:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .5 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>")}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:__H__px;overflow:hidden;background:var(--bg)}
body{font-family:"Noto Sans JP","Noto Sans CJK JP",sans-serif;color:var(--text);font-feature-settings:"palt"}
.art{position:relative;overflow:hidden;width:1080px;height:__H__px;background:repeating-linear-gradient(135deg,rgba(255,255,255,.022) 0 2px,transparent 2px 24px),var(--bg)}
.art::after{content:"";position:absolute;inset:0;background:var(--grain);opacity:.16;mix-blend-mode:overlay;pointer-events:none;z-index:9}
.stripe{position:absolute;left:0;top:0;bottom:0;width:20px;background:var(--red);z-index:3}
.glow{position:absolute;right:-260px;top:-200px;width:900px;height:900px;border-radius:50%;background:radial-gradient(closest-side,rgba(219,0,7,.26),rgba(219,0,7,0))}
.k{position:absolute;left:104px;top:96px;font:700 32px/1 var(--num);letter-spacing:.34em;color:var(--cyan)}
.emb{position:absolute;right:72px;top:64px;height:190px;filter:drop-shadow(0 12px 30px rgba(0,0,0,.5))}
h1{position:absolute;left:96px;top:150px;font:400 150px/1 var(--disp);color:#fff;letter-spacing:-.005em;text-transform:uppercase}
h1 i{font-style:normal;color:transparent;-webkit-text-stroke:4px #fff}
.lead{position:absolute;left:104px;right:72px;top:322px;font-size:42px;font-weight:900;letter-spacing:.04em}
.lead i{display:block;width:96px;height:8px;background:var(--red);margin-bottom:22px}
.foot{position:absolute;left:104px;right:72px;bottom:84px;display:flex;align-items:flex-end;justify-content:space-between;z-index:4}
.foot .ns b{display:block;font:400 54px/1 var(--disp);color:var(--gold);letter-spacing:.01em}
.foot .ns span{display:block;margin-top:14px;font-size:30px;font-weight:700;color:#fff}
.foot .url{font:700 40px/1 var(--num);letter-spacing:.1em;color:var(--sub)}
/* ピッチ（縦・上が攻め） */
.pitch{position:absolute;left:104px;right:72px;border:3px solid rgba(255,255,255,.22);background:
  linear-gradient(rgba(255,255,255,.14),rgba(255,255,255,.14)) 0 50%/100% 3px no-repeat,
  repeating-linear-gradient(0deg,#0F3A26 0 60px,#124430 60px 120px)}
.pitch::before{content:"";position:absolute;left:50%;top:50%;width:150px;height:150px;border:3px solid rgba(255,255,255,.14);border-radius:50%;transform:translate(-50%,-50%)}
.pitch::after{content:"";position:absolute;left:30%;right:30%;bottom:0;height:90px;border:3px solid rgba(255,255,255,.14);border-bottom:0}
.pl{position:absolute;transform:translate(-50%,-50%);display:flex;flex-direction:column;align-items:center;gap:6px;width:240px;z-index:2}
.pl i{font-style:normal;width:66px;height:66px;border-radius:50%;background:var(--red);border:4px solid #fff;display:grid;place-items:center;font:800 32px/1 var(--num);color:#fff;box-shadow:0 6px 14px rgba(0,0,0,.45)}
.pl s{text-decoration:none;font-size:24px;line-height:1.2;font-weight:900;color:#fff;white-space:nowrap;text-shadow:0 2px 8px rgba(0,0,0,.9)}
.pl.diff i{background:var(--gold);border-color:var(--gold);color:#111}
.pl.diff s{color:var(--gold)}
/* ドット絵の顔（サイトのスタメンと同じ sprites.js の 22×22 を 3 倍）＋右下に背番号 */
.pl .fc{position:relative;width:66px;height:66px;box-shadow:0 6px 14px rgba(0,0,0,.5)}
.pl .fc img{display:block;width:66px;height:66px;image-rendering:pixelated;background:#232B3B;outline:3px solid #fff}
.pl .fc b{position:absolute;right:-16px;bottom:-8px;min-width:30px;text-align:center;background:var(--red);border:2px solid #fff;font:800 19px/1 var(--num);color:#fff;padding:3px 4px}
.pl.gk .fc img{background:#3A2E0C}
.pl.diff .fc img{outline:4px solid var(--gold)}
.pl.diff .fc b{background:var(--gold);color:#111;border-color:var(--gold)}
.pin{position:absolute;left:14px;top:10px;font-size:22px;font-weight:700;line-height:1.35;color:rgba(255,255,255,.75);z-index:3}
.pin b{color:#fff}
.cap{position:absolute;left:104px;right:72px;font-size:26px;font-weight:700;color:var(--sub);letter-spacing:.02em}
.cap b{color:#fff}
.chips{position:absolute;left:104px;right:72px;display:flex;flex-wrap:wrap;gap:12px}
.chip{font-size:30px;font-weight:900;padding:10px 18px;border:2px solid var(--line);background:rgba(255,255,255,.05)}
.chip b{color:var(--gold);margin-right:12px;font-weight:900}
"""


def _e(s):
    return _h.escape(str(s or ""))


def _pitch(xi, top, height, diff=(), label=""):
    """xi の各人＝{no, n, x, y, p?, face?}。face（data: の PNG・サイトの sprites.js の SPRITES[no].face）があればドット絵の顔、無ければ背番号の丸。
    本番では https://clockend.jp/sprites.js を読んで face を足す（11/10 菅谷様「顔を今のドット絵に」）"""
    out = [f'<div class="pitch" style="top:{top}px;height:{height}px">']
    if label:
        out.append(f'<div class="pin">{label}</div>')
    for p in xi:
        cls = "pl" + (" diff" if p["no"] in diff else "") + (" gk" if p.get("p") == "GK" else "")
        y = 9 + (max(12, min(90, p["y"])) - 12) * 75 / 78   # 前 12〜GK 90 を 9〜84% に＝GK の名前がピッチの外に出ず、列が重ならない
        mark = (f'<span class="fc"><img src="{p["face"]}" alt=""><b>{p["no"]}</b></span>' if p.get("face") else f'<i>{p["no"]}</i>')
        out.append(f'<div class="{cls}" style="left:{p["x"]}%;top:{y:.1f}%">{mark}<s>{_e(p["n"])}</s></div>')
    out.append("</div>")
    return "".join(out)


def _page(h, css, body):
    return (f'<!doctype html><html lang="ja"><head><meta charset="utf-8">{FONT}<style>{BASE.replace("__H__", str(h))}{css}</style></head>'
            f'<body><div class="art">{body}</div></body></html>')


FOOT = '<div class="foot"><div class="ns"><b>NO SPOILERS.</b><span>結果は、見終わるまで伏せています。</span></div><div class="url">clockend.jp</div></div>'


def card_html(kind, d, crest):
    """d の中身は種類ごと（下の各ブロックのコメント）。crest＝紋章の src（data: か URL）"""
    head = f'<div class="stripe"></div><div class="glow"></div><img class="emb" src="{crest}" alt="">'
    if kind == "eve":
        # d: when（11/22（日）2:30）, match（ニューカッスル vs アーセナル）, comp（プレミアリーグ 第11節・アウェイ）, xi, src（社名の並び）, n（社数）, inj [(種類, 文)]
        css = (".mt{position:absolute;left:104px;right:72px;top:390px;font-size:46px;font-weight:900;letter-spacing:.02em;line-height:1.25}.mt small{display:block;margin-top:6px;font-size:26px;font-weight:700;color:var(--sub);line-height:1.3}"
               "h1{font-size:132px}.lead{top:298px}.src{position:absolute;right:72px;top:1046px;font-size:19px;font-weight:700;line-height:1.38;color:var(--sub);text-align:right}")
        # 予想が 2 社未満の日の一言（11/17 直し：「まだ 2 社そろっていません」は内輪の言い方＝次に出る物の案内に）
        cap = ("" if d.get("xi") else '<div class="cap" style="top:508px">公式スタメンは、キックオフの約1時間前にお知らせします。</div>')
        if not d.get("xi"):   # 予想が 2 社未満の日（11/14）＝ピッチの場所が空く → キックオフの時刻（日本時間）を大きく
            import re as _re
            hm = (_re.search(r"(\d{1,2}:\d{2})\s*$", str(d.get("when") or "")) or [None, ""])[1]
            css += (".ko{position:absolute;left:96px;right:72px;top:600px}.ko b{display:block;font:400 330px/1 var(--disp);color:var(--gold);letter-spacing:.01em}"
                    ".ko span{display:block;margin-top:18px;font:700 34px/1 var(--num);letter-spacing:.3em;color:var(--cyan)}")
            cap += f'<div class="ko"><b>{_e(hm)}</b><span>KICK-OFF ・ JST</span></div>'
        # xi_label＝11 人全員が 2 社以上でない時（sns_match.py が「（多くの社が選んだ並び）」を渡す・11/14）
        # 11/17 直し：ケガの札が「NO SPOILERS.」にくっついていた＝ピッチを 26px 縮めて、札を 1080 → 1046（予想なしの日は 1024）へ
        pitch = _pitch(d["xi"], 508, 522, label=f'記者<b>{d["n"]}社</b>の予想<br>{_e(d.get("xi_label") or "（2社以上が選んだ11人）")}') if d.get("xi") else ""
        src = (f'<div class="src">出典：{"<br>".join(_e(x) for x in str(d["src"]).split("・"))}</div>') if d.get("xi") else ""
        chips = "".join(f'<span class="chip"><b>{_e(k)}</b>{_e(t)}</span>' for k, t in (d.get("inj") or [])[:4])
        body = (head + '<div class="k">MATCH EVE ・ JST</div><h1>TOMORROW</h1>'
                f'<div class="lead"><i></i>{_e(d["when"])} キックオフ（日本時間）</div>'
                f'<div class="mt">{_e(d["match"])}<small>{_e(d["comp"])}</small></div>{cap}{pitch}'
                f'<div class="chips" style="top:{1046 if d.get("xi") else 1024}px;right:330px">{chips}</div>{src}{FOOT}')
        return _page(1350, css, body)
    if kind == "lineup":
        # d: fm（4-2-3-1）, xi, diff（予想と違った背番号の並び）, bench [名前], left（キックオフまでの分）
        css = ".lg{position:absolute;left:104px;right:72px;top:426px;font-size:30px;font-weight:900;color:var(--gold)}.lg span{color:var(--sub);font-weight:700;margin-left:18px}"
        bench = "・".join(_e(n) for n in d.get("bench", [])[:9])
        body = (head + f'<div class="k">STARTING XI ・ {_e(d["fm"])}</div><h1>LINE-UP</h1>'
                f'<div class="lead"><i></i>公式スタメン、出ました。</div>'
                # 予想が 2 社未満の日（pred＝False）は「● 記者の予想と違った選手」を出さない（11/14）
                + (f'<div class="lg">● 記者の予想と違った選手<span>キックオフまで あと{d["left"]}分</span></div>' if d.get("pred", True)
                   else f'<div class="lg"><span style="margin-left:0">キックオフまで あと{d["left"]}分</span></div>') +
                f'{_pitch(d["xi"], 482, 548, set(d.get("diff", [])))}'
                f'<div class="cap" style="top:1046px;line-height:1.5"><b>ベンチ</b>　{bench}</div>{FOOT}')
        return _page(1350, css, body)
    if kind == "highlight":
        # d: home/away（略・色・しま模様か）, comp（プレミアリーグ 第11節）, opp（ニューカッスル）, reel（True で 1080×1920）
        H = 1920 if d.get("reel") else 1350
        hc, ac = d["home"]["c"], d["away"]["c"]
        stripes = lambda side: (f'<div class="sp" style="clip-path:polygon({"0 0,56% 0,44% 100%,0 100%" if side == "h" else "56% 0,100% 0,100% 100%,44% 100%"})"></div>')
        css = (f".split{{position:absolute;inset:0;background:linear-gradient(105deg,{hc} 0 49.7%,#fff 49.7% 50.3%,{ac} 50.3% 100%)}}"
               ".sp{position:absolute;inset:0;background:repeating-linear-gradient(90deg,rgba(255,255,255,.13) 0 46px,transparent 46px 92px)}"
               ".shade{position:absolute;inset:0;background:linear-gradient(rgba(0,0,0,.35),rgba(0,0,0,.05) 40%,rgba(0,0,0,.55))}"
               f".ab{{position:absolute;top:{110 if H == 1350 else 220}px;left:0;right:0;display:flex;justify-content:space-between;padding:0 110px 0 120px;font:400 {120 if H == 1350 else 150}px/1 var(--disp);color:#fff;text-shadow:0 8px 30px rgba(0,0,0,.45);z-index:3}}"
               f".bigc{{position:absolute;left:50%;top:{300 if H == 1350 else 470}px;height:{300 if H == 1350 else 420}px;transform:translateX(-50%);filter:drop-shadow(0 20px 40px rgba(0,0,0,.6));z-index:3}}"
               f".hl{{position:absolute;left:0;right:0;top:{640 if H == 1350 else 960}px;text-align:center;font:400 {128 if H == 1350 else 156}px/.98 var(--disp);color:#fff;text-transform:uppercase;text-shadow:0 10px 40px rgba(0,0,0,.6);z-index:3}}"
               f".jp{{position:absolute;left:0;right:0;top:{920 if H == 1350 else 1310}px;text-align:center;font-size:{44 if H == 1350 else 50}px;font-weight:900;line-height:1.5;text-shadow:0 4px 18px rgba(0,0,0,.8);z-index:3}}"
               f".cp{{position:absolute;left:0;right:0;top:{1060 if H == 1350 else 1500}px;text-align:center;font:700 32px/1 var(--num);letter-spacing:.16em;color:#fff;opacity:.85;z-index:3}}"
               ".foot .ns b{text-shadow:0 4px 16px rgba(0,0,0,.6)}.foot .url{color:#fff}" + (".foot{bottom:150px}" if H == 1920 else ""))
        sh = stripes("h") if d["home"].get("st") else ""
        sa = stripes("a") if d["away"].get("st") else ""
        body = (f'<div class="split"></div>{sh}{sa}<div class="shade"></div><div class="stripe"></div>'
                f'<div class="ab"><span>{_e(d["home"]["s"])}</span><span>{_e(d["away"]["s"])}</span></div>'
                f'<img class="bigc" src="{crest}" alt=""><div class="hl">Highlights<br>are in.</div>'
                f'<div class="jp">ハイライト、届きました。<br>結果は、見終わるまで出ません。</div>'
                f'<div class="cp">{_e(d["comp"])}</div>{FOOT}')
        return _page(H, css, body)
    if kind == "rcover":
        # d: tag（NEW v ARS）, n（社数）, src（社名の並び）
        css = (".warn{position:absolute;left:104px;right:72px;top:430px;border:6px solid var(--gold);padding:64px 40px 56px;text-align:center;background:rgba(246,214,110,.07)}"
               ".warn b{display:block;font:400 104px/1 var(--disp);color:var(--gold);letter-spacing:.01em}"
               ".warn span{display:block;margin-top:34px;font-size:60px;font-weight:900;line-height:1.4}"
               ".warn small{display:block;margin-top:28px;font-size:34px;font-weight:700;color:#D8DEE8;line-height:1.6}")
        body = (head + f'<div class="k">MEDIA RATINGS ・ {_e(d["tag"])}</div><h1>RATINGS</h1>'
                '<div class="warn"><b>SPOILER AHEAD</b><span>ここから先は、<br>結果を含みます。</span>'
                '<small>まだの方は、ハイライトを見てから。<br>平均点と MVP は、この先に。</small></div>'
                f'<div class="cap" style="top:1030px;line-height:1.55">メディア<b>{d["n"]}社</b>の採点｜{_e(d["src"])}</div>{FOOT}')
        return _page(1350, css, body)
    if kind == "ravg":
        # d: tag, n, rows [(名前, 平均点)]（高い順）, mvp（名前）
        css = (".mvp{position:absolute;left:104px;right:72px;top:330px;display:flex;align-items:center;gap:28px;border:4px solid var(--gold);padding:22px 30px;background:rgba(246,214,110,.08)}"
               ".mvp b{font:400 64px/1 var(--disp);color:var(--gold)}.mvp span{font-size:50px;font-weight:900}.mvp em{margin-left:auto;font:800 76px/1 var(--num);font-style:normal;color:#fff}"
               ".rows{position:absolute;left:104px;right:72px;top:486px;display:grid;grid-template-columns:1fr 1fr;column-gap:36px;row-gap:4px}"
               ".r{display:grid;grid-template-columns:1fr auto;align-items:center;column-gap:12px;row-gap:8px;padding:8px 0;border-bottom:2px solid var(--line)}"
               ".r span{font-size:30px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.r b{font:800 40px/1 var(--num);color:#fff}"
               ".r i{grid-column:1/-1;height:8px;background:linear-gradient(90deg,var(--red) var(--w),rgba(255,255,255,.08) var(--w))}")
        rows = "".join(f'<div class="r" style="--w:{max(0, min(100, (v - 4) / 5 * 100)):.0f}%"><span>{_e(nm)}</span><b>{v:.1f}</b><i></i></div>' for nm, v in d["rows"][:14])
        mv = next((v for nm, v in d["rows"] if nm == d["mvp"]), 0)
        body = (head + f'<div class="k">MEDIA RATINGS ・ {d["n"]} OUTLETS</div><h1 style="font-size:120px">AVERAGE</h1>'
                f'<div class="mvp"><b>MVP</b><span>{_e(d["mvp"])}</span><em>{mv:.1f}</em></div><div class="rows">{rows}</div>'
                f'<div class="cap" style="top:1064px;line-height:1.55">メディア<b>{d["n"]}社</b>の平均｜{_e(d.get("src", ""))}</div>'
                '<div class="foot"><div class="ns"><b>MEDIA RATINGS.</b><span>メディア各社の採点の平均です。</span></div><div class="url">clockend.jp</div></div>')
        return _page(1350, css, body)
    raise ValueError(kind)
