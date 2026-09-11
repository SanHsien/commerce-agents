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

## 2026-09-11：逐筆審查上游 PR #5–#31，`reviewed_pr_through` 推進到 31

**背景**：`upstream-check.yml` 在 2026-09-07 紅燈，因為上游 `anthropics/commerce-agents` 在基準
（#4）之後新開了 27 筆 PR（`gh pr list --repo anthropics/commerce-agents --state all` 確認全數
仍是 `OPEN`，非 draft 者皆未被上游合併——這個上游本身聲明不維護、不接受貢獻，PR 停在 open 是
預期狀態，不是本 fork 需要等待的訊號）。以下逐筆記錄實際讀過 diff（`gh pr diff <n> --repo
anthropics/commerce-agents`）後的判斷；**本輪判決全部只是紀錄，沒有搬移任何程式碼到本 fork**，
真正移植需要各自的 bounded change、回歸測試與 `docs/DIVERGENCE.md` 登記。

**判決一覽**（判決詞：採納候選／延後／拒絕／觀察）：

| PR | 標題 | 實際狀態 / head | 判決 | 理由（附證據） |
|---|---|---|---|---|
| #5 | scaffold-commerce-agent.md 文法：「write the backend as X is written」→「the way X is written」 | open, `b808b55` | 採納候選（低） | 原句 `write the backend as MockRetail... is written` 語意不通順（`as X is written` 不成立的比較結構）；新句可讀。本 fork 該行現狀與上游基準相同（`sed -n '179p'` 確認），未分岔。 |
| #6 | docs/backends.md 文法：刪掉贅字 `stays` | open, `f1043f4` | 採納候選（低） | 原句「prices stays this way」主謂不一致且贅字；新句「prices this way」正確。本 fork 該行未分岔（現狀與上游基準相同）。 |
| #7 | Add WebMCP support | open, `5649221` | 觀察／需獨立評估 | 跨 4 個垂直（retail/travel/telecom/entertainment）× storefront/merchant 共 26 個檔案、新增 `web-shared` 的 `useWebMcpTools`/`createStorefrontWebMcpTools`/`createMerchantWebMcpTools`，是全新能力（瀏覽器端暴露唯讀 MCP 工具），不是缺陷修正。雖然標了 `"risk":"read-only"`／`"untrustedContent":true` 顯示作者有意識到信任邊界，但範圍與安全影響（瀏覽器暴露的工具端點如何綁定 session、是否可被同頁面其他腳本呼叫）需要獨立、有邊界的審查，不適合塞進本輪 PR 分類判決。 |
| #8 | shopping executor：cart quantity 驗成 argument error 而非 outage | open, `0a11006` | 採納候選（中） | 已重現缺陷：`shopping-agent/core/shopping_agent/executor.py:165,175` 現狀是 `int(tool_input.get("quantity") or 1)`，`quantity="abc"` 觸發原生 `ValueError`（不是 `commerce_common.execution.InvalidArguments`），落進 `BaseToolExecutor.execute` 的 `except Exception` 泛用分支（`commerce-common/commerce_common/execution.py:219-223`），回報成「unavailable」而非具名的 argument 錯誤。PR 改用既有的 `parse_argument()`（同檔案已用於 `SearchFilters`，`executor.py:135`），做法與現有慣例一致。 |
| #9 | shopping cards：model-authored `reason` 文字進 host 前先過 fence sanitizer | open, `61bad1c` | **已採納（`489286d`）** | 已重現缺陷：`shopping-agent/core/shopping_agent/enrichment.py:92,213` 現狀直接把 `pick.reason`／`pick["reason"]`（模型產生的文字）塞進 UI payload，未過 `STOREFRONT_FENCE.sanitize_text`。`commerce-common/commerce_common/fencing.py` 已有 `Fence.sanitize_text`，本專案設計規則（`AGENTS.md`「第三方內容一律圈在 fence 裡」）與既有的 ReDoS 修補案例（`docs/DIVERGENCE.md` 的 `orders.tsx` 一列）都是同一類「model/third-party 文字進 host 渲染層前要清洗」的原則，這裡是一個遺漏點：模型可在 `reason` 裡塞入 fence 標記或不可見字元。 |
| #10 | merchant guardrails：價格超過兩位小數視為違規 | open, `f184ed9` | 採納候選（中） | 已重現缺陷：`merchant-agent/core/merchant_agent/changes.py` 的 `check_guardrails`（約 70 行起）目前沒有小數位檢查，`79.795` 這類價格可以通過寫入閘門。與既有的 `check_pin_bounds.py`／guardrails 精神一致（寫入操作要在程式碼裡有上限與檢查）。 |
| #11 | config：`thinking_effort=None` 時省略 `thinking` 欄位而非送 `{"type":"disabled"}` | open, `0d599b2` | 採納候選（中，建議先核對 API 文件） | 已重現：`commerce-common/commerce_common/config.py:89-91` 現狀在 `thinking_effort is None` 時回傳 `{"thinking": {"type": "disabled"}}`。PR 的理由（「一律思考」的模型會對顯式 `disabled` 回 400）是可信的一類已知 Anthropic API 相容性問題，但本次審查無法直接連線 Anthropic API 文件逐一核對哪些現行模型型號會拒絕 `disabled`；這是行為變更（省略欄位＝聽模型預設，不是「明確關閉」），建議採納前用實際模型呼叫核對一次，而不是照單全收。 |
| #12 | demo host：缺憑證只印一行警告而非整條 traceback | open, `f269261` | 採納候選（低） | `examples/demo_common/host.py` 目前每次缺憑證的請求都 `logger.exception`（含完整 traceback）；PR 抽出 `credential_problem()` 判斷式並改用 `logger.warning`。純日誌品質改善，風險低。 |
| #13 | retail merchant mock：4 項修正（未知 metric/segment 誠實回覆、restock 數量必須>0、跨商家 session 隔離） | open, `ac105c1` | **已隨 #25 採納（`489286d`）** | diff 逐行比對（`diff pr13.diff pr25.diff`）確認 #25 是 #13 的嚴格超集：#13 的每一處改動 #25 都有，#25 多了促銷價格地板 guardrail。2026-09-11 移植時只套用 #25 的 diff，未另外處理 #13——`examples/retail/api/mock_merchant.py` 現狀已含 #13 全部 4 項修正。 |
| #14 | retail cart：以契約的 `Unavailable` 拒絕，數量<1 移除該行 | open, `4c85880` | 採納候選（中高） | 已重現兩個缺陷：① `examples/retail/api/mock_retail.py:301-304` 對「product 不存在」與「family 有 options」丟原生 `KeyError`，繞過 `shopping-agent/core/shopping_agent/executor.py` 的 `domain_error()`（只認 `Unavailable`/`NotOffered`，`executor.py:106-113`），錯誤訊息因此變成泛用的「unavailable」而非具名的變體建議清單。② `examples/demo_common/storefront_fixtures.py:447-451` 的 `set_quantity` 在 `quantity=0` 時只會把該行的 quantity 欄位設成 0，不會移除，購物車因此可能殘留數量為零的品項。 |
| #15 | merchant fixtures：`stage_campaign` 對不存在的 `campaign_id` 該拒絕 | open, `38c576b` | 採納候選（中） | 已重現：`examples/demo_common/merchant_fixtures.py` 現狀對一個不存在的 `campaign_id` 會落進 `existing is None` 分支、被當成「新增」處理，而不是回報「沒有這個 campaign 可改」。PR 改成優先檢查並拋 `ChangeNotApplicable`（既有例外類別，`merchant-agent/core/merchant_agent/changes.py:26`）。 |
| #16 | travel mock：售完或不存在的 stay 不可加入購物車 | open, `f91d857` | 採納候選（中高） | 已重現缺陷：`examples/travel/api/mock_travel.py:319` 現狀 `product = self.products[product_id]`（原生 dict 索引），未知 id 丟 `KeyError`，且**完全沒有 `in_stock` 檢查**——售完的 stay 目前可以被加進購物車，這是業務規則層級的正確性缺口，不只是錯誤訊息品質問題。 |
| #17 | ticketing：`SoldOutError` 應是契約的 `Unavailable` | open, `035ca1b` | 採納候選（中） | 已重現：`examples/entertainment/api/ticketing.py:29` 現狀 `class SoldOutError(TicketingError)`，只繼承 `ValueError`，不是 `shopping_agent.backend.Unavailable`；售完因此被 executor 的 `domain_error()` 判斷為「不是 Unavailable」而走泛用 outage 分支，而非具名的售罄訊息。 |
| #18 | `MerchantBackend` 文件字串：明講「changes 只作用在 session 的 merchant」 | open, `6639dfc` | **已採納（`489286d`）** | 純 docstring 補充（`merchant-agent/core/merchant_agent/backend.py:39-45` 現狀沒有這句），是 #13/#25 所修正之跨商家隔離缺陷的抽象基底類別契約說明；若採納 #25，#18 應一併採納以讓文件與實作一致。 |
| #19 | 提案：backend 一致性測試套件 | open (draft), `e49a738` | 觀察 | 純文件提案（新增 `docs/proposals/backend-conformance-suite.md`），作者自陳「code follows once the shape is agreed」，尚無程式碼可審。 |
| #20 | 提案：checkout 二次驗證與 handoff 拒絕 | open (draft), `b3cfe06` | 觀察 | 純文件提案。其中一句技術主張（「`Unavailable` 不是 `run_presentation` 會 relay 的 `ValueError`，所以會回報成 outage」）經查證**與本 repo 現狀不符**：`commerce-common/commerce_common/presentation.py:120-144` 的 `run_presentation` 確實只窄窄地接 `PresentationRefused`/`ValueError`，但呼叫鏈外層的 `BaseToolExecutor.execute`（`commerce-common/commerce_common/execution.py:214-223`）有更寬的 `except Exception` 分支且會先呼叫 `domain_error()`——`shopping-agent/core/shopping_agent/executor.py:106-113` 的 `domain_error()` 已經會正確辨識 `Unavailable` 並回覆具名訊息。也就是說，若 `checkout_handoff` 真的丟出 `Unavailable`，今天的行為就已經是「具名拒絕」而不是「outage」。這不影響提案其餘部分（re-validate at checkout、price staleness）的價值，但引用的既有缺陷描述不準確，列為觀察並註記此點，供日後評估提案時用。 |
| #21 | 提案：ledger claim 與跨程序/當機的 idempotent apply | open (draft), `7adc548` | 觀察 | 純文件提案，無程式碼。 |
| #22 | 提案：shopper 端訂單動作（取消/退貨/回報問題） | open (draft), `ddf43ac` | 觀察 | 純文件提案，無程式碼。 |
| #23 | 提案：staged change 衝突標記與 apply 時的過時檢查 | open (draft), `2860826` | 觀察 | 純文件提案，無程式碼。 |
| #24 | 提案：undo 與排程 apply | open (draft), `14b569a` | 觀察 | 純文件提案，無程式碼。 |
| #25 | retail merchant mock：促銷價格不可低於地板（另含 #13 全部 4 項修正） | open, `6c2c237` | **已採納（`489286d`）** | 見上方 #13 一列的重複關係。額外新增：`stage_promotion` 對「折扣在 `max_promotion_discount_pct` 上限之內、但促銷後價格仍低於 `unit_cost*1.15` 地板」的案例目前**沒有檢查**（本 fork 現狀 `examples/retail/api/mock_merchant.py` 的 `stage_promotion` 只用折扣上限把關，未讀地板），會讓促銷把商品打到低於地板卻不觸發任何 guardrail；PR 補上 `GuardrailViolation`。跨商家隔離部分理由同 #13。 |
| #26 | scaffold-commerce-agent.md 文法：「Step 2, only the role's...」補上動詞 `read` | open, `59d49e5` | 採納候選（低） | 已重現：原句「on the prototype lane (Step 2), only the role's `backend.py`...」缺主要動詞，`read these` 只管到前半句。新句補上 `read only the role's...`，並把其中一個 `and` 換成 `plus` 消歧巢狀列舉。本 fork 該行未分岔。 |
| #27 | scaffold-commerce-agent.md 文法：「Both means」→「Both mean」 | open, `f8c5ea4` | 採納候選（低，語感存疑） | 與 #26/#28 同一份檔案的不同行、非重複送件（各自改不同段落，`diff` 逐一核對過起始行號不同）。這一筆本身文法判斷有爭議：`Both` 在此處指稱「選 both 這個選項」時，英語慣用法對其單複數呼應本就分歧（`Both is/means` vs `Both are/mean` 兩種用法皆有母語者使用），不像 #5/#6/#26/#28 那樣是明確語病。建議採納前讓人工再讀一次判斷語感，不必照單全收。 |
| #28 | scaffold-commerce-agent.md 文法：補上缺漏的關係代名詞 `that` | open, `4598279` | 採納候選（低） | 已重現：原句「the path of the clone the hosted path's `managed-agents/` directory ... are read from」缺 `that` 引導的關係子句連接詞，讀起來像兩個獨立子句黏在一起。新句補上 `that` 後可讀。 |
| #29 | demo hosts：`build_storefront_host`／`build_merchant_router` 可注入自己的 `SessionStore` | open, `393a7ec` | 採納候選（中） | 現狀 `examples/demo_common/storefront.py`／`merchant.py` 的 `sessions` 一律寫死 `SessionStore(...)`（記憶體型），部署到正式環境無法接自己的資料庫、行程重啟就掉光 session。PR 加一個可選參數、預設值不變，向後相容，是產品化（而非 bug）缺口。 |
| #30 | Bump `sharp` 0.35.3 → 0.35.4（`/examples`） | open, `e888259` | **採納候選（最高，安全性）** | **GHSA-rgj7-g3m4-5g8c**（HIGH，2026-09-08 發布，`sharp: Vulnerabilities in libheif`）影響版本範圍 `< 0.35.4`，修補版本正是 `0.35.4`。已核對本 fork 現狀鎖定的正是 `sharp@0.35.3`（`examples/package-lock.json:1632` `"version": "0.35.3"`），落在受影響範圍內。查證指令：`gh api graphql -f query='{securityVulnerabilities(package:"sharp",first:20,ecosystem:NPM){nodes{advisory{ghsaId summary severity publishedAt} vulnerableVersionRange firstPatchedVersion{identifier}}}}'`。 |
| #31 | Bump `next` 16.3.0 → 16.3.4（`/examples`） | open, `2751cfa` | **採納候選（最高，安全性，CRITICAL）** | 本 fork 現狀鎖定 `next@16.3.0`（`examples/package-lock.json:1476` `"version": "16.3.0"`；八個 `package.json` 皆宣告 `^16.3.0`），落在兩個 CRITICAL 漏洞的受影響範圍：**GHSA-2xp9-vwfh-vxw4**（Unauthenticated RCE in Image Optimization API using AVIF files，範圍 `>=16.0.0,<16.3.3`，修補版 `16.3.3`）與 **GHSA-p293-qw3h-jr36**（Unauthenticated RCE on **Windows-hosted servers**，範圍同上，修補版同上）——後者對這條 Windows-first 維護線尤其相關。PR 升到 `16.3.4`，高於兩者的修補版本，兩個 CVE 都會被涵蓋。查證指令同上，`package: "next"`。 |

