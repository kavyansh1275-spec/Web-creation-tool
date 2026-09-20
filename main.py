import json
from config import CONFIG
from core import ProjectManager,TestRunner,AIProvider
from versions import build_pipeline

def run(request,version=7,existing_project=None):
    if not 1<=version<=7: raise ValueError('version must be 1-7')
    pipeline=build_pipeline(ProjectManager(CONFIG.workspace),AIProvider(CONFIG.api_key,CONFIG.model),TestRunner(),CONFIG)
    return pipeline[version-1].run(request,{'existing_project':existing_project} if existing_project else {})

def main():
    print('WEB CREATION TOOL - V1 to V7')
    request=input('What do you want to build? ').strip()
    if request:
        r=run(request,7); print(json.dumps({k:v for k,v in r.items() if k!='project'}|{'project_root':str(r['project'].root.resolve())},indent=2,default=str))
if __name__=='__main__': main()
