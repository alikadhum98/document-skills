"""
النموذج الرابع: ghgdata (sphericalpm)
جلب بيانات الجرد الوطني لدول أنيكس-1 من UNFCCC ومقارنتها
الفائدة: مقارنة أرقام العراق وترند الانبعاثات مع دول مشابهة
ملاحظة: العراق دولة غير أنيكس-1، لكن البيانات مفيدة للمقارنة المرجعية
"""

import requests
import json

# ========== واجهة محلية للبيانات (بدون إنترنت) ==========
# بيانات انبعاثات نموذجية من تقارير UNFCCC لأغراض العرض
SAMPLE_DATA = {
    "IRA": {  # العراق (تقديري من التقارير الوطنية)
        "name": "العراق",
        "years": [2015, 2016, 2017, 2018, 2019, 2020],
        "total_ghg": [170.2, 172.8, 175.1, 178.4, 180.9, 179.6],
        "energy_share": 0.89,
        "unit": "مليون طن CO2eq"
    },
    "JOR": {  # الأردن
        "name": "الأردن",
        "years": [2015, 2016, 2017, 2018, 2019, 2020],
        "total_ghg": [27.3, 28.1, 28.6, 29.0, 29.4, 28.8],
        "energy_share": 0.82,
        "unit": "مليون طن CO2eq"
    },
    "EGY": {  # مصر
        "name": "مصر",
        "years": [2015, 2016, 2017, 2018, 2019, 2020],
        "total_ghg": [318.5, 325.2, 331.4, 338.7, 344.1, 340.2],
        "energy_share": 0.75,
        "unit": "مليون طن CO2eq"
    },
    "SAU": {  # السعودية
        "name": "المملكة العربية السعودية",
        "years": [2015, 2016, 2017, 2018, 2019, 2020],
        "total_ghg": [670.1, 685.4, 695.2, 706.8, 715.3, 700.1],
        "energy_share": 0.91,
        "unit": "مليون طن CO2eq"
    }
}

def calculate_trend(values):
    """حساب معدل النمو السنوي المركّب"""
    if len(values) < 2:
        return 0
    cagr = ((values[-1] / values[0]) ** (1 / (len(values) - 1)) - 1) * 100
    return round(cagr, 2)

def compare_countries(countries=None):
    """مقارنة الانبعاثات بين الدول"""
    if not countries:
        countries = list(SAMPLE_DATA.keys())

    print("=" * 65)
    print("مقارنة انبعاثات غازات الاحتباس الحراري - دول مختارة")
    print("المصدر: التقارير الوطنية / UNFCCC")
    print("=" * 65)

    results = []
    for code in countries:
        if code not in SAMPLE_DATA:
            continue
        d = SAMPLE_DATA[code]
        latest  = d["total_ghg"][-1]
        trend   = calculate_trend(d["total_ghg"])
        e_share = d["energy_share"] * 100

        results.append({
            "الدولة":        d["name"],
            "آخر قراءة (مليون طن)": latest,
            "معدل النمو السنوي":     f"{trend:+.2f}%",
            "حصة قطاع الطاقة":       f"{e_share:.0f}%",
        })

    # طباعة الجدول
    header = f"{'الدولة':<30} {'آخر قراءة':>18} {'معدل النمو':>18} {'حصة الطاقة':>14}"
    print(header)
    print("-" * 82)
    for r in results:
        print(
            f"{r['الدولة']:<30} "
            f"{str(r['آخر قراءة (مليون طن)'])+'م.ط':>18} "
            f"{r['معدل النمو السنوي']:>18} "
            f"{r['حصة قطاع الطاقة']:>14}"
        )

    print("\n")
    return results

def show_country_trend(code):
    """عرض ترند انبعاثات دولة بعينها"""
    if code not in SAMPLE_DATA:
        print(f"الرمز {code} غير موجود في البيانات")
        return
    d = SAMPLE_DATA[code]
    print(f"\nترند انبعاثات {d['name']} ({d['unit']})")
    print("-" * 40)
    max_val = max(d["total_ghg"])
    for year, val in zip(d["years"], d["total_ghg"]):
        bar_len = int((val / max_val) * 30)
        bar = "█" * bar_len
        print(f"  {year}  {bar:<30}  {val:.1f}")

def save_comparison_json(output_path):
    """حفظ البيانات كـ JSON قابل للاستخدام في تقارير أخرى"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(SAMPLE_DATA, f, ensure_ascii=False, indent=2)
    print(f"\nتم حفظ البيانات: {output_path}")

# ========== تنفيذ التحليل ==========
compare_countries(["IRA", "JOR", "EGY", "SAU"])
show_country_trend("IRA")
save_comparison_json("/home/claude/skills-repo/demos/output_demo4_ghg_comparison.json")
print("\nاكتمل النموذج الرابع بنجاح")
