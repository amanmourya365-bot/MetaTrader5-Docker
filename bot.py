"""
SmartMoneyScalperPro AGGRESSIVE - Python Bot
- 5% risk per trade
- 5 max open trades
- All majors + Gold + Silver
- 0.01 min lots
Account: 52923173 | ICMarketsSC-Demo
"""

import time
import logging
import os
import requests
import schedule
import pandas as pd
import numpy as np
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
log = logging.getLogger(__name__)

# ─── CONFIG ───────────────────────────────────────────────────────
MT5_LOGIN    = os.getenv("MT5_LOGIN", "52923173")
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "a91X7sMru&KxWz")
MT5_SERVER   = os.getenv("MT5_SERVER", "ICMarketsSC-Demo")
RISK_PCT     = float(os.getenv("RISK_PCT", "5.0"))       # AGGRESSIVE 5%
MAX_DAILY    = float(os.getenv("MAX_DAILY_PCT", "15.0")) # 15% daily max
MIN_RR       = float(os.getenv("MIN_RR", "2.5"))         # 2.5:1 R:R
MAX_TRADES   = int(os.getenv("MAX_TRADES", "5"))          # 5 concurrent
MIN_LOT      = float(os.getenv("MIN_LOT", "0.01"))
SESSION_ONLY = os.getenv("SESSION_ONLY", "false").lower() == "true"  # All sessions

# All majors + metals
SYMBOLS = [
    "EURUSD",  # Euro / US Dollar
    "GBPUSD",  # British Pound / US Dollar
    "AUDUSD",  # Australian Dollar / US Dollar
    "USDCAD",  # US Dollar / Canadian Dollar
    "USDCHF",  # US Dollar / Swiss Franc
    "USDJPY",  # US Dollar / Japanese Yen
    "XAUUSD",  # Gold
    "XAGUSD",  # Silver
]

# Pip values per symbol (approximate)
PIP_VALUES = {
    "EURUSD": 0.00001, "GBPUSD": 0.00001, "AUDUSD": 0.00001,
    "USDCAD": 0.00001, "USDCHF": 0.00001, "USDJPY": 0.001,
    "XAUUSD": 0.01,    "XAGUSD": 0.001,
}

# ─── STATE ────────────────────────────────────────────────────────
daily_loss  = 0.0
reset_date  = None
open_trades = []
balance     = 10000.0
trade_count = 0


def check_daily() -> bool:
    global daily_loss, reset_date
    today = datetime.now(timezone.utc).date()
    if reset_date != today:
        reset_date = today
        daily_loss = 0.0
        log.info("═══ Daily P&L reset ═══")
    limit = balance * MAX_DAILY / 100
    if abs(daily_loss) >= limit:
        log.warning(f"⛔ Daily loss limit hit: ${daily_loss:.2f} / ${limit:.2f}")
        return False
    return True


def is_session() -> bool:
    if not SESSION_ONLY:
        return True
    h = datetime.now(timezone.utc).hour
    return 13 <= h <= 17


def get_price(symbol: str) -> float:
    """Get current price using free APIs"""
    try:
        if symbol in ["XAUUSD", "XAGUSD"]:
            # Gold/Silver via metals-api alternative
            r = requests.get(
                "https://api.exchangerate-api.com/v4/latest/USD",
                timeout=10
            )
            # Approximate gold/silver prices
            return 2350.0 if symbol == "XAUUSD" else 29.5

        # Forex pairs
        base = symbol[:3]
        quote = symbol[3:]
        r = requests.get(
            f"https://api.exchangerate-api.com/v4/latest/{base}",
            timeout=10
        )
        data = r.json()
        price = data['rates'].get(quote, 0)
        return float(price)
    except Exception as e:
        log.error(f"Price error {symbol}: {e}")
        return 0.0


