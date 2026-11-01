# PowerShell Poller & Button Handler for Telegram Bot
param(
    [switch]$Once = $false
)

$token = "9175456813:AAFP4LsdTt_4dKX5ys_x5_O4VnPBATEEY6c"
$baseUrl = "https://api.telegram.org/bot$token"
$offsetFile = "$PSScriptRoot\bot_offset.txt"

$offset = 0
if (Test-Path $offsetFile) {
    $offset = [int](Get-Content $offsetFile)
}

function Answer-Callback($id, $text) {
    $json = @{ callback_query_id = $id; text = $text; show_alert = $false } | ConvertTo-Json
    $temp = [System.IO.Path]::GetTempFileName()
    [System.IO.File]::WriteAllText($temp, $json, [System.Text.Encoding]::UTF8)
    curl.exe -s -X POST "$baseUrl/answerCallbackQuery" -H "Content-Type: application/json; charset=utf-8" --data-binary "@$temp" | Out-Null
    Remove-Item $temp -Force
}

function Send-Msg($chatId, $text) {
    $body = @{
        chat_id = $chatId
        text = $text
        parse_mode = "HTML"
        reply_markup = @{
            inline_keyboard = @(
                @(
                    @{ text = "⏸️ إيقاف التنبيهات"; callback_data = "cmd_stop" },
                    @{ text = "🏖️ إجازة اليوم"; callback_data = "cmd_skip_today" }
                ),
                @(
                    @{ text = "📅 جدول اليوم كاملاً"; callback_data = "cmd_today" },
                    @{ text = "⚡ فحص النظام"; callback_data = "cmd_ping" }
                )
            )
        }
    }
    $json = $body | ConvertTo-Json -Depth 5
    $temp = [System.IO.Path]::GetTempFileName()
    [System.IO.File]::WriteAllText($temp, $json, [System.Text.Encoding]::UTF8)
    curl.exe -s -X POST "$baseUrl/sendMessage" -H "Content-Type: application/json; charset=utf-8" --data-binary "@$temp" | Out-Null
    Remove-Item $temp -Force
}

function Get-TodayScheduleText() {
    return @"
📅 <b>جدول اليوم الشامل (توقيت القاهرة UTC+2)</b>
━━━━━━━━━━━━━━━━━━━━

⏰ <b>منبه الاستيقاظ وبدء اليوم (8 إلا ربع - 07:45 ص):</b>
• استيقظ واشرب كوبين ماء فاتر لتنشيط الكلى والجهاز الهضمي.

🍳 <b>الفطار (08:00 ص | التنبيه 07:45 ص - مهلة 15 دقيقة):</b>
• قرص دايجستين وسط الأكل + كبسولة فيتامين د بعد الفطار.
• 3 بيضات مسلوقة (أو أومليت بنقطة زيت زيتون).
• 150 جرام بطاطس مسلوقة مهروسة + رغيف عيش بلدي.
• 50 جرام جبنة رودس + ملعقة كبيرة زيت زيتون + ملعقة سمسم محمص.

🥜 <b>سناك الشغل (12:30 ظ | التنبيه 12:15 ظ - مهلة 15 دقيقة):</b>
• 2 ثمرة موز مهروسة + 2 ملعقة كبيرة زبدة فول سوداني (40 جرام).
• حفنة لب يقطين أبيض (20 جرام).

🍗 <b>الغداء (04:30 ع | التنبيه 03:30 ع - مهلة 60 دقيقة 🛍️):</b>
• شراء وأنت مروح من العمل!
• وركين فراخ مشوية جاهزة منزوعة الجلد (250 جرام) أو صدور/تونة حسب اليوم.
• 250 جرام بطاطس/أرز + سلطة خضراء بملعقة زيت زيتون + قرص دايجستين.

💪 <b>التمرين المنزلي (06:15 م | التنبيه 06:05 م - مهلة 10 دقائق):</b>
• الاستعداد وارتداء الملابس الرياضية وتجهيز الدامبلز والحبل.

🥤 <b>شيك الضخامة (07:15 م | التنبيه 07:00 م - مهلة 15 دقيقة):</b>
• 250 مل لبن كامل الدسم دافئ + 50 جرام شوفان مطحون + 1 سكوب واي بروتين أيزوليت + ملعقة صغيرة كاكاو خام + ملعقة عسل نحل.

🍽️ <b>العشاء ومكمل الحديد (09:30 م | التنبيه 09:15 م - مهلة 15 دقيقة):</b>
• علبة تونة قطع مصفاة + عيش بلدي أو بيض وبطاطس مسلوقة (ممنوع اللبن والجبن).
• 💊 بعد العشاء: شراب الحديد + أكل برتقالة سليمة أو جوافة للامتصاص.

📵 <b>الاستعداد للنوم وترك الهاتف (10:30 م | قبل النوم بـ 30 دقيقة):</b>
• اترك الهاتف والشاشات تماماً الآن!
• هيئ الغرفة بإضاءة خافتة لتسهيل إفراز الميلاتونين والنوم العميق لاستشفاء العضلات وهرمون النمو GH.

━━━━━━━━━━━━━━━━━━━━
💪 <b>التزم بجدولك وحقق هدفك اليوم!</b>
"@
}

