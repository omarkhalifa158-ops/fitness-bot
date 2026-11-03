"""
Telegram Bot Update Poller & Command / Callback Query Handler
Runs as an asynchronous background task within FastAPI.
No external webhooks or SSL certificates required.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import httpx
import pytz

from config import TELEGRAM_BOT_TOKEN, TIMEZONE
from state_manager import state_manager
from schedule_data import get_day_schedule, format_day_summary_text

logger = logging.getLogger("TelegramBotHandler")
CAIRO_TZ = pytz.timezone(TIMEZONE)

class TelegramBotHandler:
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        self.offset = 0
        self.is_running = False

    async def answer_callback_query(
        self,
        client: httpx.AsyncClient,
        callback_query_id: str,
        text: str,
        show_alert: bool = False
    ):
        """الرد الفوري على ضغطة الزر التفاعلي لإيقاف مؤشر التحميل وإظهار التنبيه"""
        try:
            await client.post(
                f"{self.base_url}/answerCallbackQuery",
                json={
                    "callback_query_id": callback_query_id,
                    "text": text,
                    "show_alert": show_alert
                },
                timeout=5.0
            )
        except Exception as e:
            logger.debug("Error answering callback: %s", e)

    async def send_message(
        self,
        client: httpx.AsyncClient,
        chat_id: str,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None
    ):
        """إرسال رسالة رد سريعة للمستخدم باستخدام HTML الآمن"""
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            res = await client.post(f"{self.base_url}/sendMessage", json=payload, timeout=10.0)
            if res.status_code != 200:
                logger.warning("HTML send failed: %s - %s. Retrying without HTML...", res.status_code, res.text)
                payload.pop("parse_mode", None)
                payload["text"] = text.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "")
                await client.post(f"{self.base_url}/sendMessage", json=payload, timeout=10.0)
        except Exception as e:
            logger.error("Error sending response message: %s", e)

    def get_control_keyboard(self, status: str) -> Dict[str, Any]:
        """لوحة أزرار التحكم الفورية"""
        if status == "ACTIVE":
            btn_row = [
                {"text": "⏸️ إيقاف التنبيهات", "callback_data": "cmd_stop"},
                {"text": "🏖️ إجازة اليوم", "callback_data": "cmd_skip_today"}
            ]
        elif status == "PAUSED":
            btn_row = [
                {"text": "▶️ تشغيل التنبيهات", "callback_data": "cmd_start"},
                {"text": "🏖️ إجازة اليوم", "callback_data": "cmd_skip_today"}
            ]
        else:
            btn_row = [
                {"text": "▶️ تشغيل التنبيهات الآن", "callback_data": "cmd_start"},
                {"text": "⏸️ إيقاف", "callback_data": "cmd_stop"}
            ]

        return {
            "inline_keyboard": [
                btn_row,
                [
                    {"text": "📅 جدول اليوم كاملاً", "callback_data": "cmd_today"},
                    {"text": "⚡ فحص النظام", "callback_data": "cmd_ping"}
                ]
            ]
        }

    async def handle_update(self, client: httpx.AsyncClient, update: Dict[str, Any]):
        """معالجة التحديثات الواردة (رسائل نصوص أو ضغطات أزرار)"""
        # 1. معالجة الرسائل النصية والـ Commands
        if "message" in update:
            msg = update["message"]
            chat_id = str(msg.get("chat", {}).get("id"))
            text = (msg.get("text") or "").strip()

            # حفظ الـ Chat ID تلقائياً إذا لم يكن مسجلاً
            if chat_id:
                state_manager.update_telegram_chat_id(chat_id)

            if text.startswith("/start") or text == "تشغيل التنبيهات":
                state_manager.resume()
                status = state_manager.get_status()
                reply = (
                    "🚀 *أهلاً بك في نظام التنبيه الذكي للوجبات والتمارين!*\n\n"
                    "✅ تم تفعيل التنبيهات بنجاح (`ACTIVE`).\n"
                    "⏰ المنطقة الزمنية: *توقيت القاهرة (UTC+2)*.\n"
                    "🔔 سيتم تنبيهك قبل الوجبات والتمرين حسب المهلة المحددة لكل فئة:\n"
                    "• 🍗 الغداء الخارجي: قبلها بـ 60 دقيقة (3:30 عصراً).\n"
                    "• ⚡ الوجبات الخفيفة: قبلها بـ 15 دقيقة.\n"
                    "• 💪 التمرين: قبلها بـ 10 دقائق (6:05 مساءً).\n\n"
                    "يمكنك التحكم في النظام من الأزرار أدناه 👇"
                )
                await self.send_message(client, chat_id, reply, self.get_control_keyboard(status))

            elif text.startswith("/stop") or text == "إيقاف التنبيهات":
                state_manager.pause()
                status = state_manager.get_status()
                reply = "⏸️ *تم إيقاف التنبيهات مؤقتاً (`PAUSED`).*\nلن تتلقى أي إشعارات حتى تقوم بإعادة التشغيل."
                await self.send_message(client, chat_id, reply, self.get_control_keyboard(status))

            elif text.startswith("/skip_today") or text == "إجازة اليوم":
                state_manager.skip_today()
                status = state_manager.get_status()
                reply = (
                    "🏖️ *تم تفعيل وضع إجازة اليوم (`SKIPPED_TODAY`).*\n\n"
                    "لن يتم إرسال أي تنبيهات لبقية اليوم.\n"
                    "🔄 سيعود النظام للعمل تلقائياً غداً في تمام الساعة *06:00 صباحاً* بتوقيت القاهرة."
                )
                await self.send_message(client, chat_id, reply, self.get_control_keyboard(status))

            elif text.startswith("/today") or text == "جدول اليوم":
                cairo_now = datetime.now(CAIRO_TZ)
                weekday = cairo_now.weekday()
                custom_texts = state_manager.get_custom_meals()
                day_summary = format_day_summary_text(weekday, custom_texts)
                status = state_manager.get_status()
                await self.send_message(client, chat_id, day_summary, self.get_control_keyboard(status))

            elif text.startswith("/status"):
                status = state_manager.get_status()
                cairo_now = datetime.now(CAIRO_TZ).strftime("%I:%M %p")
                reply = f"ℹ️ *حالة النظام الحالية:* `{status}`\n🕒 *الوقت الآن في القاهرة:* `{cairo_now}`"
                await self.send_message(client, chat_id, reply, self.get_control_keyboard(status))

        # 2. معالجة ضغطات الأزرار التفاعلية (Callback Queries)
        elif "callback_query" in update:
            cq = update["callback_query"]
            cq_id = cq["id"]
            chat_id = str(cq.get("message", {}).get("chat", {}).get("id"))
            data = cq.get("data", "")

            if data == "cmd_start":
                state_manager.resume()
                await self.answer_callback_query(client, cq_id, "تم تفعيل التنبيهات بنجاح ✅", show_alert=True)
                status = state_manager.get_status()
                msg = "▶️ <b>تم تشغيل التنبيهات بنجاح (<code>ACTIVE</code>).</b>\nسيرسل لك النظام التنبيهات في مواعيدها المحسوبة تلقائياً."
                await self.send_message(client, chat_id, msg, self.get_control_keyboard(status))

            elif data == "cmd_stop":
                state_manager.pause()
                await self.answer_callback_query(client, cq_id, "تم إيقاف التنبيهات مؤقتاً ⏸️", show_alert=True)
                status = state_manager.get_status()
                msg = "⏸️ <b>تم إيقاف التنبيهات مؤقتاً (<code>PAUSED</code>).</b>\nلن يتم إرسال تنبيهات حتى تضغط تشغيل مجدداً."
                await self.send_message(client, chat_id, msg, self.get_control_keyboard(status))

            elif data == "cmd_skip_today":
                state_manager.skip_today()
                await self.answer_callback_query(client, cq_id, "تم أخذ إجازة اليوم 🏖️", show_alert=True)
                status = state_manager.get_status()
                msg = (
                    "🏖️ <b>تم تفعيل إجازة اليوم (<code>SKIPPED_TODAY</code>).</b>\n\n"
                    "• تم تعليق باقي تنبيهات اليوم.\n"
                    "🔄 سيعود النظام للعمل تلقائياً غداً في تمام الساعة <b>06:00 صباحاً</b> بتوقيت القاهرة."
                )
                await self.send_message(client, chat_id, msg, self.get_control_keyboard(status))

            elif data == "cmd_today":
                await self.answer_callback_query(client, cq_id, "جاري إرسال جدول اليوم... 📅")
                cairo_now = datetime.now(CAIRO_TZ)
                weekday = cairo_now.weekday()
                custom_texts = state_manager.get_custom_meals()
                day_summary = format_day_summary_text(weekday, custom_texts)
                status = state_manager.get_status()
                await self.send_message(client, chat_id, day_summary, self.get_control_keyboard(status))

            elif data == "cmd_ping":
                cairo_now = datetime.now(CAIRO_TZ).strftime("%I:%M:%S %p")
                status = state_manager.get_status()
                # 1. إظهار نافذة منبثقة واضحة بالـ Pop-up
                await self.answer_callback_query(
                    client,
                    cq_id,
                    f"✅ فحص فوري: النظام متصل ويعمل بكفاءة!\nالحالة: {status}\nتوقيت القاهرة: {cairo_now}",
                    show_alert=True
                )
                # 2. إرسال رسالة تأكيد في الشات مباشرة
                ping_msg = (
                    f"⚡ <b>فحص فوري ناجح للنظام!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"• 🟢 <b>حالة النظام:</b> <code>{status}</code>\n"
                    f"• 🕒 <b>الوقت الحالي في القاهرة:</b> <code>{cairo_now}</code>\n"
                    f"• 🔔 <b>مجدول المواعيد:</b> يعمل بكفاءة مع حماية الـ Watchdog."
                )
                await self.send_message(client, chat_id, ping_msg, self.get_control_keyboard(status))

    async def start_polling(self):
        """حلقة الاستماع المستمر لتحديثات البوت (Long Polling)"""
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not configured. Polling disabled.")
            return

        self.is_running = True
        logger.info("Starting Telegram Bot long-polling loop...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            while self.is_running:
                try:
                    url = f"{self.base_url}/getUpdates"
                    params = {"offset": self.offset, "timeout": 20}
                    response = await client.get(url, params=params)

                    if response.status_code == 200:
                        data = response.json()
                        updates = data.get("result", [])
                        for update in updates:
                            self.offset = update["update_id"] + 1
                            await self.handle_update(client, update)
                    elif response.status_code == 409:
                        logger.warning("Conflict: Another bot instance is running or webhook is active. Sleeping...")
                        await asyncio.sleep(10)
                    else:
                        logger.warning("Telegram getUpdates returned status %s", response.status_code)
                        await asyncio.sleep(5)
                except httpx.RequestError as e:
                    logger.debug("Network error during polling (will retry): %s", e)
                    await asyncio.sleep(5)
                except asyncio.CancelledError:
                    self.is_running = False
                    break
                except Exception as e:
                    logger.error("Unexpected error in Telegram polling: %s", e)
                    await asyncio.sleep(5)

    def stop_polling(self):
        self.is_running = False

# Singleton instance
bot_handler = TelegramBotHandler()