**重複／互相取代的 PR 關係**：

- **#13 與 #25**：#25 是 #13 的嚴格超集（`diff` 逐行核對，見上表）。若日後採納，只處理 #25；#13 標記延後。
- **#5／#26／#27／#28**：標題完全相同（都寫「docs: fix grammar issue in
  plugins/commerce-builder/commands/scaffold-commerce-agent.md」），**但不是同一筆修正的重送**——
  四筆改的是檔案裡四個不同段落（第 17、41、122、177 行附近），彼此互不重疊，應各自獨立判斷；
  唯一需要留意的是 #27 的文法判斷本身有爭議（見上表）。
- **#6** 是同一位／同類貢獻者對另一份檔案（`docs/backends.md`）的同型態文法修正，與上述四筆不衝突。

**Adopt 候選優先序**（給主 session 決定是否要各自開 bounded change）：

1. **#31**（next 16.3.0→16.3.4，CRITICAL RCE ×2，含 Windows-hosted 那個）
2. **#30**（sharp 0.35.3→0.35.4，HIGH，libheif）
3. **#25**（含 #13 全部修正＋促銷地板 guardrail；跨商家隔離是資料完整性/授權缺口）
4. **#9**（model-authored 文字進 UI 前缺 sanitize，安全相關但影響面小於上面三筆）
5. **#16**（售完商品可被加入購物車，業務規則缺口）
6. **#14**（cart 契約錯誤類型＋殘留零數量行）
7. **#8**、**#17**、**#10**、**#15**、**#18**、**#29**、**#11**（依序：executor 錯誤分類、售罄錯誤分類、guardrail 補洞、fixture 正確性、docstring 補充、production-readiness、API 相容性但需先核對文件）
8. **#12**、**#5**、**#6**、**#26**、**#27**、**#28**（品質/文件類，低優先）
9. **#7**、**#19**–**#24**：不進這份 adopt 優先序——#7 需要獨立的安全與範圍審查；#19–#24 是無程式碼的設計提案。

