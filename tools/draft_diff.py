#!/usr/bin/env python3
# مقارنة نسختين من مسودة تفاوضية فقرة بفقرة، وإخراج تقرير عربي بما حذف وما أضيف وما تغير.
# الاستعمال:
#   python3 tools/draft_diff.py القديمة الجديدة [ملف_الإخراج.md]
# وكل من القديمة والجديدة إما ملف pdf أو txt، وإما رقم وثيقة على docs.unfccc.int مثل 10000351.
import difflib, os, re, subprocess, sys, tempfile, urllib.parse, urllib.request

BASE = "https://docs.unfccc.int"

def fetch(ref, tmp):
    if os.path.exists(ref):
        if ref.endswith(".pdf"):
            txt = os.path.join(tmp, os.path.basename(ref) + ".txt")
            subprocess.run(["pdftotext", "-layout", ref, txt], check=True)
            return open(txt, encoding="utf-8").read()
        return open(ref, encoding="utf-8").read()
    if not re.fullmatch(r"\d{6,9}", ref):
        sys.exit("المرجع ليس ملفا ولا رقم وثيقة: " + ref)
    page = subprocess.run(["curl", "-sSL", "-m", "60", f"{BASE}/documents/{ref}"], capture_output=True, text=True).stdout
    m = re.search(r'/documents/' + ref + r'/files/[^"]+', page)
    if not m:
        if "[UNPUBLISHED]" in page:
            sys.exit(f"الوثيقة {ref} سحبتها الأمانة من النشر، فاستعمل نسخة محفوظة منها (pdf أو txt).")
        sys.exit("لم يوجد رابط ملف في صفحة الوثيقة " + ref)
    url = BASE + urllib.parse.quote(m.group(0))
    pdf = os.path.join(tmp, ref + ".pdf")
    subprocess.run(["curl", "-sSL", "-m", "120", "-o", pdf, url], check=True)
    txt = pdf + ".txt"
    subprocess.run(["pdftotext", "-layout", pdf, txt], check=True)
    return open(txt, encoding="utf-8").read()

def version(t):
    m = re.search(r"Version\s+([\d/]+\s+[\d:]+)", t)
    return m.group(1) if m else "غير مذكورة"

def paras(t):
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\d+\s+CMA\s*\d*\s*[–-]?\s*[Aa]genda item\s*\d+\s*\(?[a-z]?\)?", " ", t)
    t = re.sub(r"([;.:])\d{0,2} (?=\d{1,3}\. [A-Z])", "\\1\n", t)
    parts = t.split("\n")
    out = []
    for p in parts:
        m = re.match(r"(\d{1,3})\. (.*)", p.strip())
        if m:
            body = re.sub(r"\s\d{1,2}\s(?=See|Decision|As set|Available|Contained)", " ", m.group(2))
            out.append((m.group(1), body.strip()))
    return out

def key(body):
    return re.sub(r"[^a-z ]", "", body.lower())[:400]

def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__ or "الاستعمال: draft_diff.py القديمة الجديدة [الإخراج]")
    with tempfile.TemporaryDirectory() as tmp:
        a_txt, b_txt = fetch(sys.argv[1], tmp), fetch(sys.argv[2], tmp)
    a, b = paras(a_txt), paras(b_txt)
    sm = difflib.SequenceMatcher(None, [key(x[1]) for x in a], [key(x[1]) for x in b], autojunk=False)
    lines = [f"# مقارنة المسودتين", "", f"القديمة: {version(a_txt)} ({len(a)} فقرة)، والجديدة: {version(b_txt)} ({len(b)} فقرة).", ""]
    olds, news, pairs = [], [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != "equal":
            olds += a[i1:i2]
            news += b[j1:j2]
    sim = lambda x, y: difflib.SequenceMatcher(None, x, y).ratio()
    def head(x, y):
        # تشابه أول ثلاثين كلمة، كي لا يفسد العنوان أو الحاشية الملتصقة بآخر الفقرة المطابقة
        return difflib.SequenceMatcher(None, x.split()[:30], y.split()[:30]).ratio()
    score = lambda x, y: max(sim(x, y), head(x, y))
    for nb, tb in list(news):
        best = max(olds, key=lambda o: score(o[1], tb), default=None)
        if best and (sim(best[1], tb) >= 0.6 or head(best[1], tb) >= 0.8):
            pairs.append((best, (nb, tb)))
            olds.remove(best)
            news.remove((nb, tb))
    pairs = [p for p in pairs if sim(p[0][1], p[1][1]) < 0.995]
    n = 0
    lines += ["## الفقرات المحذوفة", ""]
    for na, ta in olds:
        n += 1
        lines += [f"{n}. الفقرة {na}: {ta}", ""]
    lines += ["## الفقرات المعدلة", ""]
    for (na, ta), (nb, tb) in sorted(pairs, key=lambda p: sim(p[0][1], p[1][1])):
        n += 1
        lines += [f"{n}. الفقرة {na} (رقمها الجديد {nb})، ونسبة التشابه {round(sim(ta, tb)*100)} بالمئة.", f"   القديمة: {ta}", f"   الجديدة: {tb}", ""]
    lines += ["## الفقرات المضافة", ""]
    for nb, tb in news:
        n += 1
        lines += [f"{n}. الفقرة {nb}: {tb}", ""]
    if n == 0:
        lines.append("لا فرق في الفقرات المرقمة.")
    report = "\n".join(lines)
    if len(sys.argv) > 3:
        open(sys.argv[3], "w", encoding="utf-8").write(report)
        print("حفظ التقرير في " + sys.argv[3])
    else:
        print(report)

if __name__ == "__main__":
    main()
