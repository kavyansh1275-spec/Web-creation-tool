from pathlib import Path
import json, re, shutil, zipfile, os, subprocess
from core import Planner, RepairEngine

class BaseVersion:
    def __init__(self,pm,planner,tests,config=None): self.pm=pm; self.planner=planner; self.tests=tests; self.config=config
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
        r=super().run(request,context); p=r['project']
        commands=r['plan'].get('test_commands',[])
        timeout=getattr(self.config,'command_timeout',60) if self.config else 60
        limit=getattr(self.config,'max_debug_iterations',3) if self.config else 3
        results=self.tests.run(p,commands,timeout) if commands else []
        history=[]
        repairer=RepairEngine(self.planner.provider,self.pm,limit)
        for i in range(limit):
            failed=[x for x in results if not x.passed]
            if not failed: break
            repair=repairer.repair(p,[{'command':x.name,'output':x.output[-12000:]} for x in failed])
            repair['iteration']=i+1; history.append(repair)
            if not repair.get('changed_files'): break
            results=self.tests.run(p,commands,timeout)
        r['test_results']=self.serial_results(results)
        r['debug_summary']={**self.tests.summary(results),'iterations':len(history),'repair_history':history}
        r['version']=3; return r
class V4VisualQA(V3AutonomousDebugger):
    number=4; name='Browser / Visual QA'
    def run(self,request,context=None):
        r=super().run(request,context); p=r['project']; snap=self.pm.snapshot(p)
        checks=[]
        for f,t in snap.items():
            if f.endswith('.html'):
                low=t.lower()
                checks += [(f+':doctype','<!doctype' in low),(f+':title','<title' in low),(f+':viewport','viewport' in low)]
        browser={'available':False,'passed':True,'reason':'Playwright optional'}
        try:
            from playwright.sync_api import sync_playwright
            import threading, http.server, os
            class Handler(http.server.SimpleHTTPRequestHandler):
                def log_message(self,*args): pass
            old=os.getcwd(); os.chdir(p.root)
            server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            errors=[]
            with sync_playwright() as pw:
                browser_obj=pw.chromium.launch(headless=True)
                page=browser_obj.new_page(viewport={'width':1280,'height':800})
                page.on('pageerror',lambda e: errors.append(str(e)))
                response=page.goto('http://127.0.0.1:'+str(server.server_port)+'/index.html',wait_until='networkidle',timeout=15000)
                screenshot=p.root/'qa-screenshot.png'; page.screenshot(path=str(screenshot),full_page=True)
                browser_obj.close()
            server.shutdown(); server.server_close(); os.chdir(old)
            browser={'available':True,'passed':bool(response and response.ok and not errors),'status':response.status if response else None,'errors':errors,'screenshot':str(screenshot)}
        except Exception as e:
            browser={'available':True,'passed':False,'reason':str(e)}
        r['visual_qa']={'static_checks':checks,'browser':browser,'passed':all(x[1] for x in checks) and browser['passed']}
        r['version']=4; return r
class V5DeploymentAgent(V4VisualQA):
    number=5; name='Deployment Agent'
    def run(self,request,context=None):
        r=super().run(request,context); p=r['project']
        artifact=p.root.parent/(p.root.name+'.zip')
        with zipfile.ZipFile(artifact,'w',zipfile.ZIP_DEFLATED) as z:
            for f in p.root.rglob('*'):
                if f.is_file() and f.name!='qa-screenshot.png': z.write(f,f.relative_to(p.root))
        deploy={'provider':'none','success':False,'reason':'No deployment credentials configured'}
        if os.getenv('VERCEL_TOKEN') and shutil.which('vercel'):
            proc=subprocess.run(['vercel','--yes','--token',os.getenv('VERCEL_TOKEN')],cwd=p.root,text=True,capture_output=True,timeout=180)
            out=(proc.stdout or '')+(proc.stderr or '')
            deploy={'provider':'vercel','success':proc.returncode==0,'output':out[-12000:]}
        elif os.getenv('NETLIFY_AUTH_TOKEN') and shutil.which('netlify'):
            proc=subprocess.run(['netlify','deploy','--prod','--dir','.'],cwd=p.root,text=True,capture_output=True,timeout=180,env={**os.environ,'NETLIFY_AUTH_TOKEN':os.getenv('NETLIFY_AUTH_TOKEN')})
            out=(proc.stdout or '')+(proc.stderr or '')
            deploy={'provider':'netlify','success':proc.returncode==0,'output':out[-12000:]}
        r['deployment']={'artifact':str(artifact.resolve()),'artifact_ready':artifact.exists(),'external':deploy}
        r['version']=5; return r
class V6ExistingProjectDeveloper(V5DeploymentAgent):
    number=6; name='Existing Project Developer'
    def run(self,request,context=None):
        existing=(context or {}).get('existing_project')
        if not existing:
            r=super().run(request,context); r['existing_project_mode']=False; r['version']=6; return r
        root=Path(existing).expanduser().resolve()
        if not root.is_dir(): raise ValueError('Existing project not found: '+str(root))
        project=self.pm.create(root.name)
        for src in root.rglob('*'):
            if src.is_file() and '.git' not in src.parts and 'node_modules' not in src.parts and '__pycache__' not in src.parts:
                dst=project.root/src.relative_to(root); dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
        before=self.pm.snapshot(project); changed=False; explanation=''
        if self.planner.provider.client:
            prompt='Modify this project for the user request. Return ONLY JSON with files and explanation. Files must contain complete replacement contents.\nREQUEST:\n'+request+'\nPROJECT:\n'+json.dumps(before)
            raw=self.planner.provider.generate(prompt)
            try:
                patch=self.planner.provider.extract_json(raw); files=patch.get('files',{})
                self.pm.write_files(project,files); changed=bool(files); explanation=patch.get('explanation','')
            except Exception as e: explanation='AI change failed: '+str(e)
        snap=self.pm.snapshot(project)
        commands=[]
        if 'package.json' in snap:
            try:
                pkg=json.loads(snap['package.json']);
                if pkg.get('scripts',{}).get('test'): commands=['npm test -- --runInBand']
            except Exception: pass
        results=self.tests.run(project,commands) if commands else []
        r={'version':6,'project':project,'plan':{'project_name':project.name,'test_commands':commands},'existing_project_mode':True,'change_applied':changed,'change_explanation':explanation,'test_results':self.serial_results(results),'validation':self.validate(project)}
        return r
class V7AutonomousAIProductEngineer(V6ExistingProjectDeveloper):
    number=7; name='Autonomous AI Product Engineer'
    def run(self,request,context=None):
        r=super().run(request,context); p=r['project']; r['engineering_report']={'phases':['understand','plan','build','test','debug','browser-qa','deploy/package'],'project_files':len(self.pm.snapshot(p)),'tests':r.get('debug_summary',r.get('test_results')),'visual_qa':r.get('visual_qa'),'deployment':r.get('deployment'),'status':'completed_with_report'}; r['version']=7; return r

def build_pipeline(pm,provider,tests,config=None):
    planner=Planner(provider)
    return [V1WebsiteGenerator(pm,planner,tests,config),V2FullStackDeveloper(pm,planner,tests,config),V3AutonomousDebugger(pm,planner,tests,config),V4VisualQA(pm,planner,tests,config),V5DeploymentAgent(pm,planner,tests,config),V6ExistingProjectDeveloper(pm,planner,tests,config),V7AutonomousAIProductEngineer(pm,planner,tests,config)]
