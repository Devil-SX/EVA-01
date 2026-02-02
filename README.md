# PRD Loop

Python 实现的 Ralph 自主开发循环系统。将 spec 文档转换为 PRD，然后自动循环调用 Claude Code 实现所有 user stories。

## 安装

```bash
./install.sh
```

安装后会在 `~/.local/bin/` 创建 `spec-to-prd` 和 `impl-prd` 两个命令。

## 卸载

```bash
./uninstall.sh
```

---

## 命令详解

### spec-to-prd

将 spec markdown 文件转换为 PRD JSON 格式。**会自动分析现有项目结构**，生成与现有代码库兼容的 PRD。

```bash
spec-to-prd <SPEC_FILE> [OPTIONS]
```

> **注意**:
> - 如果 `.prd` 目录不存在，会自动初始化创建
> - 会自动分析当前目录的项目结构、配置文件、Git 信息

#### 项目上下文分析

`spec-to-prd` 会自动收集以下信息并提供给 Claude：

| 分析内容 | 说明 |
|----------|------|
| 目录结构 | 项目文件树（最深 4 层，排除 node_modules 等） |
| 配置文件 | package.json, pyproject.toml, tsconfig.json 等 |
| README | 项目文档 |
| Git 信息 | 当前分支、提交数量 |

这样生成的 PRD 会：
- 遵循现有代码风格和约定
- 引用需要修改的现有文件
- 考虑项目的技术栈（Node/Python/Rust 等）
- 增量开发而非重写

#### 参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `SPEC_FILE` | - | Spec markdown 文件路径（必需） |
| `--output FILE` | `-o` | 输出 PRD JSON 文件路径（默认: `.prd/prds/<name>.json`） |
| `--project NAME` | `-p` | 项目名称（默认: 从文件名推断） |
| `--model MODEL` | `-m` | Claude 模型: opus/sonnet/haiku（默认: sonnet） |
| `--timeout MINUTES` | - | Claude 超时时间，单位分钟（默认: 15） |
| `--help` | `-h` | 显示帮助信息 |

#### 使用示例

```bash
# 转换 spec 文件为 PRD（自动分析项目结构）
spec-to-prd my-feature.md

# 使用 opus 模型（更强的上下文理解）
spec-to-prd my-feature.md -m opus

# 使用 haiku 模型（更快更便宜）
spec-to-prd my-feature.md --model haiku

# 指定输出路径和项目名称
spec-to-prd my-feature.md -o output.json -p "My Project"

# 设置超时时间为 30 分钟
spec-to-prd my-feature.md --timeout 30
```

---

### impl-prd

自主循环实现 PRD 中的 user stories。

```bash
impl-prd [OPTIONS]
```

#### 参数

| 参数 | 说明 |
|------|------|
| `--prd FILE` | 指定 PRD 文件路径（默认: `.prd/prds/` 下最新的文件） |
| `--max-iterations N` | 最大循环迭代次数（默认: 50） |
| `--timeout MINUTES` | Claude 输出超时时间，单位分钟（默认: 15） |
| `--model`, `-m` | Claude 模型: opus/sonnet/haiku（默认: sonnet） |
| `--no-progress-threshold N` | 连续无进展次数阈值，超过后停止（默认: 3） |
| `--resume` | 从上次状态恢复继续执行 |
| `--status` | 显示当前状态后退出 |
| `--reset` | 重置状态，重新开始 |
| `--verbose` | 显示详细输出 |
| `--help` | 显示帮助信息 |

> **注意**: impl-prd 默认使用 `--dangerously-skip-permissions` 模式运行，以实现完全自主执行。

#### 使用示例

```bash
# 使用最新的 PRD 文件开始实现
impl-prd

# 使用 opus 模型
impl-prd -m opus

# 指定 PRD 文件
impl-prd --prd .prd/prds/my-feature.json

# 设置最大迭代次数和超时
impl-prd --max-iterations 100 --timeout 20

# 查看当前状态
impl-prd --status

# 从上次中断处恢复
impl-prd --resume

# 重置状态重新开始
impl-prd --reset

# 连续 5 次无进展后停止
impl-prd --no-progress-threshold 5
```

---

## 目录结构

首次运行 `spec-to-prd` 时会自动创建以下目录结构：

