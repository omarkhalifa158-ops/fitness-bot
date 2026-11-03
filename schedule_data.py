"""
Schedule Data and Lead-Time Calculation Logic
Timezone: Africa/Cairo (UTC+2)
"""
from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Optional

# =====================================================================
# 1. تعريف فئات التنبيه وأوقات الإشعار المسبق (Lead Time Logic)
# =====================================================================
CATEGORIES = {
    "OUTSIDE_ORDER_MEAL": {
        "name_ar": "وجبة تتطلب شراء/طلب خارجي",
        "lead_time_minutes": 60,
        "badge_emoji": "🍗",
        "description": "إشعار قبل الوجبة بـ 60 دقيقة لتتمكن من الشراء والطلب في طريق عودتك"
    },
    "LIGHT_MEAL_OR_SNACK": {
        "name_ar": "وجبة خفيفة / سناك / شيك",
        "lead_time_minutes": 15,
        "badge_emoji": "⚡",
        "description": "إشعار قبل الوجبة بـ 15 دقيقة للتحضير السريع"
    },
    "WORKOUT": {
        "name_ar": "تمرين رياضي منزلي",
        "lead_time_minutes": 10,
        "badge_emoji": "💪",
        "description": "إشعار قبل التمرين بـ 10 دقائق لارتداء الملابس والاستعداد"
    },
    "SLEEP_ROUTINE": {
        "name_ar": "روتين النوم وترك الهاتف",
        "lead_time_minutes": 30,
        "badge_emoji": "📵",
        "description": "إشعار قبل موعد النوم بـ 30 دقيقة لترك الشاشات والهاتف"
    },
    "ALARM_OR_ROUTINE": {
        "name_ar": "منبه الاستيقاظ الصباحي",
        "lead_time_minutes": 0,
        "badge_emoji": "⏰",
        "description": "منبه في تمام الساعة 07:45 صباحاً (8 إلا ربع) لبدء اليوم بنشاط"
    }
}

# أسماء الأيام باللغة العربية (0: الإثنين إلى 6: الأحد)
WEEKDAYS_AR = {
    0: "الإثنين",
    1: "الثلاثاء",
    2: "الأربعاء",
    3: "الخميس",
    4: "الجمعة",
    5: "السبت",
    6: "الأحد"
}

