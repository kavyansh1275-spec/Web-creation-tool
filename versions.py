from pathlib import Path
import json, re, shutil, zipfile, os, subprocess, threading, http.server
from core import Planner, RepairEngine
from deployer import GitHubRenderDeployer

class BaseVersion:
    def __init__(self,pm,planner,tests,config=None): self.pm=pm; self.planner=planner; self.tests=tests; self.config=config
    def build(self,request,name=None):
        plan=self.planner.plan(request); project=self.pm.create(name or plan.get('project_name','generated-web-app')); self.pm.write_files(project,plan.get('files',{})); return project,plan
    def validate(self,project):
        snap=self.pm.snapshot(project); return {'files':len(snap),'has_html':any(p.endswith('.html') for p in snap)}
    @staticmethod
    def serial_results(results):
        return [{'name':x.name,'passed':x.passed,'output':x.output[-12000:],'duration':x.duration} for x in results]

class V1WebsiteGenerator(BaseVersion):
    number=1; name='Website Generator'
    def run(self,request,context=None):
        project,plan=self.build(request)
        result={'version':1,'project':project,'plan':plan,'validation':self.validate(project)}
        result['offline']=bool(plan.get('offline'))
        result['deployment']=({'success':False,'provider':'render','reason':'Offline generation was not deployed.'} if plan.get('offline') else GitHubRenderDeployer(project,self.config).deploy())
        return result

class V2FullStackDeveloper(V1WebsiteGenerator):
    number=2; name='Full-Stack Developer'
    def run(self,request,context=None):
        project,plan=self.build(request)
        if not (project.root/'README.md').exists(): (project.root/'README.md').write_text('# Generated Project\n\nCreated by Web Creation Tool.\n',encoding='utf-8')
        if not (project.root/'.gitignore').exists(): (project.root/'.gitignore').write_text('__pycache__/\n.env\n',encoding='utf-8')
        result={'version':2,'project':project,'plan':plan,'validation':self.validate(project),'stack_detected':self.detect_stack(project)}
        if plan.get('offline'):
            result['offline']=True
            result['deployment']={'success':False,'provider':'render','reason':'Offline generation did not produce a production-ready application; deployment was skipped.'}
        else:
            result['deployment']=GitHubRenderDeployer(project,self.config).deploy()
        return result
    def detect_stack(self,p):
        s=self.pm.snapshot(p); return {'python':any(x.endswith('.py') for x in s),'javascript':any(x.endswith(('.js','.jsx','.ts','.tsx')) for x in s),'html':any(x.endswith('.html') for x in s)}

class V3AutonomousDebugger(V2FullStackDeveloper):
    number=3; name='Autonomous Debugging'
    def _copy_existing(self, existing):
        root=Path(existing).expanduser().resolve()
        if not root.is_dir(): raise ValueError('Existing project not found: '+str(root))
        project=self.pm.create(root.name)
        if project.root.resolve() != root:
            for src in root.rglob('*'):
                if src.is_file() and '.git' not in src.parts and 'node_modules' not in src.parts and '__pycache__' not in src.parts:
                    dst=project.root/src.relative_to(root); dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
        return project

    def _restore(self, project, snapshot):
        current=self.pm.snapshot(project)
        for rel in current:
            if rel not in snapshot and not str(current[rel]).startswith('<binary file:'):
                (project.root/rel).unlink(missing_ok=True)
        self.pm.write_files(project,{k:v for k,v in snapshot.items() if not str(v).startswith('<binary file:')})

    def run(self,request,context=None):
        context=context or {}
        supplied_project=context.get('project'); existing=context.get('existing_project')
        if supplied_project is not None:
            p=supplied_project; plan={'project_name':p.name,'test_commands':[]}
        elif existing:
            p=self._copy_existing(existing); plan={'project_name':p.name,'test_commands':[]}
        else:
            p,plan=self.build(request)
        commands=list(plan.get('test_commands',[]) or [])
        if not commands:
            snap=self.pm.snapshot(p)
            if 'package.json' in snap:
                try:
                    if json.loads(snap['package.json']).get('scripts',{}).get('test'): commands=['npm test -- --runInBand']
                except Exception: pass
            elif 'pytest.ini' in snap or 'pyproject.toml' in snap or any(x.startswith('tests/') for x in snap):
                commands=['pytest -q']
        timeout=getattr(self.config,'command_timeout',60) if self.config else 60
        limit=max(1,getattr(self.config,'max_debug_iterations',3) if self.config else 3)
        results=self.tests.run(p,commands,timeout) if commands else []
        history=[]; accepted=bool(results) and all(x.passed for x in results)
        repairer=RepairEngine(self.planner.provider,self.pm,limit)
        for iteration in range(1,limit+1):
            failed=[x for x in results if not x.passed]
            if not failed and not (not commands and self.planner.provider.client and (supplied_project is not None or existing)):
                break
            before=self.pm.snapshot(p)
            evidence=[{'command':x.name,'output':x.output[-12000:]} for x in failed] or [{'command':'manual-debug-request','output':request+'\nPROJECT:\n'+json.dumps(before)}]
            repair=repairer.repair(p,evidence); repair['iteration']=iteration
            if not repair.get('changed_files'):
                history.append(repair); break
            trial=self.tests.run(p,commands,timeout) if commands else []
            trial_ok=bool(trial) and all(x.passed for x in trial)
            if trial_ok:
                results=trial; accepted=True; history.append({**repair,'accepted':True}); break
            self._restore(p,before)
            history.append({**repair,'accepted':False,'rollback':True})
            results=trial
        r={'version':3,'project':p,'plan':{**plan,'test_commands':commands},'validation':self.validate(p),
           'test_results':self.serial_results(results),
           'debug_summary':{**self.tests.summary(results),'iterations':len(history),'repair_history':history},
           'quality_gate':{'passed':accepted,'tests_defined':bool(commands),'tests_executed':bool(results),
                           'tests_passed':bool(results) and all(x.passed for x in results)}}
        if plan.get('offline'): r['offline']=True
        return r

