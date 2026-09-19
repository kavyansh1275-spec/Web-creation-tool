from core import ProjectManager

def test_project_manager(tmp_path):
    pm=ProjectManager(tmp_path); p=pm.create('hello world'); pm.write_files(p,{'index.html':'<h1>Hello</h1>'}); assert (p.root/'index.html').read_text()=='<h1>Hello</h1>'

def test_snapshot(tmp_path):
    pm=ProjectManager(tmp_path); p=pm.create('x'); pm.write_files(p,{'a.txt':'abc'}); assert pm.snapshot(p)['a.txt']=='abc'
