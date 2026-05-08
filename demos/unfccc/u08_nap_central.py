"""
النموذج الثامن: NAP Central
بناء مصفوفة الخطة الوطنية للتكيف (NAP) للعراق
الرابط: https://napcentral.org/
الفائدة: هيكلة خطة التكيف الوطنية بما يتوافق مع متطلبات الاتفاقية
"""

import json

# ========== مصفوفة NAP العراق ==========
iraq_nap = {
    "party": "Iraq",
    "nap_title": "الخطة الوطنية للتكيف مع تغير المناخ - العراق 2025-2035",
    "status": "قيد الإعداد",
    "lead_ministry": "وزارة البيئة",
    "coordination_body": "اللجنة الوطنية لتغير المناخ",
    "timeframe": "2025-2035",

    # ===== المرحلة الأولى: التأسيس =====
    "phase_1_foundation": {
        "title": "تهيئة الأرضية وتقييم الثغرات",
        "duration": "6 أشهر",
        "activities": [
            {
                "activity": "مراجعة السياسات والخطط القطاعية القائمة",
                "responsible": "وزارة البيئة",
                "output": "تقرير مراجعة شامل",
                "budget_usd": 150000
            },
            {
                "activity": "تقييم الثغرات في منظومة التكيف الوطنية",
                "responsible": "وزارة البيئة / UNDP",
                "output": "تقرير تقييم الثغرات",
                "budget_usd": 200000
            }
        ]
    },

    # ===== المرحلة الثانية: تقييم الهشاشة =====
    "phase_2_vulnerability": {
        "title": "تقييم المناخ والهشاشة والأثر",
        "priority_sectors": [
            {
                "sector": "المياه",
                "vulnerability_level": "بالغة",
                "key_risks": [
                    "تراجع تدفق نهري دجلة والفرات بنسبة 30-60% بحلول 2050",
                    "ارتفاع ملوحة المياه في الجنوب",
                    "شحّ المياه الجوفية في وسط وغرب العراق"
                ],
                "adaptation_options": [
                    "تطوير منظومة الري الحديث",
                    "بناء خزانات استراتيجية للمياه",
                    "معالجة وإعادة استخدام المياه العادمة"
                ],
                "kpi_2030": "رفع كفاءة استخدام المياه من 30% إلى 60%"
            },
            {
                "sector": "الزراعة والأمن الغذائي",
                "vulnerability_level": "عالية",
                "key_risks": [
                    "ارتفاع درجات الحرارة يقلص مواسم الزراعة",
                    "تزايد الجفاف وظاهرة التصحر",
                    "تراجع إنتاجية القمح والشعير بنسبة 20-40%"
                ],
                "adaptation_options": [
                    "تطوير أصناف نباتية مقاومة للجفاف والحرارة",
                    "توسيع الزراعة المحمية",
                    "منظومة تأمين زراعي مرتبطة بالمناخ"
                ],
                "kpi_2030": "تحقيق الاكتفاء الذاتي من القمح بنسبة 50%"
            },
            {
                "sector": "الصحة",
                "vulnerability_level": "عالية",
                "key_risks": [
                    "موجات حرارة شديدة تتجاوز 50 درجة",
                    "انتشار الأمراض المنقولة بالمياه",
                    "تدهور جودة الهواء بفعل العواصف الترابية"
                ],
                "adaptation_options": [
                    "تطوير نظام إنذار مبكر بموجات الحرارة",
                    "تحسين منظومة الصرف الصحي في الريف",
                    "بناء مراكز إيواء مُكيَّفة في المدن"
                ],
                "kpi_2030": "خفض الوفيات المرتبطة بالحرارة 30%"
            },
            {
                "sector": "الطاقة",
                "vulnerability_level": "متوسطة",
                "key_risks": [
                    "انخفاض كفاءة محطات الطاقة في الحرارة العالية",
                    "زيادة الطلب على التبريد صيفاً"
                ],
                "adaptation_options": [
                    "تنويع مصادر الطاقة نحو الشمسية",
                    "تحسين كفاءة الطاقة في المباني"
                ],
                "kpi_2030": "12% طاقة متجددة في مزيج الكهرباء"
            }
        ]
    },

    # ===== المرحلة الثالثة: الخطة التنفيذية =====
    "phase_3_implementation": {
        "total_budget_usd_million": 2800,
        "financing_sources": {
            "domestic_budget_pct": 25,
            "GCF_pct": 35,
            "GEF_pct": 10,
            "bilateral_aid_pct": 20,
            "private_sector_pct": 10
        },
        "monitoring_indicators": [
            "نسبة السكان المعرّضين لإجهاد مائي شديد",
            "مساحة الأراضي الزراعية المتأثرة بالتصحر",
            "عدد حالات الوفاة بسبب موجات الحرارة",
            "كمية الأمطار السنوية مقارنة بالأساس"
        ]
    },

    # ===== مؤشرات التقدم =====
    "progress_tracking": {
        "reporting_cycle": "سنوي إلى الاتفاقية",
        "linked_to_btр": True,
        "linked_to_ndc": True,
        "sdg_alignment": ["SDG6", "SDG2", "SDG3", "SDG13"]
    }
}

# ========== طباعة الملخص ==========
print("=" * 65)
print(iraq_nap["nap_title"])
print("=" * 65)
print(f"\nالحالة: {iraq_nap['status']}")
print(f"الجهة القائدة: {iraq_nap['lead_ministry']}")
print(f"الإطار الزمني: {iraq_nap['timeframe']}")
print(f"\nالقطاعات ذات الأولوية:")
for sec in iraq_nap["phase_2_vulnerability"]["priority_sectors"]:
    level_icon = {"بالغة": "🔴", "عالية": "🟠", "متوسطة": "🟡"}.get(sec["vulnerability_level"], "⚪")
    print(f"  {level_icon} {sec['sector']:<25} الهشاشة: {sec['vulnerability_level']}")

budget = iraq_nap["phase_3_implementation"]["total_budget_usd_million"]
print(f"\nإجمالي الميزانية المطلوبة: {budget:,} مليون دولار")
print(f"SDGs المرتبطة: {', '.join(iraq_nap['progress_tracking']['sdg_alignment'])}")

out = "/home/claude/skills-repo/demos/unfccc/output_u08_nap_matrix.json"
with open(out, 'w', encoding='utf-8') as f:
    json.dump(iraq_nap, f, ensure_ascii=False, indent=2)
print(f"\nتم حفظ مصفوفة NAP: {out}")
