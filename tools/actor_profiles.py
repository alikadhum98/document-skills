#!/usr/bin/env python3
"""Build one profile per negotiating actor from references/party_positions.json.

Each profile gathers, across sessions and conferences: the sessions where the actor spoke,
its tone over time, the camps it took, its positions, its English formulations with their dates,
its tactics and how Iraq can use them. Battle cards read these profiles for part three
(who will speak, their earlier phrases, their concessions).

Usage:
  python3 tools/actor_profiles.py                 rebuild references/actor_profiles.json
  python3 tools/actor_profiles.py --show Japan    print one profile as readable text
  python3 tools/actor_profiles.py --find fees     actors whose positions or phrases mention a word
"""
import argparse
import collections
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "references" / "party_positions.json"
OUT = ROOT / "references" / "actor_profiles.json"

ALIASES = {
    "EU": "European Union",
    "UK": "United Kingdom",
    "AGN": "African Group",
    "African Group (AGN)": "African Group",
    "CfRN": "Coalition for Rainforest Nations",
    "United Arab Emirates for Arab Group": "Arab Group",
}
SKIP = re.compile(r"^(unidentified|unnamed|developed party|co-facilitator|chair)", re.I)
TONE_RANK = {"1_support": 1, "2_conditional_openness": 2, "3_soft_opposition": 3, "4_strong_opposition": 4, "5_red_line": 5}


def actors_of(raw):
    """Return [(name, certain)] for one actor field, dropping unidentified speakers."""
    raw = raw.strip()
    certain = not re.search(r"likely|unclear|\?", raw, re.I)
    base = re.sub(r"\s*\(.*?\)\s*", " ", raw).strip()
    if SKIP.match(base) or not base:
        return []
    parts = [p.strip() for p in re.split(r",| and ", base) if p.strip()]
    if len(parts) > 1 and any(SKIP.match(p) or p.lower().startswith("others") or p.lower().startswith("a small") for p in parts):
        parts = [p for p in parts if not (SKIP.match(p) or p.lower().startswith("others") or p.lower().startswith("a small"))]
    return [(ALIASES.get(p, p), certain) for p in parts]


def build():
    entries = json.loads(SRC.read_text(encoding="utf-8"))["entries"]
    prof = {}
    for e in sorted(entries, key=lambda x: x["date"]):
        for name, certain in actors_of(e["actor"]):
            p = prof.setdefault(name, {"actor": name, "appearances": [], "camps": collections.Counter(),
                                       "positions": [], "formulations_en": [], "tactics": [], "use_for_iraq": []})
            m = re.match(r"[1-5]_[a-z_]+", e.get("tone") or "")
            p["appearances"].append({"date": e["date"], "session": e["session"], "tone": m.group(0) if m else "",
                                     "tone_note": (e.get("tone") or "")[m.end():].strip() if m else (e.get("tone") or ""),
                                     "attribution": e["attribution"] if certain else "uncertain_actor",
                                     "entry": e["id"]})
            p["camps"][e["camp"]] += 1
            for k in ("positions", "formulations_en"):
                for t in e.get(k, []):
                    if t and t not in [x["text"] for x in p[k]]:
                        p[k].append({"text": t, "date": e["date"], "entry": e["id"]})
            for k in ("tactics", "use_for_iraq"):
                t = e.get(k)
                if t and t not in [x["text"] for x in p[k]]:
                    p[k].append({"text": t, "date": e["date"]})
    out = []
    for p in prof.values():
        tones = [TONE_RANK.get(a["tone"], 0) for a in p["appearances"] if a["tone"] in TONE_RANK]
        p["camps"] = dict(p["camps"].most_common())
        ranked = [a["tone"] for a in p["appearances"] if a["tone"] in TONE_RANK]
        p["tone_first_last"] = [ranked[0], ranked[-1]] if ranked else ["", ""]
        p["tone_average"] = round(sum(tones) / len(tones), 1) if tones else None
        p["count"] = len(p["appearances"])
        out.append(p)
    out.sort(key=lambda p: (-p["count"], p["actor"]))
    return {"about": "ملفات المفاوضين مبنية آليا من references/party_positions.json بالأداة tools/actor_profiles.py. لا تعدل يدويا، بل يعدل السجل ثم يعاد البناء.",
            "source_entries": len(entries), "actors": out}


def show(data, name):
    for p in data["actors"]:
        if p["actor"].lower() == name.lower():
            print(f"{p['actor']}: {p['count']} مداخلة، النبرة من {p['tone_first_last'][0]} إلى {p['tone_first_last'][1]}، المعسكرات {p['camps']}")
            for a in p["appearances"]:
                print(f"  {a['date']} {a['session']} [{a['tone']}, {a['attribution']}]")
            print("الصيغ:")
            for f in p["formulations_en"]:
                print(f"  {f['date']}: {f['text']}")
            print("الاستعمال للعراق:")
            for u in p["use_for_iraq"]:
                print(f"  {u['date']}: {u['text']}")
            return
    raise SystemExit("لا ملف بهذا الاسم")


def find(data, word):
    rx = re.compile(re.escape(word), re.I)
    for p in data["actors"]:
        hits = [x for k in ("positions", "formulations_en") for x in p[k] if rx.search(x["text"])]
        if hits:
            print(f"{p['actor']} ({len(hits)}):")
            for h in hits[:4]:
                print(f"  {h['date']}: {h['text']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show")
    ap.add_argument("--find")
    a = ap.parse_args()
    data = build()
    if a.show:
        show(data, a.show)
    elif a.find:
        find(data, a.find)
    else:
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{len(data['actors'])} actors from {data['source_entries']} entries -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
