import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import time

# === CONFIGURATION ===
SYMBOL = "EURUSD"
TIMEFRAME = mt5.TIMEFRAME_M15
RSI_PERIOD = 14
WINDOW = 20
RISK_REWARD_RATIO = 2
LOT_SIZE = 0.1
MAGIC_NUMBER = 123456
DEVIATION = 20

# === INIT ===
if not mt5.initialize():
    raise RuntimeError("MT5 initialization failed")

def get_data(symbol, timeframe, bars=500):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def detect_divergences(df):
    df['RSI'] = calculate_rsi(df['close'], RSI_PERIOD)

    df['Bullish_Div'] = False
    df['Bearish_Div'] = False

    for i in range(WINDOW, len(df) - 1):
        price_low1 = df['close'].iloc[i - WINDOW:i].idxmin()
        price_low2 = df['close'].iloc[i - WINDOW + 1:i + 1].idxmin()

        rsi_low1 = df['RSI'].loc[price_low1]
        rsi_low2 = df['RSI'].loc[price_low2]

        if df['close'].loc[price_low2] < df['close'].loc[price_low1] and rsi_low2 > rsi_low1:
            df.at[df.index[i], 'Bullish_Div'] = True

        price_high1 = df['close'].iloc[i - WINDOW:i].idxmax()
        price_high2 = df['close'].iloc[i - WINDOW + 1:i + 1].idxmax()

        rsi_high1 = df['RSI'].loc[price_high1]
        rsi_high2 = df['RSI'].loc[price_high2]

        if df['close'].loc[price_high2] > df['close'].loc[price_high1] and rsi_high2 < rsi_high1:
            df.at[df.index[i], 'Bearish_Div'] = True

    return df

def place_trade(action, price, sl, tp):
    order_type = mt5.ORDER_TYPE_BUY if action == "buy" else mt5.ORDER_TYPE_SELL
    sl = round(sl, 5)
    tp = round(tp, 5)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOT_SIZE,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": DEVIATION,
        "magic": MAGIC_NUMBER,
        "comment": "RSI Divergence",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print("Trade failed:", result)
    else:
        print(f"{action.upper()} ORDER placed at {price}, SL: {sl}, TP: {tp}")

def run_strategy():
    df = get_data(SYMBOL, TIMEFRAME)
    df = detect_divergences(df)

    last = df.iloc[-1]
    previous = df.iloc[-2]

    price = last['close']

    if last['Bullish_Div']:
        sl = df['low'][-WINDOW:].min()
        tp = price + (price - sl) * RISK_REWARD_RATIO
        place_trade("buy", price, sl, tp)

    elif last['Bearish_Div']:
        sl = df['high'][-WINDOW:].max()
        tp = price - (sl - price) * RISK_REWARD_RATIO
        place_trade("sell", price, sl, tp)

# === MAIN LOOP ===
while True:
    run_strategy()
    time.sleep(60)  # Check every 1 minute
