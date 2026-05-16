# =========================
# MESSAGE EVENT
# =========================

if handler:

    @handler.add(MessageEvent, message=TextMessage)
    def handle_message(event):

        text = event.message.text

        reply = ""

        quick_reply = QuickReply(
            items=[

                QuickReplyButton(
                    action=MessageAction(
                        label="💰 รายรับ",
                        text="ขาย "
                    )
                ),

                QuickReplyButton(
                    action=MessageAction(
                        label="💸 รายจ่าย",
                        text="จ่าย "
                    )
                ),

                QuickReplyButton(
                    action=MessageAction(
                        label="📊 สรุปวันนี้",
                        text="สรุปวันนี้"
                    )
                )

            ]
        )

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
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
                TextSendMessage(
                    text=reply,
                    quick_reply=quick_reply
                )
            )

        except Exception as e:

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"Error: {str(e)}")
            )