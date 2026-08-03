# codex-reset-likelihood — 設計文件

> 2026-08-04．狀態：已核可，待實作
> 產品脈絡見 [`PRODUCT.md`](../../../PRODUCT.md)

## 1. 問題

OpenAI 偶爾會手動「加碼重置」Codex 使用者的 weekly cap。這件事沒有公告 API、不定時、由商業決策驅動。現有的社群工具（`jskoiz/has-codex-rate-limits-reset-today`、`RyuuMeow/Will-Tibo-Reset`）全部把**推文判讀**當作唯一訊號源。

推文是關於事件的傳聞，不是事件。當 rollout 分批進行、或 OpenAI 根本沒發推時，那些系統是瞎的，而且**無法知道自己瞎了** —— 沒有客觀錨點，就無從估計自己的召回率。

## 2. 兩個彼此獨立的問題

本站回答兩個問題，並且在版面與計分上都不讓它們混淆：

| | 問題 | 性質 | 計分方式 |
|---|---|---|---|
| **Track A** | 最近是否發生了加碼重置？何時？ | 量測 | 偵測延遲、召回率 |
| **Track B** | 在已經 $t$ 天沒發生的條件下，未來 24h 風險率？ | 推論 | Brier score、校準曲線 |

兩個計分量的定義（避免日後各自解讀）：

- **偵測延遲** $= \text{observed\_at} - \text{mid}(\text{occurred\_at})$。下界由輪詢間隔決定，因為事件只能被定位在區間內、不可能定位到時點。
- **召回率**：分母是**事後**由社群共識確認為真、且落在本站運轉期間內的加碼重置事件；分子是本站當時獨立偵測到的。社群共識只用於**事後評分**，絕不進入 Track A 的即時判準（見第 3 節）。

名稱用 `likelihood` 而非 `will`：本站給的是風險率，不是預言。可宣稱偵測延遲與召回率，**不宣稱**提前 N 天的準確預測。

## 3. 核心判別式

每次 `/wham/usage` 回應都帶有 weekly window 宣告的 `reset_at`。因此例行滾動是**可預期的**，加碼重置不是：

```
額度上升  AND  now <  前次觀測宣告的 reset_at   →  加碼重置
額度上升  AND  now ≥  前次觀測宣告的 reset_at   →  例行滾動（忽略）
```

這是確定性的，不需要任何語言模型。**前提是 collector 必須保存前一次觀測** —— 它是狀態機，不是無狀態輪詢。

社群訊號因此被降級為待校準的 leading indicator，**絕不進入 Track A 的判準**；否則 gold standard 被噪訊污染，兩張評分卡就一起失效。

## 4. 系統架構

```
[本機 collector] ×N          v1: N=1     v2: N=眾包
  ~/.codex/auth.json → GET /wham/usage（輪詢，保存前次觀測）
  → 偵測 secondary_window 跳變 → 套用判別式
  → 簽章                              憑證永不離開本機
        │ POST /observations
        ↓
[ingest]  驗簽 → 去重 → append-only event log (JSONL, git-tracked)
                                                 ↑
[social watcher] (cron) ─────────────────────────┘
  X / Reddit / HN → LLM 判讀 → Observation（advisory only）
        │
        ↓
[decision core]   純函數：event log → 判斷（無 I/O）
  ├─ Detector : 是否發生、何時、延遲多久
  └─ Hazard   : 未來 24h 風險率
        │
        ↓
[web]  Track A（事實）+ Track B（推論）+ 兩張評分卡 + 公開 archive/API
```

**decision core 必須是純函數。** 輸入 event log、輸出判斷、不做任何 I/O。backtest 因此等於「拿歷史 log 重跑同一個函數」，校準曲線才可重現、可被外部檢驗。任何在決策層偷發網路請求的設計，都會讓評分卡失去意義。

## 5. 證據層

```
Observation {
  source:        "self-account" | "social" | "crowd"
  observed_at:   timestamp        ← 何時「看到」
  occurred_at:   interval         ← 何時「發生」（區間，非時點）
  evidence_kind: "quota_jump" | "announcement" | "user_report" | "schema_drift"
  payload:       {...}
  signature:     bytes            ← self / crowd 必須簽章
}
```

`source` 是唯一需要為 v2 眾包擴充的欄位；決策層不動。

**`quota_jump` 的 payload 必須包含判別式的全部輸入**，否則第 9 節「任何人能重跑 decision core」只是宣稱：

```
payload(quota_jump) {
  prev_observed_at:  timestamp    ← 前一次觀測的時刻
  prev_reset_at:     timestamp    ← 前一次觀測所宣告的 reset_at ← 判別式據此分類
  prev_remaining:    number
  curr_remaining:    number
  curr_reset_at:     timestamp
}
```

判別式只讀這五個欄位。任何人拿到 log 就能獨立重跑分類，並且能檢查我們有沒有把例行滾動誤記成加碼重置。

**`observed_at` 與 `occurred_at` 分開是這個設計最重要的欄位決策。** 混用兩者會悄悄污染偵測延遲評分卡 —— 延遲的定義正是兩者之差。更關鍵的是，輪詢讓 `occurred_at` 天生是**區間**：只知道事件發生在〔上次輪詢, 這次輪詢〕之間。這在統計上是 interval-censored data，存活分析本來就有處理它的標準機制。副作用是輪詢間隔成為統計設計問題（區間寬度 vs API 禮貌），而不是隨手填的常數。

