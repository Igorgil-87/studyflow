from pathlib import Path
css=Path('static/css/style.css').read_text(encoding='utf-8')
required=['UX Sprint 14: responsive refinement','@media (max-width:1023px)','@media (max-width:767px)','@media (max-width:639px)','@media (max-width:380px)','94dvh','safe-area-inset-bottom','.cx-controls{grid-template-columns:1fr!important}','.ux-trend-card-top{flex-wrap:wrap}']
for x in required:
    assert x in css, x
for f in ['templates/home.html','templates/curso.html','templates/trends.html']:
    s=Path(f).read_text(encoding='utf-8')
    assert 'width=device-width, initial-scale=1.0' in s, f
print('UX RESPONSIVENESS SPRINT 14 OK')
