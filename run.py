"""エントリポイント: データ収集 → 分析 → 予測 → レポート生成。

使い方:
    .venv\\Scripts\\python.exe run.py            # レポート生成
    .venv\\Scripts\\python.exe run.py --open     # 生成後に既定ブラウザで開く
    .venv\\Scripts\\python.exe run.py --quiet    # ログ最小
"""
from __future__ import annotations

import argparse
import logging
import sys
import webbrowser

# UTF-8 出力を強制（Windows コンソール対策）
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from nyk_predictor import config
from nyk_predictor import prices as prices_mod
from nyk_predictor import news as news_mod
from nyk_predictor import sentiment as sentiment_mod
from nyk_predictor import forecast as forecast_mod
from nyk_predictor import report as report_mod

log = logging.getLogger("nyk")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="日本郵船 株価予測レポート生成")
    ap.add_argument("--open", action="store_true", help="生成後にレポートを開く")
    ap.add_argument("--quiet", action="store_true", help="ログ最小化")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("株価データ取得中: %s", config.TICKER)
    prices = prices_mod.fetch_prices()
    log.info("  %d 営業日ぶんを取得（%s 〜 %s）",
             len(prices), prices.index[0].date(), prices.index[-1].date())

    technical = prices_mod.technical_snapshot(prices)
    log.info("テクニカル: 終値 %.0f 円 / RSI %.0f",
             technical["close"], technical["rsi14"] or 0)

    try:
        news_items = news_mod.collect_news()
        log.info("ニュース %d 件取得", len(news_items))
    except Exception as e:  # ニュース取得失敗でも予測は継続
        log.warning("ニュース取得に失敗: %s", e)
        news_items = []

    news_score = sentiment_mod.score_news(news_items)
    log.info("センチメント %.2f（信頼度 %.2f, スコア付与 %d 件）",
             news_score["sentiment"], news_score["confidence"], news_score["n_scored"])

    forecast = forecast_mod.build_forecast(prices, news_score, technical)
    log.info("予測ドリフト（年率）%.2f%% / ボラ %.1f%%",
             forecast["total_drift_annualized_pct"], forecast["annualized_vol_pct"])

    out = report_mod.write_reports(prices, technical, news_items, news_score, forecast)

    print("\n" + out["text"] + "\n")
    print("HTML レポート: " + out["latest_html"])

    if args.open:
        webbrowser.open(out["latest_html"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
