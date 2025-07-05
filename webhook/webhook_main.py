from fastapi import FastAPI, Request, HTTPException
import aiohttp
import asyncio
from webhook.config import CHAPA_SECRET_KEY
from webhook.db import create_database_connection  # You already have this
from datetime import datetime, timedelta


app = FastAPI()

CHAPA_VERIFY_URL = "https://api.chapa.co/v1/transaction/verify/"
@app.post("/chapa/webhook")
async def chapa_webhook(request: Request):
    data = await request.json()
    tx_ref = data.get("tx_ref")

    if not tx_ref:
        raise HTTPException(status_code=400, detail="Missing tx_ref")

    # Step 1: Verify the payment with Chapa
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {CHAPA_SECRET_KEY}"}
        async with session.get(f"{CHAPA_VERIFY_URL}{tx_ref}", headers=headers) as resp:
            verify_data = await resp.json()

            if resp.status != 200 or verify_data["status"] != "success":
                raise HTTPException(status_code=400, detail="Verification failed")

            status = verify_data["data"]["status"]
            if status != "success":
                raise HTTPException(status_code=400, detail="Payment not completed")

    # Step 2: Look up payment details in your database
    conn = await create_database_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, plan FROM chapa_payments WHERE tx_ref = %s", (tx_ref,))
    result = cursor.fetchone()

    if not result:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Payment record not found")

    user_id, plan = result

    # Step 3: Calculate VIP expiry
    if plan == "chapa_1m":
        expiry = datetime.now() + timedelta(days=30)
    elif plan == "chapa_6m":
        expiry = datetime.now() + timedelta(days=30 * 6)
    elif plan == "chapa_1y":
        expiry = datetime.now() + timedelta(days=365)
    else:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid plan")

    # Step 4: Update user to VIP
    cursor.execute(
        "UPDATE users SET is_vip = TRUE, vip_expiry_date = %s WHERE user_id = %s",
        (expiry, user_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "VIP updated successfully"}
