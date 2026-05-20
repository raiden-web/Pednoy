print("NEW VERSION")
from flask import Flask, request

from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent,
    FollowEvent,
    TextMessage,
    TextSendMessage,
    QuickReply,
    QuickReplyButton,
    MessageAction
)

from oauth2client.service_account import ServiceAccountCredentials
import gspread

from datetime import datetime
import json
import os

app = Flask(__name__)

# =========================
# LINE CONFIG
# =========================

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = None
handler = None

if LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET:
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    handler = WebhookHandler(LINE_CHANNEL_SECRET)
    print("✅ LINE CONNECTED")
else:
    print("⚠️ LINE ENV NOT FOUND")

# =========================
# GOOGLE SHEETS
# =========================

sheet = None

try:
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    google_creds_raw = os.getenv("GOOGLE_CREDENTIALS")

    if google_creds_raw:
        google_creds = json.loads(google_creds_raw)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Statement").sheet1
        print("✅ Google Sheets Connected")
    else:
        print("⚠️ GOOGLE_CREDENTIALS NOT FOUND")

except Exception as e:
    print("❌ Google Sheets Error:", e)

# =========================
# USER STATE
# =========================

user_states = {}

# =========================
# QUICK REPLY (ใช้ร่วมกันทั้งระบบ)
# =========================

def get_quick_reply():
    return QuickReply(
        items=[
            QuickReplyButton(
                action=MessageAction(label="💰 เพิ่มรายรับ", text="เพิ่มรายรับ")
            ),
            QuickReplyButton(
                action=MessageAction(label="💸 เพิ่มรายจ่าย", text="เพิ่มรายจ่าย")
            ),
            QuickReplyButton(
                action=MessageAction(label="📊 สรุปวันนี้", text="สรุปวันนี้")
            ),
        ]
    )

# =========================
# BOT DISCLAIMER (แจ้งเตือนทุกครั้ง)
# =========================

BOT_NOTICE = "🤖 Bot นี้ใช้สำหรับบันทึกบัญชีเท่านั้น ไม่สามารถสนทนาทั่วไปได้\n"
BOT_DIVIDER = "─────────────────\n"

# =========================
# HOME
# =========================

@app.route("/")
def home():
    return "LINE BOT RUNNING"

# =========================
# CALLBACK
# =========================

@app.route("/callback", methods=['POST'])
def callback():
    if not handler:
        return "LINE NOT CONFIGURED", 500

    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    handler.handle(body, signature)
    return 'OK'

# =========================
# EVENTS
# =========================

