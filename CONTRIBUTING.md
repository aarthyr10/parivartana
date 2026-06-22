# Contributing to PARIVARTANA

Thanks for your interest in improving PARIVARTANA. This guide covers the local
setup, how to run the checks, and the conventions we follow for pull requests.

## Development setup

```bash
git clone <your-fork-url>
cd parivartana
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys / HUGGINGFACE_TOKEN as needed
```

Datasets and model checkpoints are **not** stored in git. See the
"Data & model downloads" section of `README.md` for how to obtain them. Most of
the test suite runs without any downloaded data — loaders degrade gracefully
when their local path is empty.

## Running the checks

```bash
pytest                       # unit + integration tests
pytest tests/unit            # unit tests only
ruff check .                 # lint
```

Please make sure `pytest` and `ruff check .` pass before opening a pull request.

## Pull request guidelines

- Branch from `main` and keep each PR focused on a single change.
- Write a clear description of *what* changed and *why*.
- Add or update tests for any behaviour change.
- Update the relevant docs (`README.md`, `docs/`) when you change public
  behaviour, configuration, or the dataset/model layout.
- Do not commit datasets, model weights, run outputs, secrets, or other files
  matched by `.gitignore`.

## Coding conventions

- Target Python 3.10+ and prefer type hints on public functions.
- Keep modules small and follow the existing package layout under `src/`.
- The codebase favours self-documenting names and docstrings over inline
  comments — keep new code in the same style.

## Reporting issues

Open a GitHub issue with a minimal reproduction: the COBOL input (or dataset
key), the command you ran, what you expected, and what happened instead.

## License

By contributing, you agree that your contributions will be licensed under the
MIT License (see `LICENSE`).
