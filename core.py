from dataclasses import dataclass, field
from pathlib import Path
import json, re, subprocess, time, os

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
            rel=str(rel).replace('\\\\','/').strip()
            if not rel or rel.startswith('/') or re.match(r'^[A-Za-z]:',rel) or '..' in Path(rel).parts:
                raise ValueError('Unsafe project path: '+rel)
            path=(project.root/rel).resolve()
            path.relative_to(project.root.resolve())
            if not isinstance(content,str): raise ValueError('File content must be text: '+rel)
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(content,encoding='utf-8'); project.files[rel]=content
    def snapshot(self,project):
        out={}
        for p in project.root.rglob('*'):
            if not p.is_file() or '.git' in p.parts:
                continue
            rel=str(p.relative_to(project.root))
            try:
                out[rel]=p.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                out[rel]=f'<binary file: {p.stat().st_size} bytes>'
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
    @staticmethod
    def safe_command(command):
        command=str(command).strip()
        if not command or len(command)>300:
            return False
        forbidden=['&&','||',';','|','>','<','`','$(']
        if any(token in command for token in forbidden) or '\n' in command or '\r' in command:
            return False
        allowed=re.match(r'^(python(?:\s+-m\s+[A-Za-z0-9_.-]+(?:\s+.*)?)?|pytest(?:\s+.*)?|npm\s+(?:test|run\s+[A-Za-z0-9:_-]+)(?:\s+.*)?|node\s+[A-Za-z0-9_./-]+(?:\s+.*)?)$',command,re.I)
        return bool(allowed)
    def run(self,project,commands,timeout=60):
        results=[]
        for command in commands:
            if not self.safe_command(command):
                results.append(TestResult(str(command),False,'Rejected unsafe or unsupported test command.',0.0))
            else:
                results.append(self.runner.run(command,project.root,timeout))
        return results
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
        models=[x.strip() for x in os.getenv('WEB_CREATION_MODELS',self.model).split(',') if x.strip()]
        last=None
        for model in models:
            try:
                response=self.client.models.generate_content(model=model,contents=prompt)
                text=getattr(response,'text','') or ''
                if text.strip():
                    self.model=model
                    return text
            except Exception as exc:
                last=exc
        if last: raise RuntimeError('All configured AI models failed: '+str(last))
        return ''
    @staticmethod
    def extract_json(text):
        text=text.strip()
        if text.startswith('```'): text=re.sub(r'^```(?:json)?\\s*|\\s*```$','',text,flags=re.I|re.S)
        return json.loads(text)

class Planner:
    SYSTEM='''You are the production engineering planner for a serious software-generation system.\nReturn ONLY valid JSON with project_name, files, test_commands, stack, summary.\nImplement the user's request completely, not as a toy scaffold.\nEvery requested major feature must have working code and relevant configuration.\nGenerate complete files, never pseudocode, TODO placeholders, ellipses, fake URLs, or claims of completed deployment.\nInclude automated tests for important business logic and major flows when the chosen stack supports them.\nUse environment variables for secrets and deterministic offline/demo behavior for AI features.\nNever invent real financial/business results; label estimates and assumptions.\nAll file paths must be relative and safe.'''
    def __init__(self,provider): self.provider=provider
    def plan(self,request):
        if not self.provider.client:
            return {
                'project_name': 'offline-generation',
                'files': {
                    'index.html': "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Offline Generation Mode</title><link rel='stylesheet' href='styles.css'></head><body><main><h1>Offline generation mode</h1><p>The AI provider is not configured. A production build was not falsely claimed.</p><p>Configure GEMINI_API_KEY and run the request again.</p></main></body></html>",
                    'styles.css': "body{font-family:system-ui,sans-serif;margin:0;padding:3rem;line-height:1.5}main{max-width:760px;margin:auto}"
                },
                'test_commands': [],
                'offline': True,
                'summary': 'AI provider unavailable; production generation not completed.'
            }
        raw=self.provider.generate(self.SYSTEM+'\nUser request:\n'+request)
        if not raw:
            raise RuntimeError('AI provider returned no content')
        plan=self.provider.extract_json(raw)
        if not isinstance(plan,dict) or not isinstance(plan.get('files'),dict):
            raise ValueError('AI returned an invalid project plan')
        return plan


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
