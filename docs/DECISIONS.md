# 維護決策

## 2026-09-05：Windows 的測試落差用「加一支 fork 自有的 requirements」與「deselect」處理，不改上游檔

> ⚠️ **本決策已被下方「2026-09-05：依賴與測試條件政策轉向」取代。** 保留原文於此作為歷史
> 記錄，不刪除；本 fork 現在的實際做法是把 `tzdata` 直接併入 `requirements-dev.txt`、把
> POSIX 權限斷言改成平台條件式測試，不再維護 `requirements-dev-windows.txt`、不再用
> `--deselect`。見下方新決策與 [`docs/DIVERGENCE.md`](DIVERGENCE.md)。

**背景**：在 Windows 11 上跑 `pytest -q`，1145 筆裡有 5 筆紅，全部落在上游測試檔：

- 4 筆（`tests/test_turn_loop.py` 三筆、`merchant-agent/runtime-messages-api/tests/test_scheduled_digest.py`
  一筆）是 `ValidationError: unknown IANA timezone: 'Europe/Lisbon'`。Windows 版 CPython
  不隨附系統 IANA 時區資料庫，`zoneinfo.ZoneInfo` 因此對每個具名時區都失敗；上游 CI 跑
  Ubuntu，系統有 `/usr/share/zoneinfo`，所以上游從來看不到這件事。
- 1 筆（`commerce-common/tests/test_memory_stores.py::test_the_file_store_is_owner_only_and_keeps_purge_generations_across_instances`）
  斷言 `stat.S_IMODE(...) == 0o600`，實得 `0o666`。Windows 沒有 POSIX 的 owner/group/other
  權限位，這是平台語意差異，不是程式錯誤。

**決定**：

1. 時區那 4 筆：新增 fork 自有的 `requirements-dev-windows.txt`（`-r requirements-dev.txt`
   ＋ `tzdata==2026.3`）。實測裝上後 4 筆全綠（1144 passed / 1 failed）。
2. 權限那 1 筆：由 `tools/dev_check.ps1` 用 `--deselect` 排除，並在 `AGENTS.md`、`README.md`
   寫明它是平台限制而非回歸，以上游 Ubuntu CI 的結果為準。

**理由**：兩個做法的共同點是**上游檔案零 diff**。改 `requirements-dev.txt` 加一行
`tzdata`、或在上游測試檔加 `@pytest.mark.skipif(sys.platform == "win32")`，都會在每次
上游同步時變成衝突點，而且是那種「衝突內容看起來無害、於是被隨手解掉」的高風險型。
`tzdata` 是測試環境依賴（由標準函式庫載入，repo 裡沒有任何套件 import 它），本來就不該
進 `requirements.txt`。deselect 寫在 fork 自有的 gate 腳本裡，上游怎麼改那支測試都不影響。

**代價與防呆**：多一支 pin 檔就多一個會靜默老化的宣告，所以
`tools/check_dependency_freshness.py` 的 `REQUIREMENT_FILES` 同步收錄它，
`tests/test_fork_dependency_freshness.py::test_every_fork_owned_requirements_file_is_checked`
把「檔案存在 × 有被檢查 × `tzdata` 確實來自這支檔」釘成契約——把該檔從
`REQUIREMENT_FILES` 拿掉，這筆測試就紅。

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

## 2026-09-05：`pip` 與 `npm` 也開放 Dependabot，用分組與 pin-bounds 檢查取代「關掉」

**決定**：三個生態系全部正常開 PR（上限 5）。`pip` 與 `npm` 從 `open-pull-requests-limit: 0`
改為 `5`，並加上三道防護：

1. **`groups`**：一次跑一個 PR，不是一個 pin 一個 PR。42 個 exact pin 若不分組會產生最多
   42 個 PR，每個看起來都合理、合起來沒人審得動。`pip` 分成 `python-dev-tools`
   （pytest／ruff／tzdata）與 `python-runtime`（其餘）兩組，因為升 lint 工具與升 runtime
   套件是兩種不同的審查：一個賭閘門，一個賭產品。`npm` 依 `dependency-type` 分 dev／production。
2. **`ignore` 七個 in-repo 套件**：它們從本地路徑 `-e ./...` 安裝、彼此 exact pin，
   `scripts/check.py` 已經在管，而且 `ci.yml` 的 `no-pypi-fallback` job 專門斷言這七個名字
   **沒有註冊在公開索引上**——所以任何針對這七個名字的升級提案只可能來自搶註者，一律不接。
3. **`tools/check_pin_bounds.py`**：比對兩份 requirements 的 exact pin 與所有
   `pyproject.toml` 宣告的範圍，pin 掉出範圍就紅。跑在 `.github/workflows/pin-bounds.yml`
   的**每一個 PR**上，以及本機 `tools/dev_check.ps1`。

Dependabot 的 PR 一律人工讀 diff 後合併，不開 auto-merge。

**訂正一筆先前的錯誤判斷**：本檔原先寫「Dependabot 例行 PR 會把某個 sibling pin 動出鎖定
範圍，製造 CI 必炸的假 PR」——**這是錯的**。實際查證：`scripts/check.py` 從頭到尾沒有讀
`requirements.txt`（`grep -n requirements scripts/check.py` 零命中），`check_package_versions`
只讀七個 `pyproject.toml`；而那七個套件在 requirements 裡是 `-e ./path` 形式，Dependabot
不會、也無法對它們提出版本升級。當時的「必炸」是憑檔案結構推測、沒有實際讀那支檢查程式就
下的結論。真正存在的風險只有三個（PR 數量、pin 掉出 pyproject 宣告範圍、搶註者對七個名字
提案），上面三道防護各對應一個。

