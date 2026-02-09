# CLAUDE.md

## Commit 流程

提交代码时，需要同步更新 README 中的 cloc badges：

1. 运行 `cloc src/ install.sh uninstall.sh commands/ --json` 获取最新代码行数
2. 更新 `README.md` 和 `README_EN.md` 中 shields.io badges 的行数（Python、Shell、Markdown）
3. Badge 格式：`https://img.shields.io/badge/<Language>-<N>_lines-<color>`
