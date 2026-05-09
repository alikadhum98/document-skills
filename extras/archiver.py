"""
أداة أرشفة المخرجات - تحفظ نسخة بتاريخ اليوم
التشغيل: python extras/archiver.py
"""

import os, shutil, datetime, glob

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY    = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
ARCH_DIR = os.path.join(ROOT, "archive", TODAY)

def archive_outputs():
    patterns = [
        "tools/*/output_*.docx",
        "tools/*/output_*.pptx",
        "tools/*/output_*.json",
        "pipeline/output_*.docx",
        "pipeline/output_*.json",
    ]
    files = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(ROOT, p)))

    if not files:
        print("  ⚠  لا توجد مخرجات للأرشفة.")
        return

    os.makedirs(ARCH_DIR, exist_ok=True)
    print(f"\n  أرشفة {len(files)} ملفاً إلى archive/{TODAY}/")

    for filepath in files:
        parts = os.path.relpath(filepath, ROOT).replace("\\","/").split("/")
        tool  = parts[-2] if len(parts)>=2 else "misc"
        dest  = os.path.join(ARCH_DIR, tool)
        os.makedirs(dest, exist_ok=True)
        shutil.copy2(filepath, os.path.join(dest, parts[-1]))
        print(f"     ✓ {tool}/{parts[-1]}")

    # كتابة سجل الأرشيف
    log_path = os.path.join(ARCH_DIR, "archive_log.txt")
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(f"تاريخ الأرشفة: {TODAY}\n")
        f.write(f"عدد الملفات: {len(files)}\n\n")
        for fp in files:
            f.write(f"  {os.path.relpath(fp, ROOT)}\n")

    print(f"\n  ✓  اكتملت الأرشفة: archive/{TODAY}/")
    print(f"     ({len(files)} ملفاً محفوظاً)")

def list_archives():
    arch_root = os.path.join(ROOT, "archive")
    if not os.path.exists(arch_root):
        print("  لا توجد أرشيفات بعد.")
        return
    archives = sorted(os.listdir(arch_root), reverse=True)
    print(f"\n  الأرشيفات المتاحة ({len(archives)}):")
    for arch in archives[:10]:
        arch_path = os.path.join(arch_root, arch)
        count = sum(len(files) for _,_,files in os.walk(arch_path))
        print(f"     {arch}  ({count} ملف)")

if __name__ == "__main__":
    print("="*55)
    print("  أداة أرشفة المخرجات")
    print("="*55)
    list_archives()
    archive_outputs()
