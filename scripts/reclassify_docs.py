"""Reclassify documents based on actual content (manual map after content review).

After reading the first 2500 chars of every doc, I'm assigning:
  - A real human-readable title (instead of the auto-extracted first-line fragment)
  - A more accurate legal_domain

New domain taxonomy (12 buckets):
  civil_procedure   — مرافعات شرعية: civil procedure law, evidence procedures
  criminal_procedure— إجراءات جزائية: criminal procedure law
  civil             — معاملات مدنية: civil transactions, torts, contracts
  commercial        — تجاري/شركات: companies, commerce, agency, securities, banking, franchise
  criminal          — جزائي: criminal law cases & studies
  family            — أحوال شخصية/أوقاف: personal status, marriage, divorce, inheritance, waqf
  labor             — عمل/تأمين اجتماعي: employment, civil service
  ip                — ملكية فكرية: trademarks, patents, copyright
  real_estate       — عقاري: property, expropriation, brokerage, units
  administrative    — إداري/ديوان المظالم: admin law, Board of Grievances, anti-corruption
  judicial_compendium — مجموعات قضائية: case law compilations (MoJ 14-vol set)
  legal_journal     — مجلة قضاء: Saudi Judicial Scientific Society quarterly issues (multi-topic)
  research_paper    — بحث مفرد: single-topic peer-reviewed papers
  practice_guide    — أدلة مهنية: lawyer trainee handbooks, professional certifications
  legal_updates     — تقارير شهرية: monthly regulatory updates
  template          — نماذج عقود: contract templates
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make app imports work
ROOT = Path(__file__).resolve().parent.parent / "apps" / "api"
sys.path.insert(0, str(ROOT))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://legalai:legalai@127.0.0.1:5433/legalai",
)

from sqlalchemy import create_engine, text  # noqa: E402

# Map of {doc_id: (new_title, new_domain)}. Titles are in Arabic; domains use
# the 16-bucket taxonomy described in the module docstring.
# The list below was hand-built after reading the first ~2500 chars of every
# document in the corpus.
MAP: dict[str, tuple[str, str]] = {
    # --- Civil Transactions Law + civil studies ---
    "1c03b4bc-9a74-4531-8493-aa90ffffeb93": (
        "نظام المعاملات المدنية مع الفهارس (هـ1445)",
        "civil",
    ),
    "4187a14c-b78e-463f-8e4d-0efeeb9ca2d7": (
        "سلطة المحكمة التقديرية في نظام المعاملات المدنية السعودي",
        "civil",
    ),
    "107ff1bd-03b7-4bf6-a04c-aaa08a47771f": (
        "سلطة المحكمة التقديرية في نظام المعاملات المدنية السعودي (نسخة 2)",
        "civil",
    ),
    "921dc743-94e6-43f4-bd1e-6f4dc3757230": (
        "المسؤولية التقصيرية لسائق السيارة الناشئة عن حوادث المرور وفقاً لنظام المعاملات المدنية",
        "civil",
    ),
    "c633a3ed-2849-49eb-9510-a4f07c796e24": (
        "المسؤولية العقدية للمحامي الناشئة عن عقد التدريب على أعمال المحاماة",
        "civil",
    ),
    "7bb78817-0e7c-4be2-bb72-12d1c38ef277": (
        "تقدير التعويض الناشئ عن الإثراء بلا سبب في نظام المعاملات المدنية السعودي",
        "civil",
    ),
    "7fcd7d0c-44dd-48ac-b3b6-7b8d25d265df": (
        "الطبيعة النظامية لحق المستثمر في الانتفاع بالأرض في عقود استثمار الأراضي",
        "real_estate",
    ),
    # --- Civil Procedure Law (نظام المرافعات الشرعية) ---
    "f365909b-36b2-435b-ad81-5a8e6f363846": (
        "نظام المرافعات الشرعية ولوائحه التنفيذية مع الفهارس",
        "civil_procedure",
    ),
    "45fa7e6e-a559-4a89-a607-36a440b88968": (
        "نظام المرافعات الشرعية ولوائحه التنفيذية – مركز البحوث 1442هـ (إصدار 2)",
        "civil_procedure",
    ),
    "a9e523ff-c8bd-426f-a57d-bb8250113470": (
        "نظام المرافعات الشرعية ولوائحه التنفيذية – مركز البحوث 1442هـ (نسخة 2)",
        "civil_procedure",
    ),
    "1d8ecbd2-25b4-44ed-ba0a-20ad50bb142d": (
        "نظام المرافعات الشرعية ولوائحه التنفيذية مع الفهارس (إصدار 1445هـ)",
        "civil_procedure",
    ),
    "7c057e2a-d4c3-40ed-bad6-9c0c74182034": (
        "تلخيص نظام المرافعات الشرعية للمتدربين القضائيين – القاضي عادل المنيع",
        "practice_guide",
    ),
    "3fae158b-fd68-4800-8595-9b8dbe1c3d39": (
        "سلطة المحكمة التقديرية في نظام الإثبات السعودي وأدلته الإجرائية",
        "civil_procedure",
    ),
    "fe945f9e-4edc-4513-92d3-e84009363e36": (
        "الحكم على المدعى عليه لتغيبه دون بينة",
        "civil_procedure",
    ),
    "05b83500-cdf4-4134-aeec-30b9bfe594b0": (
        "نظام التكاليف القضائية ولائحته التنفيذية مع الفهارس",
        "civil_procedure",
    ),
    "e3c627af-64ac-4b85-a3fb-61f807af0c20": (
        "السوابق القضائية – بحث محكم",
        "civil_procedure",
    ),
    "ab390d82-13fe-4b55-a29f-ab59c8b4fcc5": (
        "المرافعة عن بعد – بحث للشيخ القاضي بمحكمة التمييز",
        "civil_procedure",
    ),
    "bb662c3f-1064-4422-a6bb-f175f9b4a9b9": (
        "سلطة المحكمة التقديرية في نظام الأحوال الشخصية السعودي",
        "family",
    ),
    # --- Criminal Procedure Law ---
    "646eb6da-5314-4cb9-897f-77d083be054c": (
        "نظام الإجراءات الجزائية ولائحته التنفيذية – مركز البحوث 1442هـ",
        "criminal_procedure",
    ),
    "c5fcdc07-d5f5-4321-91b0-cb7a5ba199a8": (
        "نظام الإجراءات الجزائية ولائحته التنفيذية – مركز البحوث 1442هـ (نسخة 2)",
        "criminal_procedure",
    ),
    "0da66e24-8910-4d18-a75f-a0b169153826": (
        "السلطة التقديرية للقاضي الجزائي في النظام السعودي",
        "criminal_procedure",
    ),
    "db49b682-fcc3-4a72-a1fe-b01b9633e703": (
        "رد الاعتبار في النظام السعودي – بحث محكم",
        "criminal_procedure",
    ),
    # --- Real Estate Laws ---
    "0ab886cc-8a10-4132-bc80-7c94a2a93ab9": (
        "نظام نزع ملكية العقارات للمنفعة العامة ولائحته التنفيذية",
        "real_estate",
    ),
    "53145f20-f37d-4c17-8601-e6b4a2d3c2c3": (
        "نظام المساهمات العقارية ولائحته التنفيذية مع الفهارس",
        "real_estate",
    ),
    "5e041200-298b-4d8e-be44-97a5fbe80250": (
        "نظام ملكية الوحدات العقارية وفرزها وإدارتها ولائحته التنفيذية",
        "real_estate",
    ),
    "b1f99bfb-8ab6-46aa-83fe-0c05e6bf9c52": (
        "نظام الوساطة العقارية ولوائحه التنفيذية والتنظيمية",
        "real_estate",
    ),
    # --- Commercial / Companies ---
    "b1d1435f-8e51-4038-b4ac-be3bb653e19f": (
        "أهم المهمات في نظام الشركات بطريقة السؤال والجواب",
        "commercial",
    ),
    "bc565525-86a3-4ef5-bf7c-a58ea64af647": (
        "القواعد والمسائل القانونية في إدارة الشركات",
        "commercial",
    ),
    "5fdc8a1e-633c-4508-bff7-cf4d6d625390": (
        "المستجدات في عقود الشركات بعد صدور نظام المعاملات المدنية",
        "commercial",
    ),
    "f4a96768-ea6e-42a9-90fa-5ac40ddf0ef3": (
        "نظام الامتياز التجاري ولائحته التنفيذية وملحقاته",
        "commercial",
    ),
    "535aff07-90c2-44a3-bc82-a26bae3faa8c": (
        "أسباب وآثار إنهاء عقد الوكالة التجارية في الفقه والنظام السعودي",
        "commercial",
    ),
    "68faed69-cdfa-4fc5-b5c5-a710d9aeb88f": (
        "أسباب وآثار إنهاء عقد الوكالة التجارية في الفقه والنظام السعودي (نسخة 2)",
        "commercial",
    ),
    "88a9a944-e115-476d-bb6b-fc7be71eb3ba": (
        "مدونة الأحكام التجارية – قضايا الشركات 1441هـ (الحمودي)",
        "commercial",
    ),
    "eb278b24-ec9c-4d50-8f1b-c7d06353398c": (
        "مدونة الأحكام التجارية – قضايا التعويض 1441هـ (الحمودي)",
        "commercial",
    ),
    "8c04d267-1872-478a-b615-c7e31a53229a": (
        "قضايا صناديق الاستثمار أمام لجنة الفصل في منازعات الأوراق المالية (الحمودي)",
        "commercial",
    ),
    "72329aa8-5da9-419f-9999-ba3ccc63e9f5": (
        "قضايا العقود الخاصة أمام لجنة الفصل في منازعات الأوراق المالية (الحمودي)",
        "commercial",
    ),
    "1feda9db-6826-4491-a834-05d322490098": (
        "التوقيع على بياض – دراسة قضائية (مبارك الزايد)",
        "commercial",
    ),
    # --- IP ---
    "a1a457b9-707a-4361-bd42-f11358247bba": (
        "دعاوى الملكية الفكرية – دليل المالزم القضائي بدائرة الملكية الفكرية",
        "ip",
    ),
    "ea89f423-39bc-4f89-be70-54354237e558": (
        "العلامات التجارية والاسم التجاري – أحكامها وحمايتها في النظام السعودي",
        "ip",
    ),
    # --- Labor / Civil Service ---
    "ae5eece0-82ed-4c5c-b9ae-180032d6ad7a": (
        "أهم المواد التي يجب معرفتها في نظام العمل السعودي",
        "labor",
    ),
    "f2a539d9-b188-4849-bb7d-7dfde92ddab0": (
        "الاستقالة في قانون العمل والقانون الإداري – دراسة مقارنة",
        "labor",
    ),
    "5385e0d1-d274-4af1-a31c-cdf28800fcef": (
        "الحقوق المالية للموظفين العموميين – دراسة مقارنة بالعمل الخاص",
        "labor",
    ),
    # --- Administrative / Board of Grievances / Anti-Corruption ---
    "212f9736-47f9-4652-b378-aba8585cea83": (
        "ديوان المظالم – مجموعة الأحكام القضائية 1436-1437هـ (المجلد الأول)",
        "administrative",
    ),
    "f4174a5a-138e-43c4-92b4-966c83b19f50": (
        "ديوان المظالم – مجموعة الأحكام القضائية 1436-1437هـ (المجلد الثاني)",
        "administrative",
    ),
    "5b599b22-90c8-4a44-b33d-57b77a03b18c": (
        "نظام المرافعات أمام ديوان المظالم ولائحته التنفيذية",
        "administrative",
    ),
    "028cfaf5-98f9-4503-9837-6e8e3b6e8369": (
        "نظام التنفيذ أمام ديوان المظالم ولائحته التنفيذية مع الفهارس",
        "administrative",
    ),
    "dc4a4952-fb5b-4277-a63b-dab925458e36": (
        "نظام استئجار الدولة للعقار ولائحته التنفيذية مع الفهارس",
        "administrative",
    ),
    "a2a0efa0-f2df-4aa3-ac78-71d1b2bfb08c": (
        "نظام هيئة الرقابة ومكافحة الفساد مع الفهارس",
        "administrative",
    ),
    "b7864bea-e0c1-4294-9162-913f10e1c7c3": (
        "تنظيم الهيئة الوطنية لمكافحة الفساد – قرار مجلس الوزراء (165) 1432هـ",
        "administrative",
    ),
    "9ebfcbe5-ab94-4cb9-a0cb-d57027f6c81e": (
        "نظام الأسلحة والذخائر ولائحته التنفيذية مع الفهارس",
        "administrative",
    ),
    # --- Family / Waqf ---
    "e1a69bd0-9d2b-4bdc-8387-16db64920fe6": (
        "أحكام العزل من نظارة الوقف وفقاً للائحة تنظيم أعمال النظارة",
        "family",
    ),
    # --- MoJ 14-Volume Judicial Rulings Compilation (1435H) ---
    "9275551c-0612-447f-b146-3f420093a4f7": (
        "مجموعة الأحكام القضائية لعام 1435هـ – وزارة العدل (المجلد 1)",
        "judicial_compendium",
    ),
    "efd89ad6-af1a-485d-a956-fc23484217ae": (
        "مجموعة الأحكام القضائية لعام 1435هـ – وزارة العدل (المجلد 5)",
        "judicial_compendium",
    ),
    "59f6cc49-d937-4b93-bd84-b6b28ce4ca9f": (
        "مجموعة الأحكام القضائية لعام 1435هـ – وزارة العدل (المجلد 13)",
        "judicial_compendium",
    ),
    "bdaf329f-66f3-43cd-a21a-84f03b7bdf07": (
        "مجموعة الأحكام القضائية لعام 1435هـ – وزارة العدل (المجلد 10)",
        "judicial_compendium",
    ),
    "6285102c-3bf3-4390-9617-58da426d9ed6": (
        "مجموعة الأحكام القضائية لعام 1435هـ – وزارة العدل (المجلد 14)",
        "judicial_compendium",
    ),
    "8929031f-efe6-43aa-a7bd-0473d404de8b": (
        "مجموعة الأحكام القضائية لعام 1435هـ – وزارة العدل (المجلد 6)",
        "judicial_compendium",
    ),
    "fec8c1c8-7b66-4453-a64b-70804c94c9a1": (
        "مجموعة الأحكام القضائية لعام 1435هـ – وزارة العدل (المجلد 7)",
        "judicial_compendium",
    ),
    "7f416a6a-fd7d-4b3f-b481-f5f7a2aa47ec": (
        "مجموعة الأحكام القضائية لعام 1435هـ – وزارة العدل (المجلد 8)",
        "judicial_compendium",
    ),
    "722b8452-ef99-419b-a7a6-1b848c7e8d60": (
        "مجموعة الأحكام القضائية لعام 1435هـ – وزارة العدل (المجلد 9)",
        "judicial_compendium",
    ),
    "e3a7f28a-5faa-4950-99ac-f3d353f73dc5": (
        "مجموعة الأحكام القضائية لعام 1435هـ – وزارة العدل (المجلد 11)",
        "judicial_compendium",
    ),
    "4b4c08df-3be5-4507-a47a-192aea72986b": (
        "مجموعة الأحكام القضائية لعام 1435هـ – وزارة العدل (المجلد 12)",
        "judicial_compendium",
    ),
    "4bbaca4f-f05b-4310-a83d-3bd2356ddf84": (
        "مجموعة الأحكام القضائية لعام 1435هـ – وزارة العدل (المجلد 3)",
        "judicial_compendium",
    ),
    # --- Saudi Judicial Scientific Society Journal (مجلة قضاء) ---
    "c869cf41-cc8d-4c5f-929f-d20ecacc680c": (
        "مجلة قضاء – العدد 38 (رجب 1446هـ / يناير 2025م)",
        "legal_journal",
    ),
    "f7e81bbe-9b77-4d48-ab12-643ea53e083c": (
        "مجلة قضاء – العدد 37 (ربيع الثاني 1446هـ / نوفمبر 2024م)",
        "legal_journal",
    ),
    "e7c7cc2b-3a09-433f-8dca-4ed277ef8fe6": (
        "مجلة قضاء – العدد 33 (جمادى الأولى 1445هـ / ديسمبر 2023م)",
        "legal_journal",
    ),
    "6fd9327c-b780-4cb4-b15a-c7f923f2ae20": (
        "مجلة قضاء – العدد 29 (ربيع الثاني 1444هـ / نوفمبر 2022م)",
        "legal_journal",
    ),
    "ae74da8a-6be6-4d5b-9145-db239a635181": (
        "مجلة قضاء – العدد 34 (شعبان 1445هـ / فبراير 2024م)",
        "legal_journal",
    ),
    "f438ebab-04c9-462a-9085-c00ef660c03f": (
        "مجلة قضاء – العدد 27 (شوال 1443هـ / مايو 2022م)",
        "legal_journal",
    ),
    "bebb5f96-b839-4ebe-bd3b-4a96d660187e": (
        "مجلة قضاء – العدد 36 (محرم 1446هـ / أغسطس 2024م)",
        "legal_journal",
    ),
    "c4517cf8-09e7-47a5-861a-8b55c2a3ba64": (
        "مجلة قضاء – العدد 36 (محرم 1446هـ) – نسخة 2",
        "legal_journal",
    ),
    "aaab05ee-f371-4f19-a426-a7b3f227ecdb": (
        "مجلة قضاء – العدد 31 (شوال 1444هـ / أبريل 2023م)",
        "legal_journal",
    ),
    "4b89968a-b203-4fe2-93a0-009815b41ff2": (
        "مجلة قضاء – العدد 30 (رجب 1444هـ / فبراير 2023م)",
        "legal_journal",
    ),
    "dda69a06-2040-432a-924d-549f797cfb07": (
        "مجلة قضاء – العدد 35 (شوال 1445هـ / مايو 2024م)",
        "legal_journal",
    ),
    "bc7a0cfe-f645-4555-9b8e-b1eb946f5369": (
        "مجلة قضاء – العدد 32 (محرم 1445هـ / أغسطس 2023م)",
        "legal_journal",
    ),
    "22e54360-9bf7-42a3-8f63-f0af7e342774": (
        "مجلة قضاء – العدد 28 (محرم 1444هـ / سبتمبر 2022م)",
        "legal_journal",
    ),
    # --- Saudi Judicial Scientific Society — Single Research Papers ---
    "1d0e66e9-322b-472a-8bc0-e8f51ab02052": (
        "أطروحة دكتوراه – جامعة بيروت الإسلامية / محمد زكريا الشافعي الحلبي (746 صفحة)",
        "research_paper",
    ),
    "ff5abba6-2180-4125-a503-3f4699c6f4e0": (
        "الدفوع الموضوعية في دعاوى الأحوال الشخصية غير الزوجية – رزان الوزان (ماجستير)",
        "research_paper",
    ),
    "ff5abba6-2180-4125-a503-3f4699c6f4e0".replace("a503", "a504"): ("", ""),  # placeholder ignored
    "74b4c7f0-a635-47ce-9866-71cc75df31fe": (
        "أثر الوجاهة في التعزير – بحث محكم (د. أحمد الفهد)",
        "research_paper",
    ),
    "b78d2d8d-a27a-41d3-89b7-032d654a6aef": (
        "الاستعانة بأهل الخبرة في القضاء – بحث محكم (د. فهد الصغير)",
        "research_paper",
    ),
    "267612ce-9eb5-4950-90e5-d50fdf17445b": (
        "التلوث البيئي البري في النظام السعودي – بحث محكم (د. قاسم الفلاح)",
        "research_paper",
    ),
    "ce91b79c-a545-4b67-bfce-75329de7ce19": (
        "الجمع بين أرش الجناية وأجرة الطبيب – بحث (د. محمد التويم)",
        "research_paper",
    ),
    # --- Judicial Scientific Society "Other" research items ---
    "24635ac6-4cd7-444d-9caa-eb8c61e73346": (
        "حالة الوثائق القانونية في المملكة – دراسة تشريعية (167 صفحة)",
        "research_paper",
    ),
    "46aeb18d-0223-4b76-a06e-bf5d2299ed4b": (
        "بحث منشور من الجمعية العلمية القضائية السعودية (47 صفحة)",
        "research_paper",
    ),
    # --- MoJ Monthly Updates ---
    "bf521ad0-ad8c-492f-a7e1-c8ec39741089": (
        "التقرير الشهري لمستجدات الأنظمة واللوائح – شعبان/رمضان/شوال 1440هـ",
        "legal_updates",
    ),
    "3a0d5571-6d30-4b90-a243-228b47f9955f": (
        "التقرير الشهري لمستجدات الأنظمة – صفر 1441هـ (الإصدار 5)",
        "legal_updates",
    ),
    "c3fff85d-ac27-44d0-8963-fa82b9b65a1d": (
        "التقرير الشهري لمستجدات الأنظمة – جمادى الأول 1441هـ (الإصدار 8)",
        "legal_updates",
    ),
    "533a9c80-6a48-4fe4-af21-94b766151f8d": (
        "التقرير الشهري لمستجدات الأنظمة – جمادى الآخر 1441هـ (الإصدار 9)",
        "legal_updates",
    ),
    "ed19a9ce-ad08-4ed0-93bb-a1e3607894a9": (
        "التقرير الشهري لمستجدات الأنظمة – جمادى الثاني 1446هـ (الإصدار 69)",
        "legal_updates",
    ),
    "11f11635-caec-425b-9782-1ac3bc6b13ab": (
        "التقرير الشهري لمستجدات الأنظمة – رجب 1446هـ (الإصدار 70)",
        "legal_updates",
    ),
    # --- Practice Guides ---
    "c7e51e00-9eac-455c-9669-a1766226a574": (
        "رزمة المحامي المتدرب – دليل المحامي المبتدئ",
        "practice_guide",
    ),
    "a4af8bdb-edb5-40ad-954f-dd08bcd52f52": (
        "سبل القانون – دليل المحامي المتدرب",
        "practice_guide",
    ),
    "62e79ca6-7e1d-4295-a096-42770152724c": (
        "دليل أهم الشهادات المهنية في المجال القانوني – حصة المبرد",
        "practice_guide",
    ),
    # --- Contract Templates ---
    "61038680-cb27-4343-8be2-aa9956314572": (
        "عقد تصميم هندسي – نموذج (إف جيز للاستشارات الهندسية)",
        "template",
    ),
    "ba096088-255b-45b1-b73e-b41fd0b66d9f": (
        "نموذج عقد إيجار سيارة",
        "template",
    ),
}


def main() -> None:
    eng = create_engine(os.environ["DATABASE_URL"])
    updated = 0
    skipped = 0
    with eng.begin() as conn:
        for doc_id, (title, domain) in MAP.items():
            if not doc_id or not title:
                continue
            res = conn.execute(
                text(
                    """
                    UPDATE documents
                    SET title = :title, legal_domain = :domain
                    WHERE id = :id
                    """
                ),
                {"id": doc_id, "title": title, "domain": domain},
            )
            if res.rowcount > 0:
                updated += 1
            else:
                skipped += 1
                print(f"  ! not-found: {doc_id}")

    print(f"Updated {updated} docs (skipped {skipped})")

    # Print the new distribution
    with eng.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT COALESCE(legal_domain, 'unclassified') AS d, COUNT(*) c
                FROM documents
                GROUP BY legal_domain
                ORDER BY c DESC
                """
            )
        ).all()
        print()
        print("New domain distribution:")
        for d, c in rows:
            print(f"  {d}: {c}")


if __name__ == "__main__":
    main()
