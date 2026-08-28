"""簡易バックテスト: 過去の各時点で本モデルの予測を再構成し、
実現値と比較して方向的中率・誤差を評価する。

ニュース・センチメントは過去分を遡って取得できないため、
バックテストでは news_score を中立（0）として価格モデル部分のみを検証する。
つまり「テクニカル + トレンド + 平均回帰 + ARIMA」の素の実力の目安。

使い方:
    .venv\\Scripts\\python.exe backtest.py
    .venv\\Scripts\\python.exe backtest.py --step 5 --start 250
"""
from __future__ import annotations

import argparse
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd

from nyk_predictor import config
from nyk_predictor import prices as prices_mod
from nyk_predictor import forecast as forecast_mod

NEUTRAL_NEWS = {"sentiment": 0.0, "confidence": 0.0}


def run(step: int, start: int) -> None:
    df = prices_mod.fetch_prices()
    ind = prices_mod.add_indicators(df)
    close = df["close"].dropna()
    n = len(close)
    max_h = max(config.HORIZONS.values())

    results = {name: {"hit": 0, "tot": 0, "ape": [], "cover": 0}
               for name in config.HORIZONS}

    for i in range(start, n - max_h, step):
        hist = df.iloc[: i + 1]
        rsi = ind["rsi14"].iloc[i]
        tech = {"rsi14": None if pd.isna(rsi) else float(rsi)}
        try:
            fc = forecast_mod.build_forecast(hist, NEUTRAL_NEWS, tech)
        except Exception:
            continue
        spot = fc["spot"]
        for name, d in config.HORIZONS.items():
            realized = float(close.iloc[i + d])
            h = fc["horizons"][name]
            pred_dir = h["median"] >= spot
            real_dir = realized >= spot
            results[name]["tot"] += 1
            results[name]["hit"] += int(pred_dir == real_dir)
            results[name]["ape"].append(abs(h["median"] / realized - 1))
            if h["p10"] <= realized <= h["p90"]:
                results[name]["cover"] += 1

    print(f"\n{config.COMPANY_JP}（{config.TICKER}） バックテスト  "
          f"サンプル区間 idx {start}..{n - max_h}  step {step}")
    print("-" * 68)
    print(f"{'ホライズン':<10}{'試行':>6}{'方向的中率':>12}{'中央値MAPE':>12}{'80%帯カバー率':>14}")
    for name, r in results.items():
        if r["tot"] == 0:
            continue
        acc = r["hit"] / r["tot"] * 100
        mape = float(np.mean(r["ape"])) * 100
        cov = r["cover"] / r["tot"] * 100
        print(f"{name:<10}{r['tot']:>6}{acc:>11.1f}%{mape:>11.1f}%{cov:>13.1f}%")
    print("-" * 68)
    print("方向的中率 50% = コイン投げ相当。80%帯カバー率は理想 80%。")
    print("※ニュース補正なしの価格モデル単体の評価です。")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=int, default=5, help="評価間隔（営業日）")
    ap.add_argument("--start", type=int, default=250, help="評価開始インデックス")
    a = ap.parse_args()
    run(a.step, a.start)
