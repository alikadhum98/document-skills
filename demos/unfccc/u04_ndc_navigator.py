"""
النموذج الرابع: NDC 3.0 Navigator
تقييم العراق على المسارات السبعة لرفع طموح المساهمة الوطنية
الرابط: https://ndcnavigator.org/
الفائدة: تحديد الثغرات وأولويات الدعم في NDC العراقية القادمة
"""

import json

# ========== المسارات السبعة للـ NDC 3.0 Navigator ==========
ROUTES = {
    "R1": {
        "name_ar": "التوافق مع هدف درجة الحرارة",
        "name_en": "Aligned to Temperature Goal",
        "description": "رفع هدف التخفيف ليتوافق مع مسار 1.5 أو 2 درجة",
        "key_questions": [
            "هل يشمل هدف التخفيف جميع القطاعات؟",
            "هل يستند إلى سنة أساس واضحة وبيانات موثوقة؟",
            "هل يُقدَّم كهدف مطلق أم كثافة انبعاث؟"
        ]
    },
    "R2": {
        "name_ar": "الهدف العالمي للتكيف",
        "name_en": "Global Goal on Adaptation",
        "description": "تضمين إجراءات تكيف ملموسة وقابلة للقياس",
        "key_questions": [
            "هل تشمل NDC خطة تكيف وطنية؟",
            "هل تُحدَّد القطاعات الأكثر هشاشة (المياه، الزراعة)؟",
            "هل توجد مؤشرات قابلة للقياس لتتبع التكيف؟"
        ]
    },
    "R3": {
        "name_ar": "التحول العادل والمنصف",
        "name_en": "Just and Equitable Transition",
        "description": "ضمان أن التحول المناخي لا يُلقي عبئاً غير عادل على الفئات الهشة",
        "key_questions": [
            "هل يُراعي إجراءات التخفيف أثرها على العمالة في قطاع النفط؟",
            "هل تُدمج اعتبارات النوع الاجتماعي؟",
            "هل تُعالج احتياجات المجتمعات الريفية؟"
        ]
    },
    "R4": {
        "name_ar": "النهج الحكومي والمجتمعي الشامل",
        "name_en": "All-Of-Government and All-Of-Society",
        "description": "إشراك كافة الوزارات والقطاع الخاص والمجتمع المدني",
        "key_questions": [
            "هل تُنسَّق NDC عبر مجلس وزاري؟",
            "هل يشارك القطاع الخاص في صياغة الأهداف؟",
            "هل توجد آلية استشارة مجتمعية؟"
        ]
    },
    "R5": {
        "name_ar": "التكنولوجيا وبناء القدرات",
        "name_en": "Technology and Capacity-Building",
        "description": "تحديد الاحتياجات التكنولوجية وربطها بمصادر الدعم",
        "key_questions": [
            "هل أُجري تقييم احتياجات تكنولوجي (TNA)؟",
            "هل تُحدَّد تقنيات التخفيف والتكيف ذات الأولوية؟",
            "هل يُذكر دعم بناء القدرات المطلوب؟"
        ]
    },
    "R6": {
        "name_ar": "التمويل والسياسة المالية",
        "name_en": "Finance and Fiscal Policy",
        "description": "تحديد التكاليف ومصادر التمويل المحلي والدولي",
        "key_questions": [
            "هل تُقدَّر تكاليف تنفيذ NDC بشكل واضح؟",
            "هل تُحدَّد مصادر التمويل المحلية والدولية؟",
            "هل يوجد نظام تتبع للإنفاق المناخي؟"
        ]
    },
    "R7": {
        "name_ar": "الشفافية والتوثيق التقني",
        "name_en": "Technically Sound and Transparent",
        "description": "ضمان جودة البيانات وشفافية المنهجية",
        "key_questions": [
            "هل تستند NDC إلى جرد وطني محدّث؟",
            "هل تُوثَّق المنهجيات والافتراضات؟",
            "هل يوجد نظام MRV لتتبع التقدم؟"
        ]
    }
}

# ========== تقييم العراق على كل مسار ==========
# المقياس: 1 (ضعيف) إلى 5 (ممتاز)
IRAQ_ASSESSMENT = {
    "R1": {"score": 2, "status": "يحتاج تطوير", "notes": "الهدف الحالي 2.5% غير مشروط - منخفض نسبياً", "priority": "عالية"},
    "R2": {"score": 2, "status": "يحتاج تطوير", "notes": "خطة التكيف الوطنية لم تُستكمل بعد", "priority": "عالية"},
    "R3": {"score": 1, "status": "غائب",        "notes": "لم تُعالج اعتبارات التحول العادل بشكل كافٍ", "priority": "متوسطة"},
    "R4": {"score": 3, "status": "جزئي",        "notes": "توجد لجنة وطنية لكن تنسيق الوزارات ضعيف", "priority": "متوسطة"},
    "R5": {"score": 2, "status": "يحتاج تطوير", "notes": "TNA لم يُحدَّث منذ 2019", "priority": "عالية"},
    "R6": {"score": 1, "status": "غائب",        "notes": "لا يوجد تقدير تكاليف شامل مُرفق بـ NDC", "priority": "عالية"},
    "R7": {"score": 3, "status": "جزئي",        "notes": "جرد 2021 موجود لكن نظام MRV يحتاج تقوية", "priority": "متوسطة"},
}

# ========== طباعة التقييم ==========
print("=" * 70)
print("تقييم العراق على مسارات NDC 3.0 Navigator")
print("=" * 70)

total_score = 0
for rid, route in ROUTES.items():
    assessment = IRAQ_ASSESSMENT[rid]
    score = assessment["score"]
    total_score += score
    bar = "█" * score + "░" * (5 - score)
    print(f"\n{rid}: {route['name_ar']}")
    print(f"  التقييم: {bar} ({score}/5) - {assessment['status']}")
    print(f"  الملاحظة: {assessment['notes']}")
    print(f"  الأولوية: {assessment['priority']}")

avg = total_score / len(ROUTES)
print(f"\n{'='*70}")
print(f"المتوسط الكلي: {avg:.1f}/5.0")
print(f"المسارات ذات الأولوية العالية: " +
      ", ".join(r for r, a in IRAQ_ASSESSMENT.items() if a["priority"] == "عالية"))

# ========== توصيات مخصصة ==========
print("\n[ توصيات مخصصة للعراق ]")
recommendations = [
    "R6 - إعداد تقدير شامل لتكاليف NDC بالتنسيق مع وزارة المالية قبل COP30",
    "R1 - رفع هدف التخفيف المشروط إلى 15-20% مرتبطاً بتمويل GCF",
    "R5 - تحديث تقييم الاحتياجات التكنولوجية TNA لعام 2024",
    "R2 - استكمال الخطة الوطنية للتكيف NAP وإدراج مؤشرات قابلة للقياس",
]
for i, rec in enumerate(recommendations, 1):
    print(f"  {i}. {rec}")

# حفظ النتائج
output = {
    "party": "Iraq",
    "assessment_date": "2025-05",
    "routes": {
        rid: {**ROUTES[rid], **IRAQ_ASSESSMENT[rid]}
        for rid in ROUTES
    },
    "average_score": round(avg, 2),
    "recommendations": recommendations
}
out = "/home/claude/skills-repo/demos/unfccc/output_u04_ndc_navigator_assessment.json"
with open(out, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\nتم حفظ التقييم: {out}")
