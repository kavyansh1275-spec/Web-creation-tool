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


## Real standalone deployment

Generated websites no longer use a fake `?preview=` link as their public URL. The deployment layer publishes generated files into a dedicated `generated-sites/<project>` directory in the repository and creates an independent Render service.

For automatic deployment from the hosted Streamlit app, configure these environment variables on the Web Creation Tool service:

- `GITHUB_TOKEN` — GitHub token with Contents write access to this repository.
- `RENDER_API_KEY` — Render API key.
- `RENDER_OWNER_ID` — the Render workspace/owner ID.
- Optional: `GITHUB_REPOSITORY`, `GITHUB_BRANCH`, `DEPLOYMENT_BASE_PATH`.

Static HTML/CSS/JS projects are deployed as Render Static Sites and receive their own `onrender.com` URL. Projects containing server-side code are routed toward a Render Web Service configuration.

The Web Creation Tool only reports a live URL when the external deployment actually succeeds. Otherwise it clearly reports that the project was generated but not publicly deployed.


## Production safety gates

The tool does not treat scaffolding as a successful production build. Before deployment, supported generated projects must pass the available automated tests and browser/visual QA. Unsupported deployment stacks are rejected rather than guessed.

Deployment runtime detection:
- Static HTML: Render Static Site
- Node: requires package.json and a start script
- Python: requires requirements.txt or pyproject.toml plus app.py or main.py
- Unsupported/ambiguous stacks: deployment is blocked

Generated test commands are allowlisted before execution. Unsafe shell constructs are rejected.

CI regression tests run through GitHub Actions on pushes and pull requests to main.

## Release verification

Every release candidate can be verified through the pull-request regression workflow before it is merged to `main`. The workflow compiles the application modules, installs Playwright Chromium, runs the full pytest suite, and uploads the JUnit test report as an artifact. A release should only be merged after that workflow reports success.