class V4VisualQA(V3AutonomousDebugger):
    number=4; name='Browser / Visual QA'
    def run(self,request,context=None):
        r=super().run(request,context); p=r['project']; snap=self.pm.snapshot(p)
        checks=[]
        for f,t in snap.items():
            if f.endswith('.html'):
                low=t.lower(); checks += [(f+':doctype','<!doctype' in low),(f+':title','<title' in low),(f+':viewport','viewport' in low)]
        browser={'available':False,'passed':False,'reason':'Playwright is unavailable; browser QA cannot be considered passed.'}
        server=None; old=os.getcwd()
        try:
            from playwright.sync_api import sync_playwright
            class Handler(http.server.SimpleHTTPRequestHandler):
                def log_message(self,*args): pass
            os.chdir(p.root); server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            errors=[]
            with sync_playwright() as pw:
                browser_obj=pw.chromium.launch(headless=True); page=browser_obj.new_page(viewport={'width':1280,'height':800})
                page.on('pageerror',lambda e: errors.append(str(e)))
                response=page.goto('http://127.0.0.1:'+str(server.server_port)+'/index.html',wait_until='networkidle',timeout=15000)
                screenshot=p.root/'qa-screenshot.png'; page.screenshot(path=str(screenshot),full_page=True); browser_obj.close()
            browser={'available':True,'passed':bool(response and response.ok and not errors),'status':response.status if response else None,'errors':errors,'screenshot':str(screenshot)}
        except Exception as e:
            browser={'available':True,'passed':False,'reason':str(e)}
        finally:
            if server:
                server.shutdown(); server.server_close()
            os.chdir(old)
        r['visual_qa']={'static_checks':checks,'browser':browser,'passed':all(x[1] for x in checks) and browser['passed']}; r['version']=4; return r

class V5DeploymentAgent(V4VisualQA):
    number=5; name='Deployment Agent'
    def run(self,request,context=None):
        r=super().run(request,context); p=r['project']; artifact=p.root.parent/(p.root.name+'.zip')
        with zipfile.ZipFile(artifact,'w',zipfile.ZIP_DEFLATED) as z:
            for f in p.root.rglob('*'):
                if f.is_file() and f.name!='qa-screenshot.png': z.write(f,f.relative_to(p.root))
        qa_passed=bool(r.get('visual_qa',{}).get('passed'))
        test_results=r.get('test_results',[])
        tests_passed=bool(test_results) and all(item.get('passed') for item in r.get('test_results',[]))
        if not qa_passed or not tests_passed:
            artifact_ready=artifact.exists()
            r['deployment']={'artifact':str(artifact.resolve()),'artifact_ready':artifact_ready,
                'external':{'provider':'none','success':False,'reason':'Deployment blocked by failed or incomplete quality gates.'},
                'real':{'provider':'render','success':False,'reason':'Deployment blocked by failed or incomplete quality gates.'}}
            r['version']=5
            return r
        deploy={'provider':'none','success':False,'reason':'No deployment credentials configured'}
        if os.getenv('VERCEL_TOKEN') and shutil.which('vercel'):
            proc=subprocess.run(['vercel','--yes','--token',os.getenv('VERCEL_TOKEN')],cwd=p.root,text=True,capture_output=True,timeout=180); out=(proc.stdout or '')+(proc.stderr or '')
            deploy={'provider':'vercel','success':proc.returncode==0,'output':out[-12000:]}
        elif os.getenv('NETLIFY_AUTH_TOKEN') and shutil.which('netlify'):
            proc=subprocess.run(['netlify','deploy','--prod','--dir','.'],cwd=p.root,text=True,capture_output=True,timeout=180,env={**os.environ,'NETLIFY_AUTH_TOKEN':os.getenv('NETLIFY_AUTH_TOKEN')}); out=(proc.stdout or '')+(proc.stderr or '')
            deploy={'provider':'netlify','success':proc.returncode==0,'output':out[-12000:]}
        real={'success':False,'provider':'render','reason':'Deployment skipped because the project was generated in offline mode.'} if r.get('offline') else GitHubRenderDeployer(p,self.config).deploy()
        if real.get('success'):
            deploy={'provider':'render','success':True,'url':real.get('url'),'service_id':real.get('service_id'),'output':real.get('url','')}
        r['deployment']={'artifact':str(artifact.resolve()),'artifact_ready':artifact.exists(),'external':deploy,'real':real}; r['version']=5; return r

