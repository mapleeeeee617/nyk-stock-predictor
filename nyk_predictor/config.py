"""設定値。"""
from __future__ import annotations

from pathlib import Path

# --- 対象銘柄 -----------------------------------------------------------------
TICKER = "9101.T"          # 日本郵船（東証プライム）
COMPANY_JP = "日本郵船"
COMPANY_EN = "Nippon Yusen Kabushiki Kaisha (NYK Line)"

# --- パス -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# --- 価格データ -------------------------------------------------------------
PRICE_HISTORY_PERIOD = "3y"       # yfinance 取得期間
PRICE_INTERVAL = "1d"

# --- ニュース取得 ---------------------------------------------------------
# 公式プレスリリース一覧（年別）
NYK_NEWS_URL_TEMPLATE = "https://www.nyk.com/news/{year}/"
# Google ニュース RSS（日本語）
GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?"
    "q=%E6%97%A5%E6%9C%AC%E9%83%B5%E8%88%B9%20OR%20NYK%E3%83%A9%E3%82%A4%E3%83%B3"
    "&hl=ja&gl=JP&ceid=JP:ja"
)
NEWS_LOOKBACK_DAYS = 45           # 何日前までのニュースをスコアリングに使うか
NEWS_HALF_LIFE_DAYS = 10.0        # ニュースの時間減衰の半減期

HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; nyk-stock-predictor/0.1)"}
HTTP_TIMEOUT = 25

# --- 予測ホライズン（営業日）----------------------------------------------
HORIZONS = {
    "1週間": 5,
    "1ヶ月": 21,
    "3ヶ月": 63,
}

# --- モデルパラメータ -----------------------------------------------------
VOL_WINDOW = 60                   # ヒストリカル・ボラティリティ推定に使う営業日数
TREND_WINDOW = 40                 # 直近トレンド推定に使う営業日数
TREND_DAMPING = 0.20             # 直近トレンドを将来ドリフトへ反映する減衰率
ARIMA_WEIGHT = 0.35              # ドリフト合成での ARIMA 示唆の比重
SENTIMENT_DRIFT_SCALE = 0.15     # センチメント ±1 → 年率ドリフト ±15%
MEANREV_SCALE = 0.12            # RSI 乖離（±1）→ 年率ドリフト補正 ∓12%
MAX_ANNUAL_DRIFT = 0.20          # 年率ドリフトの上下限（暴走防止）
MC_PATHS = 20000                 # モンテカルロのパス数
TRADING_DAYS_PER_YEAR = 245
RANDOM_SEED = 20260829
