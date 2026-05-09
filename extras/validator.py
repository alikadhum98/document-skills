"""
أداة التحقق من اتساق البيانات بين الأدوات
التشغيل: python extras/validator.py
"""

import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'core'))

from shared_data import (EMISSIONS, NDC, FINANCE_MOBILIZED,
                          ARTICLE6, NDC_NAVIGATOR_SCORES, LATEST_YEAR)

CHECKS = []
WARNINGS = []
ERRORS   = []

def check(condition, message, category="info"):
    if condition:
        CHECKS.append(("✓", message, "green"))
    else:
        if category == "error":
            ERRORS.append(("✗", message, "red"))
        else:
            WARNINGS.append(("⚠", message, "yellow"))

def run_validations():
    # ===== فحص الانبعاثات والـ NDC =====
    latest = EMISSIONS.get(LATEST_YEAR, 0)
    ndc_target = NDC["هدف_غير_مشروط_tCO2eq"] / 1000

    check(latest > 0,
          f"بيانات الانبعاثات {LATEST_YEAR} موجودة: {latest:,} Gg")

    check(latest <= ndc_target,
          f"الانبعاثات ضمن هدف NDC ({latest:,} vs {ndc_target:,} Gg)",
          "error" if latest > ndc_target * 1.1 else "warning")

    check(NDC["هدف_مشروط_tCO2eq"] < NDC["هدف_غير_مشروط_tCO2eq"],
          "الهدف المشروط أطموح من غير المشروط")

    check(NDC["BAU_2030_tCO2eq"] > NDC["هدف_غير_مشروط_tCO2eq"],
          "مسار BAU أعلى من الهدف غير المشروط")

    # ===== فحص التمويل =====
    total_mob = FINANCE_MOBILIZED["إجمالي_مليون"]
    need      = NDC["احتياج_تمويل_مليار"] * 1000
    cov       = total_mob / need * 100

    check(total_mob > 0,
          f"بيانات التمويل موجودة: ${total_mob:.1f}M مُعبَّأ")

    check(cov >= 1.0,
          f"تغطية التمويل مقبولة ({cov:.3f}%)",
          "warning")

    check(FINANCE_MOBILIZED["GEF_مليون"] > 0,
          "تمويل GEF موجود")

    # ===== فحص NDC Navigator =====
    avg = sum(NDC_NAVIGATOR_SCORES.values()) / len(NDC_NAVIGATOR_SCORES)
    check(len(NDC_NAVIGATOR_SCORES) == 7,
          f"جميع مسارات Navigator السبعة محددة")

    check(all(1 <= v <= 5 for v in NDC_NAVIGATOR_SCORES.values()),
          "درجات Navigator ضمن النطاق المقبول (1-5)")

    check(avg >= 3.0,
          f"متوسط Navigator مقبول ({avg:.1f}/5.0)",
          "warning")

    # ===== فحص المادة السادسة =====
    itmos = ARTICLE6["ITMOs_سنوية"]
    check(itmos > 0,
          f"بيانات ITMOs موجودة: {itmos:,} tCO2eq/سنة")

    # التحقق من عدم تجاوز الهدف بسبب ITMOs
    adj_emissions = latest + (itmos * 10 / 1000)  # تقدير 10 سنوات
    check(adj_emissions <= ndc_target,
          f"الانبعاثات بعد تعديل ITMOs ضمن الهدف",
          "warning")

    # ===== فحص وجود ملفات الأدوات =====
    tool_files = [
        "tools/btr_generator/btr_generator.py",
        "tools/article6_tracker/a6_tracker.py",
        "tools/ghg_analyzer/ghg_analyzer.py",
        "tools/pptx_generator/pptx_generator.py",
        "tools/finance_tracker/finance_tracker.py",
        "tools/ndc_navigator/ndc_navigator.py",
        "tools/nap_central/nap_central.py",
        "tools/gcf_prep/gcf_prep.py",
        "tools/conference_manager/conference_manager.py",
        "pipeline/integration_engine.py",
        "core/shared_data.py",
    ]
    for tf in tool_files:
        exists = os.path.exists(os.path.join(ROOT, tf))
        check(exists, f"ملف الأداة موجود: {tf}", "warning")

def print_results():
    print("\n" + "="*60)
    print("  نتائج التحقق من اتساق البيانات")
    print("="*60)

    total  = len(CHECKS) + len(WARNINGS) + len(ERRORS)
    passed = len(CHECKS)

    if ERRORS:
        print(f"\n  ✗  أخطاء ({len(ERRORS)}):")
        for icon, msg, _ in ERRORS:
            print(f"     {icon}  {msg}")

    if WARNINGS:
        print(f"\n  ⚠  تحذيرات ({len(WARNINGS)}):")
        for icon, msg, _ in WARNINGS:
            print(f"     {icon}  {msg}")

    print(f"\n  ✓  فحوصات ناجحة ({passed}):")
    for icon, msg, _ in CHECKS[:5]:
        print(f"     {icon}  {msg}")
    if len(CHECKS) > 5:
        print(f"     ... و{len(CHECKS)-5} فحصاً آخر")

    print(f"\n{'='*60}")
    status = "✅ ممتاز" if not ERRORS and not WARNINGS else \
             "⚠  تحذيرات" if not ERRORS else "❌ أخطاء"
    print(f"  النتيجة الكلية: {status}  ({passed}/{total} ناجح)")

    if ERRORS:
        print(f"\n  الإجراء المطلوب: عدّل core/shared_data.py وأصلح الأخطاء أعلاه")
    elif WARNINGS:
        print(f"\n  الإجراء المقترح: راجع التحذيرات وحدّث البيانات إن لزم")
    else:
        print(f"\n  جميع البيانات متسقة - يمكن التشغيل بأمان ✓")

    return len(ERRORS) == 0

if __name__ == "__main__":
    print("="*60)
    print("  أداة التحقق من اتساق البيانات")
    print("="*60)
    run_validations()
    success = print_results()
    sys.exit(0 if success else 1)
