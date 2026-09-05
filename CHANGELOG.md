[English](CHANGELOG.en.md) | 中文版

# Changelog

本檔只記錄 **本 fork（`SanHsien/commerce-agents`）自己的維護歷史**，不記錄
`anthropics/commerce-agents` 上游的變更——上游的變更走 `tools/check_upstream_updates.py` 與
[`docs/DECISIONS.md`](docs/DECISIONS.md)。

格式依循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，版本號依循
[Semantic Versioning](https://semver.org/spec/v2.0.0.html)。

## [0.2.0] - 2026-09-05

政策轉向：不再為了與上游零 diff 而保留落後依賴版本或用測試繞道；依賴直接跟上游最新版走，
測試因此變紅就改測試條件，每一處與上游的差異登記在新建的 `docs/DIVERGENCE.md`，機器強制
一致。詳見 [`docs/DECISIONS.md`](docs/DECISIONS.md) 該日期的第二則決策。

### Added

- `docs/DIVERGENCE.md`：逐檔登記本 fork 對上游持有檔案的修改，以及跟進上游時的可執行判準。
- `tools/check_divergence.py`：比對「上游持有檔案實際被改過的清單」與 `docs/DIVERGENCE.md`
  登記的清單，兩邊對不上就非 0 退出；接進 `tools/dev_check.ps1` 與
  `.github/workflows/upstream-check.yml`。`tests/test_fork_divergence.py` 是它的合約測試。

### Changed

- `requirements-dev.txt`（上游持有，現在直接改）：`ruff` 跟到 `0.16.6`；新增一行帶
  `sys_platform == "win32"` 環境標記的 `tzdata==2026.3`。
- `.github/workflows/ci.yml`（上游持有，現在直接改）：三個 Action（`checkout` ×3、
  `setup-python` ×2、`setup-node` ×1）從浮動 tag 改成釘 commit SHA + `# vX.Y.Z` 註解。
- `commerce-common/tests/test_memory_stores.py`（上游持有，現在直接改）：POSIX `0o600`
  權限斷言改成平台條件式（`if os.name != "nt":`），不再靠 `--deselect` 整支跳過。
- `tools/dev_check.ps1`：`pytest` 移除 `--deselect`；新增 `check_divergence.py` 這一步。
- `tools/check_dependency_freshness.py`：`REQUIREMENT_FILES` 改回只有
  `requirements-dev.txt` 一份。
- `.github/dependency-deferrals.json`：四筆「等上游先升」的 deferral 清空。

### Removed

- `requirements-dev-windows.txt`：`tzdata` 已直接併入 `requirements-dev.txt`。

## [0.1.0] - 2026-09-05

### Added

- 建立 fork 開發鷹架：繁中 `README.md`（英文原檔保留為 `README.en.md`）、`AGENTS.md`、
  `NOTICE.md`、`FORK.md`、`SECURITY.md`、`CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`。
- Windows 開發環境：`.venv` + `requirements-dev-windows.txt`（＝上游 `requirements-dev.txt`
  再加 `tzdata`，補上 Windows 版 CPython 缺少的 IANA 時區資料庫）、`tools/dev_check.ps1`
  一鍵 gate（含時區資料庫前檢，並 deselect 一個 Windows 沒有 POSIX 權限語意而恆紅的上游測試）。
- 維護工具：`tools/check_dependency_freshness.py`（`requirements-dev.txt` 對 PyPI、
  `.github/workflows/*.yml` 釘選的 Action 對 GitHub Releases）、
  `tools/check_upstream_updates.py`（上游 commit／PR／issue 三軸未審查追蹤）、
  `tools/check_links.py`（維護文件相對連結檢查），各附 `tests/test_fork_*.py` 合約測試。
- GitHub Actions：`dependency-freshness.yml`（每月）、`upstream-check.yml`（每週）、
  `codeql.yml`（`python` 與 `javascript-typescript`，含排程掃描）。
- `.github/dependabot.yml`：`github-actions` 生態正常開 PR；`pip`（根目錄）與
  `npm`（`examples/`）因鎖定上游持有的 pin 檔，`open-pull-requests-limit: 0`。
- `.cursor/rules/no-upstream-pr.mdc`：機器可讀的「對外只打 origin」規則。
- `.editorconfig`、`.gitattributes`：統一縮排（2 空格，`.py`/`.ps1` 4 空格）與換行（LF）。

### Changed

- `CLAUDE.md`：最上方插入 fork 邊界區塊，其餘上游內容不動。
- `.gitignore`：append 一個 fork 區塊，忽略 `upstream-review-report.md` 與
  `dependency-freshness-report.md` 兩份生成報告。
- `ruff.toml`：`src` 陣列追加 `"tools"`。

[0.2.0]: https://github.com/SanHsien/commerce-agents/releases/tag/v0.2.0
[0.1.0]: https://github.com/SanHsien/commerce-agents/releases/tag/v0.1.0
