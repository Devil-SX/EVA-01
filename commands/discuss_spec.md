---
name: discuss_spec
description: Front-load all ambiguity resolution into the spec stage so the plan can execute in one shot without repeated user interaction later.
argument-hint: [spec file path]
---

# Core Philosophy

The cost of asking one more question now is minutes. The cost of discovering a wrong assumption during implementation is hours of rework and back-and-forth. **This command exists to pay the cheap cost upfront so the expensive cost never happens.**

Your goal: produce a spec so complete and a plan so precise that a downstream agent can execute it end-to-end with zero clarification questions.

---

Read the spec file provided by the user. If no file path is given, ask the user which spec they want to discuss.

After reading the spec, also read the repo's README, CLAUDE.md, directory structure, and other context to build a holistic understanding of the repository.

# Good Behaviors

## Discriminative Questioning — Use AskUserQuestion to Complete the Spec

Do not rush to conclusions. Your primary job is to **ask questions**.

Good behavior: after reading the spec, identify all ambiguous, missing, or potentially misleading parts, then use the `AskUserQuestion` tool to **ask the user round by round** rather than guessing and filling in yourself. Focus on 1-3 key questions per round to avoid overwhelming the user.

Directions for questioning include but are not limited to:
- **Boundary clarification**: "What is the input range for this feature? What edge cases need handling?"
- **Priority judgment**: "Among these requirements, which is the core? Which are nice-to-have?"
- **Hidden assumptions**: "Are you assuming condition X holds? What happens if it doesn't?"
- **User scenarios**: "Can you describe a typical usage scenario? Who uses this and when?"
- **Trade-off decisions**: "If A and B conflict, which do you prefer?"

Each round of questions should push the spec's clarity one step forward.

**Anti-pattern to avoid**: Asking vague, open-ended questions like "anything else?" — every question must target a specific gap that, if left unresolved, would cause implementation to stall or go wrong.

## Uncover Meta-Intent — Understand the Fundamental Purpose

Don't just look at what the spec literally says. Go one level up: **Why is the user building this repo? Where does this spec fit in their overall plan?**

Concrete approach:
1. **Infer repo purpose**: From the repo name, README, existing code structure, and commit history, deduce what core problem this repo aims to solve
2. **Locate spec's role**: Is this spec the repo's core functionality? A supporting tool? One piece of a larger goal?
3. **Verify with the user**: Present your inferred meta-intent to the user via `AskUserQuestion` for confirmation, e.g. "I believe the purpose of this repo is X, and this spec is meant to achieve the Y part — is that correct?"

The value of understanding meta-intent: **the same spec under different purposes may demand completely different implementation approaches.**

## Expand and Correct the Plan — Eliminate Future Interaction

This is where the upfront investment pays off. The plan must be refined to the point where **no further human input is needed during execution**.

After understanding the user's meta-intent, examine the existing plan in the spec (if any) and do the following:

1. **Check plan-to-intent alignment**: Can the current plan achieve the user's real intent in one pass? Are any steps missing?
2. **Fill in gaps**: If the plan only covers part of the picture, supplement the missing steps based on meta-intent so that executing the plan fully achieves the user's purpose
3. **Correct deviations**: If some steps diverge from the meta-intent (doing unnecessary work, or heading in the wrong direction), propose corrections
4. **Offer alternatives**: If you see a better path to the same goal, propose an alternative plan and explain why it's better

For each plan step, ask yourself: **"Could an agent get stuck here and need to ask the user?"** If yes, resolve that ambiguity now by asking the user during this discussion, not later during execution.

Key principle: **The plan's completeness goal is "achieve the user's intent in a single execution", not "do part of it and see".**

## Ground Engineering Details in Feasibility

Once the plan's direction is confirmed, the final step is turning the plan from "idea" into "executable engineering". Every detail left vague here becomes a blocking question during implementation.

Resolve these now:
- **Technical feasibility**: Does the tech stack support this? Are there known pitfalls?
- **Dependencies**: What preconditions are needed? Are external dependencies controllable?
- **Interface contracts**: How do modules communicate? What are the data formats?
- **Acceptance criteria**: How do we know it's done? What are the concrete test scenarios?
- **Failure modes**: What happens when things go wrong? What error handling is expected?

These engineering details should also be aligned with the user step by step via `AskUserQuestion`, not decided unilaterally.

## Final Output

After all discussion rounds are complete, write the results back to the spec file. The updated spec should be **self-contained** — anyone reading it should be able to implement without asking further questions.

Updated content must include:
- Complete requirements description after clarification
- Expanded/corrected plan with enough detail to execute without interruption
- Key engineering decisions and constraints
- Clear acceptance criteria
