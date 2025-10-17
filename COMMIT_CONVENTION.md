# Commit Convention (Lightweight Conventional Commits)

A simple, consistent convention for writing commit messages. It keeps history readable and enables automation (changelogs, release notes).

---

## Format

```
<type>(optional scope): <short summary>

[optional body]
[optional footer(s)]
```

- **Use imperative mood** (e.g., `add`, `fix`, `update`).
- **Limit the first line to ≤ 72 chars.**
- Separate the body with a **blank line** when present.

---

## Types

| Type     | When to use it                                              | Examples |
|----------|--------------------------------------------------------------|----------|
| feat     | New feature or behavior                                      | `feat(parser): add lap timestamp support` |
| fix      | Bug fix                                                      | `fix(converter): handle missing cadence` |
| docs     | Documentation-only changes                                   | `docs: update README with usage example` |
| style    | Code style/formatting (no logic change)                      | `style: run black and isort` |
| refactor | Internal code changes without changing behavior              | `refactor(parser): extract header reader` |
| perf     | Performance improvements                                     | `perf(converter): speed up record loop` |
| test     | Add/modify tests, fixtures, test infra                       | `test: add smoke test for CSV output` |
| ci       | CI, linting, workflows                                       | `ci: add GitHub Actions for pytest` |
| chore    | Maintenance, deps, build, tooling                            | `chore: pin Python 3.14 in pyenv` |

**Optional scope** clarifies the area touched: `parser`, `converter`, `cli`, `docs`, `tests`, `infra`, etc.

---

## Body (optional)

Use the body to explain **why** the change was made, trade-offs, and context. Wrap at ~72–80 chars.

```
feat(converter): support multi-session FIT files

Adds session-splitting so multiple activities in a single FIT are exported
as separate CSVs. This avoids record mixing across sessions.
```

---

## Footers (optional)

- **Refs:** Link issues/tasks. Example: `Refs: #12`
- **Co-authored-by:** Attribute contributions.
- **BREAKING CHANGE:** If behavior changes incompatibly.

```
feat(cli): add --output-dir option

Refs: #34
```

**Breaking change example:**

```
feat(converter): drop legacy CSV header layout

BREAKING CHANGE: The CSV output no longer includes deprecated columns
`vertical_oscillation` and `stance_time_balance`. Downstream scripts must
be updated.
```

---

## Good History Examples

```
feat: implement basic FIT parsing and CSV export
fix(parser): handle empty record fields without crashing
docs: add usage instructions for CLI converter
test: add unit tests for record parser
chore: update .gitignore and pin Python version
```

---

## Optional: Commit Template

Save as `.gitmessage.txt` and set `git config commit.template .gitmessage.txt`

```
# <type>(<scope>): <summary>

# Why:
#

# What:
#

# Notes/Refs:
#

# BREAKING CHANGE:
# (Describe what changed and required migrations)
```

---

## Optional: Pre-commit Hook (local)

Use [pre-commit](https://pre-commit.com/) for linting/formatting before commits. Example `.pre-commit-config.yaml` snippet:

```
repos:
  - repo: https://github.com/psf/black
    rev: 24.8.0
    hooks:
      - id: black
  - repo: https://github.com/PyCQA/isort
    rev: 5.13.2
    hooks:
      - id: isort
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.6.3
    hooks:
      - id: ruff
```

---

## Tips

- Keep commits **small and focused**.
- Prefer multiple commits over one giant dump.
- If a commit mixes changes, consider **scopes** or split into multiple commits.
- Rebase or squash locally to maintain a clean, linear history when appropriate.
