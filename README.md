<h1 align="center">EVA-01</h1>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.2.0-blue" alt="version">
  <img src="https://img.shields.io/badge/Python-1899_lines-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Shell-248_lines-4EAA25?logo=gnubash&logoColor=white" alt="Shell">
  <img src="https://img.shields.io/badge/Markdown-55_lines-000000?logo=markdown&logoColor=white" alt="Markdown">
</p>

<p align="center">
  <b><a href="./README.md">中文</a></b> | <a href="./README_EN.md">English</a>
</p>

<p align="center">
  <img src="./eva.jpg" width="100%" alt="EVA-01">
</p>

自动化生活的测试平台原型机。目标是在 AI 快速发展的时代，探索人类与 AI 高效协作的方式。

---

## 设计哲学

### 算力杠杆与人类瓶颈

人可调度的 AI 算力越多，个人能力边界越大——这就是**算力杠杆**。但 AI 每次运行都需要人参与决策和审查，人的精力是有限的——这就是**人类瓶颈**。

用三个变量描述：

- $v$ — 单位 AI 运行时间的平均交互次数
- $T$ — 一天的 AI 总运行时间（算力杠杆）
- $X = vT$ — 一天的人机交互总次数，受上限 $X_{\text{threshold}}$ 约束

目标很明确：**最大化 $T$，最小化 $X$，核心是压低 $v$。**

$v$ 的高低决定了两种截然不同的工作状态：

| 模式 | 特征 | 每小时交互次数 $v$ | 算力杠杆 $T$（$X$=50） |
|------|------|:---:|:---:|
| 疲劳模式 | 交互次数逼近精力上限，人被 AI 绑架 | 10 | 5h |
| | | 5 | 10h |
| 舒适模式 | 交互远低于上限，人享受 AI 红利 | 1 | 50h |
| | | 0.5 | 100h |

**结论：$v$ 需要压到每小时 1 次以下，才能让算力杠杆足够大且人不疲劳。**

### 降低 $v$ 的三条路径

1. **更聪明（Smarter）** — 减少返工，降低交互次数
   - 先验：规范化流程，每次改动必须过测试，AI 自检测试是否真正覆盖
   - 后验：运行问题自动记录反馈，持续学习外部案例和框架

2. **批处理（Batching）** — 集中交互，降低离散开销
   - 大规模批量运行任务，统一审查结果
   - 在 spec 阶段用 AI 辅助打磨需求，减少运行中的意外中断

3. **降负担（Simplify）** — 让每次交互更轻松
   - 自动生成结构化报告，清晰的入口和操作路径

### 辐射效应

EVA-01 是一个**实验平台**，而非封闭工具。这里沉淀的方法论——spec 驱动、自主循环、观测反馈——不局限于本仓库，可以辐射到任何需要 AI 自动化的项目中。EVA-01 验证 workflow，其他仓库复用 workflow。

---

## 工具总览

EVA-01 提供两类工具：

| 类型 | 运行方式 | 适用场景 | 安装方式 |
|------|----------|----------|----------|
| **Headless CLI** | 终端直接运行，无需人工介入 | 批量执行、CI/CD、无人值守 | `./install.sh` |
| **Claude Code Plugin** | Claude Code 交互式会话中使用 | 需求讨论、spec 打磨、人机协作 | `claude plugin install eva-01` |

### Headless CLI 工具

通过 `./install.sh` 安装到 `~/.local/bin/`，可在任意项目中直接调用：

| 命令 | 说明 |
|------|------|
| `spec-to-prd` | 将 spec 转换为 PRD JSON，自动分析项目结构 |
| `impl-prd` | 自主循环实现 PRD 中的 user stories |
| `observe-impl` | 分析执行日志，生成报告并推送 GitHub Issue |

### Claude Code Plugin（交互式）

通过 Claude Code plugin 系统安装，在会话中用 `/` 触发：

