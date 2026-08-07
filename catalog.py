"""
catalog.py — catálogo de cursos de exemplo para o Módulo Curso (enterprise).

Dados estáticos que alimentam a tela de Catálogo e o seletor de Trilhas.
Sem banco: é uma lista em memória. Quando quiser, dá para trocar por uma
tabela real sem mexer nas telas (elas consomem via /api/catalogo).
"""

CATEGORIAS = [
    "Back-end", "Front-end", "Dados", "Inteligência Artificial", "DevOps",
    "Cibersegurança", "Cloud", "UX & Design", "Mobile", "Inovação & Gestão",
]

NIVEIS = ["Básico", "Intermediário", "Avançado"]

# id, título, categoria, nível, horas, descrição
CURSOS = [
    {"id": "ia-decisao", "titulo": "Tomada de decisão com IA: otimizando estratégias com dados",
     "categoria": "Inteligência Artificial", "nivel": "Intermediário", "horas": 10,
     "desc": "Aprenda a tomar decisões estratégicas usando IA e ChatGPT. Crie modelos preditivos, simule previsões e analise métricas."},
    {"id": "video-eficiencia", "titulo": "Edição de vídeo: aumente a eficiência e produtividade",
     "categoria": "UX & Design", "nivel": "Básico", "horas": 10,
     "desc": "Aprenda a organizar suas edições no Adobe Premiere com técnicas de gradação de cores, organização e efeitos escaláveis."},
    {"id": "video-ad", "titulo": "Edição de vídeo: construa um AD empresarial",
     "categoria": "UX & Design", "nivel": "Avançado", "horas": 10,
     "desc": "Aprenda a utilizar transições, explore diversas técnicas e montagens para enriquecer suas edições."},
    {"id": "video-institucional", "titulo": "Edição de vídeo: criando um vídeo institucional",
     "categoria": "UX & Design", "nivel": "Intermediário", "horas": 10,
     "desc": "Aprenda a criar vídeos institucionais de alto impacto: enquadramentos, animações, transições e efeitos."},
    {"id": "video-identidade", "titulo": "Edição de vídeo: editando vídeos com identidade visual",
     "categoria": "UX & Design", "nivel": "Intermediário", "horas": 10,
     "desc": "Aprenda edição de vídeo com efeitos visuais, vinhetas, animações, motion design, lower thirds e videografismo."},
    {"id": "educacao-corp", "titulo": "Educação Corporativa: diagnosticando necessidades de treinamento",
     "categoria": "Inovação & Gestão", "nivel": "Avançado", "horas": 10,
     "desc": "Domine a educação corporativa e potencialize o desempenho da sua empresa através de estratégias de treinamento."},
    {"id": "python-backend", "titulo": "Desenvolvimento Back-End com Python",
     "categoria": "Back-end", "nivel": "Intermediário", "horas": 42,
     "desc": "Construa APIs robustas com Python: arquitetura, banco de dados, autenticação e boas práticas de produção."},
    {"id": "ml-engineering", "titulo": "Engenharia de Machine Learning",
     "categoria": "Dados", "nivel": "Avançado", "horas": 38,
     "desc": "MLOps na prática: pipelines, versionamento de modelos, deploy e monitoramento em produção."},
    {"id": "n8n-automacao", "titulo": "Automação de Processos com n8n",
     "categoria": "DevOps", "nivel": "Intermediário", "horas": 14,
     "desc": "Modelagem de fluxos e integração de sistemas: webhooks, triggers e orquestração sem código."},
    {"id": "cloud-aws", "titulo": "Cloud na AWS: fundamentos e arquitetura",
     "categoria": "Cloud", "nivel": "Básico", "horas": 24,
     "desc": "Provisione, escale e proteja aplicações na nuvem com os serviços essenciais da AWS."},
    {"id": "seg-ofensiva", "titulo": "Cibersegurança: introdução à segurança ofensiva",
     "categoria": "Cibersegurança", "nivel": "Intermediário", "horas": 20,
     "desc": "Pentest do zero: reconhecimento, exploração de vulnerabilidades e relatórios de segurança."},
    {"id": "react-front", "titulo": "Front-End moderno com React",
     "categoria": "Front-end", "nivel": "Intermediário", "horas": 30,
     "desc": "Componentização, hooks, estado e performance para interfaces web rápidas e escaláveis."},
]


def all_courses():
    return CURSOS


def by_id(cid: str):
    return next((c for c in CURSOS if c["id"] == cid), None)
