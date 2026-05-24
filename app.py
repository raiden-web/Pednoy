print("NEW VERSION")
from flask import Flask, request, jsonify, render_template, send_from_directory

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
LIFF_ID = os.getenv("LIFF_ID", "")

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
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
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

user_states = {}

# =========================
# ROUTES
# =========================

@app.route("/")
def home():
    return "LINE BOT RUNNING"

@app.route("/app")
def pwa_app():
    return render_template("app.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/liff")
def liff_page():
    return render_template("liff.html", liff_id=LIFF_ID)

@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json")

@app.route("/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")

# =========================
# API
# =========================

@app.route("/api/data")
def api_data():
    if not sheet:
        return jsonify({"error": "ยังไม่เชื่อม Google Sheets"}), 500
    try:
        records = sheet.get_all_records()
        return jsonify({"records": records})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/add", methods=["POST"])
def api_add():
    if not sheet:
        return jsonify({"success": False, "error": "ยังไม่เชื่อม Google Sheets"}), 500
    try:
        data = request.get_json()
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data.get("type"),
            data.get("item"),
            data.get("qty", "-"),
            data.get("amount")
        ])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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
    @handler.add(MessageEvent, message=TextMessage)
    def handle_message(event):
        text = event.message.text.strip()
        user_id = event.source.user_id
        VALID_COMMANDS = ["เพิ่มรายรับ", "เพิ่มรายจ่าย", "สรุปวันนี้", "บันทึกรายการ"]
        if user_id not in user_states and text not in VALID_COMMANDS:
            return
        reply = ""
        try:
            if text == "บันทึกรายการ":
                app_url = "https://pednoyeiei.onrender.com/app"
                reply = f"กดลิงก์นี้เพื่อเปิดแอปบันทึกรายการ:\n{app_url}"

            elif text == "เพิ่มรายรับ":
                user_states[user_id] = {"step": "income_item"}
                reply = "กรอกชื่อสินค้า"

            elif user_id in user_states and user_states[user_id]["step"] == "income_item":
                user_states[user_id]["item"] = text
                user_states[user_id]["step"] = "income_qty"
                reply = "กรอกจำนวน"

            elif user_id in user_states and user_states[user_id]["step"] == "income_qty":
                user_states[user_id]["qty"] = text
                user_states[user_id]["step"] = "income_amount"
                reply = "กรอกราคา"

            elif user_id in user_states and user_states[user_id]["step"] == "income_amount":
                item = user_states[user_id]["item"]
                qty = user_states[user_id]["qty"]
                amount = text
                if sheet:
                    sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "รายรับ", item, qty, amount])
                del user_states[user_id]
                reply = f"✅ บันทึกรายรับสำเร็จ\n\nสินค้า: {item}\nจำนวน: {qty}\nยอดเงิน: {amount} บาท"

            elif text == "เพิ่มรายจ่าย":
                user_states[user_id] = {"step": "expense_item"}
                reply = "กรอกชื่อรายการ"

            elif user_id in user_states and user_states[user_id]["step"] == "expense_item":
                user_states[user_id]["item"] = text
                user_states[user_id]["step"] = "expense_amount"
                reply = "กรอกจำนวนเงิน"

            elif user_id in user_states and user_states[user_id]["step"] == "expense_amount":
                item = user_states[user_id]["item"]
                amount = text
                if sheet:
                    sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "รายจ่าย", item, "-", amount])
                del user_states[user_id]
                reply = f"✅ บันทึกรายจ่ายสำเร็จ\n\nรายการ: {item}\nยอดเงิน: {amount} บาท"

            elif text == "สรุปวันนี้":
                if not sheet:
                    reply = "⚠️ ยังไม่เชื่อม Google Sheets"
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
                    reply = f"📊 สรุปวันนี้\n\n💰 รายรับ:  {income:,} บาท\n💸 รายจ่าย: {expense:,} บาท\n📈 กำไร:    {profit:,} บาท"

            if reply:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

        except Exception as e:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"❌ ERROR:\n{str(e)}"))

# =========================
# RUN
# =========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
