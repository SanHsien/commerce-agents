# Fork 維護說明

本 repo fork 自 [`anthropics/commerce-agents`](https://github.com/anthropics/commerce-agents)，
沿用 Apache License 2.0 與完整 Git 歷史。

## 為什麼維護 fork

- 保留上游持續更新的購物／商家 agent 參考實作（三條跑法路徑、四個垂直範例、一個 Claude Code
  plugin）。
- 採 Windows-first 維護：Windows 11 + PowerShell 是主要開發、除錯與完整驗收環境。
- 公開入口改以繁體中文為主，英文原文鏡像放 `README.en.md`。
- 建立可重現的 Windows 開發 gate，以及逐筆審查的上游追蹤（commit／PR／issue 三軸）。
- 產品程式碼、prompt、skills、範例、plugin 仍以上游為準，不因本線需求改寫成維護索引。

**回貢判準：修的是上游的 bug 就送回去；這裡獨創的文件與 Windows 維護骨架留在這裡。**

## 與上游的差異

| 項目 | 說明 |
|---|---|
| `README.md` | 繁中主檔；英文原文在 `README.en.md`（`git mv` 保留，只加了一行語言列） |
| `CLAUDE.md` | 最上方加一節 fork 邊界（指向 `AGENTS.md`、不對上游開 PR、繁中回覆），其餘上游內容原封不動 |
| `AGENTS.md` | 新增：AI agent 的單一真相源，尾端一節本 fork 的維護規則 |
| `NOTICE.md` / `FORK.md` | 新增：來源、Apache-2.0 授權說明、同步策略 |
| `CHANGELOG.md` / `CHANGELOG.en.md` | 新增：只記本 fork 自己的維護歷史，不記上游的 |
| `SECURITY.md` / `CONTRIBUTING.md` / `CODE_OF_CONDUCT.md` | 新增：短版，針對本 fork 的維護範圍 |
| `.editorconfig` / `.gitattributes` | 新增：2 空格（`.py`/`.ps1` 4 空格）、LF 換行 |
| `.cursor/rules/no-upstream-pr.mdc` | 新增：機器可讀的「對外只打 origin」規則 |
| `.github/dependabot.yml` | 新增：`github-actions` 正常開 PR；`pip`（根）與 `npm`（`/examples`）因為是上游持有的 pin 檔，`open-pull-requests-limit: 0` |
| `.github/dependency-deferrals.json` | 新增：依賴新鮮度檢查的「已審查、暫不處理」記錄，初始為空結構 |
| `.github/workflows/dependency-freshness.yml` | 新增：每月檢查 `requirements-dev.txt` 對 PyPI、workflow 釘選的 Action 對 GitHub Releases |
| `.github/workflows/upstream-check.yml` | 新增：每週對 `upstream/main` 做未審查 commit／PR／issue 檢查 |
| `.github/workflows/codeql.yml` | 新增：CodeQL 掃描 `python` 與 `javascript-typescript` |
| `tools/check_dependency_freshness.py` | 新增：見上 |
| `tools/check_upstream_updates.py` | 新增：讀寫 `tools/upstream_baseline.json` 的四面向水位（commit／PR／issue／已知分支清單） |
| `tools/check_links.py` | 新增：維護文件之間的相對連結檢查 |
| `requirements-dev-windows.txt` | 新增：`-r requirements-dev.txt` 再加 `tzdata`。Windows 版 CPython 沒有系統 IANA 時區資料庫，少了它有 4 個上游時鐘測試在本機紅。獨立成檔而不是改上游的 `requirements-dev.txt`，讓上游那份保持零 diff |
| `tools/dev_check.ps1` | 新增：Windows 本機一鍵 gate（時區資料庫前檢 → ruff → ruff format → pytest → `scripts/check.py` → `check_links.py`），並 deselect 一個 Windows 沒有 POSIX 權限語意而恆紅的上游測試 |
| `tools/upstream_baseline.json` | 新增：見 [`docs/DECISIONS.md`](docs/DECISIONS.md) |
| `tests/test_fork_*.py` | 新增：上面三支工具的合約測試（`fork_` 前綴避免撞上游 `tests/` 檔名） |
| `docs/DECISIONS.md` | 新增：本 fork 的維護決策記錄 |
| `ruff.toml` | 修改：`src` 陣列追加 `"tools"`（讓 `tools/` 的 import 排序正確） |
| `.gitignore` | 修改：append 一個 fork 區塊，忽略兩份生成報告 |

產品 `commerce-common/`、`shopping-agent/`、`merchant-agent/`、`examples/`、`plugins/`、
`.claude-plugin/`、`docs/{safety,backends,deployment}.md`、`scripts/`、`conftest.py`、
`requirements.txt`、`requirements-dev.txt`、`pytest.ini`、`.env.example`、
`.github/workflows/ci.yml`、`LICENSE` 以上游為準，除非有已記錄的 fork 修正——目前沒有。
Windows 需要的額外依賴走本 fork 自己的 `requirements-dev-windows.txt`，不改上游那兩份。

## 分支與 remote

- `origin/main`：SanHsien 維護線，也是唯一長期分支。
- 日常修改直接推 `origin/main`。不開功能分支、不開 PR；這是單人維護 fork，分支與 PR 沒有第二
  審查者，只增加同步成本。
- `upstream/main`：Anthropic 原始專案，只追蹤、不推送、不 force-push、不刪除。
- 上游目前只有 `main` 一個分支（見 `tools/upstream_baseline.json` 的 `branches` 欄位）；日後
  上游若新增分支，`tools/check_upstream_updates.py` 的報告不會自動偵測，要靠
  `upstream-check.yml` 每週跑一次 `gh api repos/anthropics/commerce-agents/branches` 人工核對
  （見 [`docs/DECISIONS.md`](docs/DECISIONS.md) 該項限制的記錄）。

不要 `git push upstream`，不要 `gh pr create` 對 `anthropics/commerce-agents`。

## 上游同步怎麼做

1. `git fetch upstream`。
2. 跑 `tools/check_upstream_updates.py --strict`（或等每週的 `upstream-check.yml` 開 issue）。
3. 對每一筆新 commit／PR／issue，決定「引用」或「不引用」，理由寫進
   [`docs/DECISIONS.md`](docs/DECISIONS.md)。
4. 引用的話，`git cherry-pick` 或手動移植，保留原作者署名；跑完整驗證（見
   [`README.md`](README.md) 的「驗證」一節）再推。
5. 決策完成後才推進 `tools/upstream_baseline.json` 的 `reviewed_through` /
   `reviewed_pr_through` / `reviewed_issue_through`；不要在還沒審查完就推進水位。

上游 `anthropics/commerce-agents` 目前關閉了 GitHub Issues（`gh issue list` 會回報 repo 已停用
issue），所以 issue 軸的檢查在這個上游上恆為「未檢查」，不是「沒有新項目」——
`tools/check_upstream_updates.py` 會把兩者分開報告，不要混為一談。

## 換一台電腦怎麼開發

```powershell
git clone https://github.com/SanHsien/commerce-agents.git
cd commerce-agents
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements-dev.txt
pwsh -NoProfile -File tools\dev_check.ps1
```

只想跑 demo、不開發維護工具時，見 [`README.md`](README.md) 的「快速開始」章節。
