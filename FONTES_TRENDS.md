# Fontes das tendências — Perplexity + Notícias

As tendências agora podem usar duas fontes extras que trazem temas **atuais e
específicos** (não genéricos) e **com fontes clicáveis** nos cards:

- **Perplexity Sonar** — IA com busca na web embutida; devolve assuntos do
  momento já com citações (links reais).
- **API de notícias** (GNews ou NewsData) — manchetes recentes com link.

Ambas são **opcionais e fail-open**: sem chave, o pipeline segue com Reddit,
HackerNews, Wikipedia e YouTube (como antes). Com elas, a qualidade sobe bastante.

---

## Perplexity (o que mais melhora os temas)

1. Crie uma conta em https://www.perplexity.ai/settings/api e gere uma API key.
   Contas novas costumam vir com crédito de teste.
2. No `.env`:
   ```properties
   PERPLEXITY_API_KEY=pplx-...
   PERPLEXITY_MODEL=sonar        # o mais barato (US$ ~0,20–1 por 1M tokens)
   ```
   O modelo `sonar` é o econômico e já inclui busca + citações. Não precisa de
   modelo caro para listar tendências.

Custo: a Sonar base fica na casa de centavos por consulta de tendências. Como já
existe o cache de 1h das trends, buscas repetidas nem chamam a IA de novo.

## Notícias (GNews — tem tier grátis)

1. Crie uma chave grátis em https://gnews.io (o plano free dá ~100 buscas/dia).
2. No `.env`:
   ```properties
   NEWS_PROVIDER=gnews
   NEWS_API_KEY=sua_chave_gnews
   NEWS_LANG=pt
   NEWS_COUNTRY=br
   ```

Prefere outro provedor? O NewsData.io também é suportado:
```properties
NEWS_PROVIDER=newsdata
NEWS_API_KEY=sua_chave_newsdata
```

---

## O que muda na prática

- Os cards de tendência passam a mostrar uma seção **FONTES** com links
  clicáveis (das citações da Perplexity e das manchetes de notícia).
- O ranker (Chain 1) foi ajustado para **preferir assuntos específicos e
  recentes** (nomes, eventos, fatos datados) em vez de temas genéricos — e dá
  peso extra ao que vem da Perplexity e das notícias, por serem os mais atuais.

## O que está testado

`_sources_test.py` valida, com respostas HTTP simuladas: o parse de tópicos e
citações da Perplexity, o parse de manchetes do GNews e do NewsData, e o
comportamento fail-open sem chave.

> Transparência: as chamadas reais às APIs (Perplexity/GNews) dependem das suas
> chaves e de rede, então não as exercitei aqui. A lógica de parsing está
> coberta por testes; o ida-e-volta real você confirma ao pôr as chaves no
> `.env` e escanear as tendências.

---

## X / Twitter (polêmicas + o que bomba)

O X traz o "pulso do momento" e as polêmicas — mas a API oficial ficou cara
(sem tier grátis, paga por leitura). Por isso usamos uma **API de terceiro**
barata, configurável por env.

1. Crie conta na **twitterapi.io** (US$ 1 de crédito grátis, sem cartão) e copie
   a API key. Custo: ~US$ 0,15 por 1.000 tweets.
2. No `.env`:
   ```properties
   X_ENABLED=1
   X_PROVIDER=twitterapi      # ou getxapi
   X_API_KEY=sua_chave
   X_LANG=pt
   X_MIN_FAVES=300            # só tweets com engajamento (o que bomba)
   ```

Como funciona: para cada categoria fazemos **duas buscas** — uma do que está
**bombando** (filtro `min_faves`) e uma de **polêmicas** (termos como treta,
revolta, escândalo). Os tweets viram insumo pro ranker, e os links aparecem
como fontes nos cards.

Custo: cada escaneamento faz ~2 buscas por categoria. Com `min_faves` alto,
volta pouco tweet (barato), e o cache de 1h evita repetição. Aparece no FinOps.

`_x_test.py` valida (com respostas simuladas no formato real da twitterapi.io)
a montagem das queries, o parse dos tweets, os headers por provider e o
fail-open sem chave. As chamadas reais dependem da sua chave e de rede.
