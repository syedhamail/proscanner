"""
Pro Scanner engine — this is the user's original strategy code, unchanged.
Do not modify the logic here; only app.py should change how it's served.
"""
import pandas as pd
import numpy as np
import time


# ------------------ Indicator Functions ------------------
def calculate_ma(data, window):
    return data.rolling(window=window).mean()


def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(data, fast=12, slow=26, signal=9):
    ema_fast = data.ewm(span=fast, adjust=False).mean()
    ema_slow = data.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


# ------------------ Support/Resistance ------------------
def find_support_resistance(df_1h, lookback_hours=48):
    df = df_1h.tail(lookback_hours).copy()
    df['high_shift'] = df['high'].shift(1)
    df['high_shift2'] = df['high'].shift(2)
    df['high_next'] = df['high'].shift(-1)
    df['high_next2'] = df['high'].shift(-2)
    df['low_shift'] = df['low'].shift(1)
    df['low_shift2'] = df['low'].shift(2)
    df['low_next'] = df['low'].shift(-1)
    df['low_next2'] = df['low'].shift(-2)

    swing_high = (df['high'] > df['high_shift']) & (df['high'] > df['high_shift2']) & (df['high'] > df['high_next']) & (df['high'] > df['high_next2'])
    swing_low = (df['low'] < df['low_shift']) & (df['low'] < df['low_shift2']) & (df['low'] < df['low_next']) & (df['low'] < df['low_next2'])

    highs = df[swing_high]['high'].values
    lows = df[swing_low]['low'].values

    def group_levels(levels, threshold_pct=0.005):
        if len(levels) == 0:
            return []
        levels = sorted(levels)
        groups = []
        current_group = [levels[0]]
        for lvl in levels[1:]:
            if (lvl - current_group[-1]) / current_group[-1] < threshold_pct:
                current_group.append(lvl)
            else:
                groups.append(np.mean(current_group))
                current_group = [lvl]
        groups.append(np.mean(current_group))
        return groups

    return group_levels(lows), group_levels(highs)


