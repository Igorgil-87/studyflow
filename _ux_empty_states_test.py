from pathlib import Path
root=Path(__file__).parent
checks={
 'templates/trends.html':['gtFilterEmpty','Nenhuma oportunidade nesta categoria','gtShowAllBtn'],
 'templates/catalogo.html':['catClearFilters','Nenhum curso corresponde a estes filtros'],
 'templates/trilhas.html':['trEmptyStart','Sua primeira trilha começa aqui'],
 'templates/certificados.html':['Seus certificados aparecerão aqui','Começar um curso'],
 'templates/eventos.html':['evEmptyCreate','Nenhum próximo evento'],
 'static/css/style.css':['UX Sprint 13 — Empty states','.ux-empty-state'],
 'static/js/trends.js':["$('gtFilterEmpty')","applyFilter('todos')"],
}
for f, needles in checks.items():
    text=(root/f).read_text()
    for n in needles: assert n in text, (f,n)
print('UX EMPTY STATES SPRINT 13 OK')