# =====================================================================
# 2. نصوص الوجبات اليومية الثابتة (Fixed Daily Meals)
# =====================================================================
FIXED_MEALS = {
    "morning_alarm": {
        "id": "morning_alarm",
        "title": "⏰ منبه الاستيقاظ والروتين الصباحي",
        "event_time": "07:45",
        "category": "ALARM_OR_ROUTINE",
        "text": (
            "⏰ *منبه الاستيقاظ والروتين الصباحي (8 إلا ربع - 7:45 ص):*\n"
            "• صباح الخير والنشاط! 🌅 حان وقت الاستيقاظ.\n"
            "• اشرب كوب أو كوبين ماء فاتر لتنشيط الدورة الدموية وتجهيز الهضم.\n"
            "• استعد لوجبة الفطار والمكملات بعد 15 دقيقة (الساعة 8:00 ص)!"
        )
    },
    "breakfast": {
        "id": "breakfast",
        "title": "🍳 وجبة الفطار",
        "event_time": "08:00",
        "category": "LIGHT_MEAL_OR_SNACK",
        "text": (
            "🍳 *تذكير الفطار (بعد 15 دقيقة - 8:00 ص):*\n"
            "• قرص دايجستين وسط الأكل + كبسولة فيتامين د بعد الفطار.\n"
            "• 3 بيضات مسلوقة (أو أومليت في نقطة زيت زيتون).\n"
            "• 150 جرام بطاطس أو بطاطا مسلوقة مهروسة + رغيف عيش بلدي (100 جرام).\n"
            "• 50 جرام جبنة رودس طبيعي عليها ملعقة كبيرة زيت زيتون (15 مل) + ملعقة سمسم محمص (10 جرام)."
        )
    },
    "work_snack": {
        "id": "work_snack",
        "title": "🥜 سناك الشغل",
        "event_time": "12:30",
        "category": "LIGHT_MEAL_OR_SNACK",
        "text": (
            "🥜 *تذكير سناك الشغل (بعد 15 دقيقة - 12:30 ظ):*\n"
            "• 2 ثمرة موز متوسطة مهروسة بالشوكة مع 2 ملعقة كبيرة زبدة فول سوداني (40 جرام).\n"
            "• حفنة لب يقطين (لب أبيض - 20 جرام)."
        )
    },
    "post_workout_shake": {
        "id": "post_workout_shake",
        "title": "🥤 شيك الضخامة السريع",
        "event_time": "19:15",
        "category": "LIGHT_MEAL_OR_SNACK",
        "text": (
            "🥤 *تذكير مشروب الضخامة السريع بدون خلاط (بعد 15 دقيقة - 7:15 م):*\n"
            "حضر الكوب الآن لينقع الشوفان 5 دقائق:\n"
            "• 250 مل لبن كامل الدسم دافئ + 50 جرام شوفان مطحون بودرة (4 ملاعق كبيرة).\n"
            "• 1 سكوب واي بروتين أيزوليت (30 جرام) + ملعقة صغيرة كاكاو خام.\n"
            "• ملعقة كبيرة عسل نحل (بدون زيت أو سمسم)."
        )
    },
    "dinner": {
        "id": "dinner",
        "title": "🍽️ العشاء ومكمل الحديد",
        "event_time": "21:30",
        "category": "LIGHT_MEAL_OR_SNACK",
        "text": (
            "🍽️ *تذكير العشاء والحديد (بعد 15 دقيقة - 9:30 م):*\n"
            "⚠️ *ممنوع اللبن أو الجبنة في هذه الوجبة لامتصاص الحديد!*\n"
            "• الاختيار (أ): علبة تونة قطع مصفاة من الزيت (140 جرام) عليها ليمون وكمون وملعقة زيت زيتون + رغيف عيش بلدي.\n"
            "• أو الاختيار (ب): 2 بيضة مسلوقة + 150 جرام بطاطا أو بطاطس مسلوقة + ملعقة زيت زيتون.\n"
            "• 💊 بعد العشاء مباشرة: جرعة شراب الحديد + أكل برتقالة سليمة أو جوافة بدون بذر."
        )
    },
    "bedtime_prep": {
        "id": "bedtime_prep",
        "title": "📵 تذكير الاستعداد للنوم وترك الهاتف",
        "event_time": "23:00",
        "category": "SLEEP_ROUTINE",
        "text": (
            "📵 *اترك الهاتف الآن واستعد للنوم (باقي 30 دقيقة - 10:30 م):*\n"
            "• حان وقت إغلاق الشاشات وترك الهاتف تماماً لتهيئة الدماغ لإفراز هرمون الميلاتونين.\n"
            "• هيئ غرفتك (إضاءة خافتة، جو هادئ، حرارة معتدلة).\n"
            "• النوم العميق (7-8 ساعات) هو حجر الأساس للبناء العضلي، استشفاء الألياف، وزيادة هرمون النمو (GH).\n"
            "• تصبح على صحة وخير ونشاط! 🌙💤"
        )
    }
}

# =====================================================================
# 3. جدول الغداء المتغير حسب اليوم (04:30 PM | تنبيه 03:30 PM)
# =====================================================================
LUNCH_SCHEDULE = {
    # السبت (5) والثلاثاء (1)
    "sat_tue": {
        "days": [5, 1],
        "title": "🍗 غداء وركين الفراخ المشوية",
        "text": (
            "🍗 *تذكير الغداء (باقي ساعة - 4:30 عصراً):*\n"
            "🛍️ *تذكر تشتري وأنت مروح!*\n"
            "• وركين فراخ مشوية جاهزة منزوعة الجلد (250 جرام صافي).\n"
            "• 250 جرام بطاطس مسلوقة أو أرز أبيض جاهز + طبق سلطة بملعقة زيت زيتون وكمون.\n"
            "• قرص دايجستين وسط الأكل."
        )
    },
    # الأحد (6) والأربعاء (2)
    "sun_wed": {
        "days": [6, 2],
        "title": "🍝 غداء صدور الفراخ والمكرونة",
        "text": (
            "🍝 *تذكير الغداء (باقي ساعة - 4:30 عصراً):*\n"
            "🛍️ *تذكر تشتري الفراخ وأنت مروح!*\n"
            "• 200 جرام صدور فراخ مشوية جاهزة.\n"
            "• 250 جرام مكرونة مسلوقة بصلصة طماطم حمراء خفيفة وملعقة زيت زيتون (بدون وايت صوص أو كريمة).\n"
            "• قرص دايجستين وسط الأكل."
        )
    },
    # الإثنين (0) والخميس (3)
    "mon_thu": {
        "days": [0, 3],
        "title": "🐟 غداء التونة السريع / فراخ مشوية",
        "text": (
            "🐟 *تذكير الغداء السريع (باقي ساعة - 4:30 عصراً):*\n"
            "• علبة تونة قطع كبيرة مصفاة (أو وركين فراخ مشوية جاهزة 250 جرام).\n"
            "• 250 جرام بطاطا أو بطاطس مسلوقة + رغيف عيش بلدي + سلطة خضراء.\n"
            "• قرص دايجستين وسط الأكل."
        )
    },
    # الجمعة (4)
    "fri": {
        "days": [4],
        "title": "🥩 غداء الجمعة (لحم/كفتة مشوية)",
        "text": (
            "🥩 *تذكير غداء الجمعة (باقي ساعة - 4:30 عصراً):*\n"
            "• 200 جرام لحم مشوي أو كفتة مشوية قليلة الدهن (أو فراخ مشوية جاهزة).\n"
            "• 250 جرام أرز أبيض أو بطاطس مسلوقة + سلطة خضراء بملعقة زيت زيتون.\n"
            "• قرص دايجستين وسط الأكل."
        )
    }
}