# ------------------ Candlestick Pattern Detection ------------------
def detect_candlestick_patterns(df_15m):
    patterns = []
    if len(df_15m) < 3:
        return patterns

    c0 = df_15m.iloc[-1]
    c1 = df_15m.iloc[-2]
    c2 = df_15m.iloc[-3]

    def body(o, c):
        return abs(c - o)

    def lower_wick(o, c, l):
        return min(o, c) - l

    def upper_wick(o, c, h):
        return h - max(o, c)

    def is_bullish(o, c):
        return c > o

    def is_bearish(o, c):
        return c < o

    def high_low_range(h, l):
        return h - l

    # ---------- Bullish Patterns ----------
    bod = body(c0['open'], c0['close'])
    low_w = lower_wick(c0['open'], c0['close'], c0['low'])
    up_w = upper_wick(c0['open'], c0['close'], c0['high'])
    if low_w > 2 * bod and up_w < bod * 0.3 and bod > 0:
        patterns.append('Hammer')

    if bod > 0 and up_w < bod * 0.05 and low_w < bod * 0.05 and is_bullish(c0['open'], c0['close']):
        patterns.append('Bullish Marubozu')

    if is_bearish(c1['open'], c1['close']) and is_bullish(c0['open'], c0['close']):
        if c0['open'] < c1['close'] and c0['close'] > c1['open']:
            patterns.append('Bullish Engulfing')

    if is_bearish(c1['open'], c1['close']) and is_bullish(c0['open'], c0['close']):
        if c0['open'] < c1['low'] and c0['close'] > (c1['open'] + c1['close']) / 2:
            patterns.append('Piercing Line')

    if abs(c0['low'] - c1['low']) / c1['low'] < 0.001:
        if is_bearish(c1['open'], c1['close']) and is_bullish(c0['open'], c0['close']):
            patterns.append('Tweezer Bottom')

    if is_bearish(c2['open'], c2['close']) and is_bullish(c0['open'], c0['close']):
        bod_c1 = body(c1['open'], c1['close'])
        bod_c2 = body(c2['open'], c2['close'])
        if bod_c1 < bod_c2 * 0.3 and c1['high'] < c2['close'] and c0['close'] > (c2['open'] + c2['close']) / 2:
            patterns.append('Morning Star')

    if (is_bullish(c2['open'], c2['close']) and is_bullish(c1['open'], c1['close']) and is_bullish(c0['open'], c0['close'])):
        if c1['close'] > c2['close'] and c0['close'] > c1['close']:
            if body(c2['open'], c2['close']) > 0 and body(c1['open'], c1['close']) > 0 and body(c0['open'], c0['close']) > 0:
                patterns.append('Three White Soldiers')

    if len(df_15m) >= 4:
        if is_bearish(c2['open'], c2['close']) and is_bullish(c0['open'], c0['close']):
            bod_c1 = body(c1['open'], c1['close'])
            rng_c1 = high_low_range(c1['high'], c1['low'])
            if rng_c1 > 0 and bod_c1 < 0.1 * rng_c1:
                if c1['low'] > c2['high'] and c0['low'] > c1['high']:
                    patterns.append('Bullish Abandoned Baby')

    # ---------- Bearish Patterns ----------
    bod = body(c0['open'], c0['close'])
    low_w = lower_wick(c0['open'], c0['close'], c0['low'])
    up_w = upper_wick(c0['open'], c0['close'], c0['high'])
    if up_w > 2 * bod and low_w < bod * 0.3 and bod > 0:
        patterns.append('Hanging Man')

    bod = body(c0['open'], c0['close'])
    low_w = lower_wick(c0['open'], c0['close'], c0['low'])
    up_w = upper_wick(c0['open'], c0['close'], c0['high'])
    if up_w > 2 * bod and low_w < bod * 0.3 and bod > 0:
        patterns.append('Shooting Star')

    if bod > 0 and up_w < bod * 0.05 and low_w < bod * 0.05 and is_bearish(c0['open'], c0['close']):
        patterns.append('Bearish Marubozu')

    if is_bullish(c1['open'], c1['close']) and is_bearish(c0['open'], c0['close']):
        if c0['open'] > c1['close'] and c0['close'] < c1['open']:
            patterns.append('Bearish Engulfing')

    if is_bullish(c1['open'], c1['close']) and is_bearish(c0['open'], c0['close']):
        if c0['open'] > c1['close'] and c0['close'] < (c1['open'] + c1['close']) / 2 and c0['close'] > c1['open']:
            patterns.append('Dark Cloud Cover')

    if abs(c0['high'] - c1['high']) / c1['high'] < 0.001:
        if is_bullish(c1['open'], c1['close']) and is_bearish(c0['open'], c0['close']):
            patterns.append('Tweezer Top')

    if is_bullish(c2['open'], c2['close']) and is_bearish(c0['open'], c0['close']):
        bod_c1 = body(c1['open'], c1['close'])
        bod_c2 = body(c2['open'], c2['close'])
        if bod_c1 < bod_c2 * 0.3 and c1['low'] > c2['close'] and c0['close'] < (c2['open'] + c2['close']) / 2:
            patterns.append('Evening Star')

    if (is_bearish(c2['open'], c2['close']) and is_bearish(c1['open'], c1['close']) and is_bearish(c0['open'], c0['close'])):
        if c1['close'] < c2['close'] and c0['close'] < c1['close']:
            if body(c2['open'], c2['close']) > 0 and body(c1['open'], c1['close']) > 0 and body(c0['open'], c0['close']) > 0:
                patterns.append('Three Black Crows')

    if len(df_15m) >= 4:
        if is_bullish(c2['open'], c2['close']) and is_bearish(c0['open'], c0['close']):
            bod_c1 = body(c1['open'], c1['close'])
            rng_c1 = high_low_range(c1['high'], c1['low'])
            if rng_c1 > 0 and bod_c1 < 0.1 * rng_c1:
                if c1['high'] < c2['low'] and c0['high'] < c1['low']:
                    patterns.append('Bearish Abandoned Baby')

    return patterns


