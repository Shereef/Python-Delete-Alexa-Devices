# AI Agent Ruleset

This file contains guidelines for any AI coding assistant or agent (such as Cursor, Copilot, Antigravity, or Claude) interacting with this repository.

## General Project Rules

1. **Language & Stack:**
   - Python >= 3.13
   - Linter/Formatter: `ruff`
   - Package Management: `uv` or `pip`

2. **Code Style & Best Practices:**
   - Follow standard Python PEP8 formatting, but rely on `ruff` for the exact rules.
   - When modifying files, preserve existing docstrings and comments unless specifically requested to rewrite them.
   - Use type hints (`typing`) wherever applicable.
   - Keep functions small and modular.

3. **Security:**
   - Do NOT hardcode credentials, tokens, or API keys in the source code.
   - Use environment variables or local `config.json` (git-ignored) for configuration.
   - Follow the `SECURITY.md` guidelines for vulnerability handling.

4. **Commits and PRs:**
   - Write descriptive commit messages.
   - Break down large changes into logical, smaller PRs if possible.

5. **Tool Usage Constraints (for autonomous agents):**
   - Prefer reading files directly via the editor tools rather than running `cat` or `grep` via terminal when editing.
   - Always run linters (`ruff check .`) before declaring a task complete.
