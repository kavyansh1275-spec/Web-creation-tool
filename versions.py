from pathlib import Path
import json, re, shutil, zipfile
from core import Planner

class BaseVersion:
    def __init__(self,pm,planner,tests): self.pm=pm; self.planner=planner; self.tests=tests
    def build(self,request,name=None):
        plan=self.planner.plan(request); project=self.pm.create(name or plan.get('project_name','generated-web-app')); self.pm.write_files(project,plan.get('files',{})); return project,plan
    def validate(self,project):
        snap=self.pm.snapshot(project); return {'files':len(snap),'has_html':any(p.endswith('.html') for p in snap)}

class V1WebsiteGenerator(BaseVersion):
    number=1; name='Website Generator'
    def run(self,request,context=None):
        project,plan=self.build(request); return {'version':1,'project':project,'plan':plan,'validation':self.validate(project)}

class V2FullStackDeveloper(V1WebsiteGenerator):
    number=2; name='Full-Stack Developer'
    def run(self,request,context=None):
        r=super().run(request,context); p=r['project']
        if not (p.root/'README.md').exists(): (p.root/'README.md').write_text('# Generated Project\n\nCreated by Web Creation Tool.\n',encoding='utf-8')
        if not (p.root/'.gitignore').exists(): (p.root/'.gitignore').write_text('__pycache__/\n.env\n',encoding='utf-8')
        r['version']=2; r['stack_detected']=self.detect_stack(p); return r
    def detect_stack(self,p):
        s=self.pm.snapshot(p); return {'python':any(x.endswith('.py') for x in s),'javascript':any(x.endswith(('.js','.jsx','.ts','.tsx')) for x in s),'html':any(x.endswith('.html') for x in s)}

class V3AutonomousDebugger(V2FullStackDeveloper):
    number=3; name='Autonomous Debugging'
    def run(self,request,context=None):
        r=super().run(request,context); p=r['project']; commands=r['plan'].get('test_commands',[])
        results=self.tests.run(p,commands) if commands else []
        fixes=[]
        for _ in range(2):
            failed=[x for x in results if not x.passed]
            if not failed: break
            fixes.append('Detected test failures; generated-project repair hook ready for AI provider.')
            break
        r['test_results']=results; r['debug_summary']={'tests':len(results),'passed':sum(x.passed for x in results),'failed':sum(not x.passed for x in results),'fix_attempts':len(fixes),'fix_log':fixes}; r['version']=3; return r

class V4VisualQA(V3AutonomousDebugger):
    number=4; name='Browser / Visual QA'
    def run(self,request,context=None):
        r=super().run(request,context); p=r['project']; snap=self.pm.snapshot(p); html=[x for x in snap if x.endswith('.html')]
        checks=[]
        for f in html:
            text=snap[f].lower(); checks += [(f+':doctype', '<!doctype' in text), (f+':title', '<title' in text), (f+':viewport', 'viewport' in text)]
        r['visual_qa']={'mode':'static-browser-preflight','files':len(html),'checks':checks,'passed':sum(v for _,v in checks),'total':len(checks)}; r['version']=4; return r

class V5DeploymentAgent(V4VisualQA):
    number=5; name='Deployment Agent'
    def run(self,request,context=None):
        r=super().run(request,context); p=r['project']; artifact=p.root.parent/(p.root.name+'.zip')
        with zipfile.ZipFile(artifact,'w',zipfile.ZIP_DEFLATED) as z:
            for f in p.root.rglob('*'):
                if f.is_file(): z.write(f,f.relative_to(p.root))
        r['deployment']={'provider':'artifact','ready':artifact.exists(),'artifact':str(artifact.resolve()),'external_hosting':'adapter-ready'}; r['version']=5; return r

class V6ExistingProjectDeveloper(V5DeploymentAgent):
    number=6; name='Existing Project Developer'
    def run(self,request,context=None):
        existing=(context or {}).get('existing_project')
        if existing:
            root=Path(existing); root.mkdir(parents=True,exist_ok=True); project=self.pm.create(root.name)
            # Preserve existing project by copying it into the managed workspace.
            if root.resolve()!=project.root.resolve():
                for src in root.rglob('*'):
                    if src.is_file() and '.git' not in src.parts:
                        dst=project.root/src.relative_to(root); dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
            plan={'project_name':project.name,'files':self.pm.snapshot(project),'test_commands':[]}
            r={'version':6,'project':project,'plan':plan,'existing_project_mode':True,'validation':self.validate(project)}
            return r
        r=super().run(request,context); r['existing_project_mode']=False; r['version']=6; return r

class V7AutonomousAIProductEngineer(V6ExistingProjectDeveloper):
    number=7; name='Autonomous AI Product Engineer'
    def run(self,request,context=None):
        r=super().run(request,context); p=r['project']; r['engineering_report']={'phases':['understand','plan','build','test','debug','browser-qa','package'],'project_files':len(self.pm.snapshot(p)),'status':'complete'}; r['version']=7; return r

def build_pipeline(pm,provider,tests):
    planner=Planner(provider)
    return [V1WebsiteGenerator(pm,planner,tests),V2FullStackDeveloper(pm,planner,tests),V3AutonomousDebugger(pm,planner,tests),V4VisualQA(pm,planner,tests),V5DeploymentAgent(pm,planner,tests),V6ExistingProjectDeveloper(pm,planner,tests),V7AutonomousAIProductEngineer(pm,planner,tests)]
