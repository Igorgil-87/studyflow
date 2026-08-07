"""
tools/anti_slop.py — bloco de regras compartilhado pra tirar o "cheiro de
IA" do texto gerado (descrição de clip, copy de carrossel, etc.).

Adaptado da skill open-source "Stop Slop" (github.com/hvpandya/stop-slop)
pro português e pro contexto do StudyFlow. Em vez de importar a skill
inteira como dependência, trouxemos só as regras que fazem diferença
prática pra conteúdo curto (descrição de vídeo, legenda de carrossel) —
o texto completo da skill é voltado pra prosa longa (ensaio, artigo).

Uso: cola ANTI_SLOP_RULES dentro do system prompt de qualquer chamada de
LLM que gere texto pro usuário final (não pra decisão interna/estrutura
de dados — só onde o TEXTO em si é o produto).
"""

ANTI_SLOP_RULES = """\
Regras pra não soar "gerado por IA" (aplique sempre, sem exceção):

- PROIBIDO abrir com frases de "limpar a garganta": "Aqui está...", \
"A verdade é...", "Vamos falar sobre...", "É importante destacar que...". \
Vai direto ao ponto.
- PROIBIDO advérbios terminados em "-mente" (realmente, basicamente, \
literalmente, simplesmente). Corta.
- PROIBIDO a estrutura "não é X, é Y" (contraste raso e repetitivo). \
Afirma Y direto.
- PROIBIDO frases genéricas vagas ("os resultados são significativos", \
"isso muda tudo", "a diferença é enorme"). Especifica O QUÊ, com número \
ou fato concreto sempre que possível.
- PROIBIDO travessão (—) separando duas ideias só pra soar "estiloso". \
Usa ponto ou vírgula.
- PROIBIDO terminar com frase de efeito genérica tipo fechamento de \
propaganda ("essa é a virada de chave", "não deixe essa chance passar").
- Varia o tamanho das frases. Três frases seguidas do mesmo tamanho = \
sinal de texto gerado.
- Trata o leitor como alguém esperto: nada de explicar demais, nada de \
"e isso é importante porque...". Afirma o fato, sem justificar óbvio.
- Verbo ativo, sujeito humano. Evita coisa abstrata "fazendo" ação \
humana ("a estratégia revela", "o dado mostra") — quem revela é a \
pessoa, não o dado.
"""
