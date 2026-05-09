"""
الواجهة التفاعلية للمنظومة
التشغيل: python menu.py
قائمة عربية تفاعلية بالأسهم دون حاجة لتذكّر أوامر
"""

import os, sys, subprocess, datetime, time

ROOT = os.path.dirname(os.path.abspath(__file__))

# ===== تعريف القوائم =====
MAIN_MENU = [
    ("🔧", "تشغيل أداة واحدة",          "tools"),
    ("🚀", "تشغيل جميع الأدوات",         "run_all"),
    ("📊", "لوحة التحكم الشاملة",        "dashboard"),
    ("📦", "حزم المخرجات (ZIP)",          "package"),
    ("🗄️", "أرشفة المخرجات بالتاريخ",   "archive"),
    ("✅", "التحقق من اتساق البيانات",   "validate"),
    ("📋", "قوالب المؤتمرات الجاهزة",    "templates"),
    ("❌", "خروج",                         "exit"),
]

TOOLS_MENU = [
    ("📄", "مولّد تقرير BTR",            "btr"),
    ("🤝", "متابعة المادة السادسة",      "a6"),
    ("📈", "تحليل الجرد الوطني",        "ghg"),
    ("🎯", "عروض PowerPoint",            "pptx"),
    ("💰", "تتبع التمويل المناخي",       "finance"),
    ("🧭", "تقييم NDC Navigator",        "ndc"),
    ("🌿", "الخطة الوطنية للتكيف",      "nap"),
    ("🏦", "وثيقة مفهوم GCF",           "gcf"),
    ("📅", "إدارة وثائق المؤتمرات",     "conf"),
    ("⬅️", "رجوع",                        "back"),
]

TEMPLATES_MENU = [
    ("🌍", "قالب COP - مؤتمر الأطراف",          "cop"),
    ("🔬", "قالب SB - الهيئتان الفرعيتان",       "sb"),
    ("🌐", "قالب مجموعة الدول العربية",           "arab"),
    ("📝", "قالب اجتماع تقني",                    "technical"),
    ("⬅️", "رجوع",                                 "back"),
]

# ===== دوال المساعدة =====
def clear():
    os.system('cls' if os.name=='nt' else 'clear')

def print_header():
    print("\n" + "="*65)
    print("   🌍  منظومة أدوات سياسات المناخ - العراق")
    print(f"   📅  {datetime.datetime.now().strftime('%Y-%m-%d  %H:%M')}")
    print("="*65)

def print_menu(items, title=""):
    if title:
        print(f"\n  {title}")
        print("  " + "-"*40)
    for i, item in enumerate(items, 1):
        icon, label, _ = item
        print(f"  [{i}]  {icon}  {label}")
    print()

def get_choice(items):
    while True:
        try:
            choice = input("  اختر رقماً: ").strip()
            n = int(choice)
            if 1 <= n <= len(items):
                return items[n-1][2]
            print("  ⚠  رقم خارج النطاق، حاول مجدداً")
        except ValueError:
            print("  ⚠  أدخل رقماً صحيحاً")
        except KeyboardInterrupt:
            print("\n  تم الإلغاء")
            return "exit"

def run_cmd(cmd, label=""):
    if label:
        print(f"\n  ▶  {label}...")
        print("  " + "-"*50)
    start = time.time()
    result = subprocess.run(
        [sys.executable] + cmd.split()[1:] if cmd.startswith("python") else cmd.split(),
        cwd=ROOT
    )
    elapsed = time.time() - start
    if result.returncode == 0:
        print(f"\n  ✓  اكتمل في {elapsed:.1f} ثانية")
    else:
        print(f"\n  ✗  فشل (رمز {result.returncode})")
    input("\n  اضغط Enter للمتابعة...")

def run_tool(key):
    tool_map = {
        "btr":     ("python tools/btr_generator/btr_generator.py",       "مولّد تقرير BTR"),
        "a6":      ("python tools/article6_tracker/a6_tracker.py",       "متابعة المادة السادسة"),
        "ghg":     ("python tools/ghg_analyzer/ghg_analyzer.py",         "تحليل الجرد"),
        "pptx":    ("python tools/pptx_generator/pptx_generator.py",     "مولّد PowerPoint"),
        "finance": ("python tools/finance_tracker/finance_tracker.py",   "تتبع التمويل"),
        "ndc":     ("python tools/ndc_navigator/ndc_navigator.py",       "تقييم NDC"),
        "nap":     ("python tools/nap_central/nap_central.py",           "خطة التكيف"),
        "gcf":     ("python tools/gcf_prep/gcf_prep.py",                 "وثيقة GCF"),
        "conf":    ("python tools/conference_manager/conference_manager.py","إدارة المؤتمرات"),
    }
    if key in tool_map:
        cmd, label = tool_map[key]
        run_cmd(cmd, label)

