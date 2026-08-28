"""統計モデルによる株価予測。

構成:
  1. ヒストリカル・ボラティリティ（EWMA）
  2. ベースライン・ドリフト = 減衰させた直近トレンド + ARIMA 示唆
  3. ニュース・センチメントによるドリフト補正
  4. 幾何ブラウン運動（GBM）モンテカルロで各ホライズンの分布を生成
  5. 参考として ARIMA の点予測も併記
"""
from __future__ import annotations

import os
import warnings

import numpy as np
import pandas as pd

from . import config

warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")


def _annualized_vol(logret: pd.Series) -> float:
    r = logret.dropna().tail(config.VOL_WINDOW)
    if len(r) < 10:
        return 0.30
    # EWMA 分散
    ew = r.ewm(span=config.VOL_WINDOW, adjust=False).std().iloc[-1]
    daily = float(ew) if np.isfinite(ew) else float(r.std())
    return daily * np.sqrt(config.TRADING_DAYS_PER_YEAR)


def _recent_trend_annualized(close: pd.Series) -> float:
    y = np.log(close.tail(config.TREND_WINDOW).values)
    if len(y) < 5:
        return 0.0
    x = np.arange(len(y))
    slope = np.polyfit(x, y, 1)[0]          # 1営業日あたりの対数リターン
    return float(slope * config.TRADING_DAYS_PER_YEAR)


def _arima_view(close: pd.Series, max_days: int) -> dict | None:
    try:
        from statsmodels.tsa.arima.model import ARIMA
    except Exception:
        return None
    y = np.log(close.tail(400).values)
    try:
        res = ARIMA(y, order=(1, 1, 1)).fit()
        fc = res.get_forecast(steps=max_days)
        mean = np.exp(fc.predicted_mean)
        ci = np.exp(fc.conf_int(alpha=0.2))
        ann_drift = float((np.log(mean[-1]) - y[-1]) / max_days * config.TRADING_DAYS_PER_YEAR)
        return {
            "mean": mean,
            "low": ci[:, 0],
            "high": ci[:, 1],
            "ann_drift": ann_drift,
        }
    except Exception:
        return None


def _clip(x: float, lim: float) -> float:
    return max(-lim, min(lim, x))


def build_forecast(prices: pd.DataFrame, news_score: dict,
                   technical: dict | None = None) -> dict:
    close = prices["close"].dropna()
    logret = np.log(close / close.shift(1))
    spot = float(close.iloc[-1])

    vol = _annualized_vol(logret)
    trend_ann = _recent_trend_annualized(close)
    max_days = max(config.HORIZONS.values())
    arima = _arima_view(close, max_days)

    # --- ドリフト合成 ---------------------------------------------------
    # 直近トレンドは強く減衰させたうえで ARIMA 示唆とブレンド
    baseline = config.TREND_DAMPING * trend_ann
    if arima:
        w = config.ARIMA_WEIGHT
        baseline = (1 - w) * baseline + w * _clip(arima["ann_drift"], config.MAX_ANNUAL_DRIFT)

    # 平均回帰: RSI が極端なら逆向きに補正（買われすぎ→弱気方向）
    meanrev_drift = 0.0
    rsi = (technical or {}).get("rsi14")
    if rsi is not None:
        meanrev_drift = -((rsi - 50.0) / 50.0) * config.MEANREV_SCALE

    sent = float(news_score.get("sentiment", 0.0))
    conf = float(news_score.get("confidence", 0.0))
    sentiment_drift = sent * conf * config.SENTIMENT_DRIFT_SCALE

    mu_ann = _clip(baseline + sentiment_drift + meanrev_drift, config.MAX_ANNUAL_DRIFT)
    dt_ = 1.0 / config.TRADING_DAYS_PER_YEAR
    mu_daily = mu_ann * dt_
    sig_daily = vol * np.sqrt(dt_)

    # --- モンテカルロ GBM ---------------------------------------------
    rng = np.random.default_rng(config.RANDOM_SEED)
    n = config.MC_PATHS
    shocks = rng.standard_normal((n, max_days))
    incr = (mu_daily - 0.5 * sig_daily**2) + sig_daily * shocks
    logpath = np.cumsum(incr, axis=1)
    pricepath = spot * np.exp(logpath)

    horizons = {}
    for name, d in config.HORIZONS.items():
        col = pricepath[:, d - 1]
        p10, p25, p50, p75, p90 = np.percentile(col, [10, 25, 50, 75, 90])
        prob_up = float((col > spot).mean())
        exp_ret = float(np.mean(col) / spot - 1)
        entry = {
            "days": d,
            "expected": round(float(np.mean(col)), 1),
            "median": round(float(p50), 1),
            "p10": round(float(p10), 1),
            "p25": round(float(p25), 1),
            "p75": round(float(p75), 1),
            "p90": round(float(p90), 1),
            "prob_up": round(prob_up, 3),
            "expected_return_pct": round(exp_ret * 100, 2),
            "band_low_pct": round((p10 / spot - 1) * 100, 1),
            "band_high_pct": round((p90 / spot - 1) * 100, 1),
        }
        if arima:
            entry["arima_point"] = round(float(arima["mean"][d - 1]), 1)
        horizons[name] = entry

    # 予測コーン（作図用の中央値パス・帯）
    cone_days = list(range(1, max_days + 1))
    cone = {
        "days": cone_days,
        "median": [round(float(x), 1) for x in np.percentile(pricepath, 50, axis=0)],
        "p10": [round(float(x), 1) for x in np.percentile(pricepath, 10, axis=0)],
        "p90": [round(float(x), 1) for x in np.percentile(pricepath, 90, axis=0)],
    }

    return {
        "spot": round(spot, 1),
        "as_of": close.index[-1].date().isoformat(),
        "annualized_vol_pct": round(vol * 100, 1),
        "recent_trend_annualized_pct": round(trend_ann * 100, 1),
        "baseline_drift_pct": round(baseline * 100, 2),
        "sentiment_drift_pct": round(sentiment_drift * 100, 2),
        "meanrev_drift_pct": round(meanrev_drift * 100, 2),
        "total_drift_annualized_pct": round(mu_ann * 100, 2),
        "arima_available": arima is not None,
        "horizons": horizons,
        "cone": cone,
    }
