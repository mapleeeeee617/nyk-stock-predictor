# 日本郵船（9101.T）株価予測システム

日本郵船の**公開情報**（公式プレスリリース・Google ニュース・株価データ）を毎日自動で収集し、
テクニカル指標とニュース・センチメントを組み合わせた**統計モデル**で、
1週間 / 1ヶ月 / 3ヶ月先の株価分布を推計して HTML レポートを生成します。

> ⚠️ **免責事項**
> 本システムの出力は公開情報に基づく統計的推計であり、**投資助言・売買推奨ではありません**。
> 将来の株価を保証するものではなく、実際の値動きは予測から大きく乖離し得ます。
> 投資判断は必ずご自身の責任で行ってください。作者・本ソフトは一切の責任を負いません。

---

## できること

| 機能 | 内容 |
|------|------|
| 株価データ取得 | Yahoo! Finance から 9101.T の日次データを3年分（`yfinance`） |
| ニュース収集 | ① nyk.com 公式ニュース一覧のスクレイピング<br>② Google ニュース RSS（「日本郵船」）の直近45日分 |
| センチメント分析 | 海運・財務ドメインに特化した**日本語キーワード辞書**でヘッドラインを採点、時間減衰で加重平均（外部LLM不要・完全オフライン処理） |
| イベント検出 | 決算・株主総会・配当・自己株式取得・M&A・格付け・海運市況・海難事故・地政学 などを正規表現で分類 |
| テクニカル分析 | 移動平均（25/75日）、RSI(14)、MACD、ボリンジャーバンド、ヒストリカル・ボラティリティ |
| 予測モデル | 幾何ブラウン運動モンテカルロ（20,000パス）。ドリフト = 減衰トレンド + ARIMA示唆 + ニュース補正 + RSI平均回帰補正。参考に ARIMA(1,1,1) の点予測も併記 |
| 出力 | `output/report_latest.html`（チャート付き）、`forecast_latest.json`、`summary_latest.txt`、`history.csv`（予測の時系列蓄積） |
| 自動実行 | Windows タスク スケジューラに平日18:15実行を登録 |
| 精度検証 | `backtest.py` で過去データの方向的中率・帯カバー率を評価 |

---

## セットアップ

すでに構築済みです（`.venv` に依存パッケージ導入済み）。再構築する場合:

```bat
cd C:\Users\k0617\nyk-stock-predictor
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 使い方

### 手動でレポート生成

```bat
.venv\Scripts\python.exe run.py
```

生成後にブラウザで開く:

```bat
.venv\Scripts\python.exe run.py --open
```

出力は `output\report_latest.html`。

### 毎営業日の自動実行を登録

```powershell
powershell -ExecutionPolicy Bypass -File .\register_task.ps1
```

- 平日（月〜金）18:15 に `run_scheduled.cmd` が走り、レポートを更新します（市場終値15:00＋ニュース反映を考慮）。
- 時刻変更: `-Time 19:00`
- 今すぐ試験実行: `Start-ScheduledTask -TaskName NYK-StockForecast`
- 解除: `powershell -ExecutionPolicy Bypass -File .\register_task.ps1 -Unregister`
- 実行ログ: `logs\run_YYYY-MM-DD.log`

### 精度のバックテスト

```bat
.venv\Scripts\python.exe backtest.py --step 5 --start 300
```

---

## 予測の読み方

- **予測中央値**：モンテカルロ・シミュレーションの中央値。点予測ではなく「ありそうな中心」。
- **下限(10%)〜上限(90%)**：80%の確率でこのレンジに収まる、という推計。**レンジの広さこそが本質**です。
- **上昇確率**：現値より上で終わるパスの割合。
- **年率ドリフト**：モデルが想定する年率トレンド。暴走防止のため ±20% でクリップされます（強い一方向トレンド時は上限に張り付きます）。

## モデルの限界（重要）

- **方向予測は当たりません。** 同梱バックテストでの方向的中率は概ね 30〜50%（コイン投げ相当かそれ以下）。
  短期の株価の向きを統計モデルで当てるのは原理的に困難です。
  一方、**80%予測帯のカバー率は約80%** とよく較正されており、
  本システムの value は「点予測」ではなく「**変動レンジと材料の把握**」にあります。
- センチメントは**見出しのキーワード一致**のみ。皮肉・文脈・打ち消しは十分に扱えず、
  誤判定もあります（例：「事故報告書分析エージェントを構築」を負の材料と誤検出）。
- 過去のニュースは遡って取得できないため、バックテストはニュース補正なしの評価です。
- 決算発表・株主総会などの**日付そのもの**（イベントカレンダー）は現状ヘッドラインからの推定のみ。
  正式には[日本郵船IRカレンダー](https://www.nyk.com/ir/)で確認してください。
- Yahoo! Finance / nyk.com の仕様変更で取得が壊れる可能性があります。

## ディレクトリ構成

```
nyk-stock-predictor/
├─ run.py                  エントリポイント（収集→分析→予測→レポート）
├─ backtest.py             精度検証
├─ register_task.ps1       タスク スケジューラ登録/解除
├─ run_scheduled.cmd       スケジュール実行ラッパー（ログ付き）
├─ requirements.txt
├─ nyk_predictor/
│  ├─ config.py            銘柄・URL・モデルパラメータ
│  ├─ prices.py            株価取得・テクニカル指標
│  ├─ news.py              ニュース収集
│  ├─ sentiment.py         日本語センチメント辞書・イベント分類
│  ├─ forecast.py          モンテカルロ + ARIMA
│  └─ report.py            チャート・HTML・JSON 生成
├─ data/                   価格キャッシュ
├─ output/                 レポート（*_latest がつねに最新）
└─ logs/                   スケジュール実行ログ
```

## パラメータ調整

`nyk_predictor/config.py`:

| 変数 | 意味 | 既定 |
|------|------|------|
| `HORIZONS` | 予測ホライズン（営業日） | 5 / 21 / 63 |
| `SENTIMENT_DRIFT_SCALE` | センチメント→ドリフト換算 | 0.15 |
| `MEANREV_SCALE` | RSI平均回帰の強さ | 0.12 |
| `MAX_ANNUAL_DRIFT` | ドリフト上下限 | 0.20 |
| `MC_PATHS` | モンテカルロ試行数 | 20000 |
| `NEWS_LOOKBACK_DAYS` | ニュース対象期間 | 45 |

センチメント辞書は `nyk_predictor/sentiment.py` の `POSITIVE` / `NEGATIVE` で増補できます。
