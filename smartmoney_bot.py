import requests
import time
import random

# ===============================
# TELEGRAM BİLGİLERİN
# ===============================
BOT_TOKEN = "8129823477:AAG2t4WQud2AEMpNDD2ancIfiv6Oksh3wyA"
CHAT_ID = "1983619537"

# ===============================
# STRATEJİ AYARLARI
# ===============================
COINS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT", "XRPUSDT"]  # ilk 100 tarama için örnek
TIMEFRAME = "1h"

# Her 30 dakikada bir tarama yap
SCAN_INTERVAL = 1800  

def check_fake_signal():
    # Burada normalde borsa API'si, EMA, Hacim, FVG vb. analizler olur.
    # Şimdilik örnek sinyal üretelim (gerçek versiyon Render'da çalışacak)
    setups = [
        ("BTCUSDT", "LONG", "1. FVG+OB + EMA uyumu + 4H trend yönüyle aynı", 100),
        ("SOLUSDT", "SHORT", "2. FVG+OB + EMA uyumu", 90),
        ("ETHUSDT", "LONG", "1. FVG+OB", 80),
    ]
    return random.sample(setups, 1)[0]  # rastgele 1 sinyal

def send_telegram_signal(coin, signal, reasons, confidence):
    msg = f"📊 *Smart Money Sinyali*\n\n💰 Coin: {coin}\n📈 İşlem: {signal}\n⚙️ Nedenler: {reasons}\n🔒 Güven: %{confidence}\n\n🚀 Entry, TP, SL otomatik analizde belirlenecek."
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, data=data)

print("Bot aktif. Sinyaller taranıyor...")

while True:
    try:
        coin, signal, reasons, confidence = check_fake_signal()
        send_telegram_signal(coin, signal, reasons, confidence)
        print(f"{coin} sinyali gönderildi. Güven: %{confidence}")
    except Exception as e:
        print("Hata:", e)
    time.sleep(SCAN_INTERVAL)
