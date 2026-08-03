# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python（本機 collector + decision core）、Vercel（serverless functions + cron 排程）、靜態前端（HTML + fetch，不放邏輯）。事件資料以 git 追蹤的 append-only JSONL 儲存。

> 來源：2026-08-03 設計討論 Section 4，使用者明確同意。

## Users

**主要使用者**：訂閱 ChatGPT / Codex 方案的開發者，在自己的 weekly cap 被用盡、或接近用盡時，想知道 OpenAI 是否已經（或即將）發放一次臨時加碼重置。

**使用情境**：額度撞牆當下，開一個分頁想快速得到一個判斷 —— 現在該等，還是該改用別的工具。時間敏感、注意力短、通常在工作被打斷的挫折狀態下。

**次要使用者**：想檢驗這個站可不可信的人。他們要看的不是首頁結論，而是歷史紀錄與校準表現。

## Product Purpose

回答兩個彼此獨立的問題，並且不讓讀者混淆兩者：

1. **事實**：OpenAI 最近是否發放了一次臨時加碼重置？何時？（detector）
2. **推論**：在已經 $t$ 天沒發生的條件下，未來 24 小時內發生的風險率是多少？（hazard）

成功的定義是**別人願意信任這個 Yes/No**，而信任來自可被外部檢驗的紀錄，不是來自語氣肯定。

## Positioning

現有同類專案（`jskoiz/has-codex-rate-limits-reset-today`、`RyuuMeow/Will-Tibo-Reset`）的唯一訊號源是**社群推文判讀** —— 推文是關於事實的傳聞，不是事實本身；OpenAI 分批 rollout 或未發推時，那些系統是瞎的。

本專案的機制差異：**直接從帳號的 `rate_limit` 欄位讀出客觀跳變**，並用一條確定性判別式區分兩種重置：

```
額度上升  AND  now < 前次觀測宣告的 reset_at  →  臨時加碼重置
額度上升  AND  now ≥ 前次觀測宣告的 reset_at  →  例行滾動（忽略）
```

社群訊號因此被降級為待校準的 noisy indicator，**絕不進入 detector 判準**。這讓本站能公開宣稱競品結構上給不出的東西：偵測延遲分布、召回率、以及風險率的校準曲線。

## Operating Context

- **collector** 在使用者自己的機器上常駐輪詢，憑證（`~/.codex/auth.json` 的 `access_token` + `account_id`）永不離開本機；只上報經簽章的匿名事件。
- **伺服器**只收事件、驗簽、寫 append-only log，永遠不持有任何人的 OAuth token。
- v1 的證據來源為單一帳號錨點 + 社群訊號；v2 開放眾包，架構上只是 `Observation.source` 多一個值。
- 眾包上報的匿名事件**公開進 git**（使用者 2026-08-03 決定，理由：專案完全公開）。

## Capabilities and Constraints

- **上游端點未公開文件化**：`https://chatgpt.com/backend-api/wham/usage` 與 `/wham/rate-limit-reset-credits`。schema 會變，必須 fail loud：收到非預期結構時記為 `schema_drift`、**停止一切推論**、首頁顯示資料管線異常。
- **事件極稀疏**：估計一年約十餘次。以 EPV ≥ 10 的粗略規則，資料只撐得起**一個** covariate。v1 因此只估 baseline hazard（Exponential 起步，資料足夠再考慮 Weibull），不放任何訊號進模型。
- **事件時間是區間，不是時點**：輪詢造成 interval censoring。`Observation` 同時記錄 `observed_at`（何時看到）與 `occurred_at`（區間）。
- **冷啟動誠實條款**：事件數 < 3 時首頁**不出任何風險數字**，直接顯示「資料不足」。這是硬規則。
- **decision core 必須是純函數**：輸入 event log、輸出判斷，不做 I/O。backtest 因此等於拿歷史 log 重跑同一個函數。
- n=1 錨點看不見分批 rollout，此限制必須在站上誠實標示。

## Brand Commitments

- 專案名 **codex-reset-likelihood**（使用者已建立目錄並定名）。`likelihood` 而非 `will` 是刻意選擇：本站給的是風險率，不是預言。
- 完全公開的開源專案。
- 語氣承諾：可宣稱偵測延遲與召回率，**不宣稱**「提前 N 天的準確預測」。

## Evidence on Hand

- 端點與認證方式已實地驗證（`~/.codex/auth.json` 為 OAuth 模式，含 `tokens.access_token` / `account_id`；回應欄位含 `rate_limit.primary_window` / `secondary_window` / `limit_reached` / `additional_rate_limits`）。
- 競品調查已完成（GitHub 搜尋共 66 個相關 repo，已讀 star 前 10 名與 predict 類 2 名）。
- **尚不存在的東西，未來設計不得捏造**：真實歷史事件資料（尚未開始收集）、任何使用者數字、任何準確率數字。站上一切數字在真實資料累積前都必須標示為示意。

## Product Principles

1. **事實與推論永不混淆。** 兩者在版面上分軌、各自帶自己的成績單，讀者不需要讀說明就能分辨哪個是量到的、哪個是算出來的。
2. **可被外部檢驗優先於看起來準確。** event log 公開進 git，任何人能 clone 下來重跑 decision core 驗證評分卡沒灌水。
3. **不確定性顯示出來，不是藏起來。** 事件畫成區間而非時點；資料不足就說資料不足。
4. **憑證永不集中。** 任何架構決策若導向「請使用者把 token 交出來」，一律否決。
5. **上游變動要吵不要靜。** schema 漂移停止推論並公告，絕不悄悄繼續出數字。

## Accessibility & Inclusion

事實／推論的區分**不得僅依賴顏色**（色覺障礙者必須也能分辨）。時間軸與熱圖須有文字或結構化替代表述。
