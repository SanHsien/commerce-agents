# 路線圖

> 本 repo 後續工作的單一真相源。做完一項，就在同一個 commit 刪掉那一列；新工作只加在這裡。
> 現況段的數字是 2026-10-29 依 `main` `1fa87d0cbf95` 查的快照，開工前先重查 GitHub。

## 現況

Anthropic `commerce-agents` 的 Windows-first 維護 fork（public）。健康：預設分支 `ci`、`CodeQL`、`Upstream check`、`Pin bounds`、`Dependency freshness` 最近一次皆 success；Dependabot 與 Code scanning 告警 0 筆；open PR 0 筆；issues 已停用（未查到 issue 數，不是 0）；無 release（證據：2026-10-29 `gh` 實查）。上游 `main` 只有 `fd4d592` 一個 commit，審查水位 `reviewed_pr_through=39`（`tools/upstream_baseline.json`），目前沒有卡住的事。近期可以直接動手的項目已完成，其餘為等外部條件的中期項目。

## 近期：可以直接動手

（目前無待辦項目）

## 中期：等條件成立再做
| 項目 | 觸發條件 | 驗收方式 | 建議執行者 | 證據 |
| --- | --- | --- | --- | --- |
| 上游新 commit／PR 審查與採納 | `Upstream check` workflow（每週一 03:00 UTC）轉 failure，或 `gh api repos/anthropics/commerce-agents/commits` 出現 `fd4d592` 之後的 commit；failure 代表有未審項目，不是工具壞 | 每個新項目逐筆讀 diff、判決寫進 `docs/DECISIONS.md`、`tools/upstream_baseline.json` 水位前進；`python tools/check_upstream_updates.py --strict` 通過；有採納的另加重現測試並登記 `docs/DIVERGENCE.md` | Claude Sonnet | `.github/workflows/upstream-check.yml:11`；`tools/upstream_baseline.json`；`docs/DECISIONS.md` 判決一覽 |
| 回收已登記的分岔（DIVERGENCE 各列） | 上游合併對應修正（例如 PR #14 `set_quantity`、contract 測試改 UTC）；`python tools/check_divergence.py` 會在上游檔案變動時要求重新比對 | 該列自 `docs/DIVERGENCE.md` 刪除、檔案回到上游版本、`check_divergence` 與 pytest 綠 | Claude Sonnet | `docs/DIVERGENCE.md:55`；`docs/DECISIONS.md` 2026-10-26 段落 |
| 依賴更新（Dependabot／Dependency freshness） | `Dependency freshness`（每月 1 日）轉紅，或 `gh api repos/SanHsien/commerce-agents/dependabot/alerts?state=open` 非空，或 Dependabot 開出 PR | 依 fork 政策跟最新版；`Pin bounds` 與 `ci` 綠；該告警 state=fixed；pin 超出 `pyproject.toml` 範圍時改宣告範圍而非回退 pin | Codex | `FORK.md` 依賴政策；`.github/workflows/dependency-freshness.yml:13`、`pin-bounds.yml` |

## 刻意不做
| 不做什麼 | 理由 | 什麼情況下重新考慮 |
| --- | --- | --- |
| 移植上游 PR #7（WebMCP） | 作者 force-push 的新 head `c877d2a` 在 8 個 `postcss.config.mjs` 夾帶混淆惡意 payload 後自行關閉；判決為拒絕、永不移植 | 不重新考慮該 head；日後若有全新、獨立來源的 WebMCP 實作，當成新項目重審 |
| 把 draft 提案 PR（#19–#24 等）當成待實作項目 | 純文件提案、無程式碼，判決為「觀察」，由 `monitored` 軸釘 head | 提案附上程式碼、或 head 變動被 `Upstream check` 抓到時，依新內容重審 |
| 改寫歷史、強推或重接上游共同祖先 | 2026-10-24 壓成單一 commit 是已知事實，不是缺陷 | 不重新考慮 |
| 為了沒有 issue 面板而啟用 issues | 停用 issues 是設定，不是缺陷；上游同樣停用，`Upstream check` 的 issue 軸固定回報 not-checked | 維護者決定要收外部回報時 |

## 維護方式

上游節奏：每週一的 `Upstream check` 為準，failure 才動手；審到哪裡看 `tools/upstream_baseline.json` 與 [`docs/DECISIONS.md`](docs/DECISIONS.md)。依賴：每月 `Dependency freshness` 加 Dependabot，跟最新版，分岔一律登記 [`docs/DIVERGENCE.md`](docs/DIVERGENCE.md)。