```
your-project/
└── .prd/
    ├── specs/          # 原始 spec markdown 文件（自动复制）
    ├── prds/           # 生成的 PRD JSON 文件
    ├── logs/           # 执行日志
    │   └── session_YYYYMMDD_HHMMSS/  # 每次运行的会话目录
    │       ├── config.json           # 运行配置快照
    │       ├── prd_snapshot.json     # PRD 开始时快照
    │       ├── args.json             # 命令行参数
    │       ├── session.log           # 主日志
    │       ├── loop_001.log          # 第 1 次循环的流式输出
    │       ├── loop_002.log          # 第 2 次循环的流式输出
    │       ├── ...
    │       └── summary.json          # 运行汇总报告
    ├── config.json     # 项目配置
    └── state.json      # 运行状态（用于恢复）
```

### 会话日志说明

每次运行 `impl-prd` 都会创建一个独立的会话目录，包含：

| 文件 | 说明 |
|------|------|
| `config.json` | 运行时的完整配置 |
| `prd_snapshot.json` | PRD 在运行开始时的状态 |
| `args.json` | 命令行参数 |
| `session.log` | 主日志文件 |
| `loop_NNN.log` | 每次循环的 Claude 流式输出 |
| `summary.json` | 运行汇总，包含每次循环的耗时统计 |

### summary.json 示例

```json
{
  "session_id": "20260202_143000",
  "start_time": "2026-02-02T14:30:00",
  "end_time": "2026-02-02T15:45:00",
  "total_duration_seconds": 4500.0,
  "exit_reason": "complete",
  "project": "MyProject",
  "total_stories": 5,
  "stories_completed": 5,
  "stories_completed_this_session": 3,
  "total_loops": 4,
  "successful_loops": 3,
  "failed_loops": 1,
  "total_api_calls": 4,
  "total_api_time_seconds": 3600.0,
  "avg_loop_duration_seconds": 1125.0,
  "loops": [
    {
      "loop_num": 1,
      "story_id": "US-001",
      "duration_seconds": 1200.0,
      "success": true,
      "story_passed": true
    }
  ]
}
```

### config.json 配置项

```json
{
  "max_calls_per_hour": 100,
  "max_iterations": 50,
  "timeout_minutes": 15,
  "output_format": "stream",
  "allowed_tools": [
    "Write", "Read", "Edit",
    "Bash(git *)", "Bash(npm *)", "Bash(pytest)"
  ],
  "session_expiry_hours": 24,
  "max_consecutive_failures": 3,
  "no_progress_threshold": 3
}
```

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `max_calls_per_hour` | 每小时最大 API 调用次数 | 100 |
| `max_iterations` | 最大循环迭代次数 | 50 |
| `timeout_minutes` | Claude 超时时间（分钟） | 15 |
| `output_format` | 输出格式: stream 或 json | stream |
| `allowed_tools` | 允许 Claude 使用的工具列表 | - |
| `session_expiry_hours` | 会话过期时间（小时） | 24 |
| `max_consecutive_failures` | 最大连续失败次数 | 3 |
| `no_progress_threshold` | 无进展阈值 | 3 |

---

## 快速开始

```bash
# 1. 进入你的项目目录
cd your-project

# 2. 创建 spec 文件
cat > my-feature.md << 'EOF'
# My Feature Spec

## Overview
Add a new feature to the project.

## Requirements
1. Create hello.py that prints "Hello, World!"
2. Add unit tests
3. Ensure type checking passes

## Acceptance Criteria
- hello.py exists and runs correctly
- All tests pass
- No type errors
EOF

# 3. 转换 spec 为 PRD（自动初始化 .prd 目录）
spec-to-prd my-feature.md

# 4. 开始自主实现循环
impl-prd
```

---

## 退出机制

impl-prd 有多种退出机制保护：

| 机制 | 触发条件 | 默认值 |
|------|----------|--------|
| 完成退出 | 所有 stories 的 `passes` 为 true | - |
| 最大迭代 | 达到 `--max-iterations` | 50 次 |
| 输出超时 | Claude 超过 N 分钟无输出 | 15 分钟 |
| 无进展断路 | 连续 N 次循环无 story 完成 | 3 次 |
| 速率限制 | 超过每小时调用次数限制 | 100 次/小时 |
| 用户中断 | Ctrl+C | - |

---

## PRD JSON 格式

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
      "acceptanceCriteria": ["Criterion 1", "Criterion 2", "Typecheck passes"],
      "priority": 1,
      "passes": false,
      "notes": "",
      "completed_at": null
    }
  ]
}
```

---

## 完成信号

Claude 完成 story 时应输出状态块：

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
