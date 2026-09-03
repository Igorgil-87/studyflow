import sys, types, importlib.util as u

def load(name, path):
    spec=u.spec_from_file_location(name,path); m=u.module_from_spec(spec); spec.loader.exec_module(m); return m
pkg=types.ModuleType('rag'); pkg.__path__=['rag']; sys.modules['rag']=pkg
cfg=load('rag.config','rag/config.py'); sys.modules['rag.config']=cfg
chunk=load('rag.chunker','rag/chunker.py'); sys.modules['rag.chunker']=chunk
store_mod=load('rag.store','rag/store.py'); sys.modules['rag.store']=store_mod
index=load('rag.index','rag/index.py'); query=load('rag.query','rag/query.py')

def emb(t):
    t=(t or '').lower(); return [float(t.count('risco')+0.01), float(t.count('crédito')+0.01)]

st=store_mod.InMemoryStore()
units=[
    {'page': 3, 'text':'A política de risco exige revisão anual do crédito.'},
    {'page': 4, 'text':'O monitoramento contínuo reduz risco operacional.'},
]
n=index.index_document('material:abc_doc.pdf','texto',emb,st,source_name='Politica.pdf',source_type='pdf',units=units,max_chars=200)
assert n==2
hits=query.search('qual a política de risco?',emb,st,top_k=2,video_id='material:abc_doc.pdf')
sources=query.format_sources(hits)
assert sources[0]['source_name']=='Politica.pdf'
assert sources[0]['page'] in (3,4)
assert sources[0]['chunk_id'] is not None
assert sources[0]['score'] is not None
prompt=query.build_prompt('qual a política?',hits)
assert '[Fonte 1]' in prompt and 'página' in prompt
ans=query.answer('risco',emb,st,lambda p:'Revisão anual [Fonte 1].',top_k=2,video_id='material:abc_doc.pdf')
assert ans['sources'][0]['citation_id']==1
assert ans['retrieval_debug']['returned']==2
print('RAG CITATIONS + PAGE METADATA + RETRIEVAL DEBUG OK ✅')
