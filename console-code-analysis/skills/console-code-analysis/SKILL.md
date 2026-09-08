---
name: console-code-analysis
description: Analyze your software project with CONSOLE and explain the results in plain language.
---

# CONSOLE code analysis

When the user asks to:
- analyze the project using CONSOLE
- analyze a Pull Request using CONSOLE
- analyze the security of the project
- analyze the security of a Pull Request

run:
```bash
python ${CLAUDE_PLUGIN_ROOT}/skills/console-code-analysis/scripts/cli.py scan .
```

Read the complete output, which should be a JSON list of security clue objects. Each clue should have at least the following fields:
- `tool`: the name of the security tool producing this clue
- `category`: category of the security tool
- `name`: name of the security issue that was found
- `description`: the description produced by the security tool

Optionally, a clue may also contain fields such as `path`, `source_name` and `source_line` that help with the issue localization.

If the user requested a Pull Request to be analyzed, ignore all the clues that do not belong to the pull request. If the user wanted the entire project to be analyzed, consider all the clues.

Prioritize the clues based on severity. Do not rely on the `severity` field from the clue but make your own assessment. Clues that have the `duplicate` field set to `true` were already seen in previous scans so give them a lower priority.

Explain the results to the user in plain language.

Provide suggestions and propose remmediation actions.