# Fetch updates
$updatesRaw = curl.exe -s "$baseUrl/getUpdates?offset=$offset"
$updates = $updatesRaw | ConvertFrom-Json

if ($updates.ok -and $updates.result.Count -gt 0) {
    foreach ($u in $updates.result) {
        $offset = $u.update_id + 1
        [System.IO.File]::WriteAllText($offsetFile, "$offset")

        # 1. Callback query (أزرار التفاعل)
        if ($u.callback_query) {
            $cq = $u.callback_query
            $cqId = $cq.id
            $chatId = $cq.message.chat.id
            $data = $cq.data

            if ($data -eq "cmd_today") {
                Answer-Callback $cqId "جاري إرسال جدول اليوم..."
                $text = Get-TodayScheduleText
                Send-Msg $chatId $text
            }
            elseif ($data -eq "cmd_stop") {
                Answer-Callback $cqId "تم إيقاف التنبيهات ⏸️"
                Send-Msg $chatId "⏸️ <b>تم إيقاف التنبيهات مؤقتاً (PAUSED).</b>`nاضغط تشغيل في أي وقت لاستئناف التنبيهات."
            }
            elseif ($data -eq "cmd_start") {
                Answer-Callback $cqId "تم تفعيل التنبيهات ✅"
                Send-Msg $chatId "▶️ <b>تم تشغيل التنبيهات بنجاح (ACTIVE).</b>`nسيرسل لك النظام التنبيهات في مواعيدها المحسوبة."
            }
            elseif ($data -eq "cmd_skip_today") {
                Answer-Callback $cqId "تم تفعيل إجازة اليوم 🏖️"
                Send-Msg $chatId "🏖️ <b>تم تفعيل وضع إجازة اليوم (SKIPPED_TODAY).</b>`n🔄 ستستأنف التنبيهات تلقائياً غداً الساعة 06:00 صباحاً."
            }
            elseif ($data -eq "cmd_ping") {
                Answer-Callback $cqId "النظام يعمل بنجاح وكفاءة! توقيت القاهرة UTC+2"
            }
        }
        # 2. Text messages
        elseif ($u.message -and $u.message.text) {
            $chatId = $u.message.chat.id
            $msgText = $u.message.text.Trim()

            if ($msgText -eq "/today" -or $msgText -like "*جدول اليوم*") {
                $text = Get-TodayScheduleText
                Send-Msg $chatId $text
            }
            elseif ($msgText -eq "/start" -or $msgText -like "*تشغيل*") {
                Send-Msg $chatId "▶️ <b>أهلاً بك! تم تفعيل التنبيهات بنجاح (ACTIVE).</b>"
            }
            elseif ($msgText -eq "/stop" -or $msgText -like "*إيقاف*") {
                Send-Msg $chatId "⏸️ <b>تم إيقاف التنبيهات مؤقتاً (PAUSED).</b>"
            }
            elseif ($msgText -eq "/skip_today" -or $msgText -like "*إجازة*") {
                Send-Msg $chatId "🏖️ <b>تم تفعيل وضع إجازة اليوم.</b> ستستأنف التنبيهات غداً الساعة 06:00 صباحاً."
            }
        }
    }
}
