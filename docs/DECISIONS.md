# 維護決策

## 2026-09-05：建立 Windows-first 維護型 fork

**決定**：fork `anthropics/commerce-agents`，保留 Apache License 2.0 與完整 Git 歷史，預設分支
維持 `main` 以降低與上游同步摩擦。本線聚焦繁中公開入口、Windows 開發 gate，以及逐筆審查的上游
追蹤。

**理由**：上游是一份設計完整的商務 agent 參考實作（購物／商家兩個角色、三條跑法、四個垂直
範例、一個 Claude Code plugin），符合維護者用 Claude Code 落地商務 agent 架構的需求。缺的是
Windows 11 上可重現的開發／驗收骨架，以及繁中入口。授權是 Apache License 2.0，fork 修改同樣
走 Apache 2.0（見 `NOTICE.md`）。

**限制**：

- 不把 fork 包裝成原創專案，不移除 Anthropic 的著作權與 Apache 2.0 標示。
- `commerce-common/`、`shopping-agent/`、`merchant-agent/`、`examples/`、`plugins/`、
  `.claude-plugin/`、`docs/{safety,backends,deployment}.md`、`scripts/` 保持產品內容，不用
  維護索引覆寫。
- 上游更新必須逐筆審查（commit／PR／issue 三軸都要看，見下方「上游同步基準」一節）。
- 不回貢，除非維護者在當次對話明確同意；上游本身聲明「這是參考實作，不維護、不接受貢獻」，
  門檻因此更高。

## 2026-09-05：維護線直接推 main，不開分支不開 PR

**決定**：fork 維護不開功能分支。改完在本機跑 `tools/dev_check.ps1`，通過後直接推
`origin/main`。遠端只留 `main`；`upstream/main` 只追蹤、不推送。

**理由**：這是單人維護 fork，分支與 PR 沒有第二審查者，只增加同步成本。

**限制**：Dependabot 仍可能對 `github-actions` 生態開 PR，讀 diff 後再合併，不自動合併；不推
`upstream`，不 force-push `main`，不刪 `upstream` remote。

## 2026-09-05：`CLAUDE.md` 只在最上方加一段薄補丁，不整檔重寫

**決定**：`CLAUDE.md` 只在檔案最上方插入一個 5～10 行的 fork 邊界區塊（指向 `AGENTS.md`
為單一真相源、聲明不對上游開 PR、聲明繁中回覆），原本上游的內容原封不動保留在補丁下方。

**理由**：`CLAUDE.md` 是上游持有的產品文件，內容是給任何 clone 這個 repo 的 agent 看的設計
規則（layout、design rules、conventions、verify 指令），這些規則本身跟「這是不是 fork」無關，
上游改版時會直接覆蓋——如果本 fork 把整份 `CLAUDE.md` 改寫成維護索引，等於每次上游更新
`CLAUDE.md` 都要手動重新合併兩份完全不同結構的文件，衝突成本高。改成單一真相源
（`AGENTS.md`，本 fork 自己的檔案，上游不會動）＋`CLAUDE.md` 只加薄補丁，上游更新
`CLAUDE.md` 時可以幾乎無腦地在補丁下方重新貼上新內容，衝突面只剩一個固定的插入點。

## 2026-09-05：`.github/dependabot.yml` 的 `pip` 與 `npm` 生態系 `open-pull-requests-limit: 0`

**決定**：`github-actions` 生態系正常開 PR（上限 5）；`pip`（根目錄）與 `npm`
（`examples/`）兩個生態系 `open-pull-requests-limit: 0`，只保留 GitHub 安全性更新
（Dependabot alerts）獨立生效，不受這個設定影響。

**理由**：`requirements.txt` 與 `examples/package-lock.json` 都是**上游持有的鎖定檔**，鎖的
是「這個版本的上游程式碼實測過」這件事，不是本 fork 的依賴選擇。`requirements.txt` 額外還有
一個結構性理由：七個套件彼此用 `==<version>` 互相釘死（`scripts/check.py` 的
`check_package_versions` 會檢查這件事），Dependabot 例行版本 PR 一次只會動一個套件，很容易
把某個 sibling pin 動出鎖定範圍，製造一個 CI 會炸、但看起來像「正常的相依性更新」的假 PR。
版本要不要動是上游的決定，不是這條維護線該自己決定的事。`github-actions` 沒有這個結構性
耦合，PR 之間彼此獨立，維持正常開放。

**限制**：GitHub 的安全性更新（Dependabot security updates）與 `open-pull-requests-limit`
無關，仍會照常對這兩個生態系開 PR；出現時照樣要讀 diff 才能合併，不能因為「這是安全性 PR」
就跳過驗證。

## 2026-09-05：依賴新鮮度檢查涵蓋 `requirements-dev.txt` 與 GitHub Actions，`examples/package-lock.json` 排除在外

**決定**：`tools/check_dependency_freshness.py` 查兩個來源——`requirements-dev.txt` 裡
`pytest`／`ruff` 的下限對 PyPI，以及 `.github/workflows/*.yml` 裡每一個
`uses: owner/repo@<sha> # vX.Y.Z` 對 GitHub Releases API。`requirements.txt`（上游的七個套件
互相釘死的 exact pin）與 `examples/package-lock.json`（npm workspace lockfile）都不查。

