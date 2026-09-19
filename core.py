from dataclasses import dataclass, field
from pathlib import Path
import json, re, subprocess, time

@dataclass
class Project:
    name: str
    root: Path
    files: dict[str,str] = field(default_factory=dict)

@dataclass
class TestResult:
    name: str
    passed: bool
    output: str = ''
    duration: float = 0.0

class ProjectManager:
    def __init__(self, workspace):
        self.workspace=Path(workspace); self.workspace.mkdir(parents=True,exist_ok=True)
    def safe_name(self,name):
        value=re.sub(r'[^a-zA-Z0-9._-]+','-',name).strip('-')
        return value or 'generated-project'
    def create(self,name):
        root=self.workspace/self.safe_name(name); root.mkdir(parents=True,exist_ok=True)
        return Project(name,root)
    def write_files(self,project,files):
        if isinstance(files,list): files={x['path']:x['content'] for x in files}
        for rel,content in files.items():
            path=project.root/rel; path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(content,encoding='utf-8'); project.files[rel]=content
    def snapshot(self,project):
        out={}
        for p in project.root.rglob('*'):
            if p.is_file() and '.git' not in p.parts: out[str(p.relative_to(project.root))]=p.read_text(encoding='utf-8',errors='replace')
        return out

class CommandRunner:
    def run(self,command,cwd,timeout=60):
        start=time.time()
        try:
            p=subprocess.run(command,cwd=cwd,shell=True,text=True,capture_output=True,timeout=timeout)
            return TestResult(command,p.returncode==0,(p.stdout or '')+(p.stderr or ''),time.time()-start)
        except subprocess.TimeoutExpired as e:
            return TestResult(command,False,f'TIMEOUT: {e}',time.time()-start)

class TestRunner:
    def __init__(self,runner=None): self.runner=runner or CommandRunner()
    def run(self,project,commands,timeout=60): return [self.runner.run(c,project.root,timeout) for c in commands]
    def summary(self,results): return {'total':len(results),'passed':sum(r.passed for r in results),'failed':sum(not r.passed for r in results)}

class AIProvider:
    def __init__(self,api_key='',model='gemini-2.5-flash'):
        self.api_key=api_key; self.model=model; self.client=None
        if api_key:
            try:
                from google import genai
                self.client=genai.Client(api_key=api_key)
            except Exception: pass
    def generate(self,prompt):
        if not self.client: return ''
        response=self.client.models.generate_content(model=self.model,contents=prompt)
        return getattr(response,'text','') or ''
    @staticmethod
    def extract_json(text):
        text=text.strip()
        if text.startswith('```'): text=re.sub(r'^```(?:json)?\\s*|\\s*```$','',text,flags=re.I|re.S)
        return json.loads(text)

class Planner:
    SYSTEM='Return ONLY valid JSON with project_name, files, and test_commands. files must be an object mapping relative paths to complete contents. Never use absolute paths.'
    def __init__(self,provider): self.provider=provider
    def plan(self,request):
        raw=self.provider.generate(self.SYSTEM+'\nUser request:\n'+request)
        if raw: return self.provider.extract_json(raw)
        return {'project_name':'generated-web-app','files':{'index.html':"<!doctype html><html><head><meta charset='utf-8'><title>Generated App</title><link rel='stylesheet' href='styles.css'></head><body><main><h1>Generated Web App</h1><p>Project scaffold created successfully.</p></main></body></html>",'styles.css':"body{font-family:system-ui,sans-serif;margin:0;padding:3rem;line-height:1.5}"},'test_commands':[]}


class RepairEngine:
    def __init__(self, provider, pm, max_iterations=3):
        self.provider, self.pm, self.max_iterations = provider, pm, max_iterations
    def repair(self, project, failures):
        if not self.provider.client or not failures:
            return {'attempted': False, 'changed_files': [], 'reason': 'AI provider unavailable or no failures'}
        prompt = 'Return ONLY JSON with files and explanation. files must contain complete replacement contents. Fix these failures.\nPROJECT:\n' + json.dumps(self.pm.snapshot(project)) + '\nFAILURES:\n' + json.dumps(failures)
        raw = self.provider.generate(prompt)
        try:
            patch = self.provider.extract_json(raw)
            files = patch.get('files', {})
            if not isinstance(files, dict):
                return {'attempted': True, 'changed_files': [], 'reason': 'invalid patch'}
            self.pm.write_files(project, files)
            return {'attempted': True, 'changed_files': list(files), 'explanation': patch.get('explanation', '')}
        except Exception as e:
            return {'attempted': True, 'changed_files': [], 'reason': str(e)}
