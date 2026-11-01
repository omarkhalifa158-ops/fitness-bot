"""
Multi-Channel Notification Dispatcher
Supports Telegram Bot (with interactive inline buttons) and WhatsApp (via CallMeBot API).
"""
import urllib.parse
import logging
from typing import Dict, Any, Optional, List
import httpx

from config import (
    TELEGRAM_BOT_TOKEN,
    ENABLE_TELEGRAM,
    ENABLE_WHATSAPP,
    CALLMEBOT_PHONE,
    CALLMEBOT_API_KEY
)
from state_manager import state_manager

logger = logging.getLogger("Notifier")
logging.basicConfig(level=logging.INFO)

class NotificationDispatcher:
    def __init__(self):
        self.telegram_base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else None

    def get_inline_keyboard(self, current_status: str) -> List[List[Dict[str, str]]]:
        """
        أزرار التحكم التفاعلية المرفقة مع الإشعارات
        """
        # صف أزرار التحكم بالحالة
        if current_status == "ACTIVE":
            status_buttons = [
                {"text": "⏸️ إيقاف التنبيهات", "callback_data": "cmd_stop"},
                {"text": "🏖️ إجازة اليوم", "callback_data": "cmd_skip_today"}
            ]
        elif current_status == "PAUSED":
            status_buttons = [
                {"text": "▶️ استئناف التنبيهات", "callback_data": "cmd_start"},
                {"text": "🏖️ إجازة اليوم", "callback_data": "cmd_skip_today"}
            ]
        else: # SKIPPED_TODAY
            status_buttons = [
                {"text": "▶️ تشغيل التنبيهات الآن", "callback_data": "cmd_start"},
                {"text": "⏸️ إيقاف", "callback_data": "cmd_stop"}
            ]

        keyboard = [
            status_buttons,
            [
                {"text": "📅 جدول اليوم كاملاً", "callback_data": "cmd_today"},
                {"text": "⚡ فحص فوري", "callback_data": "cmd_ping"}
            ]
        ]
        return keyboard

    async def send_telegram(
        self,
        text: str,
        chat_id: Optional[str] = None,
        include_controls: bool = True
    ) -> bool:
        """
        إرسال إشعار عبر Telegram Bot API مع دعم الأزرار التفاعلية وحماية التنسيق
        """
        target_chat_id = chat_id or state_manager.get_telegram_chat_id()
        if not ENABLE_TELEGRAM or not TELEGRAM_BOT_TOKEN or not target_chat_id:
            logger.warning("Telegram is disabled, or BOT_TOKEN/CHAT_ID is missing.")
            return False

        url = f"{self.telegram_base_url}/sendMessage"
        
        # تجهيز الأزرار التفاعلية
        reply_markup = None
        if include_controls:
            current_status = state_manager.get_status()
            reply_markup = {
                "inline_keyboard": self.get_inline_keyboard(current_status)
            }

        # المحاولة 1: تنسيق Markdown
        payload: Dict[str, Any] = {
            "chat_id": target_chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    logger.info("Telegram notification sent successfully to chat %s", target_chat_id)
                    return True
                else:
                    logger.warning("Markdown parse failed (%s: %s). Falling back to plain text...", res.status_code, res.text)
                    # المحاولة 2: إرسال كنص عادي لتفادي أي خطأ في رموز التنسيق
                    payload.pop("parse_mode", None)
                    # تنظيف علامات الماركداون يدوياً
                    payload["text"] = text.replace("*", "").replace("`", "")
                    res2 = await client.post(url, json=payload)
                    if res2.status_code == 200:
                        logger.info("Telegram fallback plain text sent successfully.")
                        return True
                    else:
                        logger.error("Failed to send Telegram message: %s - %s", res2.status_code, res2.text)
                        return False
        except Exception as e:
            logger.error("Exception sending Telegram message: %s", e)
            return False

    async def send_whatsapp(self, text: str) -> bool:
        """
        إرسال إشعار عبر WhatsApp باستخدام CallMeBot API المجاني
        """
        if not ENABLE_WHATSAPP or not CALLMEBOT_PHONE or not CALLMEBOT_API_KEY:
            return False

        # إزالة نجوم الماركداون للواتساب لتحسين القراءة
        clean_text = text.replace("*", "")
        encoded_text = urllib.parse.quote_plus(clean_text)
        url = f"https://api.callmebot.com/whatsapp.php?phone={CALLMEBOT_PHONE}&text={encoded_text}&apikey={CALLMEBOT_API_KEY}"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(url)
                if res.status_code == 200 and "Message queued" in res.text or res.status_code == 200:
                    logger.info("WhatsApp notification sent successfully via CallMeBot")
                    return True
                else:
                    logger.warning("WhatsApp send failed: %s - %s", res.status_code, res.text)
                    return False
        except Exception as e:
            logger.error("Exception sending WhatsApp message: %s", e)
            return False

    async def dispatch(
        self,
        title: str,
        message: str,
        category: str = "GENERAL",
        alert_time: str = "",
        is_test: bool = False
    ) -> Dict[str, Any]:
        """
        الموزع الموحد: يتحقق من حالة النظام ثم يبث الإشعار للقنوات المفعلة
        """
        current_status = state_manager.get_status()

        # إذا لم يكن فحصاً تجريبياً، نتأكد من أن النظام ACTIVE
        if not is_test and current_status != "ACTIVE":
            logger.info("Notification skipped because system status is %s", current_status)
            return {
                "sent": False,
                "reason": f"System is {current_status}",
                "status": current_status
            }

        channels_result = {}

        # 1. إرسال التيليجرام
        if ENABLE_TELEGRAM:
            channels_result["telegram"] = await self.send_telegram(message)
        else:
            channels_result["telegram"] = False

        # 2. إرسال الواتساب
        if ENABLE_WHATSAPP:
            channels_result["whatsapp"] = await self.send_whatsapp(message)
        else:
            channels_result["whatsapp"] = False

        # تسجيل الإشعار في الذاكرة الدائمة
        state_manager.record_notification(
            title=title,
            category=category,
            alert_time=alert_time,
            channels=channels_result
        )

        return {
            "sent": any(channels_result.values()),
            "channels": channels_result,
            "status": current_status
        }

# Singleton Instance
notifier = NotificationDispatcher()
