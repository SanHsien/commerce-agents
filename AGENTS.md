# AGENTS.md

本檔是所有 AI coding agent（Claude Code、Cursor、Copilot 等）在
`SanHsien/commerce-agents` 這個 fork 工作時的**單一真相源**。`CLAUDE.md` 只放一段指回本檔
的薄補丁，不重複這裡的規則；上游 `anthropics/commerce-agents` 沒有 `AGENTS.md`，本檔是這條
維護線自己建立的。

## 這個 repo 是什麼

Claude 上兩個商務 agent 的參考實作：**購物 agent**（給商家嵌進顧客端 App）與**商家 agent**
（給商家後台員工用）。每個都只定義一次（prompt、skills、工具合約、閘門），同時跑在 Messages
API、Claude Agent SDK、Managed Agents 三條路徑上；四個垂直範例（`retail`／`travel`／
`telecom`／`entertainment`）展示同一套函式庫。完整介面說明見 [`README.en.md`](README.en.md)
（上游持有的原檔）與 [`README.md`](README.md)（本 fork 的繁中版）。

### 目錄速查

- `commerce-common/commerce_common/`：兩個角色共用的東西。
- `shopping-agent/core/shopping_agent/`：型別、`StorefrontBackend`、設定、prompt、`tools/`、
  閘門、enrichment、executor。
- `merchant-agent/core/merchant_agent/`：商家對應版，外加 `changes.py`、`analysis.py`。
- `*/skills/`：每個角色五個流程，各一個 `SKILL.md`。
- `*/runtime-messages-api/`、`*/runtime-agent-sdk/`、`*/managed-agents/`：三條跑法。
- `examples/<vertical>/`：`api/`、`data/`、`storefront-web/`、`merchant-web/`。
- `plugins/commerce-builder/`：Claude Code plugin。
- `docs/`：`safety.md`、`backends.md`、`deployment.md`。`scripts/`：安裝、demo、smoke、
  截圖、check、deploy、verify。
- `tests/`：跨套件測試；各套件也有自己的 `tests/`。

### 設計規則（沿用上游，不因本 fork 改變）

- 一個模型負責整段對話；規則依出現頻率放進工具描述、prompt 或 skill。
- 靜態 prompt 與 `tools[]` 每一輪的 bytes 都相同；逐次請求的資料放在斷點後的 fenced block。
- UI 是經伺服器驗證與填值、以 `ui` 事件串流出去的呈現層工具呼叫。
- 第三方內容一律圈在 fence 裡；寫入操作有出處閘門與程式碼上限；`checkout` 不收費；商家端寫入
  只透過宿主核准生效。
- Core 與業態無關；垂直範例透過 `PresentationExtension` 加 UI，其餘留給自己。
- 每個機制只定義一次（在 `commerce_common` 或某個角色 core），三條路徑共用。

### 慣例（沿用上游）

- Python 3.11+、`ruff`（根目錄 `ruff.toml`）、`pytest`（根目錄 `pytest.ini`）、型別標註、
  `pydantic` schema；Web app 是 Next.js + TypeScript。
- 只有 ACME 這一家虛構公司；deployment/整合目標（README 的 MCP connectors 一節、
  `docs/deployment.md` 的平台與 SDK 名稱）與 CC0 分類圖片是例外。
- 改動 prompt 文字、工具描述、skill 或 fence 提示會讓 `system.md` 需要重新推導；
  `scripts/check.py` 會比對。

## Fork 維護規則（SanHsien 維護線）

> 本節只適用於 `SanHsien/commerce-agents`（本 fork）。上游 `anthropics/commerce-agents`
> 沒有這一節，也不接受回貢（它自己在 README 說「不維護、不接受貢獻」）。

- **對外只打 `origin`**：commit、push、release 一律指向 `SanHsien/commerce-agents`，唯一
  例外是維護者在**當次對話**明確同意回貢上游。`gh` 在 fork clone 的預設 repo就是上游，先
  `gh repo set-default SanHsien/commerce-agents`；`.cursor/rules/no-upstream-pr.mdc` 有機器
  可讀版本。
- **不開分支、不開 PR**：日常修改驗證通過後直接推 `origin/main`；`upstream/main` 只 fetch、
  不推送、不 force-push、不刪除。
- **Windows 開發環境**：`python -m venv .venv` 後裝 `requirements-dev.txt`。Windows 版
  CPython 沒有系統 IANA 時區資料庫，`requirements-dev.txt` 已經直接內建一行帶
  `sys_platform == "win32"` 環境標記的 `tzdata`（只在 Windows 安裝），不再需要另一份
  Windows 專屬的 requirements 檔——這是 2026-09-05 的政策轉向，見
  [`docs/DIVERGENCE.md`](docs/DIVERGENCE.md) 與 [`docs/DECISIONS.md`](docs/DECISIONS.md)。
