# YouTube Course Recovery V12

Esta recuperação usa o projeto antigo fornecido pelo usuário como referência **somente** para o fluxo frontend do módulo Curso → YouTube.

## Preservado do StudyFlow atual

- Home/branding UX v2
- Georgina / Marcos Cezar / Youtuber
- CSS responsivo e navegação mobile
- Templates atuais
- backend atual
- pipeline Python atual
- splitter atual
- downloader atual
- demais módulos

## Restaurado da referência comprovadamente funcional

`static/js/app.js` voltou ao comportamento do projeto antigo para o módulo Curso → YouTube:

1. inicia `/api/generate`;
2. acompanha SSE;
3. recebe `video_file` e `clips` no evento `complete`;
4. renderiza o vídeo principal imediatamente;
5. renderiza cada clip na aba Aulas;
6. não reidrata automaticamente curso antigo ao abrir `/curso`.

Isso remove os hotfixes de persistência/restauração que estavam bloqueando a tela e separa novamente UX de pipeline funcional.
