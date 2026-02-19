"""Conversion prompt template for spec-to-prd."""

CONVERSION_PROMPT = '''You are a PRD generator for an existing codebase.

## Task
Convert the following spec into a PRD (Product Requirements Document) JSON format.

## IMPORTANT: Analyze Project First
Before generating the PRD, you MUST:
1. Use Glob/Read tools to explore the current project structure
2. Read key configuration files (package.json, pyproject.toml, tsconfig.json, Cargo.toml, etc.)
3. Understand the existing code patterns, conventions, and architecture
4. Identify files that will need to be modified or extended
5. Identify the project's existing test framework and test directory structure (e.g., pytest, jest, mocha, cargo test)

## Input Spec:
{spec_content}

## PRD JSON Structure
Generate a valid JSON object with this exact structure:
```json
{{
  "project": "[Project name from spec or '{project_name}']",
  "branchName": "ralph/[feature-name-kebab-case]",
  "description": "[Brief description from spec]",
  "userStories": [
    {{
      "id": "US-001",
      "title": "[Short story title]",
      "description": "As a [user], I want [feature] so that [benefit]",
      "acceptanceCriteria": ["Criterion 1", "Criterion 2", "All tests pass"],
      "priority": 1,
      "passes": false,
      "notes": "[Reference specific existing files to modify]",
      "testPlan": "[Describe what tests to write: unit tests, integration tests, edge cases, expected inputs/outputs]"
    }}
  ]
}}
```

## Rules for PRD Generation:
1. **Analyze existing code patterns** - Follow the project's existing conventions, file organization, and coding style
2. **Consider dependencies** - Order stories by dependency (schema/types first, then core logic, then UI/API)
3. **Reference existing files** - In the notes field, mention specific files that will be modified or extended
4. **Incremental development** - Stories should build on existing codebase, not rewrite from scratch
5. **Small atomic stories** - Each story should be completable in one Claude session
6. **Quality criteria** - Always include appropriate quality checks (typecheck, lint, test) in acceptance criteria
7. **All stories start with passes: false**
8. **Priority numbers should be sequential (1, 2, 3, ...)**
9. **Every story MUST have a testPlan** - Describe the concrete tests to write: unit tests for new functions, integration tests for workflows, edge cases, and expected inputs/outputs. The testPlan should be specific enough that a developer can implement the tests from the description alone.
10. **acceptanceCriteria MUST include "All tests pass"** - Every story must have "All tests pass" (or equivalent) in its acceptance criteria to enforce regression testing before commit.

## Context-Aware Guidelines:
- If Node.js project: Consider npm scripts, existing test framework, TypeScript config
- If Python project: Consider existing test framework, type hints, package structure
- If existing tests exist: Stories should include updating/adding tests
- Identify the test runner (pytest, jest, mocha, cargo test, etc.) and note it in the first story's notes so the implementation agent knows how to run tests
- Reference the actual file paths you discovered during exploration

## IMPORTANT: Save PRD to File
After your analysis, use the Write tool to save the PRD JSON to this exact file path:
  {prd_output_path}

The JSON must be valid and parseable. Do NOT wrap it in markdown code blocks.
'''
