# main_final.py
# Eksiksiz Smart Money Scanner (ilk 100 coin)
# Özellikler:
# - Likidite öncelikli tespit
# - BOS + Order Block + FVG
# - 4H trend filtresi (zıt olanlar elenir)
# - 15m onayı (pinbar/engulfing) + EMA(9/21) uyumu
# - Hacim artışı teyidi (1H)
# - Güven yüzdesi: 4->100, 3->90, 2->85, 1->80
# - Entry / TP / SL hesaplama (TP: yakın likidite / RR fallback, SL: OB fitil alt/üst)
# - Telegram bildirimleri (kullanıcıya uygun format)

import os, time, math, requests
from datetime import datetime, timedelta
import ccxt
import pandas as pd
import numpy as np

# -------- CONFIG ----------
# Eğer Render ortamında ENV ile koyacaksan bunları Render'da ekle (Recommended)
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8129823477:AAG2t4WQud2AEMpNDD2ancIfiv6Oksh3wyA"
CHAT_ID   = os.getenv("CHAT_ID")   or "1983619537"

CHECK_INTERVAL = 15 * 60  # saniye
TOP_N = 100
SYMBOL_QUOTE = "USDT"
BINANCE = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
RATE_SLEEP = 0.6  # semboller arası bekleme

# Seans saatleri (TSİ / UTC+3) - sadece önceliklendirme (seans dışı da değerlendirilecek)
LONDON_START = (10,0); LONDON_END = (12,0)
NY_START = (15,30); NY_END = (17,30)

# ---------- UTIL ----------
def now_local():
    # TSİ approx: utc +3; sadece saat kullanıyoruz
    return datetime.utcnow() + timedelta(hours=3)

def in_priority_session():
    t = now_local().time()
    def within(start, end):
        s = start; e = end
        return (s[0], s[1]) <= (t.hour, t.minute) <= (e[0], e[1])
    return within(LONDON_START, LONDON_END) or within(NY_START, NY_END)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    try:
        r = requests.post(url, data=payload, timeout=10)
        return r.status_code
    except Exception as e:
        print("Telegram send error:", e)
        return None