## 6. 統計核心

事件是 interval-censored 的到達時間。樣本極少（估計一年十餘次），以 EPV ≥ 10 的粗略規則，資料只撐得起**一個** covariate。因此：

- **v1**：只估 baseline hazard。Exponential 起步，資料足夠再考慮 Weibull 讓 hazard 隨時間變化。配 weakly informative prior 的 Bayesian 估計，不用無母數 KM（十來個事件撐不起）。
- **不放任何訊號進模型**。社群訊號、星期別只當顯示用 context。
- **covariate 候選**：日曆矩陣若顯示明顯星期偏態，那是未來唯一負擔得起的那個 covariate 的來源。

**冷啟動誠實條款（硬規則）**：事件數 < 3 時不出任何風險數字，直接顯示「資料不足」。不寫進 spec 的話，上線第一週必然有人想填個看起來合理的數字。

## 7. 錯誤處理

上游端點（`https://chatgpt.com/backend-api/wham/usage`、`/wham/rate-limit-reset-credits`）**未公開文件化，schema 會變**。

收到非預期結構時必須 fail loud：記為 `schema_drift`、**停止一切推論**、首頁顯示資料管線異常。悄悄吞掉 schema 變更，會讓評分卡在無人知情的狀況下變成垃圾 —— 那正是本站存在要避免的失敗。

## 8. 安全與隱私

- collector 在使用者自己的機器上跑，讀自己的 token（`~/.codex/auth.json` 的 `access_token` + `account_id`）。
- 只上報**簽章後的匿名事件**：`{ observed_at, occurred_at, delta_kind, sig }`。永不上報 token、account id、prompt。
- 伺服器只收事件、驗簽、寫 log，**永遠不持有任何人的 OAuth token**。伺服器不能洩漏它從未持有的東西。
- 這個決定順便讓 v2 眾包變成零架構變更：眾包 = 別人也裝同一支 collector。
- 眾包的匿名事件**公開進 git**（2026-08-03 決定；專案完全公開）。

## 9. 技術棧

| 層 | 選擇 | 理由 |
|---|---|---|
| collector | Python 單檔、零依賴 | 眾包門檻最低（一個檔 + `python3`），跨平台 |
| decision core | Python 純函數 | 與 collector 同語言，backtest 是統計工作 |
| ingest + web | Vercel（Python serverless + cron） | 生態內已有支援 |
| event log | git 追蹤的 append-only JSONL | 見下 |
| 前端 | 靜態 HTML + fetch | 只負責顯示，不放邏輯 |

event log 存成 repo 內的 JSONL 是刻意的設計承諾：**任何人可以 clone 下來重跑 decision core，驗證評分卡沒有灌水**。可重現性因此不是宣稱，是別人能執行的動作。

## 10. 測試

依 TDD，重點在 detector 判別式的**邊界**：

- 跳變恰好落在 `reset_at` 前後一秒
- `reset_at` 本身在兩次觀測之間被改動
- 輪詢跨越視窗邊界
- 跨午夜的區間
- schema drift 時推論確實停止（而非降級）

decision core 是純函數，適合 property-based test：對任意合法 event log，Track A 的事件數不得超過輸入的 quota_jump 數；hazard 在事件數 < 3 時必須回傳「不足」而非數字。

## 11. 視覺方向

**世界**：`ikeda-datamatics`（catalog challenger，於使用者指定「Codex + 科技感」後取代骰子指派的 grounded 候選 4「觀測日誌」；seed key `3bea9a98`）。

純黑白、無灰色顏料、無色相。三種材料：

| 材料 | 承載 |
|---|---|
| 實心條碼長條 | 量測到的事實（Track A、事件區間） |
| 細線正弦曲線 | 計算出的推論（Track B、hazard） |
| 0/1 格陣 | 逐日/逐時狀態（日曆矩陣、小時條） |

字體：Martian Mono（顯示）、Azeret Mono（資料密度），全站 tabular 數字。

**純黑白強迫用形狀而非顏色區分事實與推論** —— 實心 vs 細線。這免費滿足了 PRODUCT.md 不得僅依賴顏色的無障礙條款。

三個使用者要求的視覺裝置各有原生容器，不是外掛上去的：

- **B 垂直事件流** → data node 列，每列含 24 小時軸上的區間長條與小時格
- **C 日曆矩陣** → 七列（週一～週日）× N 週的 0/1 格陣，附星期統計
- **D 雙軌時間軸** → 上軌實心條（事實）、下軌細線鋸齒（推論），共用時間軸

方向契約以 HTML 註解形式存在 `index.html` 的 `<body>` 第一個子元素，每次編輯都會重讀。

## 12. 明確的非目標

- 不預測特定某一次重置會在哪天發生。
- 不在真實觀測累積前發布任何非示意數字（目前站上所有數字都標示為 synthetic）。
- 不收集任何人的憑證。
- 不在 schema 漂移時繼續出數字。
- n=1 時看不見分批 rollout，這是結構限制，不靠增加輪詢頻率解決，必須在站上誠實標示。