**理由**：這支腳本回答的問題是「這條維護線自己宣告的下限，落後最新版本多少？」——`>=` 下限
才有「落後多少」這個概念；`requirements.txt` 裡每一條都是 `==` 精確釘選，是上游測試過的組合，
不是本 fork 宣告的相容性承諾，拿它跟 PyPI 最新版比較沒有意義，只會製造噪音。
`examples/package-lock.json` 同理是上游的 npm 鎖定檔，而且是完全不同的生態系（Node，不是
Python）；讓一支只吃 `requirements-dev.txt` 與 workflow YAML 的 stdlib 腳本去解析
`package-lock.json` 是拿一個問題硬套另一個工具，而不是延伸腳本的自然範圍。npm 那一側的漂移
交給 `.github/dependabot.yml` 的 `npm` 生態系與 GitHub 安全性更新獨立處理（見上一項決策）。

**限制**：不查 Action 執行時安裝的間接依賴（例如 `actions/setup-node` 內部拉的 Node 版本）；
只查工作流程檔裡明文釘選的 Action 本身。

## 2026-09-05：上游關閉 Issues；`tools/check_upstream_updates.py` 用第三種狀態區分「關閉」與「查不到」

**決定**：`collect_new_tickets` 在 `gh` 回報「repository has disabled issues」（或
disabled pull requests）時回傳一個獨立的 `DISABLED` 標記，不是既有的 `None`。報告上仍然顯示
「未檢查」，但 `main()` 不會把 `DISABLED` 當成檢查失敗——只有真正的 `None`（缺 token、網路
問題、baseline 的 repo URL 解析不出來）才會讓 `upstream-check.yml` 回報失敗並要求人工介入。

**理由**：`anthropics/commerce-agents` 這個上游本身關閉了 GitHub Issues
（`gh issue list --repo anthropics/commerce-agents` 回報
`the 'anthropics/commerce-agents' repository has disabled issues`）。這是上游倉庫一個**永久、
結構性**的事實，不是一次性的檢查故障。範本原本的設計（`gh` 失敗一律回傳 `None`，`main()` 對
任何 `None` 都 fail closed）在這個上游上會讓每週排程的 `upstream-check.yml` **永遠**回報失敗，
訓練維護者把紅燈當雜訊直接忽略——這正是 fail-closed 設計想避免的結果。加一個第三態讓「這個
上游本來就沒有這個功能」與「這次檢查不了，可能是真的問題」分開處理，紅燈才會保留它原本的
訊號價值。

**限制**：這個判斷是字串比對 `gh` 的錯誤訊息（`"disabled issues"` / `"disabled pull requests"`），
如果 `gh` 未來改變錯誤訊息文字，這裡會退化回「查不到」而 fail closed——退化方向是安全的（多報
一次錯誤，不是漏報一次真正的停用）。

## 2026-09-05：`.github/dependency-deferrals.json` 覆蓋四筆「本 fork 不能直接改」的落後宣告

**決定**：初次跑 `tools/check_dependency_freshness.py` 就對四個項目加上 deferral，而不是修檔
案讓它們變綠：

- `ruff`（`requirements-dev.txt` 釘的是 `0.16.3`，PyPI 當時最新是 `0.16.6`）；
- `actions/checkout`、`actions/setup-python`、`actions/setup-node`（都只出現在上游自有的
  `.github/workflows/ci.yml`，分別釘浮動的 `@v4`／`@v5`／`@v4`，GitHub Releases 當時最新是
  `7.0.1`／`7.0.0`／`7.0.0`）。

**理由**：`requirements*.txt` 與 `.github/workflows/ci.yml` 兩者都在本次任務規格的「不要動」
清單裡，本 fork 不能為了讓檢查變綠去動這兩個檔案；但它們宣告的版本確實落後，直接放著不管會讓
`dependency-freshness.yml` 從第一次跑就紅、而且永遠紅，因為沒有人會去動一個「不該動」的檔案。
Deferral 而不是 hold：因為這不是「我們review過決定就是要這個版本」的政策宣告，而是「這是上游的
檔案，版本落後是上游的決定，不是本線要做的決定」——`deferredLatest` 設成觀測到的當下最新版，
上游哪天自己升版超過這個數字，deferral 就自動失效，檢查會再次要求覆核，不會變成永久靜音。
本線自己新增的三支 workflow（`codeql.yml`／`dependency-freshness.yml`／`upstream-check.yml`）
已經釘選各自 Action 的最新 SHA，不受影響。

**限制**：`ruff` 的 deferral 只延後「要不要跟上 PyPI 最新版」的問題，不代表本機開發環境
（`.venv`）裝的就是舊版——`pip install -r requirements-dev.txt` 裝的是 `requirements-dev.txt`
釘的版本，deferral 只影響這支檢查腳本的報告，不影響實際安裝。

## 2026-09-05：上游同步基準（`tools/upstream_baseline.json`）

**基準**：建立時 `upstream/main` 與 `origin/main` 同一個 commit
`fd4d59224ab96b43c6dc6888207c67b3bd5a24cf`（"building commerce agents using claude"，
2026-08-31）；`reviewed_date` 記為 `2026-09-05`（本次 fork 落地日）。`gh api
repos/anthropics/commerce-agents/branches` 確認上游只有 `main` 一個分支。上游當時有四個
open 的 pull request（`#1`–`#4`），依循範本的慣例（見「建立 Windows-first 維護型 fork」一項
決策的精神），基準只記錄「以此為起點」，不追溯要求逐一 triage 建立前就存在的既有 PR，只有
之後新開的才算「未審查」；因此 `reviewed_pr_through` 設為 `4`。上游沒有 Issues 可查，
`reviewed_issue_through` 設為 `0` 且不具意義（見上一項決策）。

**下一次同步時要做的事**：`git fetch upstream`，跑 `tools/check_upstream_updates.py --strict`
或讀 `upstream-check.yml` 開的 issue，對每一筆新 commit／PR 決定引用或不引用並記錄在本檔，
驗證通過後才推進 `reviewed_through` / `reviewed_pr_through`。
