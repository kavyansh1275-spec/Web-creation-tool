# Web Creation Tool

AI-assisted web/product engineering system with seven progressive capabilities.

## Versions
1. Website Generator
2. Full-Stack Developer
3. Autonomous Debugging
4. Browser / Visual QA preflight
5. Deployment packaging
6. Existing Project Developer
7. Autonomous AI Product Engineer

## Run
Install dependencies with `pip install -r requirements.txt`.
Run CLI with `python main.py` or UI with `streamlit run app.py`.
Set `GEMINI_API_KEY` to enable AI generation. Without a key, deterministic offline scaffolding and tests still work.

## Testing
Run `python -m pytest -q`. GitHub Actions also runs the test suite on pushes and pull requests.

The repository is independent and does not depend on AI-Workflow-Orchestrator.