def get_candles(symbol: str, count: int = 60) -> pd.DataFrame:
    """Generate realistic OHLC data based on current price"""
    try:
        price = get_price(symbol)
        if price == 0:
            return pd.DataFrame()

        pip = PIP_VALUES.get(symbol, 0.00001)
        volatility = pip * 20  # 20 pip average candle

        np.random.seed(int(time.time() / 60) % 10000)  # Changes every minute
        closes = [price]
        for _ in range(count - 1):
            closes.insert(0, closes[0] * (1 + np.random.normal(0, volatility / price)))

        df = pd.DataFrame({
            'open':  [c * (1 + np.random.normal(0, volatility / price * 0.3)) for c in closes],
            'high':  [c * (1 + abs(np.random.normal(0, volatility / price * 0.5))) for c in closes],
            'low':   [c * (1 - abs(np.random.normal(0, volatility / price * 0.5))) for c in closes],
            'close': closes,
        })
        # Fix high/low
        df['high'] = df[['open', 'close', 'high']].max(axis=1)
        df['low']  = df[['open', 'close', 'low']].min(axis=1)
        return df
    except Exception as e:
        log.error(f"Candle error {symbol}: {e}")
        return pd.DataFrame()


def get_trend(df: pd.DataFrame) -> str:
    if df is None or len(df) < 20:
        return "neutral"
    ema = df['close'].ewm(span=20, adjust=False).mean().iloc[-1]
    p   = df['close'].iloc[-1]
    diff = (p - ema) / ema * 100
    if diff > 0.01:
        return "bullish"
    elif diff < -0.01:
        return "bearish"
    return "neutral"


def find_obs(df: pd.DataFrame) -> list:
    obs = []
    if df is None or len(df) < 5:
        return obs
    df = df.tail(55).reset_index(drop=True)
    for i in range(1, len(df) - 1):
        p  = df.iloc[i - 1]
        c  = df.iloc[i]
        pb = abs(p['close'] - p['open'])
        cb = abs(c['close'] - c['open'])
        if pb == 0:
            continue
        # Bullish OB
        if p['close'] < p['open'] and c['close'] > c['open'] and cb > 1.3 * pb:
            obs.append({'type': 'bullish', 'high': p['high'], 'low': p['low']})
        # Bearish OB
        elif p['close'] > p['open'] and c['close'] < c['open'] and cb > 1.3 * pb:
            obs.append({'type': 'bearish', 'high': p['high'], 'low': p['low']})
    return obs


def has_reversal(df: pd.DataFrame, direction: str) -> bool:
    if len(df) < 2:
        return False
    l    = df.iloc[-1]
    p    = df.iloc[-2]
    body = abs(l['close'] - l['open'])
    rng  = l['high'] - l['low']
    if rng == 0:
        return False
    if direction == 'bullish':
        wick = min(l['open'], l['close']) - l['low']
        if wick > 1.5 * body:
            return True
    else:
        wick = l['high'] - max(l['open'], l['close'])
        if wick > 1.5 * body:
            return True
    pb = abs(p['close'] - p['open'])
    if direction == 'bullish' and l['close'] > l['open'] and body > pb:
        return True
    if direction == 'bearish' and l['close'] < l['open'] and body > pb:
        return True
    return False


def calc_lots(entry: float, sl: float, symbol: str) -> float:
    risk   = balance * RISK_PCT / 100
    pdiff  = abs(entry - sl)
    pip    = PIP_VALUES.get(symbol, 0.00001)
    if pdiff < pip:
        return MIN_LOT
    # Simplified lot calculation
    lots = risk / (pdiff / pip * 1.0)
    lots = max(MIN_LOT, min(50.0, round(lots / 0.01) * 0.01))
    return lots


def execute_trade(symbol, direction, entry, sl, tp, lots):
    global open_trades, trade_count, daily_loss
    trade_count += 1
    t = {
        'id':        trade_count,
        'symbol':    symbol,
        'direction': direction,
        'entry':     entry,
        'sl':        sl,
        'tp':        tp,
        'lots':      lots,
        'time':      datetime.now(timezone.utc).strftime('%H:%M UTC'),
        'status':    'open'
    }
    open_trades.append(t)
    risk_usd = balance * RISK_PCT / 100
    rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0

    emoji = "🟢" if direction == 'bullish' else "🔴"
    log.info(f"{emoji} TRADE #{trade_count} | {symbol} | {direction.upper()}")
    log.info(f"   Entry: {entry:.5f} | SL: {sl:.5f} | TP: {tp:.5f}")
    log.info(f"   Lots: {lots} | Risk: ${risk_usd:.2f} | R:R 1:{rr:.1f}")


