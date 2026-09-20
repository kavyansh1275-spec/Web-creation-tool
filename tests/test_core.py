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
