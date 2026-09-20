from core import ProjectManager, TestRunner, AIProvider
from versions import build_pipeline

def test_all_versions(tmp_path):
    pipeline = build_pipeline(ProjectManager(tmp_path), AIProvider(), TestRunner())
    assert [x.number for x in pipeline] == list(range(1, 8))

def test_v7(tmp_path):
    pipeline = build_pipeline(ProjectManager(tmp_path), AIProvider(), TestRunner())
    r = pipeline[6].run("simple landing page", {})
    assert r["version"] == 7
    assert r["engineering_report"]["project_files"] >= 2
    assert (r["project"].root / "index.html").exists()

def test_v3_offline_has_no_fake_repair(tmp_path):
    pipeline = build_pipeline(ProjectManager(tmp_path), AIProvider(), TestRunner())
    r = pipeline[2].run("simple landing page", {})
    assert r["debug_summary"]["iterations"] == 0
    assert r["debug_summary"]["failed"] == 0

def test_v6_existing_project_copy(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "index.html").write_text("<!doctype html><html><head><title>x</title></head><body>x</body></html>", encoding="utf-8")
    pipeline = build_pipeline(ProjectManager(tmp_path / "workspace"), AIProvider(), TestRunner())
    r = pipeline[5].run("change the title", {"existing_project": str(source)})
    assert r["existing_project_mode"] is True
    assert (r["project"].root / "index.html").exists()
