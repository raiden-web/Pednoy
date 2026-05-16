from flask import Flask, request

from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage

from oauth2client.service_account import ServiceAccountCredentials
import gspread

from datetime import datetime
import os

app = Flask(__name__)

# =========================
# LINE TOKEN
# =========================

LINE_CHANNEL_ACCESS_TOKEN = "2010102408"
LINE_CHANNEL_SECRET = "6a37be4915370520fed202987ff3840a"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# =========================
# GOOGLE SHEETS
# =========================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    "statement.json",
    scope
)

client = gspread.authorize(creds)

sheet = client.open("Statement").sheet1

# =========================
# CALLBACK
# =========================

@app.route("/callback", methods=['POST'])
def callback():

    signature = request.headers['X-Line-Signature']

    body = request.get_data(as_text=True)

    handler.handle(body, signature)

    return 'OK'

# =========================
# MESSAGE EVENT
# =========================

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    text = event.message.text

    try:

        # =====================
        # รายรับ
        # =====================

        if text.startswith("ขาย"):

            parts = text.split()

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

            parts = text.split()

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

            records = sheet.get_all_records()

            income = 0
            expense = 0

            today = datetime.now().strftime("%Y-%m-%d")

            for row in records:

                if today in row['เวลา']:

                    if row['ประเภท'] == 'รายรับ':
                        income += int(row['ยอดเงิน'])

                    elif row['ประเภท'] == 'รายจ่าย':
                        expense += int(row['ยอดเงิน'])

            profit = income - expense

            reply = (
                f"สรุปวันนี้\n"
                f"รายรับ: {income} บาท\n"
                f"รายจ่าย: {expense} บาท\n"
                f"กำไร: {profit} บาท"
            )

        # =====================
        # HELP
        # =====================

        else:

            reply = (
                "คำสั่งที่ใช้ได้\n"
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
# RUN APP
# =========================

if __name__ == "__main__":
    app.run(debug=True)