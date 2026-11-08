#!/usr/bin/env bash
# تنزيل وثيقة رسمية برمزها من نظام الوثائق الرسمية للأمم المتحدة ثم استخراج نصها.
# الاستعمال: tools/un_doc.sh FCCC/PA/CMA/2026/8 [en|ar|fr|es|ru|zh] [مجلد_الحفظ]
set -eu
sym="$1"; lang="${2:-en}"; out="${3:-.}"
name="$(echo "$sym" | tr '/' '_')_${lang}"
mkdir -p "$out"
curl -sL -m 60 -o "$out/$name.pdf" "https://documents.un.org/api/symbol/access?s=${sym}&l=${lang}&t=pdf"
if file -b "$out/$name.pdf" | grep -q PDF; then
  pdftotext -layout "$out/$name.pdf" "$out/$name.txt"
  echo "تم: $out/$name.pdf و $out/$name.txt"
else
  rm -f "$out/$name.pdf"; echo "غير متاح بهذه اللغة أو الرمز غير موجود في النظام: $sym ($lang)"; exit 1
fi
