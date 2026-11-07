import os
import requests

# 1. กำหนด Credentials และ URL ของ tunnel ปัจจุบันผ่าน environment
BOT_TOKEN = os.environ.get("WEBEX_BOT_TOKEN")
TUNNEL_URL = os.environ.get("TUNNEL_URL")
if not BOT_TOKEN:
    raise RuntimeError("Set WEBEX_BOT_TOKEN in the environment")
if (
    not TUNNEL_URL
    or not TUNNEL_URL.startswith("https://")
    or not TUNNEL_URL.endswith("/webhook")
):
    raise RuntimeError(
        "Set TUNNEL_URL to the current HTTPS tunnel URL ending in /webhook"
    )

# 2. ใส่ Room ID ของทั้งสองห้อง
ROOM_IDS = {
    "IPA2026": "Y2lzY29zcGFyazovL3VybjpURUFNOnVzLXdlc3QtMl9yL1JPT00vNWEyNTFkNzAtODk4YS0xMWYxLWFiZTAtMmI4NWUyM2M2MTY1",
    "IPA2026 Exam Room": "Y2lzY29zcGFyazovL3VybjpURUFNOnVzLXdlc3QtMl9yL1JPT00vNDg0ODNjMjAtYzIwMy0xMWYxLTk0OTktNmQ3MWQ1ZmY0NTcz"
}

headers = {
    "Authorization": f"Bearer {BOT_TOKEN}",
    "Content-Type": "application/json"
}

# 3. ดึงรายการ Webhook เดิมมาตรวจสอบก่อน
response = requests.get(
    "https://webexapis.com/v1/webhooks",
    headers=headers,
    timeout=10,
)
response.raise_for_status()
existing_webhooks = response.json().get("items", [])

for room_name, room_id in ROOM_IDS.items():
    filter_str = f"roomId={room_id}"
    
    # เช็กว่ามี Webhook ของห้องนี้อยู่แล้วหรือไม่
    matched_webhook = next(
        (
            webhook
            for webhook in existing_webhooks
            if webhook.get("resource") == "messages"
            and webhook.get("event") == "created"
            and webhook.get("filter") == filter_str
        ),
        None,
    )
    
    if matched_webhook:
        # อัปเดต Target URL ของเดิม
        webhook_id = matched_webhook["id"]
        payload = {"name": f"Webhook - {room_name}", "targetUrl": TUNNEL_URL}
        res = requests.put(
            f"https://webexapis.com/v1/webhooks/{webhook_id}",
            headers=headers,
            json=payload,
            timeout=10,
        )
        res.raise_for_status()
        print(f"Updated Webhook for {room_name}: Status {res.status_code}")
    else:
        # สร้างรายการ Webhook ใหม่
        payload = {
            "name": f"Webhook - {room_name}",
            "targetUrl": TUNNEL_URL,
            "resource": "messages",
            "event": "created",
            "filter": filter_str
        }
        res = requests.post(
            "https://webexapis.com/v1/webhooks",
            headers=headers,
            json=payload,
            timeout=10,
        )
        res.raise_for_status()
        print(f"Created Webhook for {room_name}: Status {res.status_code}")