**再審觸發條件**：本輪只推進 `reviewed_pr_through`，不移植程式碼。下一次同步時（`git fetch upstream`
或 `upstream-check.yml` 排程觸發）：新開的 PR 編號高於 31 才算未審查；已審過的 #5–#31 若在上游
被關閉、合併或改動 head SHA，視為新事件需要重新讀 diff（尤其 #19–#24 draft 提案若轉成非 draft
並補上程式碼，等於是新內容，要重新審查而不是延用本次的「觀察」判決）。


## 2026-09-11（續）：上游 #32 審查；#30／#31 已由本 fork 的 Dependabot 安全更新採納

**#30／#31 已採納**：同日替本 fork 開啟 Dependabot alerts 與自動安全更新後（GitHub 對 fork 預設關閉），
Dependabot 立即對同樣三筆漏洞開了本 fork 自己的 PR：`SanHsien/commerce-agents#1`（sharp）與
`#2`（next）。讀 diff 後確認 `#2` 的 lockfile 同時把 `next` 解析到 `16.3.4`、`sharp` 解析到 `0.35.4`
（含 `@img/sharp-win32-x64`），是 `#1` 的超集，且兩個 PR 的 8 項必要檢查全過。合併 `#2`
（`c85b697`）、以「由 #2 涵蓋」關閉 `#1`、刪除兩端分支。GitHub 隨即將
GHSA-2xp9-vwfh-vxw4、GHSA-p293-qw3h-jr36（next，CRITICAL）與 GHSA-rgj7-g3m4-5g8c（sharp，HIGH）
標為 fixed，open alerts 歸零。上表 #30／#31 的「採納候選」因此已完成；沒有從上游分支取碼。
這次合併改了 9 個**上游持有**的檔案（8 個 web app 的 `package.json` 與 `examples/package-lock.json`），依本 fork 的維護契約**必須**登記 `docs/DIVERGENCE.md`，已補 9 列並附跟進上游的判準。（初稿曾寫「不另登記」，是錯的，被 `tools/check_divergence.py` 當場擋下——這正是那道機器檢查存在的理由。）

