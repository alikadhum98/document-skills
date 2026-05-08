# مهارات توليد الوثائق

مستودع يحتوي على مهارات توليد الملفات المكتبية المُخصَّصة لبيئة Claude.

## هيكل المستودع

```
skills-repo/
├── user/
│   └── docx-arabic/     # مهارة Word العربية المُخصَّصة
└── public/
    ├── pptx/            # مهارة PowerPoint
    ├── docx/            # مهارة Word الإنجليزية
    ├── xlsx/            # مهارة Excel
    ├── pdf/             # مهارة PDF
    └── ...
```

## المهارات

| المهارة | الوصف | المسار |
|---------|-------|--------|
| docx-arabic | توليد وثائق Word بالعربية مع دعم RTL | user/docx-arabic |
| pptx | توليد عروض PowerPoint | public/pptx |
| docx | توليد وثائق Word بالإنجليزية | public/docx |
| xlsx | توليد جداول Excel | public/xlsx |
| pdf | معالجة ملفات PDF | public/pdf |
