"""日本語ニュースの簡易センチメント／イベント分析。

外部モデルに依存しない語彙ベースの手法。海運・財務ドメインに特化した
キーワード辞書でヘッドラインをスコアリングし、時間減衰で加重平均する。
"""
from __future__ import annotations

import datetime as dt
import math
import re

from . import config
from .news import NewsItem

# --- 極性辞書（キーワード: 重み）-----------------------------------------
# 正: 株価にポジティブに働きやすい材料 / 負: ネガティブに働きやすい材料
POSITIVE = {
    "増配": 2.0, "復配": 2.0, "最高益": 2.5, "過去最高": 2.0, "上方修正": 2.5,
    "自己株式取得": 1.8, "自社株買い": 1.8, "取得結果": 0.8, "消却": 1.2,
    "増益": 1.5, "黒字": 1.2, "受注": 1.0, "長期契約": 1.3, "成約": 1.0,
    "提携": 1.0, "買収": 0.8, "出資参画": 0.8, "子会社化": 0.7, "完全子会社": 0.7,
    "運賃上昇": 2.0, "市況改善": 1.8, "スポット上昇": 1.5, "増額": 1.2,
    "格上げ": 2.0, "選定": 0.6, "受賞": 0.5, "新造船": 0.4, "命名": 0.2,
    "株式分割": 1.5, "増収": 1.0, "回復": 1.0, "堅調": 0.8, "好調": 1.0,
}
NEGATIVE = {
    "減配": -2.5, "無配": -3.0, "下方修正": -2.8, "赤字": -2.0, "減益": -1.8,
    "最終赤字": -2.5, "特別損失": -1.8, "減損": -1.8, "損失計上": -1.6,
    "運賃下落": -2.0, "市況悪化": -2.0, "スポット下落": -1.5, "供給過剰": -1.5,
    "事故": -1.5, "座礁": -1.8, "火災": -1.6, "衝突": -1.5, "沈没": -2.5,
    "海賊": -1.0, "拿捕": -1.5, "攻撃": -1.3, "制裁": -1.5, "違反": -1.6,
    "課徴金": -1.8, "リコール": -1.2, "訴訟": -1.0, "行政処分": -1.6,
    "格下げ": -2.0, "下落": -1.0, "急落": -1.8, "低迷": -1.3, "減速": -1.0,
    "ストライキ": -1.2, "混乱": -0.9, "遅延": -0.6, "懸念": -0.8, "警戒": -0.7,
}

# --- イベント分類（正規表現: ラベル）------------------------------------
EVENT_PATTERNS = [
    (r"(決算|通期|四半期|業績|営業利益|純利益|中間決算)", "決算・業績"),
    (r"(株主総会|定時株主総会|臨時株主総会|議案|招集)", "株主総会"),
    (r"(配当|増配|減配|復配|無配|株主還元|配当予想)", "配当・株主還元"),
    (r"(自己株式|自社株買い|取得状況|消却)", "自己株式取得"),
    (r"(公開買付|TOB|株式取得|買収|子会社化|出資)", "M&A・資本提携"),
    (r"(格付|格上げ|格下げ|見通し|R&I|JCR|ムーディーズ|S&P)", "格付け"),
    (r"(運賃|市況|スポット|用船料|BDI|SCFI|コンテナ運賃)", "海運市況"),
    (r"(脱炭素|アンモニア|LNG燃料|GHG|カーボン|環境|ESG)", "環境・脱炭素"),
    (r"(事故|座礁|火災|衝突|沈没|油濁|海賊|拿捕)", "海難・事故"),
    (r"(制裁|規制|関税|地政学|紅海|ホルムズ|パナマ運河|スエズ)", "地政学・規制"),
    (r"(中期経営計画|経営計画|自己資本|ROE|投資枠)", "経営計画"),
]


def _headline_polarity(text: str) -> tuple[float, list[str]]:
    score = 0.0
    hits: list[str] = []
    for kw, w in POSITIVE.items():
        if kw in text:
            score += w
            hits.append(f"+{kw}")
    for kw, w in NEGATIVE.items():
        if kw in text:
            score += w
            hits.append(f"-{kw}")
    # 打ち消し表現の簡易処理
    if re.search(r"(見送り|中止|撤回|否決)", text):
        score *= -0.5
    return score, hits


def classify_events(items: list[NewsItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for it in items:
        for pat, label in EVENT_PATTERNS:
            if re.search(pat, it.title):
                counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def _weight_for(item: NewsItem) -> float:
    """時間減衰 × ソース信頼度の重み。"""
    try:
        d = dt.date.fromisoformat(item.date)
        age = max((dt.date.today() - d).days, 0)
    except ValueError:
        age = 0
    decay = 0.5 ** (age / config.NEWS_HALF_LIFE_DAYS)
    src = 1.4 if item.source == "公式" else 1.0
    return decay * src


def score_news(items: list[NewsItem]) -> dict:
    """ニュース群のセンチメントを集計する。

    戻り値の sentiment は概ね [-1, 1]。
    """
    if not items:
        return {
            "sentiment": 0.0, "confidence": 0.0, "n_items": 0,
            "n_scored": 0, "weighted_raw": 0.0, "top_positive": [], "top_negative": [],
            "events": {},
        }

    total_w = 0.0
    weighted = 0.0
    scored = []
    for it in items:
        raw, hits = _headline_polarity(it.title)
        w = _weight_for(it)
        total_w += w
        if raw != 0.0:
            weighted += raw * w
            scored.append((raw * w, raw, it, hits))

    weighted_raw = weighted / total_w if total_w else 0.0
    # tanh で圧縮して [-1, 1] へ
    sentiment = math.tanh(weighted_raw / 1.5)
    # 信頼度: スコア付きニュースの本数と重みの厚みから
    n_scored = len(scored)
    confidence = min(1.0, (sum(abs(s) for s, *_ in scored) / 6.0))

    scored.sort(key=lambda x: x[0])
    top_negative = [
        {"title": it.title, "date": it.date, "url": it.url,
         "score": round(raw, 2), "hits": hits}
        for _, raw, it, hits in scored[:5] if raw < 0
    ]
    top_positive = [
        {"title": it.title, "date": it.date, "url": it.url,
         "score": round(raw, 2), "hits": hits}
        for _, raw, it, hits in reversed(scored[-5:]) if raw > 0
    ]

    return {
        "sentiment": round(sentiment, 3),
        "confidence": round(confidence, 3),
        "n_items": len(items),
        "n_scored": n_scored,
        "weighted_raw": round(weighted_raw, 3),
        "top_positive": top_positive,
        "top_negative": top_negative,
        "events": classify_events(items),
    }
