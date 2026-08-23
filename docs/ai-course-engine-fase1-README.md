# AI Course Generation Engine — Fase 1 · README de handoff

Ver diagnóstico completo em `ai-course-engine-diagnostico.md`. Este arquivo é só
o checklist prático pra colocar a Fase 1 no ar e validar com LLM de verdade.

## 1. Variáveis de ambiente necessárias

Já devem existir no seu `.env` (reaproveitadas):
```
DATABASE_URL=postgresql://...        # curso/store.py usa o mesmo Postgres do resto
ANTHROPIC_API_KEY=sk-ant-...         # AINDA NÃO CRIADA — é o próximo passo seu
OPENAI_API_KEY=sk-...                # já existe — usado como fallback
```

Novas, opcionais (têm default sensato, só mexe se quiser trocar o tier):
```
COURSE_ENGINE_MODEL=claude-opus-4-8          # CurriculumAgent + LessonContentAgent
COURSE_ENGINE_FALLBACK_MODEL=gpt-4o          # fallback se a Anthropic cair
COURSE_ENGINE_QUIZ_MODEL=                    # vazio = usa o mesmo de COURSE_ENGINE_MODEL
```

## 2. Nenhuma migração manual necessária

`curso/store.py` cria o schema sozinho (`CREATE TABLE IF NOT EXISTS` +
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) na primeira chamada — mesmo padrão
de `analytics/store.py` e `rag/store.py`. Não precisa rodar nada à parte, só
subir o código.

## 3. Checklist de validação com a chave da Anthropic (quando ela existir)

1. Confirma que `pip install -r requirements.txt` já cobre tudo — não
   adicionei nenhuma dependência nova (`langchain-anthropic` já estava
   pinado no requirements.txt do projeto).
2. Sobe o app normalmente (`docker compose -f docker-compose.prod.yml up -d
   --build` ou local).
3. Vai em `/curso` → aba **📄 Modo Criativo** → sobe um documento real
   (PDF/DOCX/PPTX/TXT/MD) → preenche o formulário → "Analisar material e
   gerar estrutura".
4. **É aqui que a saída do Claude de verdade aparece pela primeira vez** —
   tudo que testei até agora foi com o LLM mockado. Coisas pra prestar
   atenção nessa primeira geração real:
   - O manifest veio com módulos/aulas fazendo sentido pedagógico (não só
     uma lista solta de tópicos)?
   - Os `knowledge_gaps` (se aparecerem) fazem sentido, ou o modelo está
     inventando lacuna que não existe?
   - `audience`/`difficulty`/`style` vieram dentro dos valores permitidos
     (o código normaliza pro default se vier fora da lista — se isso
     disparar toda hora, o prompt precisa de ajuste)?
5. Na tela de revisão (`/curso2/<id>/revisar`), edita alguma coisa, salva,
   confirma que persistiu. Aprova.
6. Clica em "Gerar conteúdo desta aula" numa aula. Isso já é uma segunda
   chamada de LLM (LessonContentAgent) + uma terceira (quiz/flashcards via
   `tools/quiz_generator.py` com `provider="anthropic"`). Confirma que:
   - A explicação gerada realmente ensina o conceito (não só descreve
     "nesta aula vamos ver X").
   - O quiz faz sentido em cima do texto gerado (não do documento
     original inteiro — hoje o quiz é gerado a partir da explicação da
     aula, não do PDF cru).
7. Confere em `/obs` que as chamadas novas aparecem com custo — se não
   aparecer nada, é o mesmo bug do `output/observability.db` que já
   corrigimos (volume `obs_data` — confirma que o deploy que você está
   testando já tem esse volume).

## 4. Se o Claude real divergir do que o mock simulou

O ponto mais provável de atrito é o `PydanticOutputParser` falhar em
parsear a resposta (Claude decidir formatar diferente do JSON esperado).
Se isso acontecer:
- O erro aparece como `CurriculumAgentError` ou `LessonAgentError` (ambos
  capturados e devolvidos como JSON de erro pela rota, não como 500 cru).
- Antes de mexer no schema, tenta primeiro só reforçar no `_SYSTEM_PROMPT`
  (`curso/curriculum_agent.py` / `curso/lesson_agent.py`) que a resposta
  tem que seguir EXATAMENTE o formato pedido — geralmente resolve sem
  precisar trocar de biblioteca de parsing.

## 5. Onde isso já está gravado na memória do projeto

Todo o histórico desta feature (diagnóstico, decisões, bugs corrigidos no
caminho) está em `/areas/ai-course-engine.md` — não precisa repetir
contexto numa conversa nova, é só perguntar "cadê o AI Course Generation
Engine" ou similar.