# =====================================================================
# 4. جدول التمارين المنزلية المتغير (06:15 PM | تنبيه 06:05 PM)
# =====================================================================
WORKOUT_SCHEDULE = {
    # السبت (5) والثلاثاء (1)
    "sat_tue": {
        "days": [5, 1],
        "name": "علوي دفع (Upper Body A - Push Focus)",
        "type": "WORKOUT",
        "text": (
            "💪 *استعد للتمرين بعد 10 دقائق (6:15 م - علوي دفع):*\n"
            "1️⃣ ضغط صدر بالدامبلز على الأرض (Floor Dumbbell Press): 4 مجموعات × 10-12 عدة.\n"
            "2️⃣ ضغط أكتاف بالدامبلز جالساً (Seated Shoulder Press): 3 مجموعات × 10-12 عدة.\n"
            "3️⃣ تمرين ضغط عادي أو على الركبة (Push-ups): 3 مجموعات × أقصى تكرار.\n"
            "4️⃣ رفرفة جانبي بالدامبلز أو الحبل للكتف (Lateral Raises): 3 مجموعات × 15 عدة.\n"
            "5️⃣ ترايسبس بالدامبل خلف الرأس أو بالحبل (Triceps Extension): 3 مجموعات × 12 عدة."
        )
    },
    # الأحد (6) والأربعاء (2)
    "sun_wed": {
        "days": [6, 2],
        "name": "أرجل وبطن (Lower Body & Core - Legs)",
        "type": "WORKOUT",
        "text": (
            "🦵 *استعد للتمرين بعد 10 دقائق (6:15 م - أرجل وبطن):*\n"
            "1️⃣ سكوات بالدامبلز (Goblet Squat): 4 مجموعات × 12 عدة.\n"
            "2️⃣ رفعة مميتة رومانية بالدامبلز للخلفيات (Romanian Deadlift): 4 مجموعات × 10-12 عدة.\n"
            "3️⃣ طعن بالدامبلز (Dumbbell Lunges): 3 مجموعات × 10 عدات لكل رجل.\n"
            "4️⃣ سمانة بالدامبلز (Calf Raises): 4 مجموعات × 15-20 عدة.\n"
            "5️⃣ تمرين بلانك لشد البطن ومنع الكرش (Plank): 3 جولات × 45 ثانية."
        )
    },
    # الخميس (3)
    "thu": {
        "days": [3],
        "name": "علوي سحب وظهر (Upper Body B - Pull Focus)",
        "type": "WORKOUT",
        "text": (
            "🔥 *استعد للتمرين بعد 10 دقائق (6:15 م - علوي سحب وظهر):*\n"
            "1️⃣ عقلة باب بمساعدة حبل المقاومة (Pull-ups / Chin-ups): 4 مجموعات × أقصى تكرار.\n"
            "2️⃣ سحب دامبل مفرد للظهر (One-Arm Dumbbell Row): 4 مجموعات × 10-12 عدة.\n"
            "3️⃣ سحب حبل مقاومة للوجه والكتف الخلفي (Band Face Pulls): 3 مجموعات × 15 عدة.\n"
            "4️⃣ بايسبس تبادل بالدامبلز (Dumbbell Bicep Curls): 3 مجموعات × 12 عدة.\n"
            "5️⃣ بايسبس شاكوش (Hammer Curls): 3 مجموعات × 12 عدة."
        )
    },
    # الإثنين (0) والجمعة (4) - راحة
    "mon_fri_rest": {
        "days": [0, 4],
        "name": "راحة واستشفاء عضلي (Rest Days)",
        "type": "REST",
        "text": (
            "🧘‍♂️ *اليوم راحة واستشفاء عضلي (6:15 م):*\n"
            "لا يوجد تمرين حديد اليوم! يمكنك المشي الخفيف لمدة 20 دقيقة لتحفيز الهضم والشهية."
        )
    }
}

