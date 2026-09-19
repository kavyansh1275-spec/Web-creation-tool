from core import ProjectManager,TestRunner,AIProvider
from versions import build_pipeline

def test_all_versions():
    pipeline=build_pipeline(ProjectManager('workspace/test'),AIProvider(),TestRunner()); assert [x.number for x in pipeline]==list(range(1,8))

def test_v7(tmp_path):
    pipeline=build_pipeline(ProjectManager(tmp_path),AIProvider(),TestRunner()); r=pipeline[6].run('simple landing page',{}); assert r['version']==7; assert r['engineering_report']['project_files']>=2; assert (r['project'].root/'index.html').exists()
