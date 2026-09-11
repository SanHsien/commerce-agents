# 分岔登記表

本檔登記本 fork 對**上游持有檔案**的每一筆修改——上游原本就有這個檔案，本 fork 動了它。
新增的檔案（上游沒有對應版本，例如 `AGENTS.md`、`FORK.md`、`tools/` 底下的維護工具）不算
分岔，不登記在這裡；那些檔案的清單見 [`FORK.md`](../FORK.md)。

## 維護契約

**改動任何一個上游持有的檔案，就必須在這裡加一列。** 這件事由
[`tools/check_divergence.py`](../tools/check_divergence.py) 機器強制：它比對「上游基準
commit（`tools/upstream_baseline.json` 的 `reviewed_through`）到現在，哪些上游持有的檔案
被改過或刪過」與「這張表登記了哪些路徑」，兩邊對不上就非 0 退出，印出「已改但未登記」與
「已登記但其實沒改」兩份清單。這個檢查接在 `tools/dev_check.ps1`（本機／CI 的一鍵 gate）
與 `.github/workflows/upstream-check.yml`（每週）裡；合約測試在
[`tests/test_fork_divergence.py`](../tests/test_fork_divergence.py)。

最後一欄「跟進上游時怎麼處理」是這張表的重點：寫成**可執行的判準**，讓日後同步上游時不必
重新評估一次判斷，照著欄位裡的規則做決定即可。

**政策轉向**（2026-09-05，見 [`docs/DECISIONS.md`](DECISIONS.md)）：本 fork 不再因為「這是
上游持有的檔案」就保留落後版本或另開繞道檔；依賴直接跟最新版走，測試紅就改測試條件，每一處
差異都寫在這裡寫到位。這是本 fork 終究會與上游分岔的一部分，是預期結果不是風險。

