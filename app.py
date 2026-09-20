import re
from pathlib import Path
import streamlit as st

from config import CONFIG
from core import ProjectManager, TestRunner, AIProvider
from versions import build_pipeline

st.set_page_config(page_title="Web Creation Tool", page_icon="🛠️", layout="wide")

pm = ProjectManager(CONFIG.workspace)
provider = AIProvider(CONFIG.api_key, CONFIG.model)
tests = TestRunner()
pipeline = build_pipeline(pm, provider, tests, CONFIG)


def project_dirs():
    if not CONFIG.workspace.exists():
        return []
    return sorted(
        [p for p in CONFIG.workspace.iterdir() if p.is_dir() and not p.name.startswith(".")],
        key=lambda p: p.name.lower(),
    )


def project_options():
    return [p.name for p in project_dirs()]


def run_tool(version, request, context=None):
    tool = pipeline[version - 1]
    with st.spinner(f"Running V{version}: {tool.name}..."):
        return tool.run(request, context or {})


def parse_error_locations(output, project_root):
    locations = []
    patterns = [
        re.compile(r'File ["\'](.+?)["\'], line (\d+)'),
        re.compile(r'([A-Za-z0-9_./\\-]+\.(?:py|js|jsx|ts|tsx|html|css|json)):(\d+)(?::(\d+))?'),
    ]
    for line in str(output or "").splitlines():
        for pattern in patterns:
            match = pattern.search(line)
            if not match:
                continue
            raw = match.group(1).replace("\\", "/")
            try:
                line_no = int(match.group(2))
            except ValueError:
                continue
            path = Path(raw)
            if path.is_absolute():
                try:
                    rel = path.resolve().relative_to(Path(project_root).resolve())
                except Exception:
                    rel = Path(raw)
            else:
                rel = Path(raw)
            locations.append({
                "file": str(rel).replace("\\", "/"),
                "line": line_no,
                "message": line.strip(),
            })
            break
    seen = set()
    unique = []
    for item in locations:
        key = (item["file"], item["line"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def show_code_location(project_root, file_path, line_no):
    root = Path(project_root).resolve()
    path = (root / file_path).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        st.error("Unsafe file location.")
        return
    if not path.exists() or not path.is_file():
        st.warning(f"File not found: {file_path}")
        return

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        st.info("The file is empty.")
        return

    idx = max(0, min(len(lines) - 1, line_no - 1))
    start = max(0, idx - 4)
    end = min(len(lines), idx + 5)
    st.markdown(f"**Location: {file_path} — line {line_no}**")
    for number in range(start, end):
        marker = "➡️" if number == idx else "  "
        st.code(f"{marker} {number + 1:>4} | {lines[number]}", language=path.suffix.lstrip(".") or "text")


def result_message(result):
    return {
        1: "Website created successfully.",
        2: "Full-stack project created successfully.",
        3: "Debugging finished.",
        4: "Browser / visual QA finished.",
        5: "Deployment / packaging finished.",
        6: "Project modification finished.",
        7: "Full product engineering finished.",
    }.get(result.get("version"), "Task finished.")


def show_result(result):
    project = result.get("project")
    root = str(project.root.resolve()) if project else None
    version = result.get("version")

    st.session_state.setdefault("chat", []).append({
        "role": "assistant",
        "content": result_message(result),
    })

    st.divider()
    st.subheader("💬 Web Creation Tool")
    st.success(result_message(result))

    if project:
        st.markdown("### Project")
        st.code(str(project.root.resolve()))

    if version in (1, 2, 6, 7) and project:
        if version in (1, 2, 7):
            st.info("Your project is ready in the workspace. Use Deploy / Package to publish it and get a public URL.")

    if version == 3:
        results = result.get("test_results", [])
        failed = [item for item in results if not item.get("passed")]

        if not results:
            st.success("No automated test command was available, so there are no test failures to report.")
        elif not failed:
            st.success(f"No errors found. {len(results)} test(s) passed.")
        else:
            st.error(f"Error found: {len(failed)} test(s) failed.")
            for index, failure in enumerate(failed):
                st.markdown(f"### Error {index + 1}: {failure.get('name', 'test')}")
                st.code(failure.get("output", ""), language="text")
                locations = parse_error_locations(failure.get("output", ""), root)
                if locations:
                    st.markdown("Click a location to jump to the problem:")
                    for loc_index, loc in enumerate(locations):
                        key = f"jump-{index}-{loc_index}-{loc['file']}-{loc['line']}"
                        if st.button(
                            f"📍 {loc['file']} — line {loc['line']}",
                            key=key,
                            use_container_width=True,
                        ):
                            st.session_state["code_location"] = (
                                root,
                                loc["file"],
                                loc["line"],
                            )
                            st.rerun()

        debug = result.get("debug_summary", {})
        if debug.get("iterations") is not None:
            st.caption(f"Repair/debug iterations: {debug.get('iterations', 0)}")

    elif version == 4:
        qa = result.get("visual_qa", {})
        if qa.get("passed"):
            st.success("Browser and visual QA passed.")
        else:
            st.error("QA found problems.")

        browser = qa.get("browser", {})
        screenshot = browser.get("screenshot")
        if screenshot and Path(screenshot).exists():
            st.image(screenshot, caption="Latest browser QA screenshot", use_container_width=True)

        for error in browser.get("errors", []):
            st.error("Browser error")
            st.code(error, language="text")

    elif version == 5:
        deployment = result.get("deployment", {})
        artifact = deployment.get("artifact")
        if deployment.get("artifact_ready") and artifact and Path(artifact).exists():
            st.success("Your packaged project is ready.")
            st.download_button(
                "⬇️ Download project ZIP",
                Path(artifact).read_bytes(),
                file_name=Path(artifact).name,
                mime="application/zip",
            )

        external = deployment.get("external", {})
        if external.get("success"):
            st.success("Your website has been deployed.")
            output = external.get("output", "")
            urls = re.findall(r"https?://[^\s\)]+", output)
            for index, url in enumerate(urls[:5]):
                st.link_button("🌐 Open deployed website", url, key=f"deploy-url-{index}")
        elif external.get("reason"):
            st.info(external["reason"])

    elif version == 6:
        if result.get("change_applied"):
            st.success("The requested changes were applied.")
        else:
            st.warning("No project changes were applied.")

        if result.get("change_explanation"):
            st.write(result["change_explanation"])

        failures = [item for item in result.get("test_results", []) if not item.get("passed")]
        if failures:
            st.error("The modified project has test failures.")
            for failure in failures:
                st.code(failure.get("output", ""), language="text")
        else:
            st.success("The modified project has no reported test failures.")

    elif version == 7:
        st.success("The full engineering pipeline completed.")
        report = result.get("engineering_report", {})
        st.write(" → ".join(report.get("phases", [])))

        deployment = report.get("deployment") or {}
        external = deployment.get("external", {}) if isinstance(deployment, dict) else {}
        if external.get("success"):
            output = external.get("output", "")
            urls = re.findall(r"https?://[^\s\)]+", output)
            for index, url in enumerate(urls[:5]):
                st.link_button("🌐 Open deployed website", url, key=f"v7-url-{index}")

    with st.expander("Technical result"):
        st.json({key: value for key, value in result.items() if key != "project"})


st.session_state.setdefault("chat", [])

st.title("🛠️ Web Creation Tool")
st.caption("Chat with the tool while it builds, modifies, debugs, tests, QA-checks and packages your projects.")

for message in st.session_state.get("chat", []):
    with st.chat_message(message["role"]):
        st.write(message["content"])

location = st.session_state.get("code_location")
if location:
    st.divider()
    st.subheader("🔎 Error location")
    show_code_location(*location)
    if st.button("Close code view"):
        del st.session_state["code_location"]
        st.rerun()

st.subheader("What do you want to do?")

c1, c2, c3 = st.columns(3)
with c1:
    create = st.button("🌐 Web Creation", use_container_width=True, type="primary")
    modify = st.button("✏️ Modify Project", use_container_width=True)
with c2:
    debug = st.button("🐞 Debug", use_container_width=True)
    qa = st.button("🔍 Browser / Visual QA", use_container_width=True)
with c3:
    deploy = st.button("🚀 Deploy / Package", use_container_width=True)
    full = st.button("🤖 Full AI Product Engineer", use_container_width=True)

if create:
    st.session_state["mode"] = "create"
if modify:
    st.session_state["mode"] = "modify"
if debug:
    st.session_state["mode"] = "debug"
if qa:
    st.session_state["mode"] = "qa"
if deploy:
    st.session_state["mode"] = "deploy"
if full:
    st.session_state["mode"] = "full"

mode = st.session_state.get("mode")

if mode == "create":
    st.divider()
    st.header("🌐 Web Creation")
    description = st.chat_input("Describe the website you want to create...")
    if description and description.strip():
        st.session_state["chat"].append({"role": "user", "content": description.strip()})
        show_result(run_tool(2, description.strip()))

elif mode == "modify":
    st.divider()
    st.header("✏️ Modify Project")
    options = project_options()
    if not options:
        st.info("No projects found in the workspace yet. Create a website first.")
    else:
        selected = st.selectbox("Choose your project", options)
        request = st.chat_input("Tell me what you want to change...")
        if request and request.strip():
            st.session_state["chat"].append({"role": "user", "content": request.strip()})
            show_result(run_tool(6, request.strip(), {"existing_project": str(CONFIG.workspace / selected)}))

elif mode == "debug":
    st.divider()
    st.header("🐞 Debug")
    source_mode = st.radio("How do you want to debug?", ["Choose a project", "Paste code"], horizontal=True)

    if source_mode == "Choose a project":
        options = project_options()
        if not options:
            st.info("No projects found in the workspace yet.")
        else:
            selected = st.selectbox("Choose your project to debug", options)
            request = st.chat_input("Tell me what is wrong, or ask me to find all bugs...")
            if request is not None:
                request_text = request.strip() or "Find and fix bugs in this project."
                st.session_state["chat"].append({"role": "user", "content": request_text})
                show_result(run_tool(3, request_text, {"existing_project": str(CONFIG.workspace / selected)}))
    else:
        code = st.text_area("Paste your code", height=300)
        filename = st.text_input("Filename", value="index.html")
        request = st.text_area("What is wrong? (optional)", height=100)
        if st.button("Debug Code", type="primary") and code.strip():
            project = pm.create("debug-session")
            pm.write_files(project, {filename.strip() or "index.html": code})
            request_text = request.strip() or "Find and fix bugs in the supplied code."
            st.session_state["chat"].append({"role": "user", "content": request_text})
            show_result(run_tool(3, request_text, {"project": project}))

elif mode == "qa":
    st.divider()
    st.header("🔍 Browser / Visual QA")
    options = project_options()
    if not options:
        st.info("No projects found in the workspace yet.")
    else:
        selected = st.selectbox("Choose your project to test", options)
        request = st.text_input("QA note (optional)", value="Run browser and visual QA on this project.")
        if st.button("Run QA", type="primary"):
            st.session_state["chat"].append({"role": "user", "content": request})
            show_result(run_tool(4, request, {"existing_project": str(CONFIG.workspace / selected)}))

elif mode == "deploy":
    st.divider()
    st.header("🚀 Deploy / Package")
    options = project_options()
    if not options:
        st.info("No projects found in the workspace yet.")
    else:
        selected = st.selectbox("Choose your project", options)
        if st.button("Deploy / Package", type="primary"):
            st.session_state["chat"].append({"role": "user", "content": f"Deploy/package {selected}"})
            show_result(run_tool(5, "Prepare this existing project for deployment.", {"existing_project": str(CONFIG.workspace / selected)}))

elif mode == "full":
    st.divider()
    st.header("🤖 Full AI Product Engineer")
    description = st.chat_input("Describe the product you want me to build...")
    if description and description.strip():
        st.session_state["chat"].append({"role": "user", "content": description.strip()})
        show_result(run_tool(7, description.strip()))

st.divider()
with st.expander("Workspace projects"):
    options = project_options()
    if options:
        for name in options:
            st.write(f"📁 {name}")
    else:
        st.write("No generated projects yet.")

st.caption("Set GEMINI_API_KEY for AI generation, modification and autonomous repair. Offline scaffolding still works.")
