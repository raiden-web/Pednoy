from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
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

        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            google_creds,
            scope
        )

        client = gspread.authorize(creds)

        sheet = client.open("Statement").sheet1

        print("✅ Google Sheets Connected")

    else:
        print("⚠️ GOOGLE_CREDENTIALS NOT FOUND")

except Exception as e:
    print("❌ Google Sheets Error:", e)

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
        return "LINE not configured", 500

    signature = request.headers.get('X-Line-Signature', '')

    body = request.get_data(as_text=True)

    handler.handle(body, signature)

    return 'OK'

# =========================
# MESSAGE EVENT
# =========================

if handler:

    @handler.add(MessageEvent, message=TextMessage)
    def handle_message(event):

        text = event.message.text

        reply = ""

        try:

            # =====================
            # รายรับ
            # =====================

            if text.startswith("ขาย"):

                if not sheet:
                    reply = "ยังไม่เชื่อม Google Sheets"

                else:

                    parts = text.split()

                    if len(parts) < 4:
                        reply = "รูปแบบ: ขาย สินค้า จำนวน ราคา"

                    else:

                        item = parts[1]
                        qty = parts[2]
                        amount = parts[3]

                        sheet.append_row([
                            str(datetime.now()),
                            "รายรับ",
                            item,
                            qty,
                            amount
                        ])

                        reply = f"บันทึกยอดขายแล้ว +{amount} บาท"

            # =====================
            # รายจ่าย
            # =====================

            elif text.startswith("จ่าย"):

                if not sheet:
                    reply = "ยังไม่เชื่อม Google Sheets"

                else:

                    parts = text.split()

                    if len(parts) < 3:
                        reply = "รูปแบบ: จ่าย รายการ ราคา"

                    else:

                        item = parts[1]
                        amount = parts[2]

                        sheet.append_row([
                            str(datetime.now()),
                            "รายจ่าย",
                            item,
                            "-",
                            amount
                        ])

                        reply = f"บันทึกรายจ่ายแล้ว -{amount} บาท"

            # =====================
            # สรุปวันนี้
            # =====================

            elif text == "สรุปวันนี้":

                if not sheet:
                    reply = "ยังไม่เชื่อม Google Sheets"

                else:

                    records = sheet.get_all_records()

                    income = 0
                    expense = 0

                    today = datetime.now().strftime("%Y-%m-%d")

                    for row in records:

                        if today in str(row.get('เวลา', '')):

                            if row.get('ประเภท') == 'รายรับ':
                                income += int(row.get('ยอดเงิน', 0))

                            elif row.get('ประเภท') == 'รายจ่าย':
                                expense += int(row.get('ยอดเงิน', 0))

                    profit = income - expense

                    reply = (
                        f"สรุปวันนี้\n"
                        f"รายรับ: {income}\n"
                        f"รายจ่าย: {expense}\n"
                        f"กำไร: {profit}"
                    )

            else:

                reply = (
                    "คำสั่ง:\n"
                    "ขาย สินค้า จำนวน ราคา\n"
                    "จ่าย รายการ ราคา\n"
                    "สรุปวันนี้"
                )

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply)
            )

        except Exception as e:

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"Error: {str(e)}")
            )

# =========================
# RUN
# =========================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(host="0.0.0.0", port=port)