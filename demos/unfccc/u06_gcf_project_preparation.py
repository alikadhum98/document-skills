"""
النموذج السادس: Green Climate Fund - Project Preparation
أداة لتحضير وثيقة مفهوم المشروع (Concept Note) لصندوق GCF
الرابط: https://www.greenclimate.fund/
الفائدة: تسريع تحضير مشاريع GCF العراقية بقالب جاهز
"""

import json

def build_gcf_concept_note(project_data):
    """بناء وثيقة مفهوم المشروع وفق قالب GCF"""

    concept_note = {
        # القسم أ: معلومات المشروع
        "A_project_info": {
            "title": project_data["title"],
            "country": "Iraq",
            "NDA": "Ministry of Environment",
            "NDA_focal_point": "قسم التمويل المناخي",
            "accredited_entity": project_data.get("ae", "UNDP"),
            "project_size": project_data["size_category"],
            "modality": project_data.get("modality", "مشروع"),
            "result_area": project_data["result_area"],
            "GCF_funding_requested_usd": project_data["gcf_amount"],
            "cofinancing_usd": project_data.get("cofinancing", 0),
            "duration_years": project_data.get("duration", 5)
        },

        # القسم ب: المشكلة والفرصة
        "B_problem_and_context": {
            "climate_vulnerability": project_data["vulnerability_context"],
            "current_barriers": project_data["barriers"],
            "theory_of_change": project_data["theory_of_change"]
        },

        # القسم ج: المخرجات والأهداف
        "C_expected_results": {
            "mitigation_target": project_data.get("mitigation_Gg", None),
            "adaptation_beneficiaries": project_data.get("beneficiaries", None),
            "outputs": project_data["outputs"]
        },

        # القسم د: متطلبات GCF
        "D_gcf_requirements": {
            "paradigm_shift_potential": project_data["paradigm_shift"],
            "country_ownership": "تستند إلى NDC العراق والخطة الوطنية للتكيف",
            "gender_consideration": project_data.get("gender", "سيُدمج تحليل النوع الاجتماعي في مرحلة التصميم التفصيلي"),
            "environmental_safeguards": "سيُطبَّق إطار الضمانات البيئية والاجتماعية لـ GCF",
            "monitoring_framework": "نظام MRV مرتبط بمنظومة الشفافية الوطنية"
        },

        # ملخص التكاليف
        "E_cost_summary": {
            "component_costs": project_data.get("components", []),
            "management_fee_pct": 8.5,
            "total_gcf": project_data["gcf_amount"],
            "total_cofinancing": project_data.get("cofinancing", 0),
            "total_project": project_data["gcf_amount"] + project_data.get("cofinancing", 0)
        }
    }

    return concept_note

# ========== مشروع نموذجي: تعزيز مرونة قطاع المياه ==========
water_project = {
    "title": "تعزيز مرونة قطاع المياه في ظل تغير المناخ في العراق",
    "size_category": "متوسط (10-50 مليون دولار)",
    "result_area": "تكيف - توافر المياه وتأمين الأمن الغذائي",
    "gcf_amount": 35000000,
    "cofinancing": 20000000,
    "ae": "UNDP",
    "duration": 6,
    "vulnerability_context": (
        "يواجه العراق ضغطاً متصاعداً على موارد المياه جراء ارتفاع درجات الحرارة "
        "وانخفاض هطول الأمطار وتراجع منسوب نهري دجلة والفرات. "
        "القطاع الزراعي يستهلك 85% من المياه المتاحة وهو الأكثر تأثراً."
    ),
    "barriers": [
        "ضعف كفاءة الري التقليدي (20-30% فقط)",
        "غياب منظومة بيانات هيدرولوجية متكاملة",
        "محدودية التمويل لتحديث البنية التحتية المائية",
        "ضعف قدرات المزارعين على التكيف مع شح المياه"
    ],
    "theory_of_change": (
        "من خلال نشر تقنيات الري الحديثة وبناء قدرات 50,000 مزارع "
        "وتطوير منظومة إنذار مبكر بالجفاف، سيرتفع إنتاج الغذاء بنسبة 30% "
        "مع خفض استهلاك المياه 40% بحلول 2030."
    ),
    "beneficiaries": "1.2 مليون مزارع في محافظات ذي قار وميسان والمثنى",
    "outputs": [
        "تأهيل 150,000 هكتار بأنظمة ري حديثة",
        "إنشاء 12 محطة رصد هيدرولوجي",
        "تدريب 500 مهندس زراعي ومسؤول محلي",
        "تطوير خطط إدارة المياه لـ 20 محافظة"
    ],
    "paradigm_shift": (
        "تحويل قطاع الزراعة من الاعتماد على الري التقليدي إلى نظام مائي ذكي "
        "مُدار بالبيانات، مع تضمين الاعتبارات المناخية في السياسة المائية الوطنية."
    ),
    "components": [
        {"المكوّن": "تقنيات الري الحديث", "التكلفة_USD": 18000000},
        {"المكوّن": "منظومة البيانات والرصد", "التكلفة_USD": 6000000},
        {"المكوّن": "بناء القدرات والتدريب", "التكلفة_USD": 5000000},
        {"المكوّن": "إدارة المشروع والمتابعة", "التكلفة_USD": 4000000},
        {"المكوّن": "تقييم الأثر والتقييم", "التكلفة_USD": 2000000},
    ]
}

cn = build_gcf_concept_note(water_project)

print("=" * 65)
print("وثيقة مفهوم المشروع - صندوق المناخ الأخضر")
print(f"المشروع: {cn['A_project_info']['title']}")
print("=" * 65)
print(f"\nحجم المشروع:       {cn['A_project_info']['project_size']}")
print(f"تمويل GCF:         {cn['A_project_info']['GCF_funding_requested_usd']/1e6:.1f} مليون دولار")
print(f"التمويل المشترك:   {cn['A_project_info']['cofinancing_usd']/1e6:.1f} مليون دولار")
print(f"إجمالي المشروع:    {cn['E_cost_summary']['total_project']/1e6:.1f} مليون دولار")
print(f"\nالمستفيدون: {cn['C_expected_results']['adaptation_beneficiaries']}")
print(f"\nمكوّنات المشروع:")
for comp in cn["E_cost_summary"]["component_costs"]:
    print(f"  {comp['المكوّن']:<35} {comp['التكلفة_USD']/1e6:.1f}م$")

out = "/home/claude/skills-repo/demos/unfccc/output_u06_gcf_concept_note.json"
with open(out, 'w', encoding='utf-8') as f:
    json.dump(cn, f, ensure_ascii=False, indent=2)
print(f"\nتم حفظ وثيقة المفهوم: {out}")
