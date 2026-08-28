"""レポート生成（PNG チャート + HTML + JSON + テキスト要約）。"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from jinja2 import Template

from . import config

DISCLAIMER = (
    "本レポートは公開情報に基づく統計的推計であり、投資助言・売買推奨ではありません。"
    "将来の株価を保証するものではなく、実際の値動きは予測から大きく乖離し得ます。"
    "投資判断は必ずご自身の責任で行ってください。"
)


def make_chart(prices: pd.DataFrame, forecast: dict, path: Path) -> None:
    from .prices import add_indicators

    ind = add_indicators(prices).tail(180)
    last_date = ind.index[-1]
    future_dates = pd.bdate_range(last_date, periods=len(forecast["cone"]["days"]) + 1)[1:]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11, 7), gridspec_kw={"height_ratios": [3, 1]}, sharex=False
    )

    ax1.plot(ind.index, ind["close"], color="#1f3b73", lw=1.6, label="終値")
    ax1.plot(ind.index, ind["sma25"], color="#e08a00", lw=1.0, label="25日移動平均")
    ax1.plot(ind.index, ind["sma75"], color="#8a8a8a", lw=1.0, label="75日移動平均")

    cone = forecast["cone"]
    ax1.plot(future_dates, cone["median"], color="#c0392b", lw=1.6, ls="--", label="予測中央値")
    ax1.fill_between(future_dates, cone["p10"], cone["p90"], color="#c0392b", alpha=0.12,
                     label="予測レンジ(10–90%)")
    ax1.axvline(last_date, color="#999", lw=0.8, ls=":")
    ax1.set_title(f"{config.COMPANY_JP}（{config.TICKER}）  株価と予測  基準日 {forecast['as_of']}")
    ax1.set_ylabel("株価（円）")
    ax1.legend(loc="upper left", fontsize=8, ncol=2)
    ax1.grid(alpha=0.25)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    ax2.plot(ind.index, ind["rsi14"], color="#2c7", lw=1.0)
    ax2.axhline(70, color="#c0392b", lw=0.7, ls="--")
    ax2.axhline(30, color="#1f3b73", lw=0.7, ls="--")
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("RSI(14)")
    ax2.grid(alpha=0.25)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


HTML_TEMPLATE = Template("""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ company }} 株価予測レポート {{ generated }}</title>
<style>
 body{font-family:"Segoe UI","Hiragino Kaku Gothic ProN",Meiryo,sans-serif;margin:0;background:#f4f5f7;color:#1c1c1c}
 .wrap{max-width:960px;margin:0 auto;padding:24px}
 h1{font-size:1.4rem;margin:0 0 4px} h2{font-size:1.1rem;margin:28px 0 10px;border-left:4px solid #1f3b73;padding-left:8px}
 .muted{color:#666;font-size:.85rem}
 .card{background:#fff;border:1px solid #e2e2e2;border-radius:8px;padding:16px;margin-top:12px}
 table{border-collapse:collapse;width:100%;font-size:.92rem}
 th,td{border:1px solid #e0e0e0;padding:7px 9px;text-align:right}
 th{background:#eef1f6;text-align:center} td.l,th.l{text-align:left}
 .up{color:#1a7f37;font-weight:600}.down{color:#c0392b;font-weight:600}
 .pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:.8rem;background:#eef1f6}
 img{max-width:100%;height:auto;border:1px solid #e2e2e2;border-radius:6px}
 ul{margin:6px 0 0;padding-left:20px} li{margin:3px 0}
 .disc{background:#fff8e5;border:1px solid #f0dca0;border-radius:6px;padding:12px;font-size:.82rem;margin-top:24px}
 a{color:#1f3b73}
</style></head><body><div class="wrap">

<h1>{{ company }}（{{ ticker }}） 株価予測レポート</h1>
<div class="muted">生成日時 {{ generated }} ／ 価格基準日 {{ f.as_of }} ／ 現値 <b>{{ "{:,.0f}".format(f.spot) }} 円</b></div>

<h2>1. 予測サマリー（モンテカルロ 20,000 パス）</h2>
<div class="card">
<table>
<tr><th class="l">ホライズン</th><th>予測中央値</th><th>期待リターン</th><th>下限(10%)</th><th>上限(90%)</th><th>上昇確率</th>{% if f.arima_available %}<th>ARIMA点予測</th>{% endif %}</tr>
{% for name, h in f.horizons.items() %}
<tr>
 <td class="l">{{ name }}（{{ h.days }}営業日）</td>
 <td>{{ "{:,.0f}".format(h.median) }} 円</td>
 <td class="{{ 'up' if h.expected_return_pct>=0 else 'down' }}">{{ "%+.1f"|format(h.expected_return_pct) }}%</td>
 <td>{{ "{:,.0f}".format(h.p10) }} 円<br><span class="muted">{{ "%+.1f"|format(h.band_low_pct) }}%</span></td>
 <td>{{ "{:,.0f}".format(h.p90) }} 円<br><span class="muted">{{ "%+.1f"|format(h.band_high_pct) }}%</span></td>
 <td class="{{ 'up' if h.prob_up>=0.5 else 'down' }}">{{ "%.0f"|format(h.prob_up*100) }}%</td>
 {% if f.arima_available %}<td>{{ "{:,.0f}".format(h.arima_point) }} 円</td>{% endif %}
</tr>
{% endfor %}
</table>
<p class="muted">年率換算ドリフト {{ f.total_drift_annualized_pct }}%（ベースライン {{ f.baseline_drift_pct }}% ＋ ニュース補正 {{ f.sentiment_drift_pct }}% ＋ 平均回帰補正 {{ f.meanrev_drift_pct }}%） ／ 年率ボラティリティ {{ f.annualized_vol_pct }}% ／ 直近トレンド（年率）{{ f.recent_trend_annualized_pct }}%</p>
</div>

<h2>2. チャート</h2>
<div class="card"><img src="{{ chart_name }}" alt="price chart"></div>

<h2>3. テクニカル状況</h2>
<div class="card">
<p>終値 {{ "{:,.0f}".format(t.close) }} 円（前日比 <span class="{{ 'up' if t.change_pct>=0 else 'down' }}">{{ "%+.2f"|format(t.change_pct) }}%</span>）
{% if t.rsi14 %}／ RSI(14) {{ "%.0f"|format(t.rsi14) }}{% endif %}
{% if t.hv20 %}／ HV20 {{ "%.0f"|format(t.hv20*100) }}%{% endif %}</p>
<ul>{% for s in t.signals %}<li>{{ s }}</li>{% endfor %}</ul>
</div>

<h2>4. ニュース・センチメント</h2>
<div class="card">
<p>総合センチメント <span class="pill">{{ "%+.2f"|format(n.sentiment) }}</span>
（-1〜+1、対象 {{ n.n_items }} 件 / スコア付与 {{ n.n_scored }} 件、信頼度 {{ "%.2f"|format(n.confidence) }}）</p>
{% if n.events %}<p class="muted">検出イベント: {% for k,v in n.events.items() %}{{ k }}×{{ v }}{% if not loop.last %} ／ {% endif %}{% endfor %}</p>{% endif %}
{% if n.top_positive %}<p><b>ポジティブ材料</b></p><ul>
{% for x in n.top_positive %}<li>[{{ x.date }}] <a href="{{ x.url }}" target="_blank" rel="noopener">{{ x.title }}</a> <span class="muted">{{ x.hits|join(" ") }}</span></li>{% endfor %}</ul>{% endif %}
{% if n.top_negative %}<p><b>ネガティブ材料</b></p><ul>
{% for x in n.top_negative %}<li>[{{ x.date }}] <a href="{{ x.url }}" target="_blank" rel="noopener">{{ x.title }}</a> <span class="muted">{{ x.hits|join(" ") }}</span></li>{% endfor %}</ul>{% endif %}
</div>

<h2>5. 直近ニュース一覧（{{ news_list|length }} 件）</h2>
<div class="card"><ul>
{% for it in news_list[:25] %}
<li>[{{ it.date }}] <span class="muted">{{ it.source }}</span> <a href="{{ it.url }}" target="_blank" rel="noopener">{{ it.title }}</a></li>
{% endfor %}
</ul></div>

<div class="disc"><b>免責事項:</b> {{ disclaimer }}</div>
<div class="muted" style="margin-top:10px">nyk-stock-predictor v{{ version }}</div>
</div></body></html>
""")


def _text_summary(ctx: dict) -> str:
    f = ctx["forecast"]
    n = ctx["news"]
    lines = [
        f"{ctx['company']}（{ctx['ticker']}） 株価予測  生成 {ctx['generated']}",
        f"価格基準日 {f['as_of']} / 現値 {f['spot']:,.0f} 円",
        f"年率ドリフト {f['total_drift_annualized_pct']}% / 年率ボラ {f['annualized_vol_pct']}%",
        f"ニュース・センチメント {n['sentiment']:+.2f}（信頼度 {n['confidence']:.2f}, {n['n_items']}件）",
        "",
    ]
    for name, h in f["horizons"].items():
        lines.append(
            f"[{name:>4}] 中央値 {h['median']:,.0f}円  期待 {h['expected_return_pct']:+.1f}%  "
            f"レンジ {h['p10']:,.0f}〜{h['p90']:,.0f}円  上昇確率 {h['prob_up']*100:.0f}%"
        )
    lines += ["", "免責: " + DISCLAIMER]
    return "\n".join(lines)


def write_reports(prices, technical: dict, news_items, news_score: dict,
                  forecast: dict) -> dict:
    from . import __version__

    now = dt.datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M")
    chart_name = f"chart_{stamp}.png"
    make_chart(prices, forecast, config.OUTPUT_DIR / chart_name)
    # latest 用にも複製
    make_chart(prices, forecast, config.OUTPUT_DIR / "chart_latest.png")

    ctx = {
        "company": config.COMPANY_JP,
        "ticker": config.TICKER,
        "generated": now.strftime("%Y-%m-%d %H:%M"),
        "f": forecast,
        "forecast": forecast,
        "t": technical,
        "n": news_score,
        "news": news_score,
        "news_list": [it.as_dict() for it in news_items],
        "chart_name": chart_name,
        "disclaimer": DISCLAIMER,
        "version": __version__,
    }

    html = HTML_TEMPLATE.render(**ctx)
    (config.OUTPUT_DIR / f"report_{stamp}.html").write_text(html, encoding="utf-8")
    latest_html = html.replace(chart_name, "chart_latest.png")
    (config.OUTPUT_DIR / "report_latest.html").write_text(latest_html, encoding="utf-8")

    payload = {
        "generated": ctx["generated"],
        "ticker": config.TICKER,
        "technical": technical,
        "news_score": news_score,
        "forecast": forecast,
        "news": ctx["news_list"],
    }
    (config.OUTPUT_DIR / f"forecast_{stamp}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (config.OUTPUT_DIR / "forecast_latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    text = _text_summary(ctx)
    (config.OUTPUT_DIR / "summary_latest.txt").write_text(text, encoding="utf-8")

    # 履歴を1行追記（時系列で予測を蓄積・後日精度検証用）
    hist = config.OUTPUT_DIR / "history.csv"
    row = {
        "generated": ctx["generated"], "as_of": forecast["as_of"], "spot": forecast["spot"],
        "sentiment": news_score["sentiment"], "drift_ann_pct": forecast["total_drift_annualized_pct"],
        "vol_ann_pct": forecast["annualized_vol_pct"],
    }
    for name, h in forecast["horizons"].items():
        row[f"{name}_median"] = h["median"]
        row[f"{name}_prob_up"] = h["prob_up"]
    df = pd.DataFrame([row])
    df.to_csv(hist, mode="a", header=not hist.exists(), index=False, encoding="utf-8-sig")

    return {"html": str(config.OUTPUT_DIR / f"report_{stamp}.html"),
            "latest_html": str(config.OUTPUT_DIR / "report_latest.html"),
            "text": text}
