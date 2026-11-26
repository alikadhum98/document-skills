#!/usr/bin/env python3
"""Conference setup helper for the conference-lifecycle skill.

Commands:
  new ID --title T --city C --start YYYY-MM-DD --end YYYY-MM-DD --tz ZONE [--from YYYY-MM-DD] [--out DIR]
      Create conferences/ID/conference.json from the template.
  prompts ID
      Print the morning and evening scheduled-task prompts and their cron lines as JSON.
  check ID
      Validate a conference file and list what is still missing.
  active
      Print the id of the active conference (status active), else the newest one.
"""
import argparse
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
CONF = ROOT / "conferences"
PROMPTS = pathlib.Path(__file__).resolve().parents[1] / "prompts"
ALLIANCE_AR = {"arab_group": "المجموعة العربية", "lmdc": "LMDC", "opec": "أوبك", "g77": "مجموعة ال77 والصين"}
FILE_AR = {"Article6": "المادة السادسة", "Mitigation": "التخفيف", "Transparency": "الشفافية والإبلاغ",
           "Finance": "التمويل", "Adaptation": "التكيف", "LossDamage": "الخسائر والأضرار",
           "ResponseMeasures-Trade": "تدابير الاستجابة والتجارة", "GST-JustTransition": "الحصيلة العالمية والانتقال العادل",
           "External": "المحافل الخارجية"}
# fixed minutes keep the runs off the hour and half hour
MORNING = (6, 47)
EVENING = (20, 53)


def load(cid, base=CONF):
    return json.loads((base / cid / "conference.json").read_text(encoding="utf-8"))


def day(s):
    return dt.date.fromisoformat(s)


def crons(start, end, hour, minute, tz):
    """One cron line per calendar month the dates touch."""
    out, d = [], start
    while d <= end:
        last = min(end, (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1))
        days = str(d.day) if d.day == last.day else f"{d.day}-{last.day}"
        out.append(f"CRON_TZ={tz} {minute} {hour} {days} {d.month} *")
        d = last + dt.timedelta(days=1)
    return out


def fill(text, c):
    scope = c["scope"]
    names = [FILE_AR.get(f, f) for f in scope.get("files", [])]
    scope_text = "، ".join(names) + (f" ({scope['file_notes']})" if scope.get("file_notes") else "")
    values = {
        "id": c["id"], "title": c["title"], "scope": scope_text,
        "coordination": "، ".join(ALLIANCE_AR.get(a, a) for a in scope.get("coordination", [])),
        "coordination_from": scope.get("coordination_from", c["start"]),
        "g77_query": c.get("mail_queries", {}).get("g77", ""),
        "news_mail": " أو ".join(n["mail"] for n in c.get("news_sources", [])) or "لا مصادر",
        "enb_folder": c["drive"].get("news_folders", {}).get("enb", {}).get("id", "") or "(أنشئ مجلد ENB أولا)",
        "g77_prefix": c.get("calendar_prefixes", {}).get("g77", "G77:"),
        "krisp_tag": c.get("krisp", {}).get("tag", c["id"]),
        "repo_daily": c["repo"]["daily"],
        "reference_name": c["files"]["intervention_reference"]["name"],
    }
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    if "{{" in text:
        raise SystemExit("unfilled placeholder in prompt: " + text[text.index("{{"):][:40])
    return text


def prompts(cid):
    c = load(cid)
    start, end, tz = day(c["start"]), day(c["end"]), c["timezone"]
    # the morning brief runs from the first day to the day after the end, the evening one from the day before
    return {
        "morning": {"name": f"{cid} موجز الصباح", "prompt": fill((PROMPTS / "morning.md").read_text(encoding="utf-8"), c),
                    "cron": crons(start, end + dt.timedelta(days=1), *MORNING, tz)},
        "evening": {"name": f"{cid} خلاصة المساء وأوراق الغد", "prompt": fill((PROMPTS / "evening.md").read_text(encoding="utf-8"), c),
                    "cron": crons(start - dt.timedelta(days=1), end, *EVENING, tz)},
        "enb_desktop": {"name": f"{cid} حفظ تقارير ENB", "prompt": fill((PROMPTS / "enb_desktop.md").read_text(encoding="utf-8"), c),
                        "cron": crons(start, end + dt.timedelta(days=4), 7, 41, tz),
                        "where": "Claude desktop app on the user's PC (Cowork scheduled task, browser available to the app; the user browses with Edge), not a cloud trigger"},
        "note": "cron lines repeat every year: disable all tasks at (اختم المؤتمر).",
    }


def check(cid):
    c = load(cid)
    missing = []
    if not c["drive"]["root_folder"].get("id"):
        missing.append("drive.root_folder.id")
    days = (day(c["end"]) - day(c["start"])).days + 1
    have = c["drive"].get("day_folders", {})
    want = [str(day(c["start"]) + dt.timedelta(days=i)) for i in range(days)]
    gaps = [d for d in want if d not in have]
    if gaps:
        missing.append("drive.day_folders: " + " ".join(gaps))
    if not c["sessions"].get("main"):
        missing.append("sessions.main")
    for key in ("morning", "evening"):
        if key not in c.get("triggers", {}):
            missing.append("triggers." + key)
    for p in c["repo"].values():
        if p and not (ROOT / p).exists() and c["status"] != "planned":
            missing.append("repo path not found: " + p)
    return {"id": cid, "status": c["status"], "missing": missing}


def active():
    confs = [p.parent.name for p in CONF.glob("*/conference.json") if p.parent.name != "_template"]
    data = [(load(i), i) for i in confs]
    act = [i for c, i in data if c["status"] == "active"]
    if act:
        return act[0]
    return max(data, key=lambda x: x[0]["start"])[1] if data else ""


def new(a):
    out = pathlib.Path(a.out) if a.out else CONF
    target = out / a.id / "conference.json"
    if target.exists():
        raise SystemExit(f"{target} exists already")
    c = json.loads((CONF / "_template" / "conference.json").read_text(encoding="utf-8"))
    c.update(id=a.id, title=a.title, city=a.city, country=a.country or "", start=a.start, end=a.end, timezone=a.tz, status="planned")
    day(a.start), day(a.end)
    c["scope"]["coordination_from"] = a.start_coord or a.start
    c["drive"]["root_folder"]["name"] = a.id
    c["files"]["intervention_reference"]["name"] = f"{a.id}_intervention_reference.json"
    c["repo"] = {k: f"conferences/{a.id}/{k}" for k in ("daily", "papers", "analysis")} | {"final_report": "", "handover": ""}
    c["krisp"] = {"name_prefix": a.id, "tag": a.id}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(target)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("id")
    n.add_argument("--title", required=True)
    n.add_argument("--city", required=True)
    n.add_argument("--start", required=True)
    n.add_argument("--end", required=True)
    n.add_argument("--tz", required=True)
    n.add_argument("--from", dest="start_coord")
    n.add_argument("--country")
    n.add_argument("--out")
    for name in ("prompts", "check"):
        sub.add_parser(name).add_argument("id")
    sub.add_parser("active")
    a = ap.parse_args()
    if a.cmd == "new":
        print(new(a))
    elif a.cmd == "prompts":
        print(json.dumps(prompts(a.id), ensure_ascii=False, indent=2))
    elif a.cmd == "check":
        print(json.dumps(check(a.id), ensure_ascii=False, indent=2))
    else:
        print(active())


if __name__ == "__main__":
    sys.exit(main())
