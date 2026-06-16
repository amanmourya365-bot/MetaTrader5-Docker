"""
SmartMoneyScalperPro - Python Trading Bot
IC Markets Demo: 52923173 | ICMarketsSC-Demo
"""

import time
import logging
import os
from datetime import datetime, timezone
import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

MT5_LOGIN    = int(os.getenv("MT5_LOGIN", "52923173"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "a91X7sMru&KxWz")
MT5_SERVER   = os.getenv("MT5_SERVER", "ICMarketsSC-Demo")
SYMBOL       = os.getenv("SYMBOL", "EURUSD")
RISK_PCT     = float(os.getenv("RISK_PCT", "1.0"))
MAX_DAILY    = float(os.getenv("MAX_DAILY_PCT", "3.0"))
MIN_RR       = float(os.getenv("MIN_RR", "3.0"))
MAX_TRADES   = int(os.getenv("MAX_TRADES", "2"))
SESSION_ONLY = os.getenv("SESSION_ONLY", "true").lower() == "true"
MAGIC        = 777777
OB_LOOKBACK  = 50
SL_PIPS      = 5

daily_loss       = 0.0
daily_reset_date = None

try:
    import MetaTrader5 as mt5
    MT5_OK = True
    log.info("MetaTrader5 library loaded")
except ImportError:
    MT5_OK = False
    mt5 = None
    log.warning("MetaTrader5 not available - simulation mode")


def is_session() -> bool:
    h = datetime.now(timezone.utc).hour
    return 13 <= h <= 17


def get_htf_trend(df) -> str:
    if df is None or len(df) < 200:
        return "neutral"
    ema = df['close'].ewm(span=200, adjust=False).mean().iloc[-1]
    p   = df['close'].iloc[-1]
    return "bullish" if p > ema else "bearish" if p < ema else "neutral"


def find_obs(df) -> list:
    obs = []
    df  = df.tail(OB_LOOKBACK + 5).reset_index(drop=True)
    for i in range(1, len(df) - 1):
        p = df.iloc[i - 1]
        c = df.iloc[i]
        pb = abs(p['close'] - p['open'])
        cb = abs(c['close'] - c['open'])
        if pb == 0:
            continue
        if p['close'] < p['open'] and c['close'] > c['open'] and cb > 2 * pb:
            obs.append({'type': 'bullish', 'high': p['high'], 'low': p['low']})
        elif p['close'] > p['open'] and c['close'] < c['open'] and cb > 2 * pb:
            obs.append({'type': 'bearish', 'high': p['high'], 'low': p['low']})
    return obs


def has_reversal(df, direction) -> bool:
    if len(df) < 2:
        return False
    l = df.iloc[-1]
    p = df.iloc[-2]
    body  = abs(l['close'] - l['open'])
    range_ = l['high'] - l['low']
    if range_ == 0:
        return False
    if direction == 'bullish':
        wick = l['open'] - l['low'] if l['close'] > l['open'] else l['close'] - l['low']
        if wick > 2 * body:
            return True
    else:
        wick = l['high'] - l['close'] if l['close'] < l['open'] else l['high'] - l['open']
        if wick > 2 * body:
            return True
    pb = abs(p['close'] - p['open'])
    if direction == 'bullish' and l['close'] > l['open'] and body > pb:
        return True
    if direction == 'bearish' and l['close'] < l['open'] and body > pb:
        return True
    return False


def lot_size(balance, entry, sl) -> float:
    risk   = balance * RISK_PCT / 100.0
    pdiff  = abs(entry - sl)
    if pdiff == 0:
        return 0.0
    ticks  = pdiff / 0.00001
    lots   = risk / (ticks * 1.0)
    return max(0.01, min(100.0, round(lots / 0.01) * 0.01))


def check_daily(balance) -> bool:
    global daily_loss, daily_reset_date
    today = datetime.now(timezone.utc).date()
    if daily_reset_date != today:
        daily_reset_date = today
        daily_loss = 0.0
        log.info("Daily loss reset")
    limit = balance * MAX_DAILY / 100.0
    if abs(daily_loss) >= limit:
        log.warning(f"Daily limit hit: ${daily_loss:.2f}")
        return False
    return True


def get_rates(symbol, tf, count):
    if not MT5_OK:
        return None
    r = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if r is None:
        return None
    df = pd.DataFrame(r)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df


def open_trades() -> int:
    if not MT5_OK:
        return 0
    pos = mt5.positions_get(symbol=SYMBOL)
    return sum(1 for p in (pos or []) if p.magic == MAGIC)


def trade(direction, entry, sl, tp, lots):
    if not MT5_OK:
        log.info(f"[SIM] {direction.upper()} {lots} | E:{entry:.5f} SL:{sl:.5f} TP:{tp:.5f}")
        return
    ot = mt5.ORDER_TYPE_BUY if direction == 'bullish' else mt5.ORDER_TYPE_SELL
    tick = mt5.symbol_info_tick(SYMBOL)
    price = tick.ask if direction == 'bullish' else tick.bid
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL, "volume": lots,
        "type": ot, "price": price,
        "sl": sl, "tp": tp,
        "deviation": 10, "magic": MAGIC,
        "comment": "SMSP_Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    r = mt5.order_send(req)
    if r.retcode == mt5.TRADE_RETCODE_DONE:
        log.info(f"✅ {direction.upper()} {lots} @ {price:.5f} SL:{sl:.5f} TP:{tp:.5f}")
    else:
        log.error(f"❌ Trade failed: {r.retcode} {r.comment}")


def manage():
    global daily_loss
    if not MT5_OK:
        return
    pos = mt5.positions_get(symbol=SYMBOL)
    if not pos:
        return
    for p in pos:
        if p.magic != MAGIC:
            continue
        entry = p.price_open
        sl    = p.sl
        tp    = p.tp
        risk  = abs(entry - sl)
        if risk == 0:
            continue
        tick = mt5.symbol_info_tick(SYMBOL)
        cp   = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
        pt   = mt5.symbol_info(SYMBOL).point
        nsl  = sl
        if p.type == mt5.POSITION_TYPE_BUY:
            if cp >= entry + risk and entry + 2*pt > sl:
                nsl = entry + 2*pt
            if cp >= entry + risk*2:
                nsl = max(nsl, cp - risk*0.5)
        else:
            if cp <= entry - risk and entry - 2*pt < sl:
                nsl = entry - 2*pt
            if cp <= entry - risk*2:
                nsl = min(nsl, cp + risk*0.5)
        if nsl != sl:
            mt5.order_send({"action": mt5.TRADE_ACTION_SLTP,
                            "position": p.ticket, "symbol": SYMBOL,
                            "sl": nsl, "tp": tp})
            log.info(f"SL moved to {nsl:.5f}")
        if p.profit < 0:
            daily_loss += p.profit


def main():
    log.info("=== SmartMoneyScalperPro Bot Starting ===")
    log.info(f"Account: {MT5_LOGIN} | Server: {MT5_SERVER}")
    log.info(f"Symbol: {SYMBOL} | Risk: {RISK_PCT}% | MaxDaily: {MAX_DAILY}%")

    if MT5_OK:
        if not mt5.initialize():
            log.error("MT5 init failed")
            return
        ok = mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
        if not ok:
            log.error(f"Login failed: {mt5.last_error()}")
            return
        log.info(f"✅ Connected! Balance: ${mt5.account_info().balance:.2f}")
        balance = mt5.account_info().balance
    else:
        log.info("Simulation mode - balance: $10,000")
        balance = 10000.0

    while True:
        try:
            if MT5_OK and mt5.account_info():
                balance = mt5.account_info().balance

            if not check_daily(balance):
                time.sleep(3600)
                continue

            if SESSION_ONLY and not is_session():
                log.info("Outside session - waiting 5min")
                time.sleep(300)
                continue

            if open_trades() >= MAX_TRADES:
                manage()
                time.sleep(60)
                continue

            manage()

            if MT5_OK:
                m5 = get_rates(SYMBOL, mt5.TIMEFRAME_M5, OB_LOOKBACK + 10)
                h4 = get_rates(SYMBOL, mt5.TIMEFRAME_H4, 250)
            else:
                m5 = h4 = None

            if m5 is None:
                time.sleep(60)
                continue

            trend = get_htf_trend(h4)
            log.info(f"Trend: {trend} | Open: {open_trades()}/{MAX_TRADES}")

            if trend == "neutral":
                time.sleep(60)
                continue

            obs = find_obs(m5)
            if MT5_OK:
                tick = mt5.symbol_info_tick(SYMBOL)
                cp   = tick.ask if trend == 'bullish' else tick.bid
                pt   = mt5.symbol_info(SYMBOL).point
                buf  = SL_PIPS * pt * 10
            else:
                cp  = m5['close'].iloc[-1]
                pt  = 0.00001
                buf = 0.0005

            for ob in reversed(obs):
                if trend == 'bullish' and ob['type'] == 'bullish':
                    if ob['low'] - buf <= cp <= ob['high'] + buf:
                        if has_reversal(m5, 'bullish'):
                            sl = ob['low'] - buf
                            tp = cp + (cp - sl) * MIN_RR
                            ls = lot_size(balance, cp, sl)
                            if ls > 0:
                                log.info(f"🟢 BUY signal at OB {ob['low']:.5f}-{ob['high']:.5f}")
                                trade('bullish', cp, sl, tp, ls)
                                break

                elif trend == 'bearish' and ob['type'] == 'bearish':
                    if ob['low'] - buf <= cp <= ob['high'] + buf:
                        if has_reversal(m5, 'bearish'):
                            sl = ob['high'] + buf
                            tp = cp - (sl - cp) * MIN_RR
                            ls = lot_size(balance, cp, sl)
                            if ls > 0:
                                log.info(f"🔴 SELL signal at OB {ob['low']:.5f}-{ob['high']:.5f}")
                                trade('bearish', cp, sl, tp, ls)
                                break

            time.sleep(60)

        except KeyboardInterrupt:
            log.info("Stopped")
            break
        except Exception as e:
            log.error(f"Error: {e}")
            time.sleep(60)

    if MT5_OK:
        mt5.shutdown()


if __name__ == "__main__":
    main()
