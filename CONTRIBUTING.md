# Contributing to Term Chameleon

Thank you for your interest in contributing!

## Development setup

```bash
git clone https://github.com/connectwithprakash/term-chameleon.git
cd term-chameleon
uv sync --extra dev
```

## Running tests

```bash
uv run --extra dev pytest -q
```

## Linting

```bash
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
```

## Building

```bash
uv build
```

## Commit style

Use conventional commit messages:

- `feat:` new feature
- `fix:` bug fix
- `refactor:` code cleanup without behavior change
- `docs:` documentation only
- `ci:` CI/configuration
- `chore:` misc

## Pull requests

1. Fork and branch from `main`.
2. Ensure `ruff check` and `pytest` pass.
3. Add tests for new features.
4. Keep commits focused.

## iTerm2 integration testing

For live iTerm2 testing:

```bash
uv sync --extra iterm
uv run term-chameleon iterm-api-check
```

macOS Screen Recording permission is required for screenshot-based testing.
