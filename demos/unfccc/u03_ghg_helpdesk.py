"""
النموذج الثالث: GHG Help Desk
نظام لصياغة وتوثيق الاستفسارات التقنية الموجّهة لمكتب الدعم
الرابط: GHGCapacityBuilding@unfccc.int
الفائدة: بناء أرشيف منظّم للأسئلة التقنية والردود لفريق الجرد العراقي
"""

import json
from datetime import datetime

# ========== قاعدة بيانات الاستفسارات ==========
help_desk_db = {
    "party": "Iraq",
    "contact_email": "ghg-inventory@moe.gov.iq",
    "queries": []
}

def new_query(category, subject_ar, question_ar, sector, urgency="متوسطة"):
    """إنشاء استفسار تقني جديد"""
    qid = f"IRQ-{datetime.now().strftime('%Y%m')}-{len(help_desk_db['queries'])+1:03d}"
    query = {
        "id": qid,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "مُرسَل",
        "urgency": urgency,
        "sector": sector,
        "category": category,
        "subject": subject_ar,
        "question": question_ar,
        "response": None,
        "resolution_date": None
    }
    help_desk_db["queries"].append(query)
    return query

def mark_resolved(query_id, response_text):
    """تسجيل رد مكتب الدعم"""
    for q in help_desk_db["queries"]:
        if q["id"] == query_id:
            q["status"] = "مُغلَق"
            q["response"] = response_text
            q["resolution_date"] = datetime.now().strftime("%Y-%m-%d")
            return True
    return False

def print_summary():
    """طباعة ملخص الاستفسارات"""
    total = len(help_desk_db["queries"])
    open_q  = sum(1 for q in help_desk_db["queries"] if q["status"] != "مُغلَق")
    closed  = total - open_q
    print(f"\nإجمالي الاستفسارات: {total}  |  مفتوحة: {open_q}  |  مغلقة: {closed}")
    print("-" * 70)
    for q in help_desk_db["queries"]:
        status_icon = "✓" if q["status"] == "مُغلَق" else "○"
        print(f"{status_icon} [{q['id']}] {q['subject'][:45]:<45} | {q['urgency']}")

# ========== استفسارات نموذجية من الجرد العراقي ==========
q1 = new_query(
    category="منهجية الحساب",
    subject_ar="معامل الانبعاث الافتراضي للغاز المشعل في حقول النفط",
    question_ar=(
        "نواجه صعوبة في تحديد معامل الانبعاث المناسب للغاز المشعل "
        "في حقول النفط العراقية. هل يمكن استخدام معامل IPCC 2006 "
        "الافتراضي للفئة 1B2a أم يُفضّل الاعتماد على قياسات ميدانية؟ "
        "وما هو الحد الأدنى من القياسات المطلوبة للانتقال إلى المستوى الثاني؟"
    ),
    sector="1B_fugitive_emissions",
    urgency="عالية"
)

q2 = new_query(
    category="تصنيف المصادر",
    subject_ar="تصنيف انبعاثات محطات معالجة المياه العادمة",
    question_ar=(
        "هل تُصنَّف انبعاثات CH4 من محطات معالجة المياه العادمة "
        "ضمن الفئة 4D (معالجة مياه الصرف) أم 4B (الصحة البيئية)؟ "
        "وكيف يتم التعامل مع محطات تعمل جزئياً فقط؟"
    ),
    sector="4_waste",
    urgency="متوسطة"
)

q3 = new_query(
    category="إعداد BTR",
    subject_ar="متطلبات إعداد جداول CRT للدول النامية في BTR1",
    question_ar=(
        "هل الدول النامية مثل العراق ملزمة بتقديم جميع جداول CRT "
        "المطلوبة من دول أنيكس-1 في BTR1؟ أم توجد مرونة؟ "
        "وهل مرونة LDC/SIDS تنطبق على العراق؟"
    ),
    sector="general_BTR",
    urgency="عالية"
)

# تسجيل رد على استفسار واحد (نموذجي)
mark_resolved(
    q3["id"],
    "الدول النامية من غير LDC/SIDS ملزمة بتقديم BTR1 بحلول 31 ديسمبر 2024، "
    "مع مرونة في اختيار جداول CRT وفق قدراتها. يُرجى مراجعة الفقرة 4 من "
    "قرار 18/CMA.1 وجداول المرونة في الإرشادات التقنية."
)

# ========== طباعة وحفظ ==========
print("=" * 70)
print("سجل استفسارات GHG Help Desk - العراق")
print("=" * 70)
print_summary()

out = "/home/claude/skills-repo/demos/unfccc/output_u03_ghg_helpdesk_log.json"
with open(out, 'w', encoding='utf-8') as f:
    json.dump(help_desk_db, f, ensure_ascii=False, indent=2)
print(f"\nتم حفظ السجل: {out}")