| 命令 | 说明 |
|------|------|
| `/discuss_spec` | 通过辨析式提问挖掘用户真实意图，完善 spec 和 plan |

Plugin 的核心价值：**在 spec 阶段把所有模糊点问清楚，让后续 headless 执行一次到位，避免反复交互。**

---

## 快速开始

```bash
# 安装 Headless CLI
./install.sh

# 安装 Claude Code Plugin
claude plugin marketplace add /path/to/my-ralph/.claude-plugin/marketplace.json
claude plugin install eva-01

# 进入你的项目
cd your-project

# 先用交互式 plugin 打磨需求
# （在 Claude Code 会话中）/discuss_spec my-feature.md

# 再用 headless CLI 批量执行
spec-to-prd my-feature.md
impl-prd
```

卸载：CLI 用 `./uninstall.sh`，Plugin 用 `claude plugin uninstall eva-01`

---

## 命令详解

### spec-to-prd

将 spec markdown 转换为 PRD JSON。会自动分析项目结构，生成与现有代码兼容的 PRD。

```bash
spec-to-prd <SPEC_FILE> [OPTIONS]
```

自动收集的项目上下文：

| 内容 | 说明 |
|------|------|
| 目录结构 | 文件树（最深 4 层，排除 node_modules 等） |
| 配置文件 | package.json, pyproject.toml, tsconfig.json 等 |
| README | 项目文档 |
| Git 信息 | 当前分支、提交数量 |

生成的 PRD 会遵循现有代码风格，引用需修改的文件，考虑技术栈，增量开发而非重写。

| 参数 | 简写 | 说明 |
|------|------|------|
| `SPEC_FILE` | - | Spec markdown 文件路径（必需） |
| `--output FILE` | `-o` | 输出路径（默认: `.prd/prds/<name>.json`） |
| `--project NAME` | `-p` | 项目名称（默认: 从文件名推断） |
| `--model MODEL` | `-m` | Claude 模型: opus/sonnet/haiku（默认: sonnet） |
| `--timeout MINUTES` | - | 超时分钟数（默认: 15） |

```bash
spec-to-prd my-feature.md              # 基本用法
spec-to-prd my-feature.md -m opus      # 用 opus 模型
spec-to-prd my-feature.md -o out.json  # 指定输出路径
```

---

### impl-prd

自主循环实现 PRD 中的 user stories。

```bash
impl-prd [OPTIONS]
```

| 参数 | 说明 |
|------|------|
| `--prd FILE` | PRD 文件路径（默认: `.prd/prds/` 下最新） |
| `--max-iterations N` | 最大迭代次数（默认: 50） |
| `--timeout MINUTES` | 输出超时分钟数（默认: 15） |
| `--model`, `-m` | Claude 模型（默认: sonnet） |
| `--no-progress-threshold N` | 连续无进展阈值（默认: 3） |
| `--resume` | 从上次状态恢复 |
| `--status` | 显示当前状态后退出 |
| `--reset` | 重置状态，重新开始 |
| `--verbose` | 详细输出 |
| `--no-observe` | 结束后不自动运行 observe-impl |

> impl-prd 默认以 `--dangerously-skip-permissions` 运行，实现完全自主执行。结束时自动调用 `observe-impl`。

```bash
impl-prd                          # 开始实现
impl-prd -m opus                  # 用 opus 模型
impl-prd --resume                 # 恢复上次进度
impl-prd --status                 # 查看当前状态
```

#### 退出机制

| 机制 | 触发条件 | 默认值 |
|------|----------|--------|
| 完成退出 | 所有 stories 通过 | - |
| 最大迭代 | 达到 `--max-iterations` | 50 次 |
| 输出超时 | Claude 无输出超过 N 分钟 | 15 分钟 |
| 无进展断路 | 连续 N 次无 story 完成 | 3 次 |
| 速率限制 | 超过每小时调用上限 | 100 次/小时 |
| 用户中断 | Ctrl+C | - |

