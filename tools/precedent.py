#!/usr/bin/env python3
# باحث السوابق: يبحث عن عبارة في سجل اللغة المتفق عليها وفي مجلد نصوص اختياري، ويعيد مواضع ورودها مرتبة زمنيا.
# الاستعمال:
#   python3 tools/precedent.py "national circumstances" [مجلد_نصوص_txt]
# يطبع لكل موضع: السنة، والمصدر والرمز والموقع، ودرجة التحقق، ومقتطفا حول العبارة.
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "references", "agreed_language.json")

def snippet(text, m, width=160):
    s, e = max(0, m.start() - width), min(len(text), m.end() + width)
    return ("..." if s else "") + text[s:e].strip() + ("..." if e < len(text) else "")

def search_registry(rx):
    hits = []
    for x in json.load(open(REG, encoding="utf-8"))["entries"]:
        t = x.get("text_en", "")
        m = rx.search(t)
        if m:
            hits.append((str(x.get("date") or x.get("year") or ""), f"{x.get('symbol','')} {x.get('location','')}".strip(), x.get("status", ""), snippet(t, m), x.get("id", "")))
    return hits

def search_folder(rx, folder):
    hits = []
    for dp, _, files in os.walk(folder):
        for f in files:
            if not f.endswith(".txt"):
                continue
            t = re.sub(r"\s+", " ", open(os.path.join(dp, f), encoding="utf-8", errors="ignore").read())
            yr = re.search(r"(19|20)\d{2}", f)
            for m in rx.finditer(t):
                hits.append((yr.group(0) if yr else "", f, "نص محلي غير مسجل", snippet(t, m), ""))
    return hits

def main():
    if len(sys.argv) < 2:
        sys.exit("الاستعمال: precedent.py \"العبارة\" [مجلد_نصوص]")
    words = sys.argv[1].split()
    rx = re.compile(r"\s+".join(re.escape(w) for w in words), re.I)
    hits = search_registry(rx)
    if len(sys.argv) > 2:
        hits += search_folder(rx, sys.argv[2])
    hits.sort(key=lambda h: h[0])
    if not hits:
        print("لم توجد العبارة في السجل" + (" ولا في المجلد." if len(sys.argv) > 2 else "."))
        return
    for i, (when, where, status, snip, eid) in enumerate(hits, 1):
        print(f"{i}. {when} | {where} | {status}" + (f" | {eid}" if eid else ""))
        print(f"   {snip}\n")
    print(f"عدد المواضع: {len(hits)}. لا يقتبس في وثيقة خارجية إلا ما درجته verified_original.")

if __name__ == "__main__":
    main()
