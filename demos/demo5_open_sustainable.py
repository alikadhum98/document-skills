"""
النموذج الخامس: open-sustainable-technology
دليل ذكي للبحث في الأدوات المناخية مفتوحة المصدر
الفائدة: اكتشاف أدوات جاهزة قبل بناء أي شيء من الصفر
"""

import json

# ========== قاعدة بيانات الأدوات (مستخلصة من المستودع) ==========
TOOLS_DB = [
    {
        "الاسم": "climate-policy-radar",
        "الرابط": "https://github.com/climatepolicyradar",
        "المجال": "سياسات المناخ",
        "الوصف": "قاعدة بيانات شاملة لسياسات المناخ الوطنية والدولية مع محرك بحث نصي",
        "الكلمات": ["سياسة", "قوانين", "تشريعات", "NDC", "خطط مناخية"],
        "الاستخدام_المباشر": "البحث في سياسات المناخ العراقية والعربية ومقارنتها بالدول الأخرى"
    },
    {
        "الاسم": "openclimatefix",
        "الرابط": "https://github.com/openclimatefix",
        "المجال": "الطاقة المتجددة",
        "الوصف": "أدوات التنبؤ بالطاقة الشمسية وطاقة الرياح بالذكاء الاصطناعي",
        "الكلمات": ["طاقة شمسية", "رياح", "تنبؤ", "شبكة كهربائية"],
        "الاستخدام_المباشر": "تقدير إمكانات الطاقة المتجددة في العراق كجزء من مساهمة NDC"
    },
    {
        "الاسم": "PyPSA",
        "الرابط": "https://github.com/PyPSA/PyPSA",
        "المجال": "نمذجة الطاقة",
        "الوصف": "نمذجة منظومات الطاقة وحساب انبعاثات الكهرباء",
        "الكلمات": ["نمذجة طاقة", "انبعاثات كهرباء", "شبكة", "تحول طاقوي"],
        "الاستخدام_المباشر": "نمذجة منظومة الكهرباء العراقية وحساب انبعاثاتها في الجرد الوطني"
    },
    {
        "الاسم": "FAOSTAT-GHG",
        "الرابط": "https://github.com/CIAT/FAOSTAT",
        "المجال": "الزراعة والأراضي",
        "الوصف": "بيانات انبعاثات الزراعة والأراضي من منظمة الأغذية والزراعة",
        "الكلمات": ["زراعة", "AFOLU", "أراضي", "ثروة حيوانية"],
        "الاستخدام_المباشر": "حساب انبعاثات قطاع AFOLU في الجرد الوطني وفق منهجية IPCC"
    },
    {
        "الاسم": "carbon-budget",
        "الرابط": "https://github.com/globalcarbonproject",
        "المجال": "الميزانية الكربونية",
        "الوصف": "بيانات الميزانية الكربونية العالمية والانبعاثات التاريخية",
        "الكلمات": ["ميزانية كربونية", "انبعاثات تاريخية", "1.5 درجة", "2 درجة"],
        "الاستخدام_المباشر": "تحديد حصة العراق في الميزانية الكربونية العالمية للمفاوضات"
    },
    {
        "الاسم": "unfccc-data-portal",
        "الرابط": "https://github.com/unfccc",
        "المجال": "بيانات UNFCCC",
        "الوصف": "واجهة برمجية رسمية لبيانات الأمم المتحدة للمناخ",
        "الكلمات": ["UNFCCC", "CRF", "BTR", "تقارير شفافية", "NDC"],
        "الاستخدام_المباشر": "استخراج بيانات تقارير الشفافية للعراق والدول العربية برمجياً"
    },
    {
        "الاسم": "MRV-system",
        "الرابط": "https://github.com/mrv-system",
        "المجال": "القياس والإبلاغ والتحقق",
        "الوصف": "أدوات بناء منظومة MRV للدول النامية",
        "الكلمات": ["MRV", "قياس", "إبلاغ", "تحقق", "شفافية"],
        "الاستخدام_المباشر": "بناء منظومة MRV وطنية متوافقة مع إطار الشفافية المعزز"
    },
    {
        "الاسم": "article6-tracker",
        "الرابط": "https://github.com/carbon-pulse",
        "المجال": "المادة السادسة",
        "الوصف": "تتبع صفقات المادة 6.2 وائتمانات المادة 6.4 دولياً",
        "الكلمات": ["المادة السادسة", "ITMOs", "6.2", "6.4", "كربون"],
        "الاستخدام_المباشر": "متابعة سوق الكربون الدولي وتحديد الفرص المتاحة للعراق"
    },
]

def search_tools(keyword):
    """البحث في الأدوات بكلمة مفتاحية"""
    results = []
    keyword_lower = keyword.lower()
    for tool in TOOLS_DB:
        if (keyword in tool["الوصف"] or
            keyword in tool["المجال"] or
            any(keyword in k for k in tool["الكلمات"])):
            results.append(tool)
    return results

def show_tools_by_domain():
    """عرض الأدوات مجمّعة حسب المجال"""
    domains = {}
    for tool in TOOLS_DB:
        domain = tool["المجال"]
        if domain not in domains:
            domains[domain] = []
        domains[domain].append(tool)

    print("=" * 65)
    print("دليل الأدوات المناخية مفتوحة المصدر")
    print("المصدر: open-sustainable-technology / GitHub")
    print("=" * 65)

    for domain, tools in domains.items():
        print(f"\n[ {domain} ]")
        print("-" * 40)
        for t in tools:
            print(f"  {t['الاسم']}")
            print(f"  الرابط: {t['الرابط']}")
            print(f"  الفائدة: {t['الاستخدام_المباشر']}")
            print()

def recommend_for_task(task):
    """توصية بالأدوات بناءً على المهمة"""
    TASK_MAP = {
        "جرد":        ["FAOSTAT-GHG", "PyPSA", "unfccc-data-portal"],
        "مفاوضات":    ["carbon-budget", "article6-tracker", "climate-policy-radar"],
        "MRV":        ["MRV-system", "unfccc-data-portal"],
        "طاقة":       ["openclimatefix", "PyPSA"],
        "شفافية":     ["unfccc-data-portal", "MRV-system"],
    }
    for key, tools in TASK_MAP.items():
        if key in task:
            matched = [t for t in TOOLS_DB if t["الاسم"] in tools]
            print(f"\nأدوات مقترحة لمهمة '{task}':")
            for t in matched:
                print(f"  {t['الاسم']}: {t['الاستخدام_المباشر']}")
            return
    print(f"لا توجد توصية محددة لـ '{task}' - جرّب البحث الحر")

# ========== تنفيذ النموذج ==========
show_tools_by_domain()
recommend_for_task("جرد وطني")
recommend_for_task("مفاوضات المادة السادسة")

# حفظ الدليل كـ JSON
output_path = "/home/claude/skills-repo/demos/output_demo5_climate_tools_directory.json"
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(TOOLS_DB, f, ensure_ascii=False, indent=2)
print(f"\nتم حفظ دليل الأدوات: {output_path}")
print("اكتمل النموذج الخامس بنجاح")
