"""
nova_webhook.py — TradingView webhook receiver + signal processor
Pulls market data → runs ConfluenceEngine → generates signal → saves to Supabase + sends Telegram

Run on Railway: python nova_webhook.py
"""
import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx

from nova_core.signal_generator import SignalGenerator, InvestorStyle
from nova_core.confluence_engine import ConfluenceEngine
from nova_core.risk_calculator import RiskCalculator

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "8523785829:AAGnyoKSjFxfzWPvBx5ETm0qEVu6GXTAhfs")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://llqobekmngowvmwenpda.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
GOLD_CHANNEL_ID = os.getenv("GOLD_CHANNEL_ID", "-1003977021472")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "verstige_signals_2026")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s"
)
logger = logging.getLogger("nova_webhook")

# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(title="NOVA Signal Processor", version="1.0")
signal_gen = SignalGenerator()
confluence = ConfluenceEngine()
risk_calc = RiskCalculator()

# ── Supabase Helpers ──────────────────────────────────────────────────────────
async def save_to_supabase(signal: dict) -> bool:
    """Save signal to Supabase gold_signals table."""
    if not SUPABASE_KEY:
        logger.warning("SUPABASE_SERVICE_ROLE_KEY not set — skipping DB save")
        return False

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "direction": signal["direction"],
        "entry_price": signal["entry_price"],
        "stop_loss": signal["stop_loss"],
        "take_profit": signal["take_profit"],
        "risk_reward": signal["risk_reward_ratio"],
        "risk_pips": signal["risk_amount_pips"],
        "confidence": signal["confidence"],
        "confluence_count": signal["confluence_count"],
        "investor_views": json.dumps(signal.get("investor_views", [])),
        "recommendation": signal["recommendation"],
        "telegram_sent": False,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/gold_signals",
                headers=headers,
                json=payload,
                timeout=10.0
            )
        if resp.status_code in (200, 201):
            logger.info(f"Saved signal {signal['id']} to Supabase")
            return True
        else:
            logger.error(f"Supabase error: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Supabase exception: {e}")
        return False


async def send_telegram(message: str) -> bool:
    """Send message to Telegram trading channel."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": GOLD_CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10.0)
        if resp.status_code == 200:
            logger.info("Telegram alert sent")
            return True
        else:
            logger.error(f"Telegram error: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram exception: {e}")
        return False


# ── Webhook Handler ────────────────────────────────────────────────────────────
@app.post("/webhook")
async def receive_webhook(request: Request):
    """
    TradingView sends alerts here. Format:
    {
      "symbol": "XAUUSD",
      "direction": "long",
      "entry_price": 2345.67,
      "atr": 15.5,
      "price": 2345.00,
      "session_high": 2348.00,
      "session_low": 2342.00,
      "bias": "long",
      "price_action_pattern": "pin_bar_bull",
      "volume": 1.8,
      "avg_volume": 1.2,
      "htf_trend": "up",
      "active_session": "london",
      "rsi": 58,
      "fair_value": 2330,
      "macro_cycle": "contraction",
      "risk_sentiment": "fear"
    }
    """
    # Validate secret
    secret = request.headers.get("X-Webhook-Secret", "")
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    body = await request.json()
    logger.info(f"Received webhook: {json.dumps(body, indent=2)}")

    # Generate signal
    try:
        signal = signal_gen.generate(body, body["direction"], body["entry_price"])
    except Exception as e:
        logger.error(f"Signal generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Signal generation error: {e}")

    # Save to Supabase
    await save_to_supabase(signal.__dict__)

    # Send to Telegram based on confidence
    if signal.confidence == "HIGH" and signal.confluence_count >= 5:
        # Full report for HIGH confidence
        message = signal.to_telegram_format()
        await send_telegram(message)
        logger.info(f"HIGH confidence signal sent: {signal.id}")
    elif signal.confidence == "MEDIUM":
        # Brief alert for MEDIUM — no trade
        brief = f"⚠️ **{signal.direction.upper()}** {signal.symbol} @ {signal.entry_price:.2f}\n"
        brief += f"Confidence: {signal.confidence} ({signal.confluence_count}/6 confluences)\n"
        brief += f"Recommendation: ALERT ONLY — insufficient confluence for execution"
        await send_telegram(brief)
        logger.info(f"MEDIUM signal alert sent: {signal.id}")
    else:
        logger.info(f"LOW confidence signal skipped: {signal.id}")

    return JSONResponse({
        "status": "processed",
        "signal_id": signal.id,
        "confidence": signal.confidence,
        "confluence_count": signal.confluence_count,
        "recommendation": signal.recommendation,
    })


# ── Manual Signal Trigger ──────────────────────────────────────────────────────
@app.post("/signal/generate")
async def generate_manual_signal(data: dict):
    """
    For testing / manual triggers. Post JSON directly:
    {
      "symbol": "XAUUSD",
      "direction": "long",
      "entry_price": 2345.67,
      ... (same fields as webhook)
    }
    """
    try:
        signal = signal_gen.generate(data, data["direction"], data["entry_price"])
        return {
            "status": "generated",
            "signal": signal.__dict__,
            "formatted": signal.to_telegram_format(),
        }
    except Exception as e:
        logger.error(f"Manual signal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "nova_webhook", "version": "1.0"}


@app.get("/")
async def root():
    return {
        "service": "NOVA Signal Processor",
        "endpoints": [
            "POST /webhook — TradingView alert endpoint",
            "POST /signal/generate — Manual signal generation",
            "GET /health — Health check",
        ]
    }


# ── Startup ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    logger.info(f"Starting NOVA webhook server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)