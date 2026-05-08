"""
النموذج الثاني: IPCC 2006 Inventory Software
حساب انبعاثات القطاعات الرئيسية وفق منهجية IPCC 2006
الرابط: https://www.ipcc-nggip.iges.or.jp/software/
الفائدة: التحقق من حسابات الجرد الوطني وتوحيد المنهجية
"""

# ========== معاملات الإمكانية الاحترارية العالمية AR5 ==========
GWP = {"CO2": 1, "CH4": 28, "N2O": 265, "HFCs": 1300, "SF6": 23500}

# ========== معاملات الانبعاث الافتراضية IPCC 2006 ==========
EMISSION_FACTORS = {
    "natural_gas":   {"CO2": 56100, "CH4": 1,    "N2O": 0.1},   # kg/TJ
    "crude_oil":     {"CO2": 73300, "CH4": 3,    "N2O": 0.6},
    "diesel":        {"CO2": 74100, "CH4": 3.9,  "N2O": 3.9},
    "gasoline":      {"CO2": 69300, "CH4": 25,   "N2O": 8},
    "coal":          {"CO2": 94600, "CH4": 1,    "N2O": 1.5},
    "fuel_oil":      {"CO2": 77400, "CH4": 3,    "N2O": 0.6},
}

# ========== بيانات النشاط العراقية (TJ) ==========
IRAQ_ACTIVITY_DATA = {
    2019: {
        "natural_gas": 1850000,
        "crude_oil":   420000,
        "diesel":      380000,
        "gasoline":    290000,
        "coal":        15000,
        "fuel_oil":    95000,
    },
    2020: {
        "natural_gas": 1780000,
        "crude_oil":   395000,
        "diesel":      360000,
        "gasoline":    275000,
        "coal":        12000,
        "fuel_oil":    88000,
    }
}

def calc_tier1_emissions(activity_tj, fuel_type):
    """حساب المستوى الأول من الانبعاثات"""
    ef = EMISSION_FACTORS[fuel_type]
    results = {}
    for gas, factor in ef.items():
        emissions_kg = activity_tj * factor       # kg
        emissions_gg = emissions_kg / 1e6        # Gg
        results[gas] = emissions_gg
    co2eq = (results["CO2"] * GWP["CO2"] +
             results["CH4"] * GWP["CH4"] +
             results["N2O"] * GWP["N2O"])
    results["CO2eq"] = co2eq
    return results

def calc_national_inventory(year):
    """حساب الجرد الوطني لسنة محددة"""
    activity = IRAQ_ACTIVITY_DATA.get(year, {})
    total = {"CO2": 0, "CH4": 0, "N2O": 0, "CO2eq": 0}
    details = {}
    for fuel, tj in activity.items():
        em = calc_tier1_emissions(tj, fuel)
        details[fuel] = em
        for gas in total:
            total[gas] += em[gas]
    return total, details

def uncertainty_range(value, pct=15):
    """نطاق عدم اليقين (±% افتراضي للمستوى الأول)"""
    return value * (1 - pct/100), value * (1 + pct/100)

# ========== تشغيل الحسابات ==========
print("=" * 60)
print("حسابات الجرد الوطني العراقي - قطاع الطاقة")
print("المنهجية: IPCC 2006 المستوى الأول")
print("=" * 60)

for year in [2019, 2020]:
    total, details = calc_national_inventory(year)
    low, high = uncertainty_range(total["CO2eq"])

    print(f"\n[ سنة {year} ]")
    print(f"{'الوقود':<18} {'CO2 (Gg)':>14} {'CH4 (Gg)':>12} {'CO2eq (Gg)':>14}")
    print("-" * 60)
    for fuel, em in details.items():
        name_map = {
            "natural_gas": "الغاز الطبيعي",
            "crude_oil":   "النفط الخام",
            "diesel":      "الديزل",
            "gasoline":    "البنزين",
            "coal":        "الفحم",
            "fuel_oil":    "زيت الوقود"
        }
        print(f"{name_map[fuel]:<18} {em['CO2']:>14,.1f} {em['CH4']:>12,.2f} {em['CO2eq']:>14,.1f}")

    print("-" * 60)
    print(f"{'الإجمالي':<18} {total['CO2']:>14,.1f} {total['CH4']:>12,.2f} {total['CO2eq']:>14,.1f}")
    print(f"نطاق عدم اليقين (±15%): {low:,.0f} إلى {high:,.0f} Gg CO2eq")

# حفظ النتائج
import json
results_all = {}
for year in [2019, 2020]:
    total, details = calc_national_inventory(year)
    results_all[str(year)] = {
        "total": {k: round(v, 2) for k, v in total.items()},
        "by_fuel": {fuel: {gas: round(val, 4) for gas, val in em.items()}
                    for fuel, em in details.items()}
    }

out = "/home/claude/skills-repo/demos/unfccc/output_u02_ipcc_calculations.json"
with open(out, 'w', encoding='utf-8') as f:
    json.dump(results_all, f, ensure_ascii=False, indent=2)
print(f"\nتم حفظ النتائج: {out}")
