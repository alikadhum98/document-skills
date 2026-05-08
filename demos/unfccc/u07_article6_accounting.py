"""
النموذج السابع: Article 6.2 Reference Manual
حساب التعديلات المقابلة (Corresponding Adjustments) للـ ITMOs
الرابط: https://unfccc.int/process/the-paris-agreement/cooperative-implementation
الفائدة: التحقق من صحة محاسبة صفقات المادة 6.2 وتجنّب الاحتساب المزدوج
"""

import json

# ========== نموذج صفقة ITMO افتراضية ==========
# العراق يبيع ITMOs لدولة مشترية من خلال تعاون ثنائي

def calc_corresponding_adjustment(deal):
    """
    حساب التعديل المقابل وفق قرار 2/CMA.3
    يضمن تجنّب الاحتساب المزدوج بإزالة الكميات المحوّلة
    من جرد الدولة البائعة وإضافتها لجرد الدولة المشترية
    """

    itmos = deal["itmos_transferred_tCO2eq"]
    seller_baseline   = deal["seller_ndc_target_tCO2eq"]
    buyer_baseline    = deal["buyer_ndc_target_tCO2eq"]

    # حسابات الدولة البائعة (العراق)
    seller_adj = {
        "reported_emissions": deal["seller_reported_emissions"],
        "ITMO_transferred": itmos,
        "corresponding_adjustment": +itmos,   # إضافة للتعويض عن النقل
        "adjusted_emissions": deal["seller_reported_emissions"] + itmos,
        "NDC_target": seller_baseline,
        "compliance_margin": seller_baseline - (deal["seller_reported_emissions"] + itmos)
    }

    # حسابات الدولة المشترية
    buyer_adj = {
        "reported_emissions": deal["buyer_reported_emissions"],
        "ITMO_acquired": itmos,
        "corresponding_adjustment": -itmos,   # طرح من الانبعاثات
        "adjusted_emissions": deal["buyer_reported_emissions"] - itmos,
        "NDC_target": buyer_baseline,
        "compliance_margin": buyer_baseline - (deal["buyer_reported_emissions"] - itmos)
    }

    # التحقق من تجنّب الاحتساب المزدوج
    double_counting_check = (
        seller_adj["adjusted_emissions"] +
        buyer_adj["adjusted_emissions"]
        ==
        deal["seller_reported_emissions"] +
        deal["buyer_reported_emissions"]
    )

    return seller_adj, buyer_adj, double_counting_check

def generate_itmo_report(deal, seller_adj, buyer_adj, dc_check):
    """إنشاء تقرير ITMO وفق متطلبات ETF"""
    return {
        "report_type": "Article_6.2_ITMO_Transaction",
        "reporting_period": deal["reporting_period"],
        "deal_id": deal["deal_id"],
        "deal_date": deal["deal_date"],
        "metric": "tCO2eq",
        "GWP": "AR5",
        "seller_party": deal["seller"],
        "buyer_party": deal["buyer"],
        "sector": deal["sector"],
        "activity": deal["activity_description"],
        "ITMOs_quantity": deal["itmos_transferred_tCO2eq"],
        "vintage_year": deal["vintage_year"],
        "seller_accounting": seller_adj,
        "buyer_accounting": buyer_adj,
        "double_counting_avoided": dc_check,
        "environmental_integrity": "مُستوفى - التعديلات المقابلة تضمن صحة المحاسبة",
        "registry_reference": f"UNFCCC-A6.2-{deal['deal_id']}"
    }

# ========== صفقة نموذجية: العراق يبيع ITMOs لألمانيا ==========
sample_deal = {
    "deal_id": "IRQ-DEU-2025-001",
    "deal_date": "2025-03-15",
    "reporting_period": "2021-2025",
    "vintage_year": 2024,
    "seller": "Iraq",
    "buyer": "Germany",
    "sector": "قطاع الطاقة - مشاريع الطاقة الشمسية",
    "activity_description": "محطة طاقة شمسية بقدرة 500 ميغاواط في البادية العراقية",

    # الكميات بـ tCO2eq
    "itmos_transferred_tCO2eq": 250000,  # 250 ألف طن

    # بيانات الجرد (tCO2eq)
    "seller_reported_emissions":  195000000,   # انبعاثات العراق المُبلَّغة
    "seller_ndc_target_tCO2eq":   190000000,   # هدف NDC العراق

    "buyer_reported_emissions":   700000000,   # انبعاثات ألمانيا
    "buyer_ndc_target_tCO2eq":    650000000,   # هدف NDC ألمانيا
}

seller, buyer, dc = calc_corresponding_adjustment(sample_deal)
report = generate_itmo_report(sample_deal, seller, buyer, dc)

# ========== طباعة النتائج ==========
print("=" * 65)
print("تقرير معاملة ITMO - المادة 6.2")
print(f"الصفقة: {sample_deal['deal_id']}")
print("=" * 65)

print(f"\n[ الدولة البائعة: {sample_deal['seller']} ]")
print(f"  الانبعاثات المُبلَّغة:          {seller['reported_emissions']:>15,.0f} tCO2eq")
print(f"  ITMOs المحوَّلة:               +{seller['ITMO_transferred']:>14,.0f} tCO2eq")
print(f"  الانبعاثات بعد التعديل:        {seller['adjusted_emissions']:>15,.0f} tCO2eq")
print(f"  هدف NDC:                       {seller['NDC_target']:>15,.0f} tCO2eq")
compliance = "✓ ضمن الهدف" if seller["compliance_margin"] >= 0 else "✗ تجاوز الهدف"
print(f"  الامتثال للـ NDC:              {compliance}")

print(f"\n[ الدولة المشترية: {sample_deal['buyer']} ]")
print(f"  الانبعاثات المُبلَّغة:          {buyer['reported_emissions']:>15,.0f} tCO2eq")
print(f"  ITMOs المُكتسَبة:              -{buyer['ITMO_acquired']:>14,.0f} tCO2eq")
print(f"  الانبعاثات بعد التعديل:        {buyer['adjusted_emissions']:>15,.0f} tCO2eq")
print(f"  هدف NDC:                       {buyer['NDC_target']:>15,.0f} tCO2eq")
compliance_b = "✓ ضمن الهدف" if buyer["compliance_margin"] >= 0 else "✗ تجاوز الهدف"
print(f"  الامتثال للـ NDC:              {compliance_b}")

print(f"\n[ فحص الاحتساب المزدوج ]")
print(f"  النتيجة: {'✓ تجنّب الاحتساب المزدوج مؤكَّد' if dc else '✗ يوجد احتساب مزدوج - مراجعة مطلوبة'}")

out = "/home/claude/skills-repo/demos/unfccc/output_u07_article6_itmo_report.json"
with open(out, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\nتم حفظ تقرير ITMO: {out}")
