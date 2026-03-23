# Contributing to Bento

Thanks for your interest in contributing.

## Getting started

```bash
git clone https://github.com/HabiRabbu/bento.git
cd bento
pip install -e '.[dev]'
pytest
```

This installs the project in editable mode with development dependencies (pytest, pytest-qt, mypy, ruff).

## Commit messages

We follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/). Every commit message must have a **type**, an optional **scope**, and a **description**:

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | When to use |
|------|-------------|
| `feat` | A new feature or user-visible behaviour. |
| `fix` | A bug fix. |
| `docs` | Documentation only (README, CREATING_BLOCKS.md, docstrings). |
| `style` | Formatting, whitespace, lint fixes — no logic change. |
| `refactor` | Code change that neither fixes a bug nor adds a feature. |
| `perf` | Performance improvement. |
| `test` | Adding or updating tests. |
| `build` | Build system or dependency changes (pyproject.toml, PKGBUILD). |
| `ci` | CI/CD configuration (GitHub Actions workflows). |
| `chore` | Maintenance tasks that don't fit another type. |

### Scope

The scope is optional but encouraged. Use the module or area being changed:

```
feat(blocks): add on_periodic() lifecycle hook
fix(config): handle missing .env on first launch
docs(readme): add troubleshooting section for Wayland
test(loader): cover duplicate block ID override
ci(release): attach wheel to GitHub Release
```

### Breaking changes

Append `!` after the type/scope, and include a `BREAKING CHANGE:` footer:

```
feat(blocks)!: rename on_focus() to on_activate()

BREAKING CHANGE: All blocks must rename their on_focus() method to on_activate().
```

### Examples

```
feat(settings): add import/export buttons to settings dialog
fix(hotkey): re-register hotkey after KDE session restart
docs: add CREATING_BLOCKS.md guide
test(config): verify .env file permissions
chore: bump PyQt6 minimum to 6.6
```

## Pull requests

1. Fork the repo and create a branch from `main`.
2. Make your changes. Keep commits atomic — one logical change per commit.
3. Run the full check suite before pushing:
   ```bash
   ruff check bento_app/ tests/
   mypy bento_app/
   pytest
   ```
4. Open a pull request against `main`. The title should follow Conventional Commits format.
5. Fill in the PR description with what changed and why.

## Code style

- **Formatter/linter**: [Ruff](https://docs.astral.sh/ruff/) — config in `pyproject.toml`.
- **Type checking**: [mypy](https://mypy.readthedocs.io/) with strict settings.
- **Line length**: 99 characters.
- **Python version**: 3.11+ (use modern syntax — `|` unions, `match`, etc.).
- **Imports**: sorted by ruff (`isort`-compatible).
- **Docstrings**: use them for public classes and functions. One-liner is fine for simple methods.

## Testing

- All tests live in `tests/`.
- Use `pytest-qt` fixtures (`qapp`, `qtbot`) when testing Qt widgets.
- Set `QT_QPA_PLATFORM=offscreen` for headless CI (already set in `conftest.py`).
- Use `tmp_config_dir` and `loader_env` fixtures from `conftest.py` to isolate tests from real config.

## Block contributions

If you are contributing a new block to [bento-blocks](https://github.com/HabiRabbu/bento-blocks), see [CREATING_BLOCKS.md](CREATING_BLOCKS.md) for the full block API reference. The same conventions apply — conventional commits, ruff, and tests.

## Changelog

We maintain a [CHANGELOG.md](CHANGELOG.md) following [Keep a Changelog](https://keepachangelog.com/). When your PR adds a user-visible change, add an entry under the `[Unreleased]` section. The maintainer will move it to the appropriate version on release.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](bento/LICENSE).
