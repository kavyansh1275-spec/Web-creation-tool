import json
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


def show_result(result):
    st.success(f"V{result.get('version', '?')} completed")
    project = result.get("project")
    if project:
        st.code(str(project.root.resolve()))
    safe = {k: v for k, v in result.items() if k != "project"}
    st.json(safe)


st.title("🛠️ Web Creation Tool")
st.caption("Choose what you want to do. The tool will ask only the questions needed for that job.")

# Main action menu
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
    description = st.text_area(
        "Describe your website",
        placeholder="Example: Create a modern gym management website with members, plans, payments and a dashboard.",
        height=160,
    )
    if st.button("Create Website", type="primary") and description.strip():
        show_result(run_tool(2, description.strip()))

elif mode == "modify":
    st.divider()
    st.header("✏️ Modify Project")
    options = project_options()
    if not options:
        st.info("No projects found in the workspace yet. Create a website first.")
    else:
        selected = st.selectbox("Choose your project", options)
        request = st.text_area(
            "What do you want to modify?",
            placeholder="Example: Add a dark mode toggle and improve the dashboard.",
            height=130,
        )
        if st.button("Modify Project", type="primary") and request.strip():
            path = str(CONFIG.workspace / selected)
            show_result(run_tool(6, request.strip(), {"existing_project": path}))

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
            request = st.text_area(
                "Describe the bug (optional)",
                placeholder="Example: The login button does nothing.",
                height=100,
            )
            if st.button("Debug Project", type="primary"):
                path = str(CONFIG.workspace / selected)
                show_result(run_tool(3, request.strip() or "Find and fix bugs in this project.", {"existing_project": path}))

    else:
        code = st.text_area(
            "Paste your code",
            placeholder="Paste the code you want the debugger to inspect...",
            height=300,
        )
        filename = st.text_input("Filename", value="index.html")
        request = st.text_area(
            "What is wrong? (optional)",
            placeholder="Example: The page is blank and the button does not work.",
            height=100,
        )
        if st.button("Debug Code", type="primary") and code.strip():
            project_name = "debug-session"
            project = pm.create(project_name)
            pm.write_files(project, {filename.strip() or "index.html": code})
            show_result(run_tool(3, request.strip() or "Find and fix bugs in the supplied code.", {"project": project}))

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
            path = str(CONFIG.workspace / selected)
            show_result(run_tool(4, request, {"existing_project": path}))

elif mode == "deploy":
    st.divider()
    st.header("🚀 Deploy / Package")
    options = project_options()
    if not options:
        st.info("No projects found in the workspace yet.")
    else:
        selected = st.selectbox("Choose your project", options)
        st.caption("The deployment step packages the project and uses Vercel/Netlify when their credentials and CLI are configured.")
        if st.button("Deploy / Package", type="primary"):
            path = str(CONFIG.workspace / selected)
            show_result(run_tool(5, "Prepare this existing project for deployment.", {"existing_project": path}))

elif mode == "full":
    st.divider()
    st.header("🤖 Full AI Product Engineer")
    description = st.text_area(
        "Describe the product you want built",
        placeholder="Example: Build a complete appointment booking web app for a local clinic.",
        height=160,
    )
    if st.button("Start Full Build", type="primary") and description.strip():
        show_result(run_tool(7, description.strip()))

st.divider()
with st.expander("Workspace projects"):
    options = project_options()
    if options:
        for name in options:
            st.write(f"📁 {name}")
    else:
        st.write("No generated projects yet.")

st.caption("Tip: Set GEMINI_API_KEY for AI generation, modification and autonomous repair. Offline scaffolding still works.")
