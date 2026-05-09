"""
أداة حزم المخرجات - تجمع كل التقارير في ملف ZIP واحد
التشغيل: python extras/packager.py
"""

import os, zipfile, datetime, glob, shutil

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY    = datetime.date.today().strftime("%Y-%m-%d")
OUT_DIR  = os.path.join(ROOT, "packages")

def collect_outputs():
    """جمع جميع ملفات المخرجات"""
    patterns = [
        "tools/*/output_*.docx",
        "tools/*/output_*.pptx",
        "tools/*/output_*.json",
        "pipeline/output_*.docx",
        "pipeline/output_*.json",
    ]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(ROOT, pattern)))
    return sorted(files)

def create_package():
    os.makedirs(OUT_DIR, exist_ok=True)
    zip_name = os.path.join(OUT_DIR, f"climate_tools_outputs_{TODAY}.zip")

    files = collect_outputs()
    if not files:
        print("  ⚠  لا توجد ملفات مخرجات بعد. شغّل الأدوات أولاً.")
        return None

    print(f"\n  جاري حزم {len(files)} ملفاً...")

    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filepath in files:
            # اسم الملف داخل ZIP بمسار مختصر
            rel = os.path.relpath(filepath, ROOT)
            parts = rel.replace("\\","/").split("/")
            # tool_name/filename
            if len(parts) >= 2:
                arcname = f"{parts[-2]}/{parts[-1]}"
            else:
                arcname = parts[-1]
            zf.write(filepath, arcname)
            print(f"     + {arcname}")

    size_kb = os.path.getsize(zip_name) / 1024
    print(f"\n  ✓  تم إنشاء الحزمة: {zip_name}")
    print(f"     الحجم: {size_kb:.1f} KB  |  الملفات: {len(files)}")
    return zip_name

if __name__ == "__main__":
    print("="*55)
    print("  أداة حزم المخرجات")
    print("="*55)
    create_package()
