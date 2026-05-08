"""
النموذج الأول: ETF Reporting Tools
بناء هيكل بيانات BTR/NIR وفق معايير الاتفاقية وتصديره JSON
الرابط: https://unfccc.int/etf-reporting-tools-help
الفائدة: تنظيم بيانات الجرد العراقي بصيغة متوافقة مع منصة ETF الرسمية
"""

import json
from datetime import datetime

# ========== هيكل BTR العراقي - القسم الأول: الجرد الوطني ==========
btr_iraq = {
    "metadata": {
        "party": "Iraq",
        "party_code": "IRQ",
        "report_type": "BTR1",
        "submission_year": 2024,
        "base_year": 1990,
        "reporting_years": list(range(1990, 2022)),
        "guidelines": "IPCC 2006 Guidelines",
        "global_warming_potentials": "AR5",
        "prepared_by": "Ministry of Environment / Climate Policy Division",
        "submission_date": "2024-12-31"
    },

    # ===== القسم 1: الجرد الوطني =====
    "national_inventory": {
        "summary_table": {
            # الوحدة: Gg CO2 equivalent
            "sectors": {
                "1_energy": {
                    "name_ar": "الطاقة",
                    "name_en": "Energy",
                    "emissions_2020": 165430.5,
                    "emissions_2019": 169823.2,
                    "subcategories": {
                        "1A_fuel_combustion": {
                            "name_ar": "احتراق الوقود",
                            "emissions_2020": 158200.0,
                            "fuel_types": {
                                "liquid_fuels": 98500.0,
                                "gaseous_fuels": 52300.0,
                                "solid_fuels": 7400.0
                            }
                        },
                        "1B_fugitive": {
                            "name_ar": "الانبعاثات المتسرّبة",
                            "emissions_2020": 7230.5,
                            "note": "تشمل تسرّب الغاز من حقول النفط والغاز"
                        }
                    }
                },
                "2_IPPU": {
                    "name_ar": "العمليات الصناعية واستخدام المنتجات",
                    "name_en": "IPPU",
                    "emissions_2020": 8750.3,
                    "emissions_2019": 9120.1
                },
                "3_AFOLU": {
                    "name_ar": "الزراعة والأراضي والغابات",
                    "name_en": "AFOLU",
                    "emissions_2020": 12340.8,
                    "emissions_2019": 12580.4,
                    "removals_2020": -1250.0
                },
                "4_waste": {
                    "name_ar": "النفايات",
                    "name_en": "Waste",
                    "emissions_2020": 3820.6,
                    "emissions_2019": 3750.2
                }
            },
            "total_excl_LULUCF": {
                "2020": 190342.2,
                "2019": 195273.9,
                "1990": 82400.0
            },
            "total_incl_LULUCF": {
                "2020": 189092.2,
                "2019": 193773.9
            }
        }
    },

    # ===== القسم 2: التقدم نحو NDC =====
    "ndc_progress": {
        "ndc_target": {
            "type": "unconditional",
            "base_year": 2021,
            "target_year": 2030,
            "reduction_percentage": 2.5,
            "conditional_reduction": 15.0,
            "conditional_on": "دعم مالي وتقني دولي"
        },
        "indicators": [
            {
                "indicator": "حصة الطاقة المتجددة في مزيج الكهرباء",
                "baseline_2021": 2.1,
                "current_2023": 4.8,
                "target_2030": 12.0,
                "unit": "النسبة المئوية",
                "trend": "إيجابي"
            },
            {
                "indicator": "كثافة انبعاثات قطاع الكهرباء",
                "baseline_2021": 0.68,
                "current_2023": 0.65,
                "target_2030": 0.55,
                "unit": "كغ CO2/كيلوواط ساعة",
                "trend": "إيجابي"
            }
        ]
    },

    # ===== القسم 3: السياسات والإجراءات =====
    "policies_measures": [
        {
            "id": "PM_001",
            "name_ar": "استراتيجية الطاقة الوطنية 2030",
            "sector": "1_energy",
            "type": "استراتيجية وطنية",
            "status": "قيد التنفيذ",
            "expected_reduction_2030": 8500,
            "unit": "Gg CO2eq"
        },
        {
            "id": "PM_002",
            "name_ar": "برنامج الطاقة الشمسية الوطني",
            "sector": "1_energy",
            "type": "برنامج حكومي",
            "status": "قيد التنفيذ",
            "expected_reduction_2030": 12000,
            "unit": "Gg CO2eq"
        }
    ],

    # ===== القسم 4: احتياجات الدعم =====
    "support_needs": {
        "finance": {
            "total_needed_usd_million": 88000,
            "received_2023_usd_million": 1200,
            "gap_usd_million": 86800
        },
        "technology_transfer": [
            "تقنيات الطاقة الشمسية وتخزين الطاقة",
            "تقنيات احتجاز الكربون وتخزينه",
            "أنظمة MRV الرقمية المتقدمة"
        ],
        "capacity_building": [
            "تدريب مجمّعي الجرد الوطني على IPCC 2006",
            "بناء نظام MRV وطني متكامل",
            "تطوير نماذج تحليل السيناريوهات"
        ]
    }
}

# ========== تصدير الملفات ==========
# JSON الكامل
json_path = "/home/claude/skills-repo/demos/unfccc/output_u01_iraq_btr_structure.json"
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(btr_iraq, f, ensure_ascii=False, indent=2)
print(f"تم إنشاء: {json_path}")

# ملخص النص
print("\n===== ملخص هيكل BTR العراقي =====")
inv = btr_iraq["national_inventory"]["summary_table"]
total = inv["total_excl_LULUCF"]
print(f"إجمالي الانبعاثات 2020 (بدون LULUCF): {total['2020']:,.1f} Gg CO2eq")
print(f"إجمالي الانبعاثات 2019:                {total['2019']:,.1f} Gg CO2eq")
print(f"إجمالي الانبعاثات 1990 (سنة الأساس):   {total['1990']:,.1f} Gg CO2eq")
change = ((total['2020'] - total['1990']) / total['1990']) * 100
print(f"التغيير منذ 1990: {change:+.1f}%")
print(f"\nاحتياجات التمويل: {btr_iraq['support_needs']['finance']['total_needed_usd_million']:,} مليون دولار")
print(f"الفجوة التمويلية: {btr_iraq['support_needs']['finance']['gap_usd_million']:,} مليون دولار")