**保留的舊決定與理由**（作為歷史）：原本 `pip`／`npm` 設 `0`，理由是「鎖檔鎖的是上游實測過的
組合，版本要不要動是上游的決定」。政策轉向後這個理由不成立——本 fork 現在自己決定版本，
測試紅就修，差異登記在 [`DIVERGENCE.md`](DIVERGENCE.md)。

**限制**：

- `tools/check_pin_bounds.py` 只比對**宣告與 pin 的一致性**，不保證新版本行為相容——那是
  `pytest`、`scripts/check.py` 與 `ci.yml` 的 `web` build 的工作。三者都綠才算可合併。
- 它的版本比較只涵蓋這個 repo 實際用到的運算子（`>=`／`>`／`<=`／`<`／`==`／`!=`／`~=`）
  的數值 release 段，不是完整的 PEP 440 實作（那要 `packaging` 依賴，本工具堅持只用標準
  函式庫）。**看不懂的宣告回報 `unparsable` 而不是放行**——靜默略過看不懂的東西，等於在最
  可能出事的那一類上報綠。
- Dependabot 的安全性更新與 `open-pull-requests-limit` 無關，本來就會開 PR；照樣要讀 diff。
- pin 掉出宣告範圍時，正確做法是**同一個變更裡把 pyproject 的範圍一起提高**，並在
  [`DIVERGENCE.md`](DIVERGENCE.md) 補一列（那會多動一個上游檔案），不是把檢查關掉。

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

## 2026-09-05：依賴與測試條件政策轉向——不再為了與上游零 diff 而保留落後版本或繞道

**決定**：維護者推翻了本檔最上面那則「Windows 的測試落差用『加一支 fork 自有的
requirements』與『deselect』處理，不改上游檔」的決策。新政策四點：

1. 依賴直接跟上游最新版走，不因為「宣告檔是上游持有的」就保留落後版本或另開繞道檔。
2. 測試因此變紅就改測試條件，不用 deselect／skip 繞過。
3. 每一處與上游的差異都在 repo 裡登記清楚，登記到「日後跟進上游時不必重新評估判斷」的
   程度——見新建的 [`docs/DIVERGENCE.md`](DIVERGENCE.md)。
4. 接受這個 fork 終究會與上游分岔，這是預期結果不是風險。

**落地內容**：

- `requirements-dev.txt`（上游持有，現在直接改）：`ruff` 從 `0.16.3` 跟到 PyPI 當時最新的
  `0.16.6`（已實測 `ruff check .` 與 `ruff format --check .` 在全部 219 個檔案上零差異）；
  新增一行帶 `sys_platform == "win32"` 環境標記的 `tzdata==2026.3`，取代原本獨立的
  `requirements-dev-windows.txt`（已刪除，連同 `tools/check_dependency_freshness.py` 的
  `REQUIREMENT_FILES`、`tests/test_fork_dependency_freshness.py`、
  `.github/workflows/dependency-freshness.yml` 的 `paths:` 都一併改回只認
  `requirements-dev.txt`）。
- `.github/workflows/ci.yml`（上游持有，現在直接改）：三個 Action（`actions/checkout`
  ×3、`actions/setup-python` ×2、`actions/setup-node` ×1）從浮動 tag 改成釘 commit SHA +
  `# vX.Y.Z` 註解，對齊本 fork 自有 workflow 的釘選風格。
- `commerce-common/tests/test_memory_stores.py`（上游持有，現在直接改）：
  `test_the_file_store_is_owner_only_and_keeps_purge_generations_across_instances` 那筆
  `0o600` 斷言包進 `if os.name != "nt":`，Windows 上跳過這一行、其餘斷言（purge
  generations 跨實例存續）照常驗證；`tools/dev_check.ps1` 的 `pytest -q` 移除
  `--deselect`。
- `.github/dependency-deferrals.json` 的四筆 deferral（ruff、三個 Action）清空：那些
  deferral 記錄的理由是「等上游先升」，新政策下這個理由不再成立——本線直接自己升版，不再
  等上游。
- 新增 [`docs/DIVERGENCE.md`](DIVERGENCE.md)：逐檔登記本 fork 對上游持有檔案的修改，並由
  新增的 [`tools/check_divergence.py`](../tools/check_divergence.py) 機器比對「上游基準
  commit 到現在，上游持有檔案實際被改過的清單」與這張表登記的清單，兩邊對不上就非 0 退出；
  接進 `tools/dev_check.ps1` 與 `.github/workflows/upstream-check.yml`（該 job 的 checkout
  已經是 `fetch-depth: 0`，不用額外調整）。

**理由**：舊政策把「上游檔案零 diff」當成目標本身，代價是依賴版本落後、Windows 測試用
deselect 繞過而不是修好、每次同步都要重新判斷哪些繞道還有效。維護者判斷這個代價已經大於
「零 diff 帶來的同步簡單」——本 fork 是單人維護、不回貢的 Windows-first 分支，跟上游分岔
本來就是長期會發生的事，與其假裝零 diff、不如把每一處分岔寫清楚，讓分岔本身可審查、可機器
驗證。

**代價與防呆**：分岔清單會隨時間變長，只靠人工記憶容易漏登記或忘記刪除已經作廢的列；
`tools/check_divergence.py` 把這個防呆變成機器檢查，而不是仰賴下一個維護者的記性。
