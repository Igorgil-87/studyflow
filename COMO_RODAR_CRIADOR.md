# Como rodar o Módulo Criador (StudyFlow + MoneyPrinterTurbo juntos)

O Módulo Criador gera vídeos usando o **MoneyPrinterTurbo** como motor.
Os dois rodam juntos com **um comando**, via Docker. Siga os 3 passos.

---

## Passo 1 — Organize as pastas

Coloque a pasta do MoneyPrinter **ao lado** da pasta do StudyFlow:

```
seu-projeto/
├── youtube-study-agent/        ← este projeto (StudyFlow)
│   └── docker-compose.full.yml
└── MoneyPrinterTurbo-main/     ← descompacte o zip do MoneyPrinter aqui
    ├── Dockerfile
    ├── main.py
    └── config.example.toml
```

Se a pasta do MoneyPrinter tiver outro nome, abra o `docker-compose.full.yml`
e ajuste as duas linhas que têm `../MoneyPrinterTurbo-main`.

---

## Passo 2 — Configure as chaves do MoneyPrinter

O MoneyPrinter precisa de duas chaves (a voz Edge TTS é grátis e não precisa):

```bash
cd MoneyPrinterTurbo-main
cp config.example.toml config.toml
```

Edite o `config.toml`:
- **pexels_api_keys** → chave grátis em https://www.pexels.com/api/ (banco de vídeos)
- a chave do **LLM** que você usar (OpenAI, etc.) — na seção do provedor escolhido

E no StudyFlow, tenha seu `.env` com `OPENAI_API_KEY` (como você já usa).

---

## Passo 3 — Suba tudo com um comando

Da pasta do StudyFlow:

```bash
docker compose -f docker-compose.full.yml up --build
```

A primeira vez demora (ele builda o MoneyPrinter). Quando terminar:

- **StudyFlow** → http://localhost:5001
- **MoneyPrinter API** → http://localhost:8080/docs (não precisa abrir; é o motor)

Agora entre no StudyFlow, vá no **Módulo Criador**, digite um tema e gere.
O StudyFlow manda a tarefa pro MoneyPrinter, acompanha o progresso e traz o
vídeo final pra `static/videos/`.

---

## Como saber que está funcionando

- No Módulo Criador, ao gerar, a barra de progresso avança (footage → narração
  → legendas → render). Isso vem do MoneyPrinter em tempo real.
- Se aparecer **"MoneyPrinterTurbo indisponível"**, o motor não subiu — veja os
  logs com `docker compose -f docker-compose.full.yml logs mpt-api`.

---

## Sem Docker? (alternativa)

Se preferir rodar sem Docker, suba o MoneyPrinter à mão numa aba do terminal:

```bash
cd MoneyPrinterTurbo-main
# instale as deps dele (uv ou pip) conforme o README dele, depois:
python3 main.py        # sobe a API na porta 8080
```

E no `.env` do StudyFlow adicione:
```
MPT_API_URL=http://localhost:8080
```
Aí rode o StudyFlow normal. O Módulo Criador vai achar o motor na 8080.

---

## Módulo Criador · Imagens (Fooocus-API) — thumbnail, carrossel, capa de curso

Gera imagens com IA (Stable Diffusion XL via Fooocus-API) direto na aba
**Imagens**, dentro do Módulo Criador. Três presets prontos: Thumbnail
(16:9), Carrossel Instagram (1:1, 4 imagens) e Capa de curso.

### Por que roda diferente do MoneyPrinter

O MoneyPrinter (geração de vídeo) sobe dentro do Docker, sem problema.
O Fooocus-API **não pode** — geração de imagem por Stable Diffusion
precisa de GPU, e o **Docker Desktop no Mac não repassa acesso à GPU**
(nem Nvidia, nem Apple Silicon/MPS) pros containers. Se você tentasse
rodar o Fooocus-API dentro do Docker, ele cairia pra CPU — a diferença
entre ~15-60 segundos e vários minutos por imagem.

