# -*- coding: utf-8 -*-
"""「選手」タブのデータ（SQUAD・COMPS・YOSO）を data.js の後ろに足す（11/2・本番の取り込みで毎回）
  読む物＝ _データ_自動/squad.js（squad.py）・comps.js（comps_mock.py）・yoso.json（yoso.py）
  無い物・壊れている物は空で足す（画面が壊れないように。取り込み本体は止めない）
使い方: python players_pack.py [data.js の置き場]   既定＝見本_20261030/data.js
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUTO = os.path.join(ROOT, "_データ_自動")
DATA_JS = sys.argv[1] if len(sys.argv) > 1 else (os.environ.get("ARS_DATA_JS") or os.path.join(ROOT, "見本_20261030", "data.js"))
MARK = "// ---- 選手タブ（players_pack.py が足す）----\n"


def const_of(path, name, empty):
    try:
        src = open(path, encoding="utf-8").read()
        return json.loads(re.search(r"const %s = (.*?);\n" % name, src, re.S).group(1))
    except Exception as ex:
        print(f"{name} が読めない（空で足す）: {ex}")
        return empty


def main():
    squad = const_of(os.path.join(AUTO, "squad.js"), "SQUAD", [])
    squad_meta = const_of(os.path.join(AUTO, "squad.js"), "SQUAD_META", {})
    comps = const_of(os.path.join(AUTO, "comps.js"), "COMPS", {"matches": [], "next": {}, "lu": {}, "games": {}, "ps": {}, "extra": {}, "pl_table": [], "cl_table": [], "teams": {}})
    try:
        yoso = json.load(open(os.path.join(AUTO, "yoso.json"), encoding="utf-8"))
    except Exception as ex:
        print(f"YOSO が読めない（空で足す）: {ex}")
        yoso = {"opp": {}, "items": []}
    src = open(DATA_JS, encoding="utf-8").read()
    if MARK in src:  # 前に足した分は外してから足し直す
        src = src[:src.index(MARK)]
    add = MARK
    for k, v in (("SQUAD", squad), ("SQUAD_META", squad_meta), ("COMPS", comps), ("YOSO", yoso)):
        add += f"const {k} = {json.dumps(v, ensure_ascii=False)};\n"
    tmp = DATA_JS + ".tmp"
    open(tmp, "w", encoding="utf-8", newline="\n").write(src + add)
    os.replace(tmp, DATA_JS)
    print(f"data.js に足した：選手 {len(squad)}・試合 {len(comps.get('matches', []))}・予想 {len(yoso.get('items', []))}（{len(add) // 1024} KB）")


if __name__ == "__main__":
    main()