# ------------------ Chart Pattern Detection ------------------
def detect_chart_patterns(df_1h):
    patterns = []
    if len(df_1h) < 30:
        return patterns

    df = df_1h.copy()
    df['high_shift'] = df['high'].shift(1)
    df['high_shift2'] = df['high'].shift(2)
    df['high_next'] = df['high'].shift(-1)
    df['high_next2'] = df['high'].shift(-2)
    df['low_shift'] = df['low'].shift(1)
    df['low_shift2'] = df['low'].shift(2)
    df['low_next'] = df['low'].shift(-1)
    df['low_next2'] = df['low'].shift(-2)

    swing_high = (df['high'] > df['high_shift']) & (df['high'] > df['high_shift2']) & (df['high'] > df['high_next']) & (df['high'] > df['high_next2'])
    swing_low = (df['low'] < df['low_shift']) & (df['low'] < df['low_shift2']) & (df['low'] < df['low_next']) & (df['low'] < df['low_next2'])

    highs_idx = df.index[swing_high].tolist()
    lows_idx = df.index[swing_low].tolist()
    high_vals = df.loc[swing_high, 'high'].values
    low_vals = df.loc[swing_low, 'low'].values

    if len(high_vals) < 5 or len(low_vals) < 5:
        return patterns

    high_vals = list(high_vals)
    low_vals = list(low_vals)
    high_indices = list(highs_idx)
    low_indices = list(lows_idx)
    current_price = df['close'].iloc[-1]

    recent_high = df['high'].tail(10).max()
    recent_low = df['low'].tail(10).min()
    if current_price > recent_high * 1.002:
        patterns.append('Breakout (Bullish)')
    elif current_price < recent_low * 0.998:
        patterns.append('Breakout (Bearish)')

    if len(low_vals) >= 3:
        if abs(low_vals[-1] - low_vals[-2]) / low_vals[-2] < 0.01:
            between_highs = [h for h in high_indices if low_indices[-2] < h < low_indices[-1]]
            if len(between_highs) > 0:
                patterns.append('Double Bottom (Bullish)')

    if len(high_vals) >= 3:
        if abs(high_vals[-1] - high_vals[-2]) / high_vals[-2] < 0.01:
            between_lows = [l for l in low_indices if high_indices[-2] < l < high_indices[-1]]
            if len(between_lows) > 0:
                patterns.append('Double Top (Bearish)')

    if len(high_vals) >= 3:
        h3 = high_vals[-3:]
        if h3[1] > h3[0] and h3[1] > h3[2]:
            if abs(h3[0] - h3[2]) / h3[0] < 0.02:
                patterns.append('Head and Shoulder (Bearish)')

    if len(low_vals) >= 3:
        l3 = low_vals[-3:]
        if l3[1] < l3[0] and l3[1] < l3[2]:
            if abs(l3[0] - l3[2]) / l3[0] < 0.02:
                patterns.append('Inverse Head and Shoulder (Bullish)')

    return patterns


