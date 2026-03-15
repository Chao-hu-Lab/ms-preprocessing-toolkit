# MS Preprocessing Toolkit - Development Guide

## Project Structure

- **ms-core/** — git submodule, core processing logic (separate repo: bosschen0429/ms-core)
- **src/ms_preprocessing/** — toolkit GUI, CLI, and wrappers
- **tests/** — pytest test suite (run with `PYTHONPATH=ms-core/src`)

## Development Workflow

### 0. Pre-flight Check (MANDATORY)

Before ANY development work, always run:

```bash
git status
```

- Confirm you are on the correct branch (NOT `master` for development)
- Confirm working tree is clean — no uncommitted or untracked changes
- If dirty: commit, stash, or discard before proceeding

### 1. Branch Strategy

| Branch Type | Naming | Purpose |
|-------------|--------|---------|
| `master` | main branch | Merge/PR only, NO direct development |
| `feature/*` | feature branches | New features |
| `fix/*` | fix branches | Bug fixes |
| `chore/*` | chore branches | CI, deps, docs |

### 2. Create Isolated Workspace

Use git worktree for isolation (`.worktrees/` is already in `.gitignore`):

```bash
git worktree add .worktrees/<branch-name> -b <type>/<branch-name>
```

Use the `using-git-worktrees` skill for guided setup.

### 3. Develop and Test

Run the full test suite before considering work complete:

```bash
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x
```

All 82+ tests must pass.

### 4. Finish Branch

Use the `finishing-a-development-branch` skill to choose:
1. Merge locally to master
2. Push and create PR
3. Keep branch as-is
4. Discard

### 5. Release

1. Update version in `pyproject.toml` AND `src/ms_preprocessing/__init__.py`
2. Commit: `chore: bump version to vX.Y.Z`
3. Push to master
4. Tag: `git tag -a vX.Y.Z -m "vX.Y.Z: description"`
5. Push tag: `git push origin vX.Y.Z`
6. Build workflow auto-creates GitHub Release with `ms-preprocessing-Win-vX.Y.Z.exe`

## Submodule Rules (ms-core)

1. Make changes inside `ms-core/`
2. Commit and push in ms-core repo FIRST
3. Return to toolkit root, `git add ms-core` to update submodule reference
4. Commit in toolkit: `fix: bump ms-core for <reason>`

## Prohibited Actions

- **NO** direct development on `master`
- **NO** force push to `master`
- **NO** merging without passing tests
- **NO** skipping `git status` check before starting work

## Key Commands

```bash
# Run tests
PYTHONPATH=ms-core/src pytest tests/ -v --tb=short -x

# Build exe locally
pyinstaller ms-preprocessing.spec --clean --noconfirm

# Check version
python -c "from ms_preprocessing import __version__; print(__version__)"
```

---

## Skill Routing Rules

當任務屬於以下類別時，**開始實作前**先列出相關 skills 並詢問使用者選擇：

---

### 🎨 視覺化 / 圖像設計

可用 skills:
- `canvas-design` — 靜態設計圖像（.png / .pdf）
- `algorithmic-art` — 程式生成藝術（p5.js）
- `theme-factory` — 主題配色系統
- `claude-d3js-skill` — D3.js 互動式資料視覺化
- `kpi-dashboard-design` — KPI 儀表板設計

→ 詢問：「這個任務與視覺化/圖像設計有關，請選擇要使用的 skill：」

---

### 🐍 Python 開發

可用 skills:
- `python-pro` — Python 3.12+ 現代特性與最佳實踐
- `python-patterns` — 慣用 Python 寫法與設計模式
- `python-testing-patterns` — pytest 全面測試模式
- `claude-api` — Anthropic Claude API 整合開發

→ 詢問：「偵測到 Python 開發需求，是否需要載入相關 skill？」

---

### 🧪 測試 / QA

可用 skills:
- `superpowers:test-driven-development` — TDD 流程（Red / Green / Refactor）
- `python-testing-patterns` — pytest 專項測試策略
- `generate-tests` — 自動生成測試套件
- `test-fixing` — 系統性修復失敗測試
- `code-review-checklist` — PR review 查檢清單
- `browser-automation` — Playwright E2E 自動化測試

→ 詢問：「需要測試/QA 輔助，請選擇 skill：」

---

### 🔀 Git / 版本控制 / 發佈

可用 skills:
- `superpowers:using-git-worktrees` — git worktree 隔離開發（新功能必用）
- `superpowers:finishing-a-development-branch` — 完成分支並選擇合併策略
- `git-pushing` — 安全 git 推送操作
- `git-advanced-workflows` — rebase / cherry-pick / bisect / 子模組操作
- `commit` / `commit-commands:commit` — 建立高品質 conventional commit
- `create-pr` / `commit-commands:commit-push-pr` — 建立 PR
- `changelog-automation` — 自動維護 CHANGELOG（配合 vX.Y.Z 發佈流程）

→ 詢問：「Git / 發佈相關操作，請選擇 skill：」

---

### 🔍 程式碼品質 / 除錯 / 重構

可用 skills:
- `superpowers:systematic-debugging` — 系統性除錯（提出修復前必用）
- `lint-and-validate` — 程式碼品質自動驗證
- `kaizen` — 持續改善與技術債管理
- `concise-planning` — 輕量規劃（實作前）
- `code-review-checklist` — Code review 查檢清單

→ 詢問：「需要品質 / 除錯協助，請選擇 skill：」

---

### 📄 文件 / 文件格式

可用 skills:
- `docx` — Word 文件（.docx）
- `pdf` — PDF 操作與文字提取
- `pptx` — PowerPoint 簡報
- `xlsx` — Excel 試算表
- `doc-coauthoring` — 結構化文件協作寫作
- `internal-comms` — 內部溝通文件（報告 / 公告）

→ 詢問：「要輸出哪種格式？」

---

### 🤖 Skill / Plugin / MCP 開發

可用 skills:
- `skill-creator:skill-creator` — 建立 / 改善 Claude skills【**優先使用**】
- `superpowers:writing-skills` — Skills 撰寫指引（僅在 skill-creator 不可用時使用）
- `plugin-dev:skill-development` — Skill 開發流程
- `plugin-dev:plugin-structure` — Plugin 架構設計
- `plugin-dev:agent-development` — Agent 開發
- `plugin-dev:mcp-integration` — MCP server 整合
- `mcp-builder` — 建立 MCP server
- `claude-api` — Claude API 應用開發

→ 詢問：「這是 skill / plugin / AI 工具開發，請選擇 skill：」

---

### 🗂️ 計畫 / 架構設計

可用 skills:
- `superpowers:brainstorming` — 腦力激盪（新功能 / 設計前必用）
- `superpowers:writing-plans` — 撰寫多步驟實作計畫
- `superpowers:executing-plans` — 執行已有計畫
- `concise-planning` — 精簡快速規劃
- `feature-dev:feature-dev` — 功能開發完整引導流程

→ 詢問：「這是規劃 / 架構任務，要使用哪個 skill？」
