# Course media persistence — V11

## Bug corrigido
O curso podia renderizar normalmente ao concluir o pipeline, mas perder `video_file` e `clips` depois de refresh/restart.

A causa era uma condição de corrida no frontend: o evento `complete` persistia quiz/roadmap/vídeos, enquanto `renderQuiz()` disparava uma segunda gravação concorrente contendo apenas metadados do curso. Dependendo da ordem de conclusão dos POSTs, a segunda escrita podia deixar o curso persistido sem os caminhos de mídia.

## Correção
- removida a gravação concorrente dentro de `renderQuiz()`;
- o evento `complete` faz uma única persistência canônica contendo `job_id`, `source`, quiz, roadmap, vídeo completo e clips;
- `/api/curso-atual` pode reidratar campos faltantes diretamente do JobStore usando o `job_id` do próprio curso;
- não há varredura de arquivos globais, evitando misturar mídia entre usuários;
- `pipelines.py` e `tools/video_splitter.py` não foram alterados.

## Observação
Cursos persistidos por versões anteriores que não guardaram `job_id` não podem ser associados com segurança a arquivos existentes. Gere um novo curso uma vez na V11 para validar o fluxo completo e a persistência após F5.
