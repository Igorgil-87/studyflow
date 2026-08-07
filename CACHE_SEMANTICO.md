# Cache semântico (camada `cache/`)

Evita repetir chamadas de LLM quando a entrada é **idêntica** (cache exato) ou
**muito parecida** (cache semântico). Cada acerto vira um trace `cache_hit` com
custo zero — então a economia aparece direto no dashboard `/obs`, em dólar.

Desligado por padrão. Liga com `CACHE_ENABLED=1`.

---

## Como funciona

Para cada operação cacheável, o `smart_call` faz, em ordem:

1. **Exato** — hash SHA-256 da entrada. Barato, sem embedding, pega re-runs do
   mesmo vídeo/tema (o caso mais comum em dev e demo).
2. **Semântico** — embedding da entrada (`text-embedding-3-small`) + similaridade
   de cosseno contra as entradas da mesma operação. Acima de `CACHE_SIM_THRESHOLD`
   (0.95), é acerto. Pega entradas parecidas (ex.: mesmo transcript com pequena
   variação).
3. **Miss** — chama o LLM de verdade (via `traced_llm`, com timeout + circuit
   breaker) e guarda o resultado para a próxima.

Operações cacheadas hoje: **quiz**, **roadmap**, **highlights**, **trends_synthesize**.
A segmentação ficou de fora de propósito (chamada barata).

| Arquivo | Papel |
|---|---|
| `cache/store.py` | tabela `llm_cache` no mesmo SQLite do obs; busca exata + cosseno |
| `cache/embeddings.py` | embedding via OpenAI (lazy); cai para cache exato se indisponível |
| `cache/llm_cache.py` | `smart_call(...)` — substitui `traced_llm` nas ops cacheáveis |

---

## Ligar

```bash
CACHE_ENABLED=1 python app.py
```

Gere o mesmo quiz/tema duas vezes e abra **/obs**: a segunda execução não
chama o LLM — aparece em "Cache · acertos" e "Cache · economia (USD)".

Variáveis (`.env`):

| Variável | Default | Efeito |
|---|---|---|
| `CACHE_ENABLED` | `0` | liga o cache |
| `CACHE_SEMANTIC` | `1` | liga a camada semântica (0 = só exato) |
| `CACHE_EMBED_MODEL` | `text-embedding-3-small` | modelo de embedding |
| `CACHE_SIM_THRESHOLD` | `0.95` | limiar de cosseno para acerto semântico |

---

## Por que isso é honesto (e não só bonito)

- **O embedding custa** (~100x menos que a geração). Em um *miss*, você paga
  geração + embedding; o ganho vem nos *hits*. O `/obs` mostra os dois lados,
  então dá pra ver se o cache compensa no seu padrão de uso — não é fé.
- **Threshold alto (0.95)** de propósito: cache semântico errado entrega
  resposta de outra pergunta. Melhor errar para o lado de chamar o LLM.
- **Resultado de fallback não é cacheado** (ex.: síntese de tendências que caiu
  para `{}`), para o cache não "congelar" uma degradação.

---

## O que está testado

`_cache_test.py` cobre, com embedder e LLM **falsos** (sem chave, sem rede):
miss→grava→acerto exato (zero nova chamada ao tool), acerto semântico em chave
quase-igual, miss real em entrada diferente, e a economia no `summary`.

```bash
python _cache_test.py
```

O que **só** dá pra ver na sua máquina: embeddings reais da OpenAI e a economia
acumulando no `/obs` após jobs de verdade.

---

## Limite honesto / próximo passo

A busca semântica hoje é uma varredura O(n) por namespace — ótima para um cache
pequeno, ruim se crescer muito. O upgrade natural é o **pgvector** (que você já
tinha no roadmap): troca-se `cache/store.search_semantic` por uma query
`ivfflat/hnsw`, sem mexer no resto. A interface já isola isso.
