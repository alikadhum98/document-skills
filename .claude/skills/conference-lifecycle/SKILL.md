---
name: conference-lifecycle
description: بدء مؤتمر أو دورة تفاوضية وختامها. تشغل بكلمة (ابدأ مؤتمر) ثم الاسم، أو (اختم المؤتمر)، أو (افحص إعداد المؤتمر). البدء ينشئ ملف الإعداد ومجلدات Drive ومهمتي الصباح والمساء ويعرض قائمة الفحص قبل السفر. والختام يكتب رسالة الختام والتقرير النهائي وملف التسليم والدروس ويوقف المهام المجدولة ويغلق الإعداد. لا تستعمل لجلسة واحدة فتلك لمهارة battle-card أو live-session.
---

# بدء المؤتمر وختامه

الأداة `scripts/conference.py` تنشئ ملف الإعداد وتفحصه وتولد نصي المهمتين وسطور الجدولة منه، فلا تكتب المعرفات أو النصوص يدويا.

## البدء: (ابدأ مؤتمر) ثم الاسم

١. اسأل المستخدم بـ AskUserQuestion عما لا يعرف من: التواريخ، والمدينة، والمنطقة الزمنية، والملفات التفاوضية المتابعة، والتحالفات، وتاريخ بدء التنسيق. وخذ ما أمكن من ملف التسليم للدورة السابقة.
٢. أنشئ الإعداد:
   `python3 .claude/skills/conference-lifecycle/scripts/conference.py new <ID> --title ... --city ... --country ... --start ... --end ... --tz ... --from ...`
   ثم عبئ في الملف `scope.files` و`scope.file_notes` و`scope.coordination` و`mail_queries.scope_terms`.
٣. Drive: أنشئ مجلد المؤتمر، ثم مجلدا لكل يوم باسم التاريخ، ثم مجلدا مغلقا لكل تحالف له فرعية، ثم مجلد ENB لتقارير النشرة. واكتب المعرفات في `drive`، ومعرف مجلد ENB في `drive.news_folders.enb`.
٤. أنشئ مرجع المداخلات الأولي على Drive باسم `files.intervention_reference.name`، بالبنية نفسها المستعملة في COP31 (meta وalliances وitems وupdate_log)، وابدأ بنوده من ملف التسليم. ولا يحفظ في المستودع.
٥. اكتب `sessions.main` بمعرف هذه المحادثة (get_session دون معرف).
٦. ولد نصي المهمتين:
   `python3 .claude/skills/conference-lifecycle/scripts/conference.py prompts <ID>`
   ثم أنشئ كل مهمة بـ create_trigger بالاسم والنص وسطر الجدولة كما خرجت، مرتبطة بهذه المحادثة. وإن خرج أكثر من سطر جدولة (مؤتمر يمتد على شهرين) فمهمة لكل سطر. واكتب المعرفات في `triggers`.
٧. افحص: `python3 .claude/skills/conference-lifecycle/scripts/conference.py check <ID>` حتى تكون قائمة missing فارغة.
٨. اعرض `playbook/checklist_pre_travel.md` بندا بندا، وسجل ما بقي معلقا في `references/open_items.md`.
٩. اجعل `status` active في أول أيام المؤتمر، وcommit ثم push.

## الختام: (اختم المؤتمر)

اتبع `playbook/08_closing.md` بالترتيب، وأهم ما فيه:

١. رسالة الختام للكروب بمهارة messages-media، وتذكر كل ما اعتمد في النطاق.
٢. التقرير النهائي بمهارة arabic-word-house-v3 في مسار `repo.final_report`.
٣. ملف التسليم `handover.md` للدورة التالية، على نمط `cop31/BONN_2027_handover.md`.
٤. الدروس تضاف إلى أقسام الدروس في ملفات الدليل.
٥. عطل كل مهمة في `triggers` بـ update_trigger (enabled false)، ثم ابحث بـ list_triggers عن مهام مؤقتة للمؤتمر نفسه ما زالت مفعلة وعطلها. ولا تحذف.
٦. اطلب من كل فرعية في `sessions.subs` ملف تسليمها بـ send_message.
٧. اجعل `status` closed واكتب `next_conference`، ثم commit وانتظر (ارفع إلى GitHub).

## الفحص: (افحص إعداد المؤتمر)

شغل `check` على المؤتمر النشط (`conference.py active`) واعرض ما ينقص، وقارن `triggers` بما في list_triggers.

## قواعد

١. ملف الإعداد يحمل المعرفات، أما المحتوى المغلق فيبقى في Drive.
٢. سطور الجدولة تتكرر كل سنة، فالختام يعطل المهام دائما.
٣. لا تنشأ مهمة مجدولة قبل التأكد بـ list_triggers من أنها غير موجودة.
