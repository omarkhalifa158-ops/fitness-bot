"""
Main FastAPI Application & APScheduler Runner
Smart Fitness & Meal Notification System
Timezone: Africa/Cairo (UTC+2)
"""
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import (
    TIMEZONE,
    HOST,
    PORT,
    TELEGRAM_BOT_TOKEN,
    ENABLE_TELEGRAM,
    ENABLE_WHATSAPP,
    CALLMEBOT_PHONE
)
from schedule_data import (
    get_day_schedule,
    get_lunch_for_weekday,
    get_workout_for_weekday,
    FIXED_MEALS,
    CATEGORIES,
    WEEKDAYS_AR
)
from state_manager import state_manager
from notifier import notifier
from bot_handler import bot_handler

logger = logging.getLogger("App")
logging.basicConfig(level=logging.INFO)

CAIRO_TZ = pytz.timezone(TIMEZONE)
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Initialize APScheduler with Cairo Timezone
scheduler = AsyncIOScheduler(timezone=CAIRO_TZ)

# =====================================================================
# Job Handlers (Triggered by APScheduler at Calculated Alert Times)
# =====================================================================
async def job_morning_alarm():
    """منبه الاستيقاظ والروتين الصباحي الساعة 07:45 ص (8 إلا ربع)"""
    custom = state_manager.get_custom_meals()
    ev = FIXED_MEALS["morning_alarm"]
    text = custom.get("morning_alarm", ev["text"])
    await notifier.dispatch(
        title=ev["title"],
        message=text,
        category=ev["category"],
        alert_time="07:45"
    )

async def job_breakfast():
    """تنبيه الفطار الساعة 07:45 ص (موعد الوجبة 08:00 ص - مهلة 15 دقيقة)"""
    custom = state_manager.get_custom_meals()
    ev = FIXED_MEALS["breakfast"]
    text = custom.get("breakfast", ev["text"])
    await notifier.dispatch(
        title=ev["title"],
        message=text,
        category=ev["category"],
        alert_time="07:45"
    )

async def job_work_snack():
    """تنبيه سناك الشغل الساعة 12:15 ظ (موعد السناك 12:30 ظ - مهلة 15 دقيقة)"""
    custom = state_manager.get_custom_meals()
    ev = FIXED_MEALS["work_snack"]
    text = custom.get("work_snack", ev["text"])
    await notifier.dispatch(
        title=ev["title"],
        message=text,
        category=ev["category"],
        alert_time="12:15"
    )

async def job_lunch():
    """
    تنبيه الغداء الساعة 03:30 م (موعد الوجبة 04:30 م - مهلة 60 دقيقة للطلب الخارجي)
    يحسب وجبة اليوم بناء على اليوم الحالي من الأسبوع
    """
    cairo_now = datetime.now(CAIRO_TZ)
    weekday = cairo_now.weekday()
    lunch_info = get_lunch_for_weekday(weekday)
    meal_id = f"lunch_day_{weekday}"
    custom = state_manager.get_custom_meals()
    text = custom.get(meal_id, lunch_info["text"])
    await notifier.dispatch(
        title=f"الغداء: {lunch_info['title']}",
        message=text,
        category="OUTSIDE_ORDER_MEAL",
        alert_time="15:30"
    )

async def job_workout():
    """
    تنبيه التمرين المنزلي الساعة 06:05 م (موعد التمرين 06:15 م - مهلة 10 دقائق)
    يحسب تمرين اليوم بناء على اليوم الحالي من الأسبوع
    """
    cairo_now = datetime.now(CAIRO_TZ)
    weekday = cairo_now.weekday()
    wo_info = get_workout_for_weekday(weekday)
    wo_id = f"workout_day_{weekday}"
    custom = state_manager.get_custom_meals()
    text = custom.get(wo_id, wo_info["text"])
    await notifier.dispatch(
        title=f"التمرين: {wo_info['name']}",
        message=text,
        category="WORKOUT",
        alert_time="18:05"
    )

