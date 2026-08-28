"""株価データの取得とテクニカル指標。"""
from __future__ import annotations

import pandas as pd
import numpy as np
import yfinance as yf

from . import config


def fetch_prices() -> pd.DataFrame:
    """日次OHLCVを取得して DataFrame を返す（欠損日除去、キャッシュ保存）。"""
    df = yf.download(
        config.TICKER,
        period=config.PRICE_HISTORY_PERIOD,
        interval=config.PRICE_INTERVAL,
        auto_adjust=True,
        progress=False,
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    df = df.dropna(subset=["close"]).copy()
    df.index = pd.to_datetime(df.index)
    df.to_csv(config.DATA_DIR / "prices.csv")
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """代表的なテクニカル指標を列として追加する。"""
    out = df.copy()
    close = out["close"]

    out["sma25"] = close.rolling(25).mean()
    out["sma75"] = close.rolling(75).mean()
    out["ema12"] = close.ewm(span=12, adjust=False).mean()
    out["ema26"] = close.ewm(span=26, adjust=False).mean()
    out["macd"] = out["ema12"] - out["ema26"]
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    out["rsi14"] = 100 - 100 / (1 + rs)

    mid = close.rolling(20).mean()
    sd = close.rolling(20).std()
    out["bb_upper"] = mid + 2 * sd
    out["bb_lower"] = mid - 2 * sd

    out["logret"] = np.log(close / close.shift(1))
    out["hv20"] = out["logret"].rolling(20).std() * np.sqrt(config.TRADING_DAYS_PER_YEAR)
    return out


def technical_snapshot(df: pd.DataFrame) -> dict:
    """最新のテクニカル状況を要約した dict を返す。"""
    ind = add_indicators(df)
    last = ind.iloc[-1]
    prev = ind.iloc[-2]

    def trend(v_now, v_ref):
        if pd.isna(v_now) or pd.isna(v_ref):
            return "不明"
        return "上" if v_now > v_ref else "下"

    signals = []
    if not pd.isna(last["sma25"]) and not pd.isna(last["sma75"]):
        if last["sma25"] > last["sma75"] and prev["sma25"] <= prev["sma75"]:
            signals.append("ゴールデンクロス（25日線が75日線を上抜け）")
        elif last["sma25"] < last["sma75"] and prev["sma25"] >= prev["sma75"]:
            signals.append("デッドクロス（25日線が75日線を下抜け）")
        elif last["sma25"] > last["sma75"]:
            signals.append("中期上昇トレンド（25日線 > 75日線）")
        else:
            signals.append("中期下降トレンド（25日線 < 75日線）")

    if not pd.isna(last["rsi14"]):
        if last["rsi14"] >= 70:
            signals.append(f"RSI {last['rsi14']:.0f}：買われすぎ圏")
        elif last["rsi14"] <= 30:
            signals.append(f"RSI {last['rsi14']:.0f}：売られすぎ圏")

    if not pd.isna(last["macd"]) and not pd.isna(last["macd_signal"]):
        if last["macd"] > last["macd_signal"] and prev["macd"] <= prev["macd_signal"]:
            signals.append("MACD が買いシグナル転換")
        elif last["macd"] < last["macd_signal"] and prev["macd"] >= prev["macd_signal"]:
            signals.append("MACD が売りシグナル転換")

    return {
        "date": ind.index[-1].date().isoformat(),
        "close": float(last["close"]),
        "prev_close": float(prev["close"]),
        "change_pct": float((last["close"] / prev["close"] - 1) * 100),
        "sma25": _f(last["sma25"]),
        "sma75": _f(last["sma75"]),
        "rsi14": _f(last["rsi14"]),
        "macd": _f(last["macd"]),
        "macd_signal": _f(last["macd_signal"]),
        "hv20": _f(last["hv20"]),
        "sma25_dir": trend(last["sma25"], prev["sma25"]),
        "signals": signals,
    }


def _f(x):
    return None if pd.isna(x) else float(x)
