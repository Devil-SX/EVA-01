# Changelog

## [Unreleased]

## [0.2.0] - 2026-02-20

### Added
- `testPlan` field in `UserStory` schema for per-story test descriptions
- Test plan section in impl-prd prompt (Step 3: Implement Tests)
- Full regression test gate in impl-prd prompt (Step 4: must pass before commit)
- `ARCHITECTURE.md` maintenance steps in impl-prd prompt (Step 5 & 6)
- `CLAUDE.md` ↔ `ARCHITECTURE.md` cross-reference enforcement in impl-prd
- Rules 9-10 in spec-to-prd: require `testPlan` and "All tests pass" in acceptance criteria
- Test framework discovery step in spec-to-prd exploration phase
- `Glob`, `Bash(npx *)`, `Bash(python -m pytest *)` to default allowed_tools

### Changed
- impl-prd prompt rewritten from 4-step to 8-step workflow (read context → implement → test → regress → architecture → CLAUDE.md → commit → update PRD)
- spec-to-prd prompt: acceptanceCriteria example changed from "Typecheck passes" to "All tests pass"
- `_build_prompt` in `impl_prd.py` now passes `test_plan` to the prompt template

## [0.1.0] - 2026-02-09

### Added
- `spec-to-prd`: Convert spec markdown to PRD JSON with automatic project context analysis
- `impl-prd`: Autonomous loop to implement PRD user stories via Claude Code
- `observe-impl`: Analyze session logs, generate reports, and create GitHub issues
- `discuss_spec` slash command for interactive spec review before PRD conversion
- Framework detection and smart issue routing in observe-impl
- Session-based logging system with per-loop log files
- Privacy sanitization for GitHub issue creation
- CLAUDE.md auto-resolution for recurring patterns
- install.sh / uninstall.sh for global command installation via uv
- Claude Code plugin marketplace configuration (`.claude-plugin/`)
- Bilingual README (Chinese + English) with centered badges and language switcher
- CHANGELOG.md

### Changed
- Rename repository from `prd-loop` to `EVA-01`
- Rename Python module from `prd_loop` to `eva_01`
- Update all references: pyproject.toml, marketplace.json, install/uninstall scripts, prompts
- Restructure README with design philosophy (compute leverage, radiation effect)
- Extract prompts to separate files under `prompt/` package
- Claude updates PRD file directly instead of status parsing
- Use timestamp naming for PRD files
- Let Claude explore project structure itself in spec-to-prd

### Fixed
- Escape `{name}` placeholder in OBSERVE_PROMPT
- Use short model names for Claude CLI
- Preserve original working directory in wrapper scripts
- Use venv activation instead of `uv run` to keep cwd
- Save Claude stream output and improve error handling
