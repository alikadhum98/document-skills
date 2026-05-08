"""
النموذج الخامس: Climate Finance Data Portal
تتبع وتحليل التمويل المناخي الداخل للعراق
الرابط: https://unfccc.int/climatefinance
الفائدة: معرفة ما حصل عليه العراق من تمويل مناخي وما تبقى من فجوات
"""

import json

# ========== بيانات التمويل المناخي للعراق (نموذجية من البوابة) ==========
IRAQ_FINANCE = {
    "party": "Iraq",
    "currency": "USD",
    "data_source": "UNFCCC Climate Finance Data Portal / GEF / GCF",

    # تمويل GEF
    "GEF_projects": [
        {
            "id": "GEF-7-IRQ-001",
            "title": "تعزيز الشفافية المناخية وبناء نظام MRV الوطني",
            "status": "منفّذ",
            "amount_usd": 2500000,
            "cofinancing_usd": 5000000,
            "focal_area": "تغير المناخ",
            "implementing_agency": "UNDP",
            "approval_year": 2021,
            "sector": "شفافية وقدرات مؤسسية"
        },
        {
            "id": "GEF-7-IRQ-002",
            "title": "دعم إعداد التقرير الوطني الرابع للاتفاقية",
            "status": "مكتمل",
            "amount_usd": 350000,
            "cofinancing_usd": 0,
            "focal_area": "تغير المناخ",
            "implementing_agency": "UNEP",
            "approval_year": 2020,
            "sector": "إعداد التقارير"
        },
        {
            "id": "GEF-8-IRQ-001",
            "title": "إدارة الأراضي المستدامة في المناطق الجافة",
            "status": "نشط",
            "amount_usd": 4800000,
            "cofinancing_usd": 12000000,
            "focal_area": "تدهور الأراضي",
            "implementing_agency": "FAO",
            "approval_year": 2023,
            "sector": "AFOLU"
        }
    ],

    # تمويل صندوق المناخ الأخضر
    "GCF_projects": [
        {
            "id": "GCF-FP001-IRQ",
            "title": "تعزيز مرونة المجتمعات الزراعية في جنوب العراق",
            "status": "قيد المراجعة",
            "amount_usd": 28000000,
            "cofinancing_usd": 15000000,
            "accredited_entity": "UNDP",
            "submission_year": 2024,
            "sector": "تكيف زراعي"
        }
    ],

    # تمويل صندوق التكيف
    "Adaptation_Fund_projects": [],  # العراق لم يقدم طلبات بعد

    # الاحتياجات الواردة في NDC
    "NDC_finance_needs": {
        "total_usd_million": 88000,
        "mitigation_usd_million": 52000,
        "adaptation_usd_million": 36000,
        "timeframe": "2021-2030"
    }
}

def analyze_finance(data):
    """تحليل وضع التمويل المناخي"""
    gef_total = sum(p["amount_usd"] for p in data["GEF_projects"])
    gef_cofin = sum(p["cofinancing_usd"] for p in data["GEF_projects"])
    gcf_total = sum(p["amount_usd"] for p in data["GCF_projects"])

    total_received = gef_total + gcf_total
    total_needs    = data["NDC_finance_needs"]["total_usd_million"] * 1e6
    gap            = total_needs - total_received
    coverage_pct   = (total_received / total_needs) * 100

    print("=" * 65)
    print("تحليل التمويل المناخي - العراق")
    print("المصدر: بوابة UNFCCC للتمويل المناخي")
    print("=" * 65)
    print(f"\nصندوق GEF:")
    print(f"  عدد المشاريع:    {len(data['GEF_projects'])}")
    print(f"  إجمالي التمويل:  {gef_total/1e6:.2f} مليون دولار")
    print(f"  التمويل المشترك: {gef_cofin/1e6:.2f} مليون دولار")
    print(f"\nصندوق المناخ الأخضر (GCF):")
    print(f"  عدد المشاريع:    {len(data['GCF_projects'])}")
    print(f"  إجمالي التمويل:  {gcf_total/1e6:.2f} مليون دولار")
    print(f"\nاحتياجات NDC 2021-2030:")
    print(f"  الإجمالي:        {total_needs/1e9:.1f} مليار دولار")
    print(f"  تم تأمينه:       {total_received/1e6:.2f} مليون دولار")
    print(f"  الفجوة:          {gap/1e9:.2f} مليار دولار")
    print(f"  نسبة التغطية:    {coverage_pct:.3f}%")

    print("\n[ فرص التمويل غير المستغلة ]")
    opportunities = [
        "صندوق التكيف: لم تُقدَّم أي طلبات حتى الآن - فرصة مباشرة",
        "GCF Readiness: دعم تحضير المشاريع غير مُفعَّل بشكل كافٍ",
        "GEF-8: فترة التمويل الحالية 2022-2026 مفتوحة لمشاريع إضافية",
        "LDCF/SCCF: العراق مؤهل كدولة نامية للحصول على تمويل إضافي",
    ]
    for op in opportunities:
        print(f"  • {op}")

    return {
        "gef_total": gef_total,
        "gcf_total": gcf_total,
        "total_received": total_received,
        "gap": gap,
        "coverage_pct": round(coverage_pct, 4)
    }

analysis = analyze_finance(IRAQ_FINANCE)
IRAQ_FINANCE["analysis"] = analysis

out = "/home/claude/skills-repo/demos/unfccc/output_u05_climate_finance_tracker.json"
with open(out, 'w', encoding='utf-8') as f:
    json.dump(IRAQ_FINANCE, f, ensure_ascii=False, indent=2)
print(f"\nتم حفظ البيانات: {out}")