---

### observe-impl

分析 impl-prd 的执行日志，生成报告并可选推送 GitHub Issue。

```bash
observe-impl [OPTIONS]
```

工作流程：读取 session 日志 -> Claude 分析 -> 保存报告 -> 按需创建 Issue

| 参数 | 简写 | 说明 |
|------|------|------|
| `--session PATH` | `-s` | 指定 session 目录 |
| `--latest` | `-l` | 分析最新 session |
| `--no-issue` | - | 不创建 GitHub Issue |
| `--model MODEL` | `-m` | Claude 模型（默认: haiku） |
| `--timeout MINUTES` | - | 超时分钟数（默认: 10） |
| `--verbose` | `-v` | 详细输出 |

```bash
observe-impl --latest                # 分析最新 session
observe-impl --latest --no-issue     # 只生成报告
observe-impl --latest -m sonnet      # 用 sonnet 深入分析
```

---

## 目录结构

首次运行 `spec-to-prd` 时自动创建：

```
your-project/
└── .prd/
    ├── specs/          # 原始 spec markdown
    ├── prds/           # 生成的 PRD JSON
    ├── logs/           # 执行日志
    │   └── session_YYYYMMDD_HHMMSS/
    │       ├── config.json           # 运行配置快照
    │       ├── prd_snapshot.json     # PRD 快照
    │       ├── args.json             # 命令行参数
    │       ├── session.log           # 主日志
    │       ├── loop_001.log          # 每次循环的输出
    │       ├── summary.json          # 运行汇总
    │       └── observation_report.md # 观测报告
    ├── config.json     # 项目配置
    └── state.json      # 运行状态（用于恢复）
```

### 配置项

```json
{
  "max_calls_per_hour": 100,
  "max_iterations": 50,
  "timeout_minutes": 15,
  "output_format": "stream",
  "allowed_tools": ["Write", "Read", "Edit", "Glob", "Bash(git *)", "Bash(npm *)", "Bash(npx *)", "Bash(pytest)", "Bash(python -m pytest *)"],
  "session_expiry_hours": 24,
  "max_consecutive_failures": 3,
  "no_progress_threshold": 3
}
```

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `max_calls_per_hour` | 每小时最大 API 调用次数 | 100 |
| `max_iterations` | 最大迭代次数 | 50 |
| `timeout_minutes` | Claude 超时（分钟） | 15 |
| `output_format` | 输出格式: stream / json | stream |
| `allowed_tools` | 允许的工具列表 | - |
| `session_expiry_hours` | 会话过期时间（小时） | 24 |
| `max_consecutive_failures` | 最大连续失败次数 | 3 |
| `no_progress_threshold` | 无进展阈值 | 3 |

---

## 内部协议

### PRD JSON 格式

```json
{
  "project": "ProjectName",
  "branchName": "ralph/feature-name",
  "description": "Feature description",
  "source_spec": "specs/feature-name.md",
  "created_at": "2026-02-02T10:30:00",
  "updated_at": "2026-02-02T11:00:00",
  "userStories": [
    {
      "id": "US-001",
      "title": "Story title",
      "description": "As a [user], I want [feature] so that [benefit]",
      "acceptanceCriteria": ["Criterion 1", "Criterion 2", "All tests pass"],
      "priority": 1,
      "passes": false,
      "notes": "",
      "testPlan": "Unit test for ...; integration test for ...",
      "completed_at": null
    }
  ]
}
```

### 完成信号

Claude 完成 story 时输出：

```
---RALPH_STATUS---
STATUS: COMPLETE
STORY_ID: US-001
STORY_PASSED: true
FILES_MODIFIED: [file1.py, file2.py]
EXIT_SIGNAL: false
---END_RALPH_STATUS---
```

所有 stories 完成时输出：

```
<promise>COMPLETE</promise>
```