# =====================================================================
# 5. دوال حساب التوقيت والمهلة (Lead Time Calculator)
# =====================================================================
def calculate_alert_time(event_time_str: str, lead_time_minutes: int) -> str:
    """
    تحسب وقت إطلاق الإشعار بطرح دقائق المهلة من وقت الوجبة/التمرين
    مثال: 16:30 - 60 دقيقة = 15:30
    """
    h, m = map(int, event_time_str.split(":"))
    dummy_date = datetime(2026, 1, 1, h, m)
    alert_dt = dummy_date - timedelta(minutes=lead_time_minutes)
    return alert_dt.strftime("%H:%M")

def get_lunch_for_weekday(weekday: int) -> Dict[str, Any]:
    """تحديد وجبة الغداء المناسبة لليوم المحدد (0=الإثنين ... 6=الأحد)"""
    for key, data in LUNCH_SCHEDULE.items():
        if weekday in data["days"]:
            return data
    return LUNCH_SCHEDULE["sat_tue"]

def get_workout_for_weekday(weekday: int) -> Dict[str, Any]:
    """تحديد تمرين اليوم المناسب (0=الإثنين ... 6=الأحد)"""
    for key, data in WORKOUT_SCHEDULE.items():
        if weekday in data["days"]:
            return data
    return WORKOUT_SCHEDULE["sat_tue"]