**Por isso o Fooocus-API roda nativo no seu Mac** (fora do Docker,
usando a GPU de verdade via MPS), e o StudyFlow (que roda em Docker)
alcança ele pela rede.

### Passo 1 — Instalar e rodar o Fooocus-API

```bash
cd Fooocus-API-main
# siga o README do próprio projeto para criar o ambiente (conda ou venv)
# e instalar as dependências — a primeira vez baixa os modelos SDXL
# (vários GB, é normal demorar).

python3 main.py --host 0.0.0.0 --port 8888
```

O `--host 0.0.0.0` é importante — sem ele, o Fooocus-API só aceita
conexões de `127.0.0.1`, e os containers do StudyFlow (que chegam via
`host.docker.internal`) não conseguiriam alcançar.

Deixe essa janela do terminal aberta e rodando.

### Passo 2 — Confirma que está no ar

```bash
curl http://localhost:8888/ping
```

Deve responder `pong`.

### Passo 3 — Sobe o StudyFlow normalmente

```bash
docker compose -f docker-compose.full.yml up --build -d
```

O `docker-compose.full.yml` já está configurado com
`FOOOCUS_API_URL=http://host.docker.internal:8888` — não precisa mexer
em nada.

### Testando

Abre o StudyFlow, vai no **Módulo Criador**, clica na aba **Imagens**,
descreve o que quer (ex: "capa minimalista sobre inteligência
artificial, tons escuros e verde-limão"), escolhe o formato, e gera.

Se aparecer "Fooocus-API indisponível", confirma que o Passo 1 e 2
ainda estão de pé — é o mesmo tipo de aviso que o Módulo Criador já
mostra para o MoneyPrinter quando ele não está rodando.

---

## Atalho: subir tudo com um comando só

Em vez de abrir duas janelas de terminal (uma pro Fooocus-API, outra pro
Docker), use os scripts prontos:

```bash
bash start_studyflow.sh
```

Ele detecta sozinho se o Fooocus-API já está rodando; se não estiver,
descobre o ambiente Python certo (procura um `venv/` ou `.venv/` dentro
da pasta do Fooocus-API; se não achar nenhum, usa o `python3` comum do
Mac — o mesmo que você já usava rodando na mão), inicia em segundo
plano, espera ele ficar pronto (a 1ª vez demora mais, por causa do
carregamento dos modelos), e só depois sobe o `docker compose`.

Pra parar tudo (Docker + Fooocus-API):

```bash
bash stop_studyflow.sh
```

**Ajuste se precisar:** se a pasta do Fooocus-API não se chamar
`Fooocus-API-main` ou estiver em outro lugar, abra o
`start_studyflow.sh` e mude a variável `FOOOCUS_DIR` no topo do
arquivo — é a única coisa que pode precisar de ajuste manual.

---

## Correção necessária no Mac: PyTorch instalado errado

Se você já tentou rodar o Fooocus-API e o log mostrou algo como
`ERROR: No matching distribution found for torch==2.1.0` com uma URL
tipo `.../whl/cu121` — é um problema real do instalador automático do
Fooocus-API: ele sempre tenta instalar a build de **CUDA** (Nvidia),
mesmo em Mac. E pior: a checagem que ele usa
(`torch.cuda.is_available()`) **sempre retorna falso no Mac**, então
ele tentaria reinstalar a versão errada toda vez que você rodasse.

**Correção (uma vez só):**

```bash
cd Fooocus-API-main
pip3 install torch==2.1.0 torchvision==0.16.0
```

(sem `--extra-index-url` — o PyPI normal já tem a build certa pra Mac,
com suporte a MPS embutido)

Depois disso, o `start_studyflow.sh` já está ajustado pra rodar com
`--skip-pip`, que pula aquela checagem quebrada — sem isso, ele ia
tentar reinstalar o torch errado toda vez que você desse start.

---

## Geração lenta / timeout em Macs com pouca memória (8GB)

Se sua Mac tem 8GB de memória total (compartilhada entre sistema e
GPU), o próprio Fooocus detecta isso e usa um modo de atenção mais
lento pra caber na memória disponível (`sub quadratic attention`) — o
log chega a avisar isso na inicialização. Nesse caso, uma imagem pode
levar bem mais que 1 minuto — já ajustei o tempo de espera do
StudyFlow pra 10 minutos por chamada, então isso sozinho não deve mais
dar timeout.

Se ainda achar lento, o próprio Fooocus sugere uma flag que pode
ajudar — teste adicionando `--attention-split` ao rodar (ajuste o
`start_studyflow.sh` na linha do `main.py`, ou rode manualmente):

```bash
python3 main.py --host 0.0.0.0 --port 8888 --skip-pip --attention-split
```

Não há garantia de que fica mais rápido — depende de como o SDXL se
comporta especificamente na sua GPU — mas é a recomendação oficial do
próprio projeto pra hardware com memória limitada.

---

## Se a geração está MUITO lenta (minutos por passo, não por imagem)

Se o log mostrar algo como `178.62s/it` ou pior (segundos **por passo**,
não por imagem — uma imagem "Speed" tem 30 passos), o hardware está no
limite. Três ajustes que já vêm prontos neste projeto:

1. **`start_studyflow.sh` já roda o Fooocus-API com `caffeinate -i`** —
   impede o Mac de suspender o processo em segundo plano. Em teste
   real, vimos buracos de 10-15 minutos no log exatamente quando o Mac
   parecia estar dormindo no meio da geração.

2. **O preset padrão mudou de "Speed" (30 passos) para "Extreme Speed"
   (8 passos)** — quase 4x menos trabalho por imagem. A primeira
   geração depois dessa mudança baixa um arquivo extra
   (`sdxl_lcm_lora.safetensors`), bem menor que o checkpoint principal
   — é normal, só acontece uma vez.

3. **Se ainda estiver lento demais**, reinicie o Fooocus-API
   (`bash stop_studyflow.sh` e depois `bash start_studyflow.sh`) antes
   de tentar de novo — jobs presos de tentativas antigas ficam na fila
   e atrasam os pedidos novos.

**Sendo honesto:** em Macs com 8GB de memória total, SDXL (o modelo por
trás do Fooocus) é pesado. Mesmo com esses ajustes, uma imagem pode
continuar levando alguns minutos — é bem provável que seja o limite
real desse hardware para esse tipo de tarefa, não algo 100%
resolvível só por configuração.

---

## Atualização: preset trocado para "Lightning" (4 passos)

Depois de testar "Extreme Speed" (8 passos) e ainda achar lento, o
preset padrão do Módulo Criador · Imagens agora é **"Lightning"** — só
4 passos por imagem (era 30 no começo). O próprio Fooocus ajusta
sampler e CFG automaticamente pra esse modo, não precisa mexer em
nada além do preset.

**Primeira geração depois dessa troca**: baixa mais um arquivo
(`sdxl_lightning_4step_lora.safetensors`, pequeno) — normal, só uma
vez.

**Trade-off honesto**: com só 4 passos, a imagem pode sair um pouco
menos refinada/detalhada que com "Speed" ou "Extreme Speed" — é o
preço de ser tão mais rápido. Se a qualidade incomodar, dá pra testar
trocar `"Lightning"` por `"Hyper-SD"` em `tools/fooocus_client.py`
(mesmo custo de velocidade, técnica um pouco diferente, vale comparar
qual agrada mais no seu caso).

---

## Segundo motor: geração de imagem na nuvem (OpenAI)

Como o Fooocus local ficou lento demais no hardware atual (8GB
compartilhados), a aba **Imagens** agora tem um seletor de **Motor de
geração**:

- **☁️ Nuvem (OpenAI)** — padrão. Usa `gpt-image-1-mini` na API da
  OpenAI. Rápido (segundos, não minutos), sem depender da GPU local.
  Tem custo por imagem (bem baixo: ~$0,005 a $0,02 por imagem em
  qualidade "low", o padrão configurado). Usa a mesma `OPENAI_API_KEY`
  que o resto do StudyFlow já usa — nada novo pra configurar.

- **💻 Local (Fooocus)** — continua disponível, pra quando você tiver
  mais memória disponível ou quiser gerar sem custo por imagem. Segue
  os ajustes que já fizemos (Lightning, caffeinate).

Os dois motores geram no mesmo formato de saída (thumbnail, carrossel,
capa de curso) — só muda onde o processamento acontece.

**Ajustar o modelo/qualidade da nuvem** (opcional, no `.env`):
```
OPENAI_IMAGE_MODEL=gpt-image-1-mini   # mais barato; gpt-image-1.5 ou
                                       # gpt-image-2 = mais caro, melhor qualidade
OPENAI_IMAGE_QUALITY=low              # low/medium/high — mais alto = mais caro
```

---

## Publicar carrossel direto no Instagram

Depois de gerar as imagens (aba Imagens do Criador), aparece um botão
**"Publicar carrossel"** — publica direto na sua conta do Instagram.

### Por que precisa de duas peças (Cloudinary + Instagram)

O Instagram **não aceita** receber a imagem em bytes — ele exige uma
URL pública, e os servidores da Meta baixam a imagem sozinhos a partir
dela. Como o StudyFlow roda local, uso o **Cloudinary** como ponte:
sobe a imagem lá (fica pública, grátis), e uso essa URL pra publicar.

### Passo 1 — Cloudinary (armazenamento das imagens)

1. Crie uma conta grátis em https://cloudinary.com (sem cartão)
2. No painel, em **Account Details**, pegue: **Cloud name**, **API Key**, **API Secret**
3. Adicione no `.env`:
```
CLOUDINARY_CLOUD_NAME=seu-cloud-name
CLOUDINARY_API_KEY=sua-api-key
CLOUDINARY_API_SECRET=seu-api-secret
```

### Passo 2 — Conta do Instagram (Business/Creator + Página do Facebook)

1. No app do Instagram: Configurações → Conta → mude pra **Conta Profissional**
   (Business ou Creator — qualquer um dos dois serve)
2. Vincule essa conta a uma **Página do Facebook** (pode criar uma nova,
   não precisa ter seguidores nem nada — é só o vínculo técnico que a
   Meta exige)

### Passo 3 — App de desenvolvedor + token de acesso

1. Vá em https://developers.facebook.com → **Meus Apps** → **Criar App**
   → escolha o tipo **Negócios**
2. No painel do app, adicione o produto **Instagram Graph API**
3. Vá em **Ferramentas** → **Explorador da API Graph** (Graph API Explorer)
4. Selecione seu app, gere um **Token de Acesso do Usuário** com as
   permissões: `instagram_basic`, `instagram_content_publish`,
   `pages_read_engagement`
5. Esse token dura só 1 hora — troque por um de longa duração (60 dias)
   seguindo o guia da Meta ["Access Tokens"](https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived)
6. Pra achar o **ID da sua conta profissional do Instagram**: no Graph
   API Explorer, consulte `GET /me/accounts` (lista suas Páginas), pegue
   o ID da Página, depois `GET /<PAGE_ID>?fields=instagram_business_account`

Adicione no `.env`:
```
IG_BUSINESS_ACCOUNT_ID=o-id-numerico-da-conta
IG_ACCESS_TOKEN=o-token-de-longa-duracao
```

### Sobre o token expirar

O token de longa duração dura **60 dias**. Depois disso, "Publicar"
vai dar erro de autenticação — é só gerar um token novo (passo 3,
itens 3-5) e atualizar o `.env`. Não escrevi renovação automática
porque isso exigiria implementar login OAuth completo — desproporcional
pra uso de uma conta só.

### Rótulo de conteúdo por IA

Toda publicação feita por aqui já marca automaticamente
`is_ai_generated=true` — é o rótulo oficial que a própria Meta oferece
pra transparência de conteúdo gerado por IA, não algo que dá pra
desligar (nem deveria).