# ---------- FETCH HELPERS ----------
def fetch_klines(symbol, timeframe, limit=200):
    # returns DataFrame with columns: ts, open, high, low, close, volume
    raw = BINANCE.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=['ts','open','high','low','close','volume'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms') + pd.Timedelta(hours=3)  # TSİ
    return df

def fetch_top_symbols(n=TOP_N):
    # get 24hr tickers and sort by quoteVolume
    arr = BINANCE.fetch_tickers()
    pairs = [s for s in arr.keys() if s.endswith("/" + SYMBOL_QUOTE)]
    # build list of (symbol, quoteVolume)
    tv = []
    for p in pairs:
        t = arr[p]
        qv = float(t.get('quoteVolume') or 0)
        tv.append((p, qv))
    tv_sorted = sorted(tv, key=lambda x: x[1], reverse=True)
    return [x[0] for x in tv_sorted[:n]]

# ---------- INDICATORS & PATTERNS ----------
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def detect_4h_trend(symbol):
    kl4 = fetch_klines(symbol, '4h', limit=250)
    closes = kl4['close']
    e50 = ema(closes, 50).iloc[-1]
    e200 = ema(closes, 200).iloc[-1]
    if pd.isna(e50) or pd.isna(e200):
        return "neutral"
    return "bull" if e50 > e200 else "bear"

def detect_liquidity_grab_from_1h(df1h):
    # Likidite alımı: son mumun wick'i önceki extremeyi aşmışsa
    if len(df1h) < 3:
        return None
    last = df1h.iloc[-1]
    prev = df1h.iloc[-2]
    # yukarıya fitil atıp geri dönme -> short_liq (longları stop'lar)
    if last['high'] > prev['high'] * 1.0001 and last['close'] < last['high'] * 0.998:
        return "short_liq"
    # aşağı fitil atıp geri dönme -> long_liq
    if last['low'] < prev['low'] * 0.9999 and last['close'] > last['low'] * 1.002:
        return "long_liq"
    return None

def detect_bos_and_order_block(df1h):
    # BOS: son kapanış önceki N mum içindeki max veya min'i kırdı mı?
    window = min(60, len(df1h)-2)
    if window < 5:
        return {"bos": False}
    highs = df1h['high'].iloc[-(window+2):-1]
    lows = df1h['low'].iloc[-(window+2):-1]
    prev_max = highs.max()
    prev_min = lows.min()
    last_close = df1h['close'].iloc[-1]
    res = {"bos": False}
    if last_close > prev_max:
        res.update({"bos": True, "dir": "bull"})
    elif last_close < prev_min:
        res.update({"bos": True, "dir": "bear"})
    else:
        return res
    # order block: find last opposite color significant candle before BOS
    for i in range(len(df1h)-3, 0, -1):
        o = float(df1h['open'].iloc[i]); c = float(df1h['close'].iloc[i])
        size = abs(c - o)
        prev_avg = df1h['close'].pct_change().abs().iloc[-20:].mean() if len(df1h) > 20 else 0
        # pick opposite color large body
        if res['dir'] == 'bull' and c < o and size > 0:
            res['order_block'] = {"top": float(df1h['high'].iloc[i]), "bottom": float(df1h['low'].iloc[i]), "idx": i}
            break
        if res['dir'] == 'bear' and c > o and size > 0:
            res['order_block'] = {"top": float(df1h['high'].iloc[i]), "bottom": float(df1h['low'].iloc[i]), "idx": i}
            break
    return res

def detect_fvg(df1h):
    # Basic 3-candle FVG detection
    fvg_list = []
    for i in range(len(df1h)-2):
        h0 = float(df1h['high'].iloc[i]); l0 = float(df1h['low'].iloc[i])
        h2 = float(df1h['high'].iloc[i+2]); l2 = float(df1h['low'].iloc[i+2])
        # bullish FVG: h0 < l2
        if h0 < l2:
            fvg_list.append({"type":"bull","top":h0,"bottom":l2,"idx":i})
        # bearish FVG: h2 < l0
        if h2 < l0:
            fvg_list.append({"type":"bear","top":h2,"bottom":l0,"idx":i})
    return fvg_list

def fvg_touched(fvg, last_close):
    return fvg["bottom"] <= last_close <= fvg["top"]

def volume_increase(df1h):
    vols = df1h['volume'].astype(float).iloc[-10:].values
    if len(vols) < 4:
        return False
    last = vols[-1]
    avg_prev = vols[:-1].mean() if len(vols[:-1])>0 else 0
    return last > avg_prev * 1.15

def ema_15m_dir(df15m):
    closes = df15m['close']
    e9 = ema(closes, 9).iloc[-1] if len(closes) >= 9 else None
    e21 = ema(closes, 21).iloc[-1] if len(closes) >= 21 else None
    if e9 is None or e21 is None:
        return None
    return "bull" if e9 > e21 else "bear"

def detect_15m_confirmation(df15m):
    if len(df15m) < 2:
        return None
    o1,c1,h1,l1 = df15m[['open','close','high','low']].iloc[-2].astype(float)
    o2,c2,h2,l2 = df15m[['open','close','high','low']].iloc[-1].astype(float)
    # Bullish engulfing
    if c2 > o2 and c1 < o1 and o2 < c1 and c2 > o1:
        return "bullish_engulfing"
    # Bearish engulfing
    if c2 < o2 and c1 > o1 and o2 > c1 and c2 < o1:
        return "bearish_engulfing"
    # pinbar checks
    body = abs(c2 - o2); rng = h2 - l2
    if rng > 0 and body / rng < 0.35:
        upper = h2 - max(c2, o2); lower = min(c2, o2) - l2
        if lower > upper * 1.5:
            return "bullish_pinbar"
        if upper > lower * 1.5:
            return "bearish_pinbar"
    return None

# ---------- ENTRY / TP / SL ----------
def calc_entry_tp_sl(side, df1h, order_block):
    last = float(df1h['close'].iloc[-1])
    if order_block:
        ob_top = float(order_block['top']); ob_bot = float(order_block['bottom'])
    else:
        ob_top = ob_bot = None

    if side == "LONG":
        sl = ob_bot * 0.999 if ob_bot else last * 0.99
        recent_high = float(df1h['high'].iloc[-50:].max())
        tp = recent_high
        # ensure acceptable RR (>=1.5), else set 1:2
        rr = (tp - last) / (last - sl) if (last - sl) != 0 else None
        if rr is None or rr < 1.5:
            tp = last + (last - sl) * 2
        return last, tp, sl
    else:
        sl = ob_top * 1.001 if ob_top else last * 1.01
        recent_low = float(df1h['low'].iloc[-50:].min())
        tp = recent_low
        rr = (last - tp) / (sl - last) if (sl - last) != 0 else None
        if rr is None or rr < 1.5:
            tp = last - (sl - last) * 2
        return last, tp, sl

# ---------- ANALYZE SYMBOL ----------
def analyze_symbol(symbol):
    try:
        df1h = fetch_klines(symbol, '1h', limit=200)
        df15 = fetch_klines(symbol, '15m', limit=200)
    except Exception as e:
        print(symbol, "kline fetch error:", e)
        return None

    # 1) likidite önceliği
    liq = detect_liquidity_grab_from_1h(df1h)
    if not liq:
        return None  # likidite yoksa ilk şart sağlanmıyor; öncelik olduğu için eliyoruz

    # 2) BOS & OB
    bos_ob = detect_bos_and_order_block(df1h)
    if not bos_ob.get('bos'):
        return None

    # 3) FVG
    fvg_list = detect_fvg(df1h)
    chosen_fvg = None
    last_close = float(df1h['close'].iloc[-1])
    for f in reversed(fvg_list):
        if fvg_touched(f, last_close):
            chosen_fvg = f
            break

    # 4) 4H trend
    trend4h = detect_4h_trend(symbol)
    dirn = bos_ob.get('dir')  # 'bull' or 'bear'
    # filter opposite
    if (trend4h == 'bull' and dirn == 'bear') or (trend4h == 'bear' and dirn == 'bull'):
        return None

    # 5) volume & 15m ema
    vol_ok = volume_increase(df1h)
    ema15 = ema_15m_dir(df15)
    ema_ok = (ema15 == 'bull' and dirn == 'bull') or (ema15 == 'bear' and dirn == 'bear')

    # 6) 15m confirmation candle
    conf15 = detect_15m_confirmation(df15)

    # CRITERIA (user-specified 4 items)
    c1 = bool(chosen_fvg and bos_ob.get('order_block'))   # FVG + OB
    c2 = True  # 4H trend uyumu (we already filtered opposites)
    c3 = in_priority_session()  # session prioritized but not required
    c4 = vol_ok or ema_ok

    count_true = sum([1 if x else 0 for x in (c1,c2,c3,c4)])
    if count_true == 4:
        conf = 100
    elif count_true == 3:
        conf = 90
    elif count_true == 2:
        conf = 85
    elif count_true == 1:
        conf = 80
    else:
        return None

    side = "LONG" if dirn == "bull" else "SHORT"
    entry, tp, sl = calc_entry_tp_sl(side, df1h, bos_ob.get('order_block'))

    passed = []
    if c1: passed.append("1. FVG+OB")
    if c2: passed.append("2. 4H trend uyumlu")
    if c3: passed.append("3. Londra/NY öncelik")
    if c4: passed.append("4. Hacim/EMA teyidi")

    msg = (
        f"📊 Coin: {symbol}\n"
        f"📈 İşlem önerisi: {side}\n"
        f"🔐 Güven: %{conf}\n"
        f"📋 Sağlanan kriterler: {', '.join(passed)}\n"
        f"🔎 15m onay: {conf15}\n"
        f"💰 Entry: {round(entry,6)}\n"
        f"🎯 TP: {round(tp,6)}\n"
        f"🛑 SL: {round(sl,6)}\n"
        f"⏰ Zaman(TSİ): {now_local().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Detay: BOS:{bos_ob.get('bos')} | Liquidity:{liq} | FVG:{'Yes' if chosen_fvg else 'No'} | OB:{'Yes' if bos_ob.get('order_block') else 'No'} | VolInc:{vol_ok} | EMA15:{ema15}"
    )
    return {"symbol": symbol, "conf": conf, "msg": msg}

# ---------- MAIN LOOP ----------
def main():
    print("SmartMoney bot starting...")
    try:
        symbols = fetch_top_symbols(TOP_N)
    except Exception as e:
        print("Top symbols fetch error:", e)
        symbols = []
    # ensure we have at least something
    if not symbols:
        symbols = ["BTC/USDT","ETH/USDT","BNB/USDT","SOL/USDT","ADA/USDT"][:TOP_N]

    send_telegram("✅ SmartMoney BOT (100 coin) başlatıldı.")
    while True:
        sent = 0
        for s in symbols:
            try:
                res = analyze_symbol(s)
                if res:
                    status = send_telegram(res["msg"])
                    print(f"[{now_local().strftime('%H:%M')}] Sent {s} conf {res['conf']} status {status}")
                    sent += 1
                time.sleep(RATE_SLEEP)
            except Exception as e:
                print("analyze error", s, e)
                continue
        print(f"Scan complete ({now_local().strftime('%Y-%m-%d %H:%M:%S')}) Sent: {sent}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