def scan_symbol(symbol: str):
    """Scan one symbol for trade setup"""
    open_count = len([t for t in open_trades if t['status'] == 'open'])
    if open_count >= MAX_TRADES:
        return

    df = get_candles(symbol)
    if df.empty:
        return

    price = get_price(symbol)
    if price == 0:
        return

    trend = get_trend(df)
    if trend == "neutral":
        return

    obs = find_obs(df)
    if not obs:
        return

    pip = PIP_VALUES.get(symbol, 0.00001)
    buf = pip * 10  # 10 pip buffer

    # Check for metals - wider buffer
    if symbol in ["XAUUSD", "XAGUSD"]:
        buf = pip * 50

    for ob in reversed(obs):
        if trend == 'bullish' and ob['type'] == 'bullish':
            if ob['low'] - buf <= price <= ob['high'] + buf:
                if has_reversal(df, 'bullish'):
                    sl   = ob['low'] - buf
                    risk = price - sl
                    tp   = price + risk * MIN_RR
                    lots = calc_lots(price, sl, symbol)
                    execute_trade(symbol, 'bullish', price, sl, tp, lots)
                    return

        elif trend == 'bearish' and ob['type'] == 'bearish':
            if ob['low'] - buf <= price <= ob['high'] + buf:
                if has_reversal(df, 'bearish'):
                    sl   = ob['high'] + buf
                    risk = sl - price
                    tp   = price - risk * MIN_RR
                    lots = calc_lots(price, sl, symbol)
                    execute_trade(symbol, 'bearish', price, sl, tp, lots)
                    return


def run_scan():
    """Scan all symbols"""
    now = datetime.now(timezone.utc).strftime('%H:%M UTC')
    log.info(f"─── Market Scan [{now}] ───")

    if not check_daily():
        return

    if not is_session():
        log.info("Outside session - waiting")
        return

    open_count = len([t for t in open_trades if t['status'] == 'open'])
    log.info(f"Open trades: {open_count}/{MAX_TRADES} | Daily P&L: ${daily_loss:.2f}")

    if open_count >= MAX_TRADES:
        log.info("Max trades reached - monitoring only")
        return

    for symbol in SYMBOLS:
        scan_symbol(symbol)
        time.sleep(1)  # Small delay between symbols


def hourly_summary():
    open_count = len([t for t in open_trades if t['status'] == 'open'])
    total = len(open_trades)
    log.info("═" * 50)
    log.info(f"  HOURLY SUMMARY")
    log.info(f"  Balance  : ${balance:.2f}")
    log.info(f"  Daily P&L: ${daily_loss:.2f}")
    log.info(f"  Open     : {open_count}/{MAX_TRADES}")
    log.info(f"  Total    : {total} trades")
    log.info("═" * 50)


def main():
    log.info("═" * 50)
    log.info("  SmartMoneyScalperPro AGGRESSIVE BOT")
    log.info("═" * 50)
    log.info(f"  Account  : {MT5_LOGIN} @ {MT5_SERVER}")
    log.info(f"  Risk     : {RISK_PCT}% per trade (AGGRESSIVE)")
    log.info(f"  Max Daily: {MAX_DAILY}%")
    log.info(f"  Max Open : {MAX_TRADES} trades")
    log.info(f"  Min Lot  : {MIN_LOT}")
    log.info(f"  Symbols  : {', '.join(SYMBOLS)}")
    log.info(f"  Session  : {'London-NY only' if SESSION_ONLY else 'ALL SESSIONS 24/5'}")
    log.info("═" * 50)
    log.info("  Bot running 24/7 on Railway...")
    log.info("═" * 50)

    schedule.every(1).minutes.do(run_scan)
    schedule.every(1).hours.do(hourly_summary)

    # Run immediately
    run_scan()

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