def apply_template(key):
    """تطبيق قالب مؤتمر جاهز"""
    templates = {
        "cop": {
            "الاسم": "COP31 - الإمارات 2026",
            "المكان": "أبوظبي - الإمارات",
            "التاريخ": "نوفمبر 2026",
            "من": "2026-11-10",
            "إلى": "2026-11-21",
        },
        "sb": {
            "الاسم": "SB62 - بون 2026",
            "المكان": "بون - ألمانيا",
            "التاريخ": "يونيو 2026",
            "من": "2026-06-02",
            "إلى": "2026-06-13",
        },
        "arab": {
            "الاسم": "اجتماع مجموعة الدول العربية - التنسيقي",
            "المكان": "القاهرة - مصر",
            "التاريخ": "أبريل 2026",
            "من": "2026-04-15",
            "إلى": "2026-04-16",
        },
        "technical": {
            "الاسم": "ورشة عمل تقنية - الجرد الوطني",
            "المكان": "بغداد - العراق",
            "التاريخ": "مارس 2026",
            "من": "2026-03-10",
            "إلى": "2026-03-11",
        },
    }
    if key not in templates:
        return

    tmpl = templates[key]
    conf_path = os.path.join(ROOT, "tools/conference_manager/conf_data.py")
    content   = open(conf_path, encoding='utf-8').read()

    import re
    for field, value in [
        ("الاسم",    tmpl["الاسم"]),
        ("المكان",   tmpl["المكان"]),
        ("التاريخ",  tmpl["التاريخ"]),
        ("التاريخ_من", tmpl["من"]),
        ("التاريخ_إلى", tmpl["إلى"]),
    ]:
        pattern = rf'"{field}":\s*"[^"]*"'
        replacement = f'"{field}":           "{value}"'
        content = re.sub(pattern, replacement, content, count=1)

    open(conf_path, 'w', encoding='utf-8').write(content)
    print(f"\n  ✓  تم تطبيق قالب: {tmpl['الاسم']}")
    print(f"     المكان: {tmpl['المكان']}  |  التاريخ: {tmpl['التاريخ']}")

    regen = input("\n  هل تريد إعادة توليد وثيقة المؤتمر الآن؟ (y/n): ").strip().lower()
    if regen == 'y':
        run_cmd("python tools/conference_manager/conference_manager.py", "توليد وثيقة المؤتمر")
    else:
        input("\n  اضغط Enter للمتابعة...")

# ===== الحلقة الرئيسية =====
def main():
    while True:
        clear()
        print_header()
        print_menu(MAIN_MENU, "القائمة الرئيسية")
        choice = get_choice(MAIN_MENU)

        if choice == "exit":
            print("\n  إلى اللقاء!\n")
            break

        elif choice == "tools":
            clear(); print_header()
            print_menu(TOOLS_MENU, "اختر الأداة")
            tool = get_choice(TOOLS_MENU)
            if tool != "back":
                run_tool(tool)

        elif choice == "run_all":
            run_cmd("python run_all.py", "تشغيل جميع الأدوات")

        elif choice == "dashboard":
            run_cmd("python pipeline/integration_engine.py", "لوحة التحكم الشاملة")

        elif choice == "package":
            run_cmd("python extras/packager.py", "حزم المخرجات")

        elif choice == "archive":
            run_cmd("python extras/archiver.py", "أرشفة المخرجات")

        elif choice == "validate":
            run_cmd("python extras/validator.py", "التحقق من البيانات")

        elif choice == "templates":
            clear(); print_header()
            print_menu(TEMPLATES_MENU, "اختر قالب المؤتمر")
            tmpl = get_choice(TEMPLATES_MENU)
            if tmpl != "back":
                apply_template(tmpl)

if __name__ == "__main__":
    main()