class V6ExistingProjectDeveloper(V5DeploymentAgent):
    number=6; name='Existing Project Developer'
    def run(self,request,context=None):
        existing=(context or {}).get('existing_project')
        if not existing:
            r=super().run(request,context); r['existing_project_mode']=False; r['version']=6; return r
        root=Path(existing).expanduser().resolve()
        if not root.is_dir(): raise ValueError('Existing project not found: '+str(root))
        project=self.pm.create(root.name)
        if project.root.resolve() != root:
            for src in root.rglob('*'):
                if src.is_file() and '.git' not in src.parts and 'node_modules' not in src.parts and '__pycache__' not in src.parts:
                    dst=project.root/src.relative_to(root); dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
        before=self.pm.snapshot(project); changed=False; explanation=''
        if self.planner.provider.client:
            prompt='Modify this project for the user request. Return ONLY JSON with files and explanation. Files must contain complete replacement contents.\nREQUEST:\n'+request+'\nPROJECT:\n'+json.dumps(before)
            try:
                patch=self.planner.provider.extract_json(self.planner.provider.generate(prompt)); files=patch.get('files',{})
                if isinstance(files,dict): self.pm.write_files(project,files); changed=bool(files)
                explanation=patch.get('explanation','')
            except Exception as e: explanation='AI change failed: '+str(e)
        snap=self.pm.snapshot(project); commands=[]
        if 'package.json' in snap:
            try:
                if json.loads(snap['package.json']).get('scripts',{}).get('test'): commands=['npm test -- --runInBand']
            except Exception: pass
        results=self.tests.run(project,commands) if commands else []
        result={'version':6,'project':project,'plan':{'project_name':project.name,'test_commands':commands},'existing_project_mode':True,'change_applied':changed,'change_explanation':explanation,'test_results':self.serial_results(results),'validation':self.validate(project)}
        if changed and results and all(x.passed for x in results):
            result['deployment']=GitHubRenderDeployer(project,self.config).deploy()
        elif changed:
            result['deployment']={'success':False,'provider':'render','reason':'Deployment was blocked because the modified project did not pass its automated tests.'}
        else:
            result['deployment']={'success':False,'provider':'render','reason':'No verified project modification was applied; deployment was intentionally skipped.'}
        return result

class V7AutonomousAIProductEngineer(BaseVersion):
    number=7; name='Autonomous AI Product Engineer'
    def run(self,request,context=None):
        p,plan=self.build(request)
        v3=V3AutonomousDebugger(self.pm,self.planner,self.tests,self.config).run(request,{'project':p})
        v4=V4VisualQA(self.pm,self.planner,self.tests,self.config).run(request,{'project':p})
        results=v4.get('test_results',[])
        tests_passed=bool(results) and all(x.get('passed') for x in results)
        qa_passed=bool(v4.get('visual_qa',{}).get('passed'))
        gate=tests_passed and qa_passed and not plan.get('offline')
        deployment=GitHubRenderDeployer(p,self.config).deploy() if gate else {'success':False,'provider':'render','reason':'Deployment blocked by final quality gates.'}
        return {'version':7,'project':p,'plan':plan,'validation':self.validate(p),'debug':v3,
                'visual_qa':v4.get('visual_qa'),'test_results':results,
                'quality_gate':{'passed':gate,'tests_passed':tests_passed,'browser_qa_passed':qa_passed},
                'deployment':deployment,
                'engineering_report':{'phases':['understand','plan','build','debug','test','browser-qa','final-gate','deploy'],
                                      'project_files':len(self.pm.snapshot(p)),
                                      'status':'completed' if deployment.get('success') else 'blocked_by_quality_gate'}}

def build_pipeline(pm,provider,tests,config=None):
    planner=Planner(provider)
    return [V1WebsiteGenerator(pm,planner,tests,config),V2FullStackDeveloper(pm,planner,tests,config),V3AutonomousDebugger(pm,planner,tests,config),V4VisualQA(pm,planner,tests,config),V5DeploymentAgent(pm,planner,tests,config),V6ExistingProjectDeveloper(pm,planner,tests,config),V7AutonomousAIProductEngineer(pm,planner,tests,config)]