def get_day_schedule(weekday: int, custom_texts: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """
    تُرجع القائمة الكاملة المجدولة لليوم مرتبة تصاعدياً حسب وقت الإشعار (Alert Time).
    تحسب تلقائياً أوقات الإشعار مع إمكانية دمج أي تعديلات مخصصة للنصوص من الـ Dashboard.
    """
    custom_texts = custom_texts or {}
    schedule = []

    # 0. منبه الاستيقاظ (07:45 ص - 8 إلا ربع)
    alarm = FIXED_MEALS["morning_alarm"]
    alarm_lead = CATEGORIES[alarm["category"]]["lead_time_minutes"]
    schedule.append({
        "id": "morning_alarm",
        "title": alarm["title"],
        "category": alarm["category"],
        "event_time": alarm["event_time"],
        "alert_time": alarm["event_time"], # 07:45 ص مباشرة
        "lead_time": alarm_lead,
        "badge_emoji": CATEGORIES[alarm["category"]]["badge_emoji"],
        "text": custom_texts.get("morning_alarm", alarm["text"])
    })

    # 1. وجبة الفطار
    bf = FIXED_MEALS["breakfast"]
    bf_alert = calculate_alert_time(bf["event_time"], CATEGORIES[bf["category"]]["lead_time_minutes"])
    schedule.append({
        "id": "breakfast",
        "title": bf["title"],
        "category": bf["category"],
        "event_time": bf["event_time"],
        "alert_time": bf_alert,
        "lead_time": CATEGORIES[bf["category"]]["lead_time_minutes"],
        "badge_emoji": CATEGORIES[bf["category"]]["badge_emoji"],
        "text": custom_texts.get("breakfast", bf["text"])
    })

    # 2. سناك الشغل
    snk = FIXED_MEALS["work_snack"]
    snk_alert = calculate_alert_time(snk["event_time"], CATEGORIES[snk["category"]]["lead_time_minutes"])
    schedule.append({
        "id": "work_snack",
        "title": snk["title"],
        "category": snk["category"],
        "event_time": snk["event_time"],
        "alert_time": snk_alert,
        "lead_time": CATEGORIES[snk["category"]]["lead_time_minutes"],
        "badge_emoji": CATEGORIES[snk["category"]]["badge_emoji"],
        "text": custom_texts.get("work_snack", snk["text"])
    })

    # 3. الغداء المتغير (طلب خارجي - مهلة 60 دقيقة)
    lunch_info = get_lunch_for_weekday(weekday)
    lunch_category = "OUTSIDE_ORDER_MEAL"
    lunch_lead = CATEGORIES[lunch_category]["lead_time_minutes"] # 60 minutes
    lunch_alert = calculate_alert_time("16:30", lunch_lead) # 15:30 (03:30 PM)
    lunch_id = f"lunch_day_{weekday}"
    schedule.append({
        "id": lunch_id,
        "title": f"الغداء: {lunch_info['title']}",
        "category": lunch_category,
        "event_time": "16:30",
        "alert_time": lunch_alert,
        "lead_time": lunch_lead,
        "badge_emoji": CATEGORIES[lunch_category]["badge_emoji"],
        "text": custom_texts.get(lunch_id, lunch_info["text"])
    })

    # 4. التمرين المنزلي أو الراحة (مهلة 10 دقائق)
    wo_info = get_workout_for_weekday(weekday)
    wo_category = "WORKOUT"
    wo_lead = CATEGORIES[wo_category]["lead_time_minutes"] # 10 minutes
    wo_alert = calculate_alert_time("18:15", wo_lead) # 18:05 (06:05 PM)
    wo_id = f"workout_day_{weekday}"
    schedule.append({
        "id": wo_id,
        "title": f"التمرين: {wo_info['name']}",
        "category": wo_category,
        "event_time": "18:15",
        "alert_time": wo_alert,
        "lead_time": wo_lead,
        "badge_emoji": CATEGORIES[wo_category]["badge_emoji"],
        "text": custom_texts.get(wo_id, wo_info["text"])
    })

    # 5. مشروب الضخامة بعد التمرين
    shk = FIXED_MEALS["post_workout_shake"]
    shk_alert = calculate_alert_time(shk["event_time"], CATEGORIES[shk["category"]]["lead_time_minutes"])
    schedule.append({
        "id": "post_workout_shake",
        "title": shk["title"],
        "category": shk["category"],
        "event_time": shk["event_time"],
        "alert_time": shk_alert,
        "lead_time": CATEGORIES[shk["category"]]["lead_time_minutes"],
        "badge_emoji": CATEGORIES[shk["category"]]["badge_emoji"],
        "text": custom_texts.get("post_workout_shake", shk["text"])
    })

    # 6. العشاء ومكمل الحديد
    dnr = FIXED_MEALS["dinner"]
    dnr_alert = calculate_alert_time(dnr["event_time"], CATEGORIES[dnr["category"]]["lead_time_minutes"])
    schedule.append({
        "id": "dinner",
        "title": dnr["title"],
        "category": dnr["category"],
        "event_time": dnr["event_time"],
        "alert_time": dnr_alert,
        "lead_time": CATEGORIES[dnr["category"]]["lead_time_minutes"],
        "badge_emoji": CATEGORIES[dnr["category"]]["badge_emoji"],
        "text": custom_texts.get("dinner", dnr["text"])
    })

    # 7. الاستعداد للنوم وترك الهاتف (10:30 م - قبل النوم بنصف ساعة)
    slp = FIXED_MEALS["bedtime_prep"]
    slp_lead = CATEGORIES[slp["category"]]["lead_time_minutes"]
    slp_alert = calculate_alert_time(slp["event_time"], slp_lead) # 22:30
    schedule.append({
        "id": "bedtime_prep",
        "title": slp["title"],
        "category": slp["category"],
        "event_time": slp["event_time"],
        "alert_time": slp_alert,
        "lead_time": slp_lead,
        "badge_emoji": CATEGORIES[slp["category"]]["badge_emoji"],
        "text": custom_texts.get("bedtime_prep", slp["text"])
    })

    # ترتيب الجدول حسب وقت الإشعار
    schedule.sort(key=lambda x: x["alert_time"])
    return schedule

def format_day_summary_text(weekday: int, custom_texts: Optional[Dict[str, str]] = None) -> str:
    """
    تنسيق جدول اليوم بالكامل كرسالة واضحة وأنيقة للتيليجرام والواتساب بتنسيق HTML الآمن
    """
    day_name = WEEKDAYS_AR.get(weekday, "اليوم")
    events = get_day_schedule(weekday, custom_texts)

    header = f"📅 <b>جدول اليوم ({day_name}) - مواعيد الوجبات والتمارين</b>\n"
    header += f"⏰ <b>المنطقة الزمنية: توقيت القاهرة (UTC+2)</b>\n"
    header += "━━━━━━━━━━━━━━━━━━━━\n\n"

    body_parts = []
    for ev in events:
        # تنظيف علامات الماركداون واستبدالها بنصوص واضحة
        clean_ev_text = ev['text'].replace('*', '')
        body_parts.append(
            f"{ev['badge_emoji']} <b>{ev['title']}</b>\n"
            f"⏱️ موعد الحدث: <code>{ev['event_time']}</code> | 🔔 وقت التنبيه: <code>{ev['alert_time']}</code> (قبلها بـ {ev['lead_time']} دقيقة)\n"
            f"{clean_ev_text}\n"
        )

    footer = "━━━━━━━━━━━━━━━━━━━━\n💪 <b>التزم بجدولك وحقق هدفك اليوم!</b>"
    return header + "\n".join(body_parts) + footer
