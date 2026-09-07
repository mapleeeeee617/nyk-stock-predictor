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

    # チャートのラベルは英語（実行環境に日本語フォントが無くても文字化けしないため）
    ax1.plot(ind.index, ind["close"], color="#1f3b73", lw=1.6, label="Close")
    ax1.plot(ind.index, ind["sma25"], color="#e08a00", lw=1.0, label="SMA 25")
    ax1.plot(ind.index, ind["sma75"], color="#8a8a8a", lw=1.0, label="SMA 75")

    cone = forecast["cone"]
    ax1.plot(future_dates, cone["median"], color="#c0392b", lw=1.6, ls="--", label="Forecast median")
    ax1.fill_between(future_dates, cone["p10"], cone["p90"], color="#c0392b", alpha=0.12,
                     label="Forecast 10-90%")
    ax1.axvline(last_date, color="#999", lw=0.8, ls=":")
    ax1.set_title(f"{config.TICKER}  Nippon Yusen (NYK Line)  -  price & Monte Carlo forecast"
                  f"  (as of {forecast['as_of']})")
    ax1.set_ylabel("Price (JPY)")
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
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>{{ company }} 株価予測レポート {{ generated }}</title>
<style>
 *,*::before,*::after{box-sizing:border-box}
 html{-webkit-text-size-adjust:100%}
 body{font-family:"Segoe UI","Hiragino Kaku Gothic ProN",Meiryo,system-ui,sans-serif;
      margin:0;background:#f4f5f7;color:#1c1c1c;line-height:1.6;
      -webkit-font-smoothing:antialiased}
 .wrap{max-width:960px;margin:0 auto;padding:clamp(14px,4vw,28px)}
 h1{font-size:clamp(1.15rem,4.5vw,1.5rem);margin:0 0 4px;line-height:1.35}
 h2{font-size:clamp(1rem,3.5vw,1.15rem);margin:26px 0 10px;
    border-left:4px solid #1f3b73;padding-left:8px}
 .muted{color:#666;font-size:.85rem}
 .card{background:#fff;border:1px solid #e2e2e2;border-radius:8px;
       padding:clamp(12px,3.5vw,18px);margin-top:12px}
 .table-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -4px}
 table{border-collapse:collapse;width:100%;font-size:.92rem}
 th,td{border:1px solid #e0e0e0;padding:7px 9px;text-align:right;white-space:nowrap}
 th{background:#eef1f6;text-align:center}
 td.l,th.l{text-align:left}
 .up{color:#1a7f37;font-weight:600}.down{color:#c0392b;font-weight:600}
 .pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:.8rem;background:#eef1f6}
 img{max-width:100%;height:auto;display:block;border:1px solid #e2e2e2;border-radius:6px}
 ul{margin:6px 0 0;padding-left:1.25em} li{margin:4px 0;overflow-wrap:anywhere}
 a{color:#1f3b73;overflow-wrap:anywhere}
 .disc{background:#fff8e5;border:1px solid #f0dca0;border-radius:6px;
       padding:12px;font-size:.82rem;margin-top:24px}
 .note{font-size:.83rem;color:#555;background:#f0f3f8;border-radius:6px;
       padding:9px 11px;margin:0 0 10px}
 .lead{font-size:.9rem;color:#444;margin:8px 0 0}
 details.glossary{margin-top:14px;border:1px solid #e2e2e2;border-radius:8px;background:#fff}
 details.glossary>summary{cursor:pointer;padding:12px 16px;font-weight:600;font-size:.98rem;list-style:none}
 details.glossary>summary::-webkit-details-marker{display:none}
 details.glossary>summary::before{content:"▸ ";color:#1f3b73}
 details.glossary[open]>summary::before{content:"▾ "}
 details.glossary .gbody{padding:0 16px 14px}
 details.glossary dt{font-weight:600;margin-top:12px}
 details.glossary dd{margin:2px 0 0;font-size:.9rem;color:#444}
 .scrollhint{display:none;font-size:.78rem;color:#888;margin:2px 2px 0}
 @media (max-width:640px){
   body{line-height:1.5}
   th,td{padding:6px 7px;font-size:.82rem}
   .card{border-radius:6px}
   .scrollhint{display:block}
 }
 @media (prefers-color-scheme:dark){
   body{background:#15171a;color:#e6e6e6}
   .card{background:#1e2126;border-color:#333}
   h2{border-left-color:#5b8def}
   th{background:#262a30}
   th,td{border-color:#333}
   .muted,.scrollhint{color:#9aa0a6}
   .pill{background:#262a30}
   a{color:#8ab4ff}
   img{border-color:#333}
   .up{color:#4ecb71}.down{color:#ff6b6b}
   .disc{background:#2b2717;border-color:#5c5326}
   .note{background:#20242b;color:#c2c7cd}
   .lead{color:#c2c7cd}
   details.glossary{background:#1e2126;border-color:#333}
   details.glossary dd{color:#c2c7cd}
   details.glossary>summary::before{color:#8ab4ff}
 }
</style></head><body><div class="wrap">

<h1>{{ company }}（{{ ticker }}） 株価予測レポート</h1>
<div class="muted">生成日時 {{ generated }} ／ 価格基準日 {{ f.as_of }} ／ 現値 <b>{{ "{:,.0f}".format(f.spot) }} 円</b></div>
<p class="lead">公式ニュース・報道・株価データを自動収集し、統計モデルで先行き{{ f.horizons|length }}期間の株価の
<b>分布</b>（当たり／外れの一点予想ではなく、ありそうな範囲）を推計したものです。
用語は末尾の「<a href="#glossary">用語の説明</a>」を参照してください。</p>

<h2>1. 予測サマリー</h2>
<div class="card">
<p class="note"><b>モンテカルロ・シミュレーション</b>とは、株価が今後たどりうる道のりを乱数で
{{ "{:,}".format(mc_paths) }}通り試算し、その結果の散らばりから確率的な見通しを読み取る手法です。<br>
・<b>予測中央値</b>＝2万通りのちょうど真ん中の値（大きく外れた値に引っ張られにくい中心）<br>
・<b>下限(10%)／上限(90%)</b>＝結果の約8割がこの範囲に収まる、という幅。<u>この幅の広さが不確実性の大きさ</u>です<br>
・<b>上昇確率</b>＝2万通りのうち現値より高く終わった割合<br>
・<b>期待リターン</b>＝2万通りの平均値の変化率</p>
<div class="scrollhint">← 表は横スクロールできます →</div>
<div class="table-scroll">
<table>
<tr><th class="l">ホライズン</th><th>予測中央値</th><th>期待リターン</th><th>下限(10%)</th><th>上限(90%)</th><th>上昇確率</th>{% if f.arima_available %}<th>参考:ARIMA</th>{% endif %}</tr>
{% for name, h in f.horizons.items() %}
<tr>
 <td class="l">{{ name }}（{{ h.days }}営業日先）</td>
 <td>{{ "{:,.0f}".format(h.median) }} 円</td>
 <td class="{{ 'up' if h.expected_return_pct>=0 else 'down' }}">{{ "%+.1f"|format(h.expected_return_pct) }}%</td>
 <td>{{ "{:,.0f}".format(h.p10) }} 円<br><span class="muted">{{ "%+.1f"|format(h.band_low_pct) }}%</span></td>
 <td>{{ "{:,.0f}".format(h.p90) }} 円<br><span class="muted">{{ "%+.1f"|format(h.band_high_pct) }}%</span></td>
 <td class="{{ 'up' if h.prob_up>=0.5 else 'down' }}">{{ "%.0f"|format(h.prob_up*100) }}%</td>
 {% if f.arima_available %}<td>{{ "{:,.0f}".format(h.arima_point) }} 円</td>{% endif %}
</tr>
{% endfor %}
</table>
</div>
{% if f.arima_available %}<p class="muted">「参考:ARIMA」= 時系列モデル {{ f.arima_spec }} による別方式の点予測（年率ドリフト {{ f.arima_drift_annualized_pct }}%）。モンテカルロとは独立の目安です。</p>{% endif %}
<p class="muted"><b>ドリフト</b>（モデルが想定する年率の方向性）{{ f.total_drift_annualized_pct }}%
＝ ベースライン {{ f.baseline_drift_pct }}%（過去トレンド＋ARIMA）
＋ ニュース補正 {{ f.sentiment_drift_pct }}%
＋ 平均回帰補正 {{ f.meanrev_drift_pct }}%（買われすぎ／売られすぎの揺り戻し）。<br>
<b>ボラティリティ</b>（値動きの激しさ、年率）{{ f.annualized_vol_pct }}% ／ 直近トレンドは年率換算で {{ f.recent_trend_annualized_pct }}%。</p>
</div>

<h2>2. チャート</h2>
<div class="card"><img src="{{ chart_name }}" alt="price chart" loading="lazy"></div>

<h2>3. テクニカル状況</h2>
<div class="card">
<p class="note"><b>テクニカル指標</b>＝過去の株価・出来高だけから計算する売買の目安。
<b>RSI</b>は0〜100で「買われすぎ(70以上)／売られすぎ(30以下)」、
<b>移動平均</b>は一定期間の平均株価の線、
<b>HV20</b>は直近20日の値動きの荒さ（年率）です。</p>
<p>終値 {{ "{:,.0f}".format(t.close) }} 円（前日比 <span class="{{ 'up' if t.change_pct>=0 else 'down' }}">{{ "%+.2f"|format(t.change_pct) }}%</span>）
{% if t.rsi14 %}／ RSI(14) {{ "%.0f"|format(t.rsi14) }}{% endif %}
{% if t.hv20 %}／ HV20 {{ "%.0f"|format(t.hv20*100) }}%{% endif %}</p>
<ul>{% for s in t.signals %}<li>{{ s }}</li>{% endfor %}</ul>
</div>

<h2>4. ニュース・センチメント</h2>
<div class="card">
<p class="note"><b>センチメント</b>＝ニュース見出しに含まれる語（「増配」「上方修正」＝プラス、
「減益」「事故」＝マイナスなど）を集計した強気・弱気の度合い。
-1（非常に弱気）〜 +1（非常に強気）。新しいニュースほど重く数えています。</p>
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

<details class="glossary" id="glossary">
<summary>用語の説明</summary>
<div class="gbody"><dl>
<dt>モンテカルロ・シミュレーション</dt>
<dd>将来の株価が進みうる経路を乱数で膨大な回数（本レポートは {{ "{:,}".format(mc_paths) }} 回）試し、
その結果の分布から「中央値」「レンジ」「上昇確率」を読み取る手法。1つの数字を当てにいくのではなく、
起こりうる範囲を見るための道具です。</dd>
<dt>幾何ブラウン運動（GBM）</dt>
<dd>モンテカルロで株価経路を作るときの標準的な数式モデル。「一定の方向性（ドリフト）＋
ランダムな揺れ（ボラティリティ）」で価格が動くと仮定します。</dd>
<dt>ドリフト</dt>
<dd>モデルが想定する株価の平均的な方向性（年率）。過去トレンド・ARIMA・ニュース・平均回帰を
合成し、暴走を防ぐため上下 ±{{ max_drift_pct }}% で頭打ちにしています。</dd>
<dt>ボラティリティ</dt>
<dd>値動きの激しさ。数値が大きいほど予測レンジも広がります。直近約60営業日の
値動きから年率換算で推定しています。</dd>
<dt>ヒストリカル・ボラティリティ（HV）</dt>
<dd>過去の実際の値動きから計算したボラティリティ。HV20 は直近20日ぶん。</dd>
<dt>パーセンタイル（10% / 90%）</dt>
<dd>結果を小さい順に並べたときの位置。10%点＝下から1割、90%点＝下から9割。
その間（8割）が「ありそうなレンジ」。</dd>
<dt>期待リターン / 中央値</dt>
<dd>期待リターンは全シナリオの平均の変化率、中央値はちょうど真ん中のシナリオ。
分布が偏ると両者はずれます。</dd>
<dt>ARIMA</dt>
<dd>時系列データ（株価そのものの並び）から自動でパターンを学ぶ定番の統計モデル。
本レポートではモンテカルロとは別方式の「参考値」として併記しています。</dd>
<dt>センチメント</dt>
<dd>ニュース見出しの語をプラス・マイナスで採点し集計した強気／弱気の度合い（-1〜+1）。
外部AIは使わず、海運・財務用語の辞書で判定しています。</dd>
<dt>平均回帰</dt>
<dd>行きすぎた株価が平均へ戻ろうとする傾向。RSI が極端なとき、予測を逆方向へ少し補正します。</dd>
<dt>RSI</dt>
<dd>0〜100 の指標。70以上で買われすぎ、30以下で売られすぎとされます。</dd>
<dt>MACD</dt>
<dd>短期と長期の移動平均の差から売買タイミングを見る指標。</dd>
<dt>移動平均（25日・75日）</dt>
<dd>過去25日・75日の平均株価の線。短期線が長期線を上抜けるのがゴールデンクロス、
下抜けるのがデッドクロス。</dd>
</dl></div>
</details>

<div class="disc"><b>免責事項:</b> {{ disclaimer }}
<br>方向（上がるか下がるか）の的中率は概ね5割前後で、当てにいくものではありません。
本レポートの価値は「変動レンジと材料の把握」にあります。</div>
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


def _build_ctx(technical, news_items, news_score, forecast, chart_name, now):
    from . import __version__
    return {
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
        "mc_paths": config.MC_PATHS,
        "max_drift_pct": round(config.MAX_ANNUAL_DRIFT * 100),
    }


def _json_payload(ctx, technical, news_score, forecast):
    return {
        "generated": ctx["generated"],
        "ticker": config.TICKER,
        "technical": technical,
        "news_score": news_score,
        "forecast": forecast,
        "news": ctx["news_list"],
    }


def render_site(prices, technical: dict, news_items, news_score: dict,
                forecast: dict, dest) -> str:
    """Netlify などで配信する静的サイトを dest ディレクトリへ生成する。

    dest/index.html, dest/chart.png, dest/forecast.json を書き出す。
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now()

    make_chart(prices, forecast, dest / "chart.png")
    ctx = _build_ctx(technical, news_items, news_score, forecast, "chart.png", now)
    html = HTML_TEMPLATE.render(**ctx)
    (dest / "index.html").write_text(html, encoding="utf-8")
    (dest / "forecast.json").write_text(
        json.dumps(_json_payload(ctx, technical, news_score, forecast),
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return str(dest / "index.html")


def write_reports(prices, technical: dict, news_items, news_score: dict,
                  forecast: dict) -> dict:
    now = dt.datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M")
    chart_name = f"chart_{stamp}.png"
    make_chart(prices, forecast, config.OUTPUT_DIR / chart_name)
    # latest 用にも複製
    make_chart(prices, forecast, config.OUTPUT_DIR / "chart_latest.png")

    ctx = _build_ctx(technical, news_items, news_score, forecast, chart_name, now)

    html = HTML_TEMPLATE.render(**ctx)
    (config.OUTPUT_DIR / f"report_{stamp}.html").write_text(html, encoding="utf-8")
    latest_html = html.replace(chart_name, "chart_latest.png")
    (config.OUTPUT_DIR / "report_latest.html").write_text(latest_html, encoding="utf-8")

    payload = _json_payload(ctx, technical, news_score, forecast)
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
