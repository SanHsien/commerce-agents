[English](README.en.md) | 中文版

# Claude Commerce Agents

> **這是 [`anthropics/commerce-agents`](https://github.com/anthropics/commerce-agents) 的 Windows-first 維護型 fork**，沿用 Apache License 2.0 與完整 Git 歷史。產品行為跟隨上游；本維護線補上繁中文件、Windows 開發／驗收 gate，以及逐筆審查的上游追蹤。差異見 [`FORK.md`](FORK.md)，維護決策見 [`docs/DECISIONS.md`](docs/DECISIONS.md)。

Claude 上的兩個商務 agent 參考實作：一個**購物 agent**（給商家嵌進自己的 App，服務顧客），
一個**商家 agent**（給商家後台員工用）。每個 agent 的 prompt、skills、工具合約與安全閘門都只
定義一次，同時跑在 Messages API、Claude Agent SDK 與 Managed Agents 三條路徑上；四個可執行的
垂直領域範例（零售、旅遊、電信、娛樂）展示同一套函式庫在不同業態下的樣子。

> [!NOTE]
> 所有公司、品牌、產品與人物均為虛構，唯一的公司是 ACME。這個 repo 不會真的下單、不會真的
> 刷卡、不會真的改動上線中的商品：`checkout` 只把購物車渲染出來交給宿主完成，商家端的每一筆
> 寫入都要等人核准後才生效。商業規則、授權與合規是實際部署時要自己補上的。

## 快速開始：跑範例 demo

需要 Python 3.11+ 與 Node 22。

```bash
git clone https://github.com/SanHsien/commerce-agents.git && cd commerce-agents
python -m venv .venv && .venv\Scripts\activate       # Windows PowerShell；macOS/Linux 用 source .venv/bin/activate
pip install -r requirements.txt        # 七個套件與其釘選版本的依賴
copy .env.example .env                 # 填入 ANTHROPIC_API_KEY
cd examples && npm ci && cd ..         # 八個 Web App 共用一個 npm workspace
python scripts/run_demo.py retail      # API :8000 + 購物前台 :3000
```

`--merchant` 改成只啟動商家後台，`--all` 兩者都啟動。四個垂直範例：`retail`（前台 :3000／
後台 :3100）、`travel`（:3001／:3101）、`telecom`（:3002／:3102）、`entertainment`（:3003／
:3103）；各自的 README 附上可以在前台與後台試的對話開場。

## 快速開始：用 Claude Code plugin 蓋自己的 agent

`commerce-builder` plugin 會照這個 repo 的函式庫，針對你自己的系統生成一個 agent（或審查一個
既有的）：

```bash
claude plugin marketplace add SanHsien/commerce-agents
claude plugin install commerce-builder@claude-commerce-agents
claude
/scaffold-commerce-agent 幫我的商店建一個購物助理
```

其餘指令 `/add-commerce-flow`、`/author-commerce-evals`、`/review-commerce-agent` 見
[`plugins/commerce-builder/`](plugins/commerce-builder/)。

## 兩個 agent 是什麼

**購物 agent** 負責搜尋、比較、規劃、填購物車、回答訂單與政策問題，並記住顧客告訴它的事。
五個流程是 [`shopping-agent/skills/`](shopping-agent/skills/) 底下的 skills；部署方要在
[`StorefrontBackend`](shopping-agent/core/shopping_agent/backend.py) 上接上自己的商品、
購物車、訂單與政策系統。

**商家 agent** 負責解釋績效、維護商品頁、處理庫存與訂單警示、調價與促銷、草擬行銷活動；每一
筆寫入都是一筆待核准的變更，由宿主的核准介面套用。五個流程是
[`merchant-agent/skills/`](merchant-agent/skills/) 底下的 skills；部署方要在
[`MerchantBackend`](merchant-agent/core/merchant_agent/backend.py) 上接上自己的分析、商品、
庫存、定價與行銷系統。

## 目錄結構

| 目錄 | 內容 |
|---|---|
| [`commerce-common/`](commerce-common/) | 兩個角色共用的東西：設定、fencing、記憶、skills、grounding、呈現層、executor 框架、事件 |
| [`shopping-agent/core/`](shopping-agent/core/) | 購物型別、`StorefrontBackend`、prompt、工具合約、閘門、executor |
| [`shopping-agent/runtime-messages-api/`](shopping-agent/runtime-messages-api/) | `ShoppingAgent`，跑在 Messages API 上的對話迴圈 |
| [`shopping-agent/runtime-agent-sdk/`](shopping-agent/runtime-agent-sdk/) | 跑在 Claude Agent SDK 上的購物 agent，附一個 console |
| [`shopping-agent/managed-agents/`](shopping-agent/managed-agents/) | Managed Agents 用的 manifest 與購物前台 MCP server |
| [`merchant-agent/core/`](merchant-agent/core/) | 商家型別、`MerchantBackend`、prompt、工具合約、變更護欄、閘門、executor |
| [`merchant-agent/runtime-messages-api/`](merchant-agent/runtime-messages-api/) | `MerchantAgent` 與跑在 Messages API 上的分析代理 |
| [`merchant-agent/runtime-agent-sdk/`](merchant-agent/runtime-agent-sdk/) | 跑在 Claude Agent SDK 上的商家 agent，附一個會核准變更的 console |
| [`merchant-agent/managed-agents/`](merchant-agent/managed-agents/) | Managed Agents 用的 manifest、商家 MCP server、排程摘要 |
| [`examples/`](examples/) | 四個垂直範例，共用 host 程式碼（`demo_common/`）與共用 Web 程式碼（`web-shared/`） |
| [`plugins/commerce-builder/`](plugins/commerce-builder/) | Claude Code plugin |
| [`docs/`](docs/) | `safety.md`（安全規則清單）、`backends.md`（怎麼接自己的系統）、`deployment.md`（其他平台） |
| [`tests/`](tests/) | 跨套件的測試；每個套件也有自己的 `tests/` |
| [`scripts/`](scripts/) | `install.sh`、`run_demo.py`、`smoke_chat.py`、`screenshot_tour.py`、`check.py`、`deploy_managed_agent.sh`、`verify_all.py` |

完整介面細節（三種跑法、安全機制、四個垂直範例、部署到其他平台）見英文原版
[`README.en.md`](README.en.md)；那份文件是上游持有的鏡像，本 fork 不覆寫它，維護範圍見
[`FORK.md`](FORK.md)。

## 驗證

```powershell
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\check.py
```

`requirements-dev.txt` 額外裝 pytest、ruff與本 fork 的維護工具依賴（均為 stdlib，無新增
runtime 依賴）。本 fork 的 Windows 一鍵 gate 是 [`tools/dev_check.ps1`](tools/dev_check.ps1)。

## 授權

原始著作權 2026 Anthropic PBC，以 [Apache License 2.0](./LICENSE) 授權；這是一份參考實作，
不由 Anthropic 維護、也不接受回貢。本 fork 的授權與來源說明見 [`NOTICE.md`](NOTICE.md)。
