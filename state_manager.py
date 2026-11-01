"""
State Management Module for Persistent Status & Control Commands
Manages state.json, skip_today auto-reset at 06:00 AM, and custom meal edits.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import pytz

from config import STATE_FILE_PATH, CUSTOM_MEALS_PATH, TIMEZONE, TELEGRAM_CHAT_ID

CAIRO_TZ = pytz.timezone(TIMEZONE)

class StateManager:
    def __init__(self, state_path: Path = STATE_FILE_PATH, custom_meals_path: Path = CUSTOM_MEALS_PATH):
        self.state_path = state_path
        self.custom_meals_path = custom_meals_path
        self._load_state()

    def _get_default_state(self) -> Dict[str, Any]:
        return {
            "status": "ACTIVE",              # ACTIVE | PAUSED | SKIPPED_TODAY
            "skip_date": None,               # YYYY-MM-DD
            "telegram_chat_id": TELEGRAM_CHAT_ID or None,
            "last_notification_sent": None,
            "notification_history": [],
            "updated_at": datetime.now(CAIRO_TZ).isoformat()
        }

    def _load_state(self):
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception:
                self.state = self._get_default_state()
                self._save_state()
        else:
            self.state = self._get_default_state()
            self._save_state()

    def _save_state(self):
        self.state["updated_at"] = datetime.now(CAIRO_TZ).isoformat()
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def get_status(self) -> str:
        """يُرجع الحالة الحالية للنظام مع التحقق التلقائي من إعادة التعيين اليومية"""
        self.check_and_reset_daily()
        return self.state.get("status", "ACTIVE")

    def set_status(self, new_status: str, skip_date: Optional[str] = None) -> str:
        """تحديث حالة النظام (ACTIVE / PAUSED / SKIPPED_TODAY)"""
        new_status = new_status.upper()
        if new_status not in ("ACTIVE", "PAUSED", "SKIPPED_TODAY"):
            raise ValueError(f"Invalid status: {new_status}")

        self.state["status"] = new_status
        if new_status == "SKIPPED_TODAY":
            cairo_now = datetime.now(CAIRO_TZ)
            self.state["skip_date"] = skip_date or cairo_now.strftime("%Y-%m-%d")
        else:
            self.state["skip_date"] = None

        self._save_state()
        return self.state["status"]

    def skip_today(self) -> str:
        """تفعيل وضع إجازة اليوم"""
        cairo_now = datetime.now(CAIRO_TZ)
        return self.set_status("SKIPPED_TODAY", skip_date=cairo_now.strftime("%Y-%m-%d"))

    def pause(self) -> str:
        """إيقاف التنبيهات مؤقتاً لأجل غير مسمى"""
        return self.set_status("PAUSED")

    def resume(self) -> str:
        """تشغيل التنبيهات واستئناف العمل"""
        return self.set_status("ACTIVE")

    def check_and_reset_daily(self) -> bool:
        """
        التحقق اليومي: إذا كان النظام في وضع SKIPPED_TODAY،
        يتم إرجاعه تلقائياً إلى وضع ACTIVE بعد الساعة 06:00 صباحاً من اليوم التالي
        """
        if self.state.get("status") != "SKIPPED_TODAY":
            return False

        skip_date_str = self.state.get("skip_date")
        if not skip_date_str:
            self.state["status"] = "ACTIVE"
            self._save_state()
            return True

        cairo_now = datetime.now(CAIRO_TZ)
        today_str = cairo_now.strftime("%Y-%m-%d")

        try:
            skip_date = datetime.strptime(skip_date_str, "%Y-%m-%d").date()
            today_date = cairo_now.date()

            # إذا مر اليوم وأصبحنا في يوم لاحق وتجاوزت الساعة 06:00 صباحاً (أو مر أكثر من يوم كامل)
            if today_date > skip_date:
                if cairo_now.hour >= 6 or (today_date - skip_date).days > 1:
                    self.state["status"] = "ACTIVE"
                    self.state["skip_date"] = None
                    self._save_state()
                    return True
        except Exception:
            self.state["status"] = "ACTIVE"
            self._save_state()
            return True

        return False

    def update_telegram_chat_id(self, chat_id: str):
        """حفظ Chat ID التيليجرام عند اكتشافه تلقائياً من المستخدم"""
        self.state["telegram_chat_id"] = str(chat_id)
        self._save_state()

    def get_telegram_chat_id(self) -> Optional[str]:
        return self.state.get("telegram_chat_id") or TELEGRAM_CHAT_ID

    def record_notification(self, title: str, category: str, alert_time: str, channels: Dict[str, bool]):
        """تسجيل الإشعار في سجل التنبيهات للمتابعة في الـ Dashboard"""
        cairo_now = datetime.now(CAIRO_TZ)
        entry = {
            "title": title,
            "category": category,
            "alert_time": alert_time,
            "sent_at": cairo_now.strftime("%Y-%m-%d %H:%M:%S"),
            "channels": channels
        }
        self.state["last_notification_sent"] = entry
        history = self.state.get("notification_history", [])
        history.insert(0, entry)
        self.state["notification_history"] = history[:50] # الاحتفاظ بآخر 50 إشعار فقط
        self._save_state()

    # =================================================================
    # إدارة الوجبات المعدلة (Custom Meals Storage)
    # =================================================================
    def get_custom_meals(self) -> Dict[str, str]:
        if not self.custom_meals_path.exists():
            return {}
        try:
            with open(self.custom_meals_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_custom_meal(self, meal_id: str, new_text: str):
        meals = self.get_custom_meals()
        meals[meal_id] = new_text
        with open(self.custom_meals_path, "w", encoding="utf-8") as f:
            json.dump(meals, f, ensure_ascii=False, indent=2)

    def reset_custom_meal(self, meal_id: str):
        meals = self.get_custom_meals()
        if meal_id in meals:
            del meals[meal_id]
            with open(self.custom_meals_path, "w", encoding="utf-8") as f:
                json.dump(meals, f, ensure_ascii=False, indent=2)

# Singleton Instance
state_manager = StateManager()
