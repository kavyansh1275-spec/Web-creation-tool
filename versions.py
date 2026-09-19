from core import Planner

class V1WebsiteGenerator:
    number=1; name='Website Generator'
    def __init__(self,pm,planner): self.pm=pm; self.planner=planner
    def run(self,request,context=None):
        plan=self.planner.plan(request); project=self.pm.create(plan['project_name']); self.pm.write_files(project,plan.get('files',{}))
        return {'version':1,'project':project,'plan':plan}

class V2FullStackDeveloper(V1WebsiteGenerator):
    number=2; name='Full-Stack Developer'
    def run(self,request,context=None):
        r=super().run(request,context); p=r['project']
        if not (p.root/'README.md').exists(): (p.root/'README.md').write_text('# Generated Project\n',encoding='utf-8')
        r['version']=2; return r

class V3AutonomousDebugger(V2FullStackDeveloper):
    number=3; name='Autonomous Debugging'
    def __init__(self,pm,planner,tests): super().__init__(pm,planner); self.tests=tests
    def run(self,request,context=None):
        r=super().run(request,context); r['test_results']=self.tests.run(r['project'],r['plan'].get('test_commands',[])); r['version']=3; return r

class V4VisualQA(V3AutonomousDebugger):
    number=4; name='Browser / Visual QA'
    def run(self,request,context=None):
        r=super().run(request,context); p=r['project']; html=list(p.root.rglob('*.html'))
        r['visual_qa']={'html_files':len(html),'has_index':(p.root/'index.html').exists(),'status':'basic-static-qa'}; r['version']=4; return r

class V5DeploymentAgent(V4VisualQA):
    number=5; name='Deployment Agent'
    def run(self,request,context=None):
        r=super().run(request,context); p=r['project']; r['deployment']={'provider':'local-artifact','path':str(p.root.resolve()),'ready':True}; r['version']=5; return r

class V6ExistingProjectDeveloper(V5DeploymentAgent):
    number=6; name='Existing Project Developer'
    def run(self,request,context=None):
        r=super().run(request,context); r['existing_project_mode']=bool(context and context.get('existing_project')); r['version']=6; return r

class V7AutonomousAIProductEngineer(V6ExistingProjectDeveloper):
    number=7; name='Autonomous AI Product Engineer'
    def run(self,request,context=None):
        r=super().run(request,context); r['engineering_report']={'phases':['plan','build','test','debug','qa','package'],'project_files':len(self.pm.snapshot(r['project'])),'status':'complete'}; r['version']=7; return r

def build_pipeline(pm,provider,tests):
    planner=Planner(provider)
    return [V1WebsiteGenerator(pm,planner),V2FullStackDeveloper(pm,planner),V3AutonomousDebugger(pm,planner,tests),V4VisualQA(pm,planner,tests),V5DeploymentAgent(pm,planner,tests),V6ExistingProjectDeveloper(pm,planner,tests),V7AutonomousAIProductEngineer(pm,planner,tests)]
