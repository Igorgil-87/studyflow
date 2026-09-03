from pathlib import Path
root=Path(__file__).parent
home=(root/'templates/home.html').read_text()
curso=(root/'templates/curso.html').read_text()
trends=(root/'templates/trends.html').read_text()
trends_js=(root/'static/js/trends.js').read_text()
app_js=(root/'static/js/app.js').read_text()
assert 'O StudyFlow guia você pelo próximo passo.' in home
assert 'Criar plano de estudo' in curso
assert 'Adicionar link' in curso
assert 'Agente trabalhando' in curso
assert 'Buscar oportunidades' in trends
assert 'Como esta análise foi feita' in trends
assert "label.textContent = 'Buscar oportunidades'" in trends_js
assert 'Fontes para conferir' in trends_js
assert 'Criar conteúdo com esta ideia' in trends_js
assert 'Não foi possível adicionar este material. Tente novamente.' in app_js
assert 'Falha ao indexar a URL' not in app_js
print('UX WRITING SPRINT 11 OK')
