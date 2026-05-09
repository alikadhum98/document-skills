# منظومة أدوات سياسات المناخ - العراق

مستودع يحتوي على أدوات برمجية متكاملة لدعم عمل سياسات المناخ والمفاوضات الدولية.

## التثبيت السريع

```bash
git clone https://github.com/alikadhum98/document-skills
cd document-skills
pip install -r requirements.txt
```

## تشغيل الأدوات

```bash
python run_all.py              # جميع الأدوات دفعة واحدة
python run_all.py btr          # تقرير BTR
python run_all.py a6           # المادة السادسة وITMOs
python run_all.py ghg          # تحليل الجرد والرسوم البيانية
python run_all.py pptx         # عروض PowerPoint
python run_all.py finance      # التمويل المناخي وGCF
```

## الأدوات

| الأداة | الوصف | المخرج |
|--------|-------|--------|
| btr_generator | تقرير الشفافية الثنائي العربي | Word |
| article6_tracker | ITMOs والتعديلات المقابلة | Word + JSON |
| ghg_analyzer | رسوم بيانية وإحصاءات الانبعاثات | Word + JSON |
| pptx_generator | PowerPoint للمؤتمرات والمفاوضات | PPTX |
| finance_tracker | تحليل فجوات GCF والتمويل | Word + JSON |

## تخصيص البيانات

كل أداة لها ملف `*_data.py` قابل للتعديل بدون لمس كود الأداة.

## المتطلبات

Python 3.12+ | انظر requirements.txt

---
وزارة البيئة - قسم سياسات المناخ - الجمهورية العراقية
