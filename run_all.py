"""
المشغّل الرئيسي لمنظومة أدوات سياسات المناخ - العراق
التشغيل: python run_all.py
أو تشغيل أداة واحدة: python run_all.py btr
"""

import sys, os, time, datetime

TOOLS = {
    "btr":      {"الاسم":"مولّد تقرير BTR",           "المسار":"tools/btr_generator/btr_generator.py",        "الوصف":"تقرير الشفافية الثنائي العربي"},
    "a6":       {"الاسم":"متابعة المادة السادسة",      "المسار":"tools/article6_tracker/a6_tracker.py",        "الوصف":"تتبع مفاوضات ITMOs والتعديلات المقابلة"},
    "ghg":      {"الاسم":"تحليل الجرد الوطني",        "المسار":"tools/ghg_analyzer/ghg_analyzer.py",          "الوصف":"رسوم بيانية وإحصاءات الانبعاثات"},
    "pptx":     {"الاسم":"مولّد عروض المفاوضات",       "المسار":"tools/pptx_generator/pptx_generator.py",      "الوصف":"PowerPoint للمؤتمرات والمفاوضات"},
    "finance":  {"الاسم":"تتبع التمويل المناخي",       "المسار":"tools/finance_tracker/finance_tracker.py",    "الوصف":"تحليل فجوات GCF ومصادر التمويل"},
    "ndc":      {"الاسم":"تقييم NDC Navigator",        "المسار":"tools/ndc_navigator/ndc_navigator.py",        "الوصف":"تقييم المساهمة الوطنية على المسارات السبعة"},
    "nap":      {"الاسم":"الخطة الوطنية للتكيف",      "المسار":"tools/nap_central/nap_central.py",            "الوصف":"مصفوفة NAP وإجراءات التكيف القطاعية"},
    "gcf":      {"الاسم":"وثيقة مفهوم GCF",           "المسار":"tools/gcf_prep/gcf_prep.py",                  "الوصف":"مولّد Concept Note لصندوق المناخ الأخضر"},
    "conf":     {"الاسم":"إدارة وثائق المؤتمرات",     "المسار":"tools/conference_manager/conference_manager.py","الوصف":"ورقة إحاطة الوفد وجدول الجلسات ومتابعة الإجراءات"},
    "dashboard":{"الاسم":"لوحة التحكم الشاملة",      "المسار":"pipeline/integration_engine.py",               "الوصف":"ربط جميع الأدوات ولوحة المؤشرات المجمّعة"},
}

def separator(char="=", n=60):
    print(char * n)

def run_tool(key):
    tool = TOOLS[key]
    print(f"\n▶  {tool['الاسم']} - {tool['الوصف']}")
    separator("-")
    start = time.time()
    ret   = os.system(f"python {tool['المسار']}")
    elapsed = time.time() - start
    if ret == 0:
        print(f"✓  اكتملت في {elapsed:.1f} ثانية")
        return True
    else:
        print(f"✗  فشلت (رمز الخطأ: {ret})")
        return False

def run_all():
    separator()
    print("منظومة أدوات سياسات المناخ - العراق")
    print(f"التشغيل: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    separator()

    results = {}
    total_start = time.time()

    for key in TOOLS:
        success = run_tool(key)
        results[key] = success

    total = time.time() - total_start
    separator()
    print(f"\nالنتائج الكاملة ({total:.1f} ثانية إجمالاً):")
    separator("-")
    for key, success in results.items():
        icon = "✓" if success else "✗"
        print(f"  {icon}  {TOOLS[key]['الاسم']}")

    passed = sum(results.values())
    print(f"\n  {passed}/{len(TOOLS)} أدوات اكتملت بنجاح")

    if passed == len(TOOLS):
        print("\n✅ جميع المخرجات جاهزة في مجلدات tools/*/")
    else:
        failed = [TOOLS[k]["الاسم"] for k, v in results.items() if not v]
        print(f"\n⚠  فشلت: {', '.join(failed)}")

def print_help():
    separator()
    print("الاستخدام:")
    print("  python run_all.py           ← تشغيل جميع الأدوات")
    for key, tool in TOOLS.items():
        print(f"  python run_all.py {key:<8} ← {tool['الاسم']}")
    separator()

if __name__ == "__main__":
    if len(sys.argv) == 1:
        run_all()
    elif sys.argv[1] == "help":
        print_help()
    elif sys.argv[1] in TOOLS:
        run_tool(sys.argv[1])
    else:
        print(f"أداة غير معروفة: {sys.argv[1]}")
        print_help()
