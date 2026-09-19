import streamlit as st
from config import CONFIG
from core import ProjectManager,TestRunner,AIProvider
from versions import build_pipeline

st.set_page_config(page_title='Web Creation Tool',page_icon='🛠️',layout='wide')
st.title('Web Creation Tool')
st.caption('V1 → V7 AI web/product engineering pipeline')
request=st.text_area('What do you want to build?',height=140,placeholder='Build a modern fitness management website...')
version=st.slider('Engineering version',1,7,7)
existing=st.text_input('Existing project path (optional)')
if st.button('Build',type='primary') and request.strip():
    pm=ProjectManager(CONFIG.workspace); provider=AIProvider(CONFIG.api_key,CONFIG.model); tests=TestRunner(); tool=build_pipeline(pm,provider,tests)[version-1]
    with st.spinner(f'Running V{version}: {tool.name}...'):
        result=tool.run(request,{'existing_project':existing} if existing else {})
    st.success(f'V{version} complete')
    st.json({k:v for k,v in result.items() if k!='project'})
    st.code(str(result['project'].root.resolve()))