# ------------------ Main Analysis Engine ------------------
def analyze_symbol(symbol, exchange, timeframes, mode='indicators', entry_type='strict'):
    try:
        ohlcv_4h = exchange.fetch_ohlcv(symbol, timeframe='4h', limit=timeframes['4h'])
        ohlcv_1h = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=timeframes['1h'])
        ohlcv_15m = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=timeframes['15m'])

        df_4h = pd.DataFrame(ohlcv_4h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_1h = pd.DataFrame(ohlcv_1h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_15m = pd.DataFrame(ohlcv_15m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        # 1. Trend (4H)
        df_4h['MA20'] = calculate_ma(df_4h['close'], 20)
        df_4h['MA50'] = calculate_ma(df_4h['close'], 50)
        ma20_4h = df_4h['MA20'].iloc[-1]
        ma50_4h = df_4h['MA50'].iloc[-1]
        trend_bullish = ma20_4h > ma50_4h

        # 2. Entry Indicators (15M)
        df_15m['MA20'] = calculate_ma(df_15m['close'], 20)
        df_15m['RSI'] = calculate_rsi(df_15m['close'], 14)
        df_15m['MACD'], df_15m['Signal'] = calculate_macd(df_15m['close'])

        close_15m = df_15m['close'].iloc[-1]
        ma20_15m = df_15m['MA20'].iloc[-1]
        rsi_15m = df_15m['RSI'].iloc[-1]
        macd_15m = df_15m['MACD'].iloc[-1]
        signal_15m = df_15m['Signal'].iloc[-1]

        if len(df_15m) > 1:
            rsi_prev = df_15m['RSI'].iloc[-2]
            macd_prev = df_15m['MACD'].iloc[-2]
            signal_prev = df_15m['Signal'].iloc[-2]
        else:
            rsi_prev = rsi_15m
            macd_prev = macd_15m
            signal_prev = signal_15m

        # ----- ENTRY LOGIC (Strict vs Relaxed) -----
        if entry_type == 'strict':
            long_ind = (close_15m > ma20_15m) and (rsi_prev <= 30 and rsi_15m > 30) and (macd_prev <= signal_prev and macd_15m > signal_15m)
            short_ind = (close_15m < ma20_15m) and (rsi_prev >= 70 and rsi_15m < 70) and (macd_prev >= signal_prev and macd_15m < signal_15m)
        else:  # relaxed
            long_ind = (close_15m > ma20_15m) and (rsi_15m > 30) and (macd_15m > signal_15m)
            short_ind = (close_15m < ma20_15m) and (rsi_15m < 70) and (macd_15m < signal_15m)

        long_entry = False
        short_entry = False
        pattern_name = ''
        chart_patterns = []

        if mode == 'indicators':
            long_entry = long_ind
            short_entry = short_ind
        else:  # Full (Indicators + Candles + Chart Patterns)
            patterns = detect_candlestick_patterns(df_15m)
            bullish_candles = ['Hammer', 'Bullish Marubozu', 'Bullish Engulfing', 'Piercing Line', 'Tweezer Bottom',
                               'Morning Star', 'Three White Soldiers', 'Bullish Abandoned Baby']
            bearish_candles = ['Hanging Man', 'Shooting Star', 'Bearish Marubozu', 'Bearish Engulfing', 'Dark Cloud Cover',
                               'Tweezer Top', 'Evening Star', 'Three Black Crows', 'Bearish Abandoned Baby']

            has_bullish_candle = any(p in patterns for p in bullish_candles)
            has_bearish_candle = any(p in patterns for p in bearish_candles)

            chart_patterns = detect_chart_patterns(df_1h)
            bullish_charts = ['Double Bottom (Bullish)', 'Inverse Head and Shoulder (Bullish)', 'Breakout (Bullish)']
            bearish_charts = ['Double Top (Bearish)', 'Head and Shoulder (Bearish)', 'Breakout (Bearish)']
            has_bullish_chart = any(p in chart_patterns for p in bullish_charts)
            has_bearish_chart = any(p in chart_patterns for p in bearish_charts)

            if long_ind and (has_bullish_candle or has_bullish_chart):
                long_entry = True
                pattern_name = ', '.join([p for p in patterns if p in bullish_candles])
                if has_bullish_chart:
                    chart_str = ', '.join([p for p in chart_patterns if p in bullish_charts])
                    pattern_name = pattern_name + ' | Chart: ' + chart_str if pattern_name else 'Chart: ' + chart_str
            elif short_ind and (has_bearish_candle or has_bearish_chart):
                short_entry = True
                pattern_name = ', '.join([p for p in patterns if p in bearish_candles])
                if has_bearish_chart:
                    chart_str = ', '.join([p for p in chart_patterns if p in bearish_charts])
                    pattern_name = pattern_name + ' | Chart: ' + chart_str if pattern_name else 'Chart: ' + chart_str

        if not (long_entry or short_entry):
            return None

        # 3. Support / Resistance (1H)
        support_levels, resistance_levels = find_support_resistance(df_1h, 48)
        current_price = close_15m

        nearest_res = min([r for r in resistance_levels if r > current_price], default=current_price * 1.02)
        nearest_sup = max([s for s in support_levels if s < current_price], default=current_price * 0.98)

        if long_entry:
            entry_type_signal = 'LONG'
            take_profit = nearest_res
            stop_loss = nearest_sup
            conf = min(100, max(0, ((rsi_15m - 30) / 30) * 50 + ((macd_15m - signal_15m) / abs(signal_15m) if signal_15m != 0 else 0) * 50))
        else:
            entry_type_signal = 'SHORT'
            take_profit = nearest_sup
            stop_loss = nearest_res
            conf = min(100, max(0, ((70 - rsi_15m) / 30) * 50 + ((signal_15m - macd_15m) / abs(signal_15m) if signal_15m != 0 else 0) * 50))

        # =====================================================================
        # TREND FILTER REMOVED - Ab trend ki koi majboori nahi.
        # LONG ya SHORT dono aa sakte hain, chahe trend kuch bhi ho.
        # =====================================================================

        # ================== CONFIDENCE FILTER (>= 90%) ==================
        if conf < 90:
            return None
        # ===================================================================

        chart_detected = ', '.join(chart_patterns) if chart_patterns else ''

        return {
            'symbol': symbol.replace('/USDT', ''),
            'trend': 'Bullish' if trend_bullish else 'Bearish',
            'signal': entry_type_signal,
            'price': round(current_price, 6),
            'stop_loss': round(stop_loss, 6),
            'take_profit': round(take_profit, 6),
            'leverage': '3x',
            'confidence': round(conf, 1),
            'pattern': pattern_name,
            'chart_pattern': chart_detected
        }
    except Exception:
        return None


def run_scan(limit=50, mode='indicators', entry_type='strict'):
    import ccxt
    exchange = ccxt.binance({
        'rateLimit': 1200,
        'enableRateLimit': True,
    })

    markets = exchange.load_markets()
    symbols = [s for s in markets if s.endswith('/USDT') and markets[s]['active']]

    tickers = exchange.fetch_tickers(symbols[:200])
    sorted_syms = sorted(tickers.keys(), key=lambda s: tickers[s].get('quoteVolume', 0) if tickers[s] else 0, reverse=True)
    top_symbols = sorted_syms[:limit]

    results = []
    timeframes = {'4h': 60, '1h': 60, '15m': 60}

    for sym in top_symbols:
        res = analyze_symbol(sym, exchange, timeframes, mode, entry_type)
        if res:
            results.append(res)
        time.sleep(0.3)

    return results