async def job_shake():
    """تنبيه شيك الضخامة الساعة 07:00 م (موعد الشيك 07:15 م - مهلة 15 دقيقة)"""
    custom = state_manager.get_custom_meals()
    ev = FIXED_MEALS["post_workout_shake"]
    text = custom.get("post_workout_shake", ev["text"])
    await notifier.dispatch(
        title=ev["title"],
        message=text,
        category=ev["category"],
        alert_time="19:00"
    )

async def job_dinner():
    """تنبيه العشاء ومكمل الحديد الساعة 09:15 م (موعد العشاء 09:30 م - مهلة 15 دقيقة)"""
    custom = state_manager.get_custom_meals()
    ev = FIXED_MEALS["dinner"]
    text = custom.get("dinner", ev["text"])
    await notifier.dispatch(
        title=ev["title"],
        message=text,
        category=ev["category"],
        alert_time="21:15"
    )

async def job_bedtime_prep():
    """تنبيه ترك الهاتف والاستعداد للنوم الساعة 10:30 م (قبل النوم بنصف ساعة)"""
    custom = state_manager.get_custom_meals()
    ev = FIXED_MEALS["bedtime_prep"]
    text = custom.get("bedtime_prep", ev["text"])
    await notifier.dispatch(
        title=ev["title"],
        message=text,
        category=ev["category"],
        alert_time="22:30"
    )

async def job_daily_reset():
    """
    وظيفة إعادة التعيين اليومية الساعة 06:00 صباحاً بتوقيت القاهرة
    إذا كان النظام في وضع SKIPPED_TODAY يتم إرجاعه تلقائياً إلى ACTIVE
    """
    was_reset = state_manager.check_and_reset_daily()
    if was_reset:
        logger.info("Daily reset executed at 06:00 AM: Status reverted to ACTIVE.")
        if ENABLE_TELEGRAM:
            await notifier.send_telegram(
                "🌅 *صباح الخير والنشاط!*\nتمت إعادة تفعيل التنبيهات تلقائياً لليوم الجديد (`ACTIVE`). استعد ليوم صحي قوي! 💪",
                include_controls=True
            )

# =====================================================================
# Scheduler Registration
# =====================================================================
def register_scheduled_jobs():
    """تسجيل جميع المواعيد اليومية حسب حسابات المهلة بتوقيت القاهرة"""
    # 0. منبه الاستيقاظ والروتين: 07:45 ص (8 إلا ربع)
    scheduler.add_job(job_morning_alarm, CronTrigger(hour=7, minute=45, timezone=CAIRO_TZ), id="job_morning_alarm", replace_existing=True)

    # 1. الفطار: 07:45 ص (موعد الأكل 08:00 ص)
    scheduler.add_job(job_breakfast, CronTrigger(hour=7, minute=45, timezone=CAIRO_TZ), id="job_breakfast", replace_existing=True)
    
    # 2. سناك الشغل: 12:15 ظ (موعد السناك 12:30 ظ)
    scheduler.add_job(job_work_snack, CronTrigger(hour=12, minute=15, timezone=CAIRO_TZ), id="job_work_snack", replace_existing=True)
    
    # 3. الغداء الخارجي: 03:30 م (موعد الغداء 04:30 م - مهلة 60 دقيقة)
    scheduler.add_job(job_lunch, CronTrigger(hour=15, minute=30, timezone=CAIRO_TZ), id="job_lunch", replace_existing=True)
    
    # 4. تمرين المنزل: 06:05 م (موعد التمرين 06:15 م - مهلة 10 دقائق)
    scheduler.add_job(job_workout, CronTrigger(hour=18, minute=5, timezone=CAIRO_TZ), id="job_workout", replace_existing=True)
    
    # 5. شيك الضخامة: 07:00 م (موعد الشيك 07:15 م)
    scheduler.add_job(job_shake, CronTrigger(hour=19, minute=0, timezone=CAIRO_TZ), id="job_shake", replace_existing=True)
    
    # 6. العشاء ومكمل الحديد: 09:15 م (موعد العشاء 09:30 م)
    scheduler.add_job(job_dinner, CronTrigger(hour=21, minute=15, timezone=CAIRO_TZ), id="job_dinner", replace_existing=True)
    
    # 7. الاستعداد للنوم وترك الهاتف: 10:30 م (قبل النوم بنصف ساعة)
    scheduler.add_job(job_bedtime_prep, CronTrigger(hour=22, minute=30, timezone=CAIRO_TZ), id="job_bedtime_prep", replace_existing=True)

    # 8. إعادة التعيين اليومي لإجازة اليوم: 06:00 ص
    scheduler.add_job(job_daily_reset, CronTrigger(hour=6, minute=0, timezone=CAIRO_TZ), id="job_daily_reset", replace_existing=True)
    
    logger.info("All 9 recurring jobs successfully registered with APScheduler (Cairo Timezone).")

