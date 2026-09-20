import json
from pathlib import Path
from core import ProjectManager, TestRunner, AIProvider, Planner

def test_safe_project_paths(tmp_path):
    pm = ProjectManager(tmp_path)
    p = pm.create("demo")
    pm.write_files(p, {"index.html": "<!doctype html><title>ok</title>"})
    assert (p.root / "index.html").exists()
    try:
        pm.write_files(p, {"../escape.txt": "no"})
        assert False
    except ValueError:
        pass

def test_offline_planner_is_honest():
    plan = Planner(AIProvider("")).plan("Build a production SaaS")
    assert plan["offline"] is True
    assert "production build was not falsely claimed" in plan["files"]["index.html"]

def test_json_extraction():
    assert AIProvider.extract_json('{"ok": true}')["ok"] is True

def test_project_snapshot(tmp_path):
    pm = ProjectManager(tmp_path)
    p = pm.create("demo")
    pm.write_files(p, {"index.html": "<html></html>"})
    snap = pm.snapshot(p)
    assert snap["index.html"] == "<html></html>"


def test_test_runner_rejects_shell_chaining(tmp_path):
    pm = ProjectManager(tmp_path)
    p = pm.create("demo")
    runner = TestRunner()
    results = runner.run(p, ["python -m pytest && echo unsafe"])
    assert len(results) == 1
    assert results[0].passed is False
    assert "Rejected unsafe" in results[0].output

def test_test_runner_allows_safe_pytest(tmp_path):
    pm = ProjectManager(tmp_path)
    p = pm.create("demo")
    (p.root / "test_ok.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8")
    results = TestRunner().run(p, ["pytest -q"], timeout=30)
    assert results[0].passed is True

def test_project_snapshot_handles_binary(tmp_path):
    pm = ProjectManager(tmp_path)
    p = pm.create("demo")
    binary = p.root / "asset.bin"
    binary.write_bytes(bytes([0, 159, 255, 0]))
    snap = pm.snapshot(p)
    assert snap["asset.bin"].startswith("<binary file: ")


def test_compile_imports_are_valid():
    import py_compile
    for name in ("app.py", "core.py", "versions.py", "deployer.py", "main.py"):
        py_compile.compile(name, doraise=True)