- **已知的 Windows 平台限制（不是回歸，已修測試條件而非繞過）**：
  `commerce-common/tests/test_memory_stores.py::test_the_file_store_is_owner_only_and_keeps_purge_generations_across_instances`
  原本無條件斷言檔案權限是 POSIX 的 `0o600`，Windows 沒有這個語意。本 fork 把這一行斷言
  包進 `if os.name != "nt":`，其餘斷言（purge generations 跨實例存續）在 Windows 上照常
  驗證；**不再用 `pytest --deselect` 整支跳過**。登記與判準見
  [`docs/DIVERGENCE.md`](docs/DIVERGENCE.md)。
- **Windows 本機與 CI 的 canonical gate** 是 [`tools/dev_check.ps1`](tools/dev_check.ps1)：
  `ruff check` → `ruff format --check` → `pytest` → `python scripts/check.py` →
  `tools/check_links.py` → `tools/check_divergence.py` → `tools/check_pin_bounds.py`；上游既有的
  `.github/workflows/ci.yml`（Ubuntu，兩個 Python 版本 + web build + no-pypi-fallback）維持
  不動的部分，見 [`docs/DIVERGENCE.md`](docs/DIVERGENCE.md) 例外（釘選的 Action SHA 已改）。
- **上游同步**：`tools/check_upstream_updates.py` 讀寫 `tools/upstream_baseline.json` 的
  commit／PR／issue 三軸水位，PR／issue 一律用 `--state all` 查。上游關閉了 GitHub Issues，
  issue 軸恆回報「未檢查」而非「沒有新項目」，兩者不可混為一談。決策記錄見
  [`docs/DECISIONS.md`](docs/DECISIONS.md)，同步流程見 [`FORK.md`](FORK.md)。
- **依賴新鮮度**：`tools/check_dependency_freshness.py` 查兩個來源——
  `requirements-dev.txt` 對 PyPI、`.github/workflows/*.yml` 裡釘選的 GitHub Action 對
  Releases API。`examples/package-lock.json` 的 npm 依賴不查（不同生態系，交給 Dependabot）。
- **Dependabot 三個生態系全開**（`pip`／`npm`／`github-actions`，上限 5），靠三件事不亂炸：
  `groups`（一次一個 PR，不是一個 pin 一個 PR）、`ignore` 七個 in-repo 套件（它們從本地路徑
  安裝且**未註冊在公開索引**，`ci.yml` 的 `no-pypi-fallback` job 專門守這件事——針對這七個
  名字的升級提案只可能來自搶註者，一律不接）、以及
  [`tools/check_pin_bounds.py`](tools/check_pin_bounds.py)。
- **`tools/check_pin_bounds.py` 是唯一擋得住「pin 掉出宣告範圍」的檢查**：`scripts/check.py`
  **完全沒有讀 `requirements.txt`**，只看七個 `pyproject.toml` 之間的 sibling pin 一致性；
  第三方套件在 pyproject 是範圍（`anthropic>=0.91`，以及唯一的上界 `ruff>=0.15,<0.17`），
  在 requirements 是 exact pin，過去沒有東西比對兩者。此檢查跑在每個 PR
  （`.github/workflows/pin-bounds.yml`）與本機 gate 上。pin 掉出範圍時**把 pyproject 的範圍
  在同一個變更裡一起提高並登記分岔**，不要關掉檢查。
- **Dependabot PR 一律人工讀 diff 後合併，不開 auto-merge。**
- **產品內容以上游為準，但依賴與釘選版本直接跟上游最新版走**：`commerce-common/`、
  `shopping-agent/`、`merchant-agent/`、`examples/`、`plugins/`、`.claude-plugin/`、
  `docs/{safety,backends,deployment}.md`、`scripts/`、`requirements.txt`、`pytest.ini`、
  `.env.example`、`LICENSE` 不因本線維護需求改寫。`requirements-dev.txt`（ruff 版本、
  `tzdata`）與 `.github/workflows/ci.yml`（三個 Action 釘 SHA）**有**已記錄的 fork
  修正——2026-09-05 起不再因為「這是上游持有的檔案」而保留落後版本或繞道，登記與跟進上游時
  的判準見 [`docs/DIVERGENCE.md`](docs/DIVERGENCE.md)，由
  [`tools/check_divergence.py`](tools/check_divergence.py) 機器強制此表與實際改動一致。
- **文件語言**：本 fork 新增的維護文件（本檔、`FORK.md`、`NOTICE.md`、`README.md`、
  `CHANGELOG.md`、`docs/DECISIONS.md` 等）用繁體中文；產品程式碼、prompt、skill、範例的語言
  跟隨上游（英文），不因本線需求翻譯。
- **測試綠了才准提交**：`pytest -q` 全綠、`ruff check .`／`ruff format --check .` 無錯，才能
  `git commit` 再 `git push origin main`；不可用 `;` 把驗證與 commit 串成一行繞過檢查。
