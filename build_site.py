"""Netlify 用ビルドスクリプト。

データ収集 → 分析 → 予測を実行し、静的サイトを public/ に生成する。
Netlify のビルドコマンドから呼ばれる:

    pip install -r requirements.txt && python build_site.py

生成物:
    public/index.html   予測レポート
    public/chart.png     チャート
    public/forecast.json 予測データ（API 的に利用可）
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from nyk_predictor import config
from nyk_predictor import prices as prices_mod
from nyk_predictor import news as news_mod
from nyk_predictor import sentiment as sentiment_mod
from nyk_predictor import forecast as forecast_mod
from nyk_predictor import report as report_mod

DEST = Path(__file__).resolve().parent / "public"


def main() -> int:
    print(f"[build] 株価取得: {config.TICKER}")
    prices = prices_mod.fetch_prices()
    print(f"[build]   {len(prices)} 営業日  ({prices.index[0].date()} .. {prices.index[-1].date()})")

    technical = prices_mod.technical_snapshot(prices)

    try:
        news_items = news_mod.collect_news()
        print(f"[build] ニュース {len(news_items)} 件")
    except Exception as e:
        print(f"[build] ニュース取得失敗（継続）: {e}")
        news_items = []

    news_score = sentiment_mod.score_news(news_items)
    print(f"[build] センチメント {news_score['sentiment']:+.2f} "
          f"(信頼度 {news_score['confidence']:.2f})")

    forecast = forecast_mod.build_forecast(prices, news_score, technical)
    print(f"[build] 年率ドリフト {forecast['total_drift_annualized_pct']}% / "
          f"ボラ {forecast['annualized_vol_pct']}%")

    out = report_mod.render_site(prices, technical, news_items, news_score, forecast, DEST)
    print(f"[build] 生成完了: {out}")
    for name, h in forecast["horizons"].items():
        print(f"[build]   {name}: 中央値 {h['median']:,.0f}円  上昇確率 {h['prob_up']*100:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