**#32 審查**：

| PR | 標題 | 實際狀態 / head | 判決 | 理由（附證據） |
|---|---|---|---|---|
| #32 | Add Trustabl Agent Scanner to CI | open, non-draft，作者 `trustabl-kathrina`，2026-09-11 開，`f662f8c` | **拒絕** | 只新增 `.github/workflows/trustabl.yml`（+33）。本文開頭即是廠商推銷語（"We came across your repo…"），附帶的 HIGH「發現」是對 `plugins/commerce-builder/skills/*/SKILL.md` 用字的關鍵字啟發式（例如敘述提到 PII 就判 HIGH），不是程式缺陷。該 workflow 在每個 push 與 PR 上執行未經審查的第三方 Action `trustabl/trustabl-action@973f666`，並授予 `security-events: write` 與 `pull-requests: write`，等於把寫入權交給一個本 fork 從未審過的供應商；同時設 `continue-on-error: true`，**永遠不會讓 CI 變紅**——不會失敗的檢查不是閘門，只增加供應鏈攻擊面。本 fork 已在 `.github/workflows/codeql.yml` 對 `python` 與 `javascript-typescript` 跑 `security-extended`。 |

**#32 的再審觸發條件**：維護者決定要引入 agent skill 掃描器時，另開一個有界變更——審查該 Action 的
原始碼與釘選 SHA、把權限縮到只讀或只寫 `security-events`、並讓它成為**會失敗**的必要檢查，而不是
advisory。