# =====================================================================
# Lifespan Context Manager (Startup & Shutdown)
# =====================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. بدء تشغيل المجدول
    register_scheduled_jobs()
    scheduler.start()
    logger.info("APScheduler started.")

    # 2. تشغيل استماع التيليجرام في الخلفية
    bot_task = None
    if ENABLE_TELEGRAM and TELEGRAM_BOT_TOKEN:
        bot_task = asyncio.create_task(bot_handler.start_polling())
        logger.info("Telegram background polling task launched.")

    yield

    # Cleanup عند إيقاف الخادم
    if bot_task:
        bot_handler.stop_polling()
        bot_task.cancel()
    if scheduler.running:
        scheduler.shutdown(wait=False)
    logger.info("System gracefully shut down.")

# =====================================================================
# FastAPI Application
# =====================================================================
app = FastAPI(
    title="Smart Fitness & Meal Notification System",
    description="Automated multi-channel notification system tailored to Cairo timezone with custom lead-time logic.",
    version="2.0.0",
    lifespan=lifespan
)

# Helper: Compute Next Upcoming Alert
def get_next_alert_info(today_schedule):
    cairo_now = datetime.now(CAIRO_TZ)
    current_time_str = cairo_now.strftime("%H:%M")
    
    for ev in today_schedule:
        if ev["alert_time"] > current_time_str:
            h, m = map(int, ev["alert_time"].split(":"))
            target_dt = cairo_now.replace(hour=h, minute=m, second=0, microsecond=0)
            diff_mins = max(1, int((target_dt - cairo_now).total_seconds() // 60))
            hours = diff_mins // 60
            mins = diff_mins % 60
            human_time = f"{hours} ساعة و {mins} دقيقة" if hours > 0 else f"{mins} دقيقة"
            return {
                **ev,
                "remaining_minutes": diff_mins,
                "remaining_human": human_time
            }
            
    # إذا انتهت جميع تنبيهات اليوم، فالإشعار القادم هو فطار الغد الساعة 07:45 ص
    tomorrow_dt = (cairo_now + timedelta(days=1)).replace(hour=7, minute=45, second=0, microsecond=0)
    diff_mins = max(1, int((tomorrow_dt - cairo_now).total_seconds() // 60))
    hours = diff_mins // 60
    mins = diff_mins % 60
    return {
        "title": "🍳 وجبة الفطار (غداً)",
        "alert_time": "07:45",
        "event_time": "08:00",
        "lead_time": 15,
        "badge_emoji": "🍳",
        "remaining_minutes": diff_mins,
        "remaining_human": f"{hours} ساعة و {mins} دقيقة"
    }

# =====================================================================
# Web Dashboard & REST API Routes
# =====================================================================
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """عرض لوحة التحكم التفاعلية"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def api_get_status():
    """جلب حالة النظام والوقت الحالي والجدول اليومي والإشعار القادم"""
    cairo_now = datetime.now(CAIRO_TZ)
    status = state_manager.get_status()
    weekday = cairo_now.weekday()
    custom_texts = state_manager.get_custom_meals()
    today_schedule = get_day_schedule(weekday, custom_texts)
    next_alert = get_next_alert_info(today_schedule)

    chat_id = state_manager.get_telegram_chat_id()
    chat_id_display = f"{chat_id[:4]}***" if chat_id and len(chat_id) > 4 else chat_id

    return {
        "status": status,
        "cairo_time": cairo_now.strftime("%I:%M:%S %p"),
        "cairo_date": cairo_now.strftime("%Y-%m-%d"),
        "weekday": weekday,
        "day_name": WEEKDAYS_AR.get(weekday, ""),
        "telegram_configured": bool(ENABLE_TELEGRAM and TELEGRAM_BOT_TOKEN),
        "telegram_chat_id": chat_id_display,
        "whatsapp_configured": bool(ENABLE_WHATSAPP and CALLMEBOT_API_KEY and CALLMEBOT_PHONE),
        "callmebot_phone": CALLMEBOT_PHONE[:4] + "***" if CALLMEBOT_PHONE else None,
        "today_schedule": today_schedule,
        "next_alert": next_alert,
        "history": state_manager.state.get("notification_history", [])
    }

class StatusChangeRequest(BaseModel):
    action: str # ACTIVE | PAUSED | SKIPPED_TODAY

@app.post("/api/status")
async def api_set_status(req: StatusChangeRequest):
    """تغيير حالة النظام من الـ Web Dashboard"""
    action = req.action.upper()
    if action == "ACTIVE":
        new_status = state_manager.resume()
    elif action == "PAUSED":
        new_status = state_manager.pause()
    elif action == "SKIPPED_TODAY":
        new_status = state_manager.skip_today()
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    return {"success": True, "status": new_status}

@app.post("/api/send_test")
async def api_send_test():
    """إرسال إشعار فحص تجريبي فوري للقنوات المفعلة مع الأزرار التفاعلية"""
    cairo_now = datetime.now(CAIRO_TZ).strftime("%I:%M %p")
    test_message = (
        "🧪 *إشعار فحص تجريبي من نظام التنبيه الذكي!*\n\n"
        "✅ تم الاتصال بنجاح بالنظام وخادم الإشعارات.\n"
        f"🕒 توقيت القاهرة الحالي: *{cairo_now}*.\n"
        "يمكنك تجربة الضغط على أزرار التحكم أدناه للتأكد من تفاعل النظام 👇"
    )
    result = await notifier.dispatch(
        title="فحص تجريبي للنظام",
        message=test_message,
        category="TEST",
        alert_time=datetime.now(CAIRO_TZ).strftime("%H:%M"),
        is_test=True
    )
    return result

@app.get("/api/schedule/{weekday}")
async def api_get_day_schedule(weekday: int):
    """استعراض جدول يوم محدد من أيام الأسبوع (0 إلى 6)"""
    if weekday < 0 or weekday > 6:
        raise HTTPException(status_code=400, detail="Invalid weekday")
    custom_texts = state_manager.get_custom_meals()
    schedule = get_day_schedule(weekday, custom_texts)
    return {
        "weekday": weekday,
        "day_name": WEEKDAYS_AR.get(weekday, ""),
        "schedule": schedule
    }

class MealSaveRequest(BaseModel):
    meal_id: str
    text: str

@app.post("/api/meal/save")
async def api_save_meal(req: MealSaveRequest):
    """حفظ نص مخصص لوجبة أو تمرين محدد"""
    state_manager.save_custom_meal(req.meal_id, req.text)
    return {"success": True, "meal_id": req.meal_id}

class MealResetRequest(BaseModel):
    meal_id: str

@app.post("/api/meal/reset")
async def api_reset_meal(req: MealResetRequest):
    """استرجاع النص الافتراضي الأصلي للوجبة"""
    state_manager.reset_custom_meal(req.meal_id)
    return {"success": True, "meal_id": req.meal_id}

# =====================================================================
# Main Entry Point
# =====================================================================
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server on %s:%s...", HOST, PORT)
    uvicorn.run("app:app", host=HOST, port=PORT, reload=False)