if handler:

    # =====================
    # FOLLOW EVENT (เพิ่มเพื่อน)
    # =====================

    @handler.add(FollowEvent)
    def handle_follow(event):
        welcome = (
            "👋 สวัสดีครับ!\n\n"
            + BOT_NOTICE
            + BOT_DIVIDER
            + "📌 คำสั่งที่ใช้ได้\n"
            "💰 เพิ่มรายรับ\n"
            "💸 เพิ่มรายจ่าย\n"
            "📊 สรุปวันนี้"
        )
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=welcome, quick_reply=get_quick_reply())
        )

    # =====================
    # MESSAGE EVENT
    # =====================

    @handler.add(MessageEvent, message=TextMessage)
    def handle_message(event):

        text = event.message.text.strip()
        user_id = event.source.user_id
        reply = ""

        try:

            # =====================
            # เริ่มเพิ่มรายรับ
            # =====================

            if text == "เพิ่มรายรับ":
                user_states[user_id] = {"step": "income_item"}
                reply = (
                    BOT_NOTICE
                    + BOT_DIVIDER
                    + "กรอกชื่อสินค้า"
                )

            # =====================
            # กรอกชื่อสินค้า (รายรับ)
            # =====================

            elif (
                user_id in user_states and
                user_states[user_id]["step"] == "income_item"
            ):
                user_states[user_id]["item"] = text
                user_states[user_id]["step"] = "income_qty"
                reply = (
                    BOT_NOTICE
                    + BOT_DIVIDER
                    + "กรอกจำนวน"
                )

            # =====================
            # กรอกจำนวน (รายรับ)
            # =====================

            elif (
                user_id in user_states and
                user_states[user_id]["step"] == "income_qty"
            ):
                user_states[user_id]["qty"] = text
                user_states[user_id]["step"] = "income_amount"
                reply = (
                    BOT_NOTICE
                    + BOT_DIVIDER
                    + "กรอกราคา"
                )

            # =====================
            # กรอกราคา (รายรับ)
            # =====================

            elif (
                user_id in user_states and
                user_states[user_id]["step"] == "income_amount"
            ):
                item = user_states[user_id]["item"]
                qty = user_states[user_id]["qty"]
                amount = text

                if sheet:
                    sheet.append_row([
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "รายรับ",
                        item,
                        qty,
                        amount
                    ])

                del user_states[user_id]

                reply = (
                    BOT_NOTICE
                    + BOT_DIVIDER
                    + f"✅ บันทึกรายรับสำเร็จ\n\n"
                    f"สินค้า: {item}\n"
                    f"จำนวน: {qty}\n"
                    f"ยอดเงิน: {amount} บาท"
                )

            # =====================
            # เริ่มเพิ่มรายจ่าย
            # =====================

            elif text == "เพิ่มรายจ่าย":
                user_states[user_id] = {"step": "expense_item"}
                reply = (
                    BOT_NOTICE
                    + BOT_DIVIDER
                    + "กรอกชื่อรายการ"
                )

            # =====================
            # กรอกชื่อรายการ (รายจ่าย)
            # =====================

            elif (
                user_id in user_states and
                user_states[user_id]["step"] == "expense_item"
            ):
                user_states[user_id]["item"] = text
                user_states[user_id]["step"] = "expense_amount"
                reply = (
                    BOT_NOTICE
                    + BOT_DIVIDER
                    + "กรอกจำนวนเงิน"
                )

            # =====================
            # กรอกเงิน (รายจ่าย)
            # =====================

            elif (
                user_id in user_states and
                user_states[user_id]["step"] == "expense_amount"
            ):
                item = user_states[user_id]["item"]
                amount = text

                if sheet:
                    sheet.append_row([
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "รายจ่าย",
                        item,
                        "-",
                        amount
                    ])

                del user_states[user_id]

                reply = (
                    BOT_NOTICE
                    + BOT_DIVIDER
                    + f"✅ บันทึกรายจ่ายสำเร็จ\n\n"
                    f"รายการ: {item}\n"
                    f"ยอดเงิน: {amount} บาท"
                )

            # =====================
            # สรุปวันนี้
            # =====================

            elif text == "สรุปวันนี้":

                if not sheet:
                    reply = (
                        BOT_NOTICE
                        + BOT_DIVIDER
                        + "⚠️ ยังไม่เชื่อม Google Sheets"
                    )
                else:
                    records = sheet.get_all_records()
                    income = 0
                    expense = 0
                    today = datetime.now().strftime("%Y-%m-%d")

                    for row in records:
                        if today in str(row.get("เวลา", "")):
                            if row.get("ประเภท") == "รายรับ":
                                income += int(row.get("ยอดเงิน", 0))
                            elif row.get("ประเภท") == "รายจ่าย":
                                expense += int(row.get("ยอดเงิน", 0))

                    profit = income - expense

                    reply = (
                        BOT_NOTICE
                        + BOT_DIVIDER
                        + f"📊 สรุปวันนี้\n\n"
                        f"💰 รายรับ:  {income:,} บาท\n"
                        f"💸 รายจ่าย: {expense:,} บาท\n"
                        f"📈 กำไร:    {profit:,} บาท"
                    )

            # =====================
            # DEFAULT (ข้อความอื่นๆ)
            # =====================

            else:
                reply = (
                    BOT_NOTICE
                    + BOT_DIVIDER
                    + "📌 คำสั่งที่ใช้ได้\n\n"
                    "💰 เพิ่มรายรับ\n"
                    "💸 เพิ่มรายจ่าย\n"
                    "📊 สรุปวันนี้"
                )

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply, quick_reply=get_quick_reply())
            )

        except Exception as e:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"❌ ERROR:\n{str(e)}")
            )

# =========================
# RUN
# =========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)