## 2026-09-11（再續）：A 批三筆（#9、#25、#18）移植完成

**移植方式**：讀 diff（`gh pr diff <n> --repo anthropics/commerce-agents`），確認缺陷在本 fork
現狀仍存在後，`git apply --3way` 直接套用（三筆診斷全部套用乾淨，未手動調整）；沒有 fetch 上游
分支、沒有 merge、沒有 cherry-pick。#13 未另外處理——診斷已完整涵蓋在 #25 的 diff 裡，套用 #25
即等於採納 #13 的全部 4 項修正。

- **#9**：`shopping-agent/core/shopping_agent/enrichment.py` 新增 `_clean()`，`enrich_products`／
  `partial_products` 改走 `STOREFRONT_FENCE.sanitize_text`。新測試
  `test_model_authored_card_text_is_sanitized`（`shopping-agent/core/tests/test_executor.py`）。
- **#25**（含 #13）：`examples/retail/api/mock_merchant.py` 補齊五項：未知 metric/segment 誠實回覆、
  restock 數量必須 > 0、促銷日期不得倒置、促銷價格不可低於 `unit_cost*1.15` 地板（`GuardrailViolation`）、
  `get_pending_changes`／`apply_change`／`discard_change` 加 `_own()` 跨商家隔離。五支新測試
  （`examples/retail/api/tests/test_retail_merchant_backend.py`）逐一做過突變驗證。
- **#18**：`merchant-agent/core/merchant_agent/backend.py` 的 `MerchantBackend` docstring 補上
  跨商家隔離的契約說明，與 #25 的實作對齊；純文件字串變更，無新增測試。

**驗證**：`pytest -q` 1198 passed、1 skipped（基準 1192 passed／1 skipped ＋ 本輪新增 6 支測試）；
`tools/dev_check.ps1` 全綠（ruff check／format、pytest、`scripts/check.py`、`check_links.py`、
`check_divergence.py`、`check_pin_bounds.py`）；本輪未改動 `examples/` 前端檔案，未另跑
`npm run build`。`docs/DIVERGENCE.md` 新增 5 列登記這五個上游持有檔案的分岔，
`tests/test_fork_divergence.py` 的釘死集合同步更新。程式碼與測試提交於 `489286d`；本節（決策
紀錄的判決欄更新）為後續第二個 commit。

