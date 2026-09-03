# V15 — Course Composer / Georgina

## Objetivo
Transformar a revisão do Curso2 em um compositor editorial: a IA pode gerar texto, vídeo, áudio, podcast, quiz, exercício e respostas do tutor; o usuário decide o que realmente entra no curso final.

## Alterações
- Seleção por aula: Texto, Vídeo, Áudio, Podcast, Quiz e Exercício.
- Respostas do Professor podem ser adicionadas individualmente ao curso.
- `Enviar` do tutor foi substituído por `Perguntar`; cada resposta recebe `+ Incluir`.
- Botão final `Salvar curso` com título, autor, descrição e capa.
- Se nenhuma capa for informada, o StudyFlow gera uma capa Georgina própria.
- Curso final é salvo no Catálogo e mídia selecionada é copiada para pastas estáveis nos named volumes.
- Vídeo/áudio/podcast já gerados são reidratados ao reabrir a tela.
- Geração de vídeo deixa de resolver `lesson_id` pelo mapa mental e usa a lista real de aulas, evitando ficar preso em `Enfileirando...` quando a visualização do mapa falha.

## Persistência
- `lesson_inclusions` guarda a decisão editorial sem alterar o manifest original.
- Vídeos finais: `static/videos/saved_courses/<id>/curso2/`
- Áudios/podcasts: `static/audios/saved_courses/<id>/curso2/`
- Capas: `static/images/course-covers/`

## NotebookLM / Gemini Notebook Enterprise
A arquitetura recomendada é tratar NotebookLM como provider opcional, não como dependência do Course Engine. Hoje a API oficial do Gemini Notebook Enterprise (Preview) permite criar notebooks, adicionar fontes e gerar Audio Overviews. O produto oferece Video Overviews, mas a documentação pública consultada nesta fase ainda não expõe um método REST equivalente para geração de Video Overview. Portanto:

1. Primeira integração: sincronizar fontes do curso e gerar Audio Overview oficial.
2. Manter o vídeo do StudyFlow usando provider próprio até existir endpoint público documentado para Video Overview.
3. Não automatizar a interface web do NotebookLM pessoal nem depender de APIs não oficiais.

A integração exige projeto Google Cloud, Gemini Notebook Enterprise habilitado/licenciado, IAM e autenticação Cloud.