| 上游檔案 | 上游原狀 | 本 fork 狀態 | 為什麼分岔 | 跟進上游時怎麼處理 |
|---|---|---|---|---|
| `README.md` | 英文 README：兩個 agent 的介紹、快速開始、目錄結構、驗證指令。 | 全文改寫為繁體中文；最上方加一段 fork 說明區塊（連到 `README.en.md`、`FORK.md`、`docs/DECISIONS.md`）；驗證區塊改成先裝 `requirements-dev.txt` 再跑 `tools/dev_check.ps1`。 | 公開入口改以繁中為主，服務中文維護者；上游英文原文整份保留在 `README.en.md`，不是被取代。 | 上游改 `README.md` 時，把新增或變更的**產品內容**（agent 說明、目錄結構、指令變化）人工合併進本檔對應章節，同時同步貼進 `README.en.md`；不要整份覆蓋——那會蓋掉繁中內容與 fork 說明區塊。 |
| `README.en.md` | 不存在於此路徑；上游的原始內容就是 `README.md`（英文）。 | 新增檔案，內容＝上游 `README.md` 原文，`git mv` 之後只加了一行連回繁中版的語言列。 | 保留上游英文原文的完整鏡像，讓 `README.md` 可以被改寫成繁中而不遺失原文。`tools/check_divergence.py` 用一個寫死的別名（`README.en.md` → `README.md`）把它算成 `README.md` 的分岔記錄，因為 git 的重新命名偵測只能配對「刪除＋新增」，`README.md` 在這裡是「修改」而不是「刪除」，天生配不出重新命名關係——見該工具原始碼裡的說明。 | 上游更新 `README.md` 時，把新內容同步貼進 `README.en.md`（只有語言列那一行是本 fork 加的，其餘照抄上游），不要貼進 `README.md`（那份已經是繁中改寫版）。 |
| `CLAUDE.md` | 產品設計規則文件：layout、design rules、conventions、verify 指令，給任何 clone 這個 repo 的 AI agent 看。 | 最上方插入一段 5～10 行的 fork 邊界區塊（指向 `AGENTS.md` 為單一真相源、聲明不對上游開 PR、聲明繁中回覆），其餘上游內容原封不動保留在補丁下方。 | 讓任何 clone 這個 repo 的 agent 先看到 fork 邊界規則；同時把「這是不是 fork」的規則跟上游的產品設計規則分開放，降低每次上游更新 `CLAUDE.md` 時的合併衝突面。 | 上游更新 `CLAUDE.md` 時，只在補丁區塊下方貼上新內容，插入點固定在檔案最上方那一段，衝突面只有一處。 |
| `.gitignore` | Python / Node / OS 標準忽略規則。 | 尾端 append 一個 `# --- fork ---` 區塊，忽略兩份生成報告（`upstream-review-report.md`、`dependency-freshness-report.md`）。 | 本 fork 的維護工具會在本機／CI 產生這兩份報告，不該入版控。 | 上游若自己新增忽略規則，直接合併在 fork 區塊之上；若上游自己也開始忽略同名檔案，刪掉本 fork 區塊裡重複的那一行；否則這個區塊維持不動。 |
| `ruff.toml` | `src` 陣列列出上游的七個套件目錄與 `examples`、`scripts`。 | `src` 陣列追加 `"tools"`，讓 `tools/` 底下的 import 排序（`I` 規則）也被檢查。 | `tools/` 是本 fork 新增的維護工具目錄，需要跟其他目錄一樣受 ruff 檢查。 | 上游若調整 `src` 陣列（增減目錄），保留 `"tools"` 這一項不動，其餘項目照上游版本；若上游自己也新增了工具目錄的檢查，比對後決定是否簡化。 |
| `requirements-dev.txt` | `-r requirements.txt` + `pytest==9.1.1` + `pytest-asyncio==1.4.0` + `ruff==0.16.3`。 | `ruff` 跟到 PyPI 當時最新的 `0.16.6`（已實測 `ruff check .` 與 `ruff format --check .` 在 219 檔案上零差異）；新增一行帶 `sys_platform == "win32"` 環境標記的 `tzdata==2026.3`，取代原本獨立的 `requirements-dev-windows.txt`（該檔已刪除）。 | 新政策不再因為「這是上游持有的宣告檔」就保留落後版本或另開繞道檔；`ruff` 升級對整個 repo 零影響，`tzdata` 只在 Windows 上安裝、不影響其他平台的解析結果。 | 上游若自己把 `ruff` 升到 ≥ 這裡釘的版本，直接採用上游版本、刪掉這列的 ruff 部分；若上游升到不同版本，取兩者較新者。`tzdata` 那一行只要上游沒有自己加等效的平台相依處理，就繼續保留；上游若自己處理了 Windows 時區問題，比對做法後決定是否移除這一行。 |
| `.github/workflows/ci.yml` | 三個 Action 用浮動 tag：`actions/checkout@v4`（×3）、`actions/setup-python@v5`（×2）、`actions/setup-node@v4`（×1）。 | 六處全部改成 commit SHA + `# vX.Y.Z` 註解（`actions/checkout` → `v7.0.1`、`actions/setup-python` → `v7.0.0`、`actions/setup-node` → `v7.0.0`），對齊本 fork 自有 workflow（`codeql.yml`、`dependency-freshness.yml`、`upstream-check.yml`）的釘選風格。 | 供應鏈安全基準：本 fork 自有的三支 workflow 已全部釘 SHA，讓上游持有的 `ci.yml` 繼續用浮動 tag 是不一致的風險缺口；新政策不再因為「這是上游檔案」就放著不管。 | 上游若自己把這些 Action 也改成釘 SHA，直接採用上游版本、刪掉這列；若上游升到更新版本，取兩者較新者，同時更新 `# vX.Y.Z` 註解與對應的 SHA。 |
| `commerce-common/commerce_common/agent_sdk.py` | `ensure_project_skills` 用裸的 `shutil.rmtree(entry)` 移除舊的 skill 副本。 | 抽出 `_remove_tree()`：刪除前先對整棵樹 `chmod(... \| S_IWRITE)` 清掉唯讀位，再 `shutil.rmtree`。 | 這是真實的可攜性缺陷不是本機問題：`copytree`（symlink 不可用時的 fallback）會連目錄 metadata 一起複製，副本因此帶著唯讀位；移除唯讀目錄在 Windows（`os.rmdir` 直接 `WinError 5`）與 POSIX（刪子項需要父目錄可寫）都會失敗，於是**下一次呼叫死在自己上一次做出來的副本上**。任何目錄帶唯讀位的 checkout 都會重現；OneDrive Files On-Demand 會對它管的每個目錄設這個位，本 fork 就是這樣踩到的（20 筆測試紅）。 | 上游若自己修掉（用 `onexc` handler、`chmod` 前置或改走別的策略），採用上游版本並刪掉本列；若上游改寫了 `ensure_project_skills` 的其他邏輯，把 `_remove_tree` 的等效前置重新套上去，**不要**退回裸 `rmtree`——`commerce-common/tests/test_agent_sdk.py::test_ensure_project_skills_replaces_a_read_only_copy` 會擋住。 |
| `commerce-common/tests/test_agent_sdk.py` | 沒有涵蓋「副本目錄帶唯讀位」的案例。 | 新增 `test_ensure_project_skills_replaces_a_read_only_copy`，把第一次產生的副本設成唯讀後再呼叫一次。 | 上一列的修正若沒有測試釘住，下次上游同步把 `_remove_tree` 蓋回裸 `rmtree` 是**靜默**的。已做突變驗證：改回 `shutil.rmtree` 這筆測試就紅。 | 與上一列同進退：上游自己修好就一起刪；上游改寫這支測試檔就把這個案例重新套上去。 |
| `commerce-common/tests/test_memory_stores.py` | `test_the_file_store_is_owner_only_and_keeps_purge_generations_across_instances` 無條件斷言 `stat.S_IMODE(path.stat().st_mode) == 0o600`。 | 該斷言包進 `if os.name != "nt":`，Windows 上跳過這一行，其餘斷言（purge generations 跨實例存續）在所有平台照常執行；不再用 `pytest --deselect` 整支跳過測試。 | Windows 沒有 POSIX owner/group/other 權限位語意，`os.open(..., 0o600)` 在 Windows 上不是這個平台驗證得了的承諾。新政策要求測試紅就改測試條件，不用 deselect 繞過，且要保留這支測試在 Windows 上仍能驗證的其餘行為。 | 上游若自己加上等效的平台條件（例如也改成 `if os.name != "nt"` 或 `sys.platform` 判斷），直接採用上游版本、刪掉這列；若上游修改了這支測試的其他邏輯，把同樣的平台條件寫法重新套用到新版本上。 |
| `examples/web-shared/storefront/orders.tsx` | `estimateOf` 用可在惡意長字串上產生超線性回溯的正規表示式拆分日期與括號註記。 | 改呼叫 `estimate.mjs` 的線性 parser，保留原本貪婪括號與換行處理語意，避免 `js/polynomial-redos`。 | 訂單的 `estimated_delivery` 會進入 storefront；即使正常資料很短，也不應讓外部字串觸發瀏覽器主執行緒的超線性耗時。 | 上游若改成其他可證明為線性的解析方式，採用上游版本並刪除本列；否則在同步時保留這段 parser 呼叫。 |
| `examples/package.json` | `build` 直接建置八個 workspace，沒有先跑 storefront 純函式測試。 | 新增 `prebuild`，以 Node test runner 執行 `estimate.test.mjs`。 | ReDoS 修補需要永久覆蓋舊 grammar 與惡意長輸入；只靠 build 不能驗證解析相容性。 | 上游若加入涵蓋同一 parser 的測試入口，整併到上游入口並刪除本列；否則保留 `prebuild`。 |
| `examples/retail/storefront-web/package.json` | 宣告 `"next": "^16.3.0"`。 | 宣告 `"next": "^16.3.4"`。 | `next@16.3.0` 落在兩個 CRITICAL 漏洞範圍：GHSA-2xp9-vwfh-vxw4（AVIF 觸發 Image Optimization API 未驗證 RCE）與 GHSA-p293-qw3h-jr36（**Windows 主機**未驗證 RCE），修補版 16.3.3。由本 fork 自己的 Dependabot 安全 PR `SanHsien/commerce-agents#2` 升級（`c85b697`），8 項必要檢查全過，合併後 GitHub 將三筆 alert 標為 fixed。同一個 PR 同時改了另外七個 web app 的 `package.json` 與 `examples/package-lock.json`，理由相同，見下方各列。 | 上游若自己把 `next` 宣告升到 ≥ `^16.3.4`，採用上游版本並刪掉本列；若上游升到更高版本，取兩者較新者。**不要**把宣告退回 `^16.3.0` 以求與上游零 diff——那會重新打開兩個 CRITICAL RCE。 |
| `examples/retail/merchant-web/package.json` | 宣告 `"next": "^16.3.0"`。 | 宣告 `"next": "^16.3.4"`。 | 與 `examples/retail/storefront-web/package.json` 同一次安全升級（`#2`，`c85b697`）。 | 與該列同進退。 |
| `examples/travel/storefront-web/package.json` | 宣告 `"next": "^16.3.0"`。 | 宣告 `"next": "^16.3.4"`。 | 與 `examples/retail/storefront-web/package.json` 同一次安全升級（`#2`，`c85b697`）。 | 與該列同進退。 |
| `examples/travel/merchant-web/package.json` | 宣告 `"next": "^16.3.0"`。 | 宣告 `"next": "^16.3.4"`。 | 與 `examples/retail/storefront-web/package.json` 同一次安全升級（`#2`，`c85b697`）。 | 與該列同進退。 |
| `examples/telecom/storefront-web/package.json` | 宣告 `"next": "^16.3.0"`。 | 宣告 `"next": "^16.3.4"`。 | 與 `examples/retail/storefront-web/package.json` 同一次安全升級（`#2`，`c85b697`）。 | 與該列同進退。 |
| `examples/telecom/merchant-web/package.json` | 宣告 `"next": "^16.3.0"`。 | 宣告 `"next": "^16.3.4"`。 | 與 `examples/retail/storefront-web/package.json` 同一次安全升級（`#2`，`c85b697`）。 | 與該列同進退。 |
| `examples/entertainment/storefront-web/package.json` | 宣告 `"next": "^16.3.0"`。 | 宣告 `"next": "^16.3.4"`。 | 與 `examples/retail/storefront-web/package.json` 同一次安全升級（`#2`，`c85b697`）。 | 與該列同進退。 |
| `examples/entertainment/merchant-web/package.json` | 宣告 `"next": "^16.3.0"`。 | 宣告 `"next": "^16.3.4"`。 | 與 `examples/retail/storefront-web/package.json` 同一次安全升級（`#2`，`c85b697`）。 | 與該列同進退。 |
| `examples/package-lock.json` | 解析 `next@16.3.0`、`sharp@0.35.3`（含 `@next/swc-*` 與 `@img/sharp-*` 平台套件）。 | 解析 `next@16.3.4`、`sharp@0.35.4`（含 `@img/sharp-win32-x64@0.35.4`），libvips 1.3.2 → 1.3.3。 | 同一次 Dependabot 安全升級（`#2`，`c85b697`）的鎖檔結果；`sharp@0.35.3` 另落在 GHSA-rgj7-g3m4-5g8c（HIGH，libheif）範圍，`next` 依賴 `sharp`，所以 `#2` 的鎖檔一併修掉，獨立的 sharp PR `#1` 因此以「由 #2 涵蓋」關閉。 | 上游若自己重新產生鎖檔，採用上游版本**前**先確認 `next` ≥ 16.3.3、`sharp` ≥ 0.35.4，並跑 `npm ci && npm run build` 與 `tools/dev_check.ps1`；兩者都達標就刪掉本列。鎖檔衝突時以重新 `npm install` 解，不要手動合併雜湊。 |
