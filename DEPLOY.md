# Deploy do StudyFlow na nuvem

Este guia parte do princípio de que você vai testar o **Oracle Cloud Free**
primeiro (é genuinamente grátis pra sempre) e, se não der certo, migra pro
**Hetzner** (pago, mas confiável — passo B no final).

Os arquivos `docker-compose.prod.yml` e `.env.production.example` já foram
preparados — este guia é só o que fazer com eles.

---

## Parte A — Oracle Cloud Free (tentativa #1, $0)

### A.1 — Criar a conta e a instância

1. Crie uma conta em https://cloud.oracle.com (pede cartão de crédito pra
   verificação, mas o tier "Always Free" nunca cobra nada — só serve pra
   provar que você é uma pessoa real).
2. No console, vá em **Compute → Instances → Create Instance**.
3. Escolha a imagem: **Canonical Ubuntu 24.04** (ou a mais recente LTS
   disponível na lista "Always Free Eligible").
4. Em **Shape**, clique em "Change Shape" → aba **Ampere** → escolha
   `VM.Standard.A1.Flex` → ajusta pra **2 OCPU / 12 GB RAM** (o máximo do
   tier grátis hoje).
5. **Se der erro de "Out of capacity"**: é um problema conhecido do Oracle
   Free — a região que você escolheu está sem servidor ARM disponível no
   momento. Tenta de novo em outro horário, ou troca de região (na criação
   da conta você escolhe uma "home region" — depois de criada, pode ser
   difícil trocar, então se travar muito, considera recriar a conta numa
   região diferente, tipo `us-ashburn-1` ou `sa-saopaulo-1`).
6. Em **Networking**, deixe criar uma VCN nova (padrão). Marque "Assign a
   public IPv4 address".
7. Em **Add SSH keys**, escolha "Generate a key pair for me" e **baixe a
   chave privada** (arquivo `.key` ou `.pem`) — é a única vez que ela
   aparece.
8. Clique em **Create**. Espera uns 2-5 minutos até o status virar
   "Running". Anota o **IP público** que aparece.

### A.2 — Abrir as portas (Security List)

Por padrão, o Oracle só libera a porta 22 (SSH). Precisa abrir as portas
do StudyFlow:

1. Vá em **Networking → Virtual Cloud Networks** → clique na VCN criada.
2. Clique na **Security List** padrão (Default Security List).
3. **Add Ingress Rules** — adiciona uma regra pra cada porta:
   - `5001` (StudyFlow web)
   - `5678` (n8n, só se for usar automação)
4. Em cada regra: Source CIDR = `0.0.0.0/0`, IP Protocol = TCP, Destination
   Port Range = a porta (ex: `5001`).

### A.3 — Conectar e preparar o servidor

No seu Mac, dá permissão de leitura só pro seu usuário na chave baixada
(o SSH recusa se estiver muito aberta):

```bash
chmod 600 ~/Downloads/sua-chave.key
ssh -i ~/Downloads/sua-chave.key ubuntu@SEU_IP_PUBLICO
```

Já conectado no servidor, instala o Docker:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# desconecta e conecta de novo pra o grupo "docker" valer
exit
```

Conecta de novo (mesmo comando `ssh` de antes), e confirma:

```bash
docker --version
docker compose version
```

### A.4 — Subir o projeto

Ainda sem domínio, então vamos direto por IP.

**No seu Mac**, compacte o projeto (sem os arquivos de segredo — eles vão
separados, no passo seguinte):

```bash
cd /caminho/pra/pasta/que/contem/youtube-study-agent
zip -r studyflow.zip youtube-study-agent -x "*.git*" -x "*__pycache__*" -x "*.env"
scp -i ~/Downloads/sua-chave.key studyflow.zip ubuntu@SEU_IP_PUBLICO:~
```

**No servidor**, descompacta:

```bash
unzip studyflow.zip
cd youtube-study-agent
```

### A.5 — Configurar o `.env` de produção

```bash
cp .env.production.example .env
nano .env
```

Preencha **todos os valores marcados** — procure por `TROQUE_ISSO` e
`GERE_UMA_CHAVE` no arquivo (são 5 no total, não é só 1 ou 2):

- `APP_PASS` — senha de login do StudyFlow
- `SECRET_KEY` — gere com `python3 -c "import secrets;print(secrets.token_hex(32))"`
- `DATABASE_URL` (a senha embutida na URL, depois de `studyflow:`) e
  `POSTGRES_PASSWORD` — **essas duas precisam ser a MESMA senha**, senão
  o Postgres não sobe (a senha do usuário tem que bater com a que o
  `DATABASE_URL` tenta usar pra conectar)
- `N8N_PASSWORD` — senha de acesso ao painel do n8n

Pode gerar uma senha forte rápido com `openssl rand -hex 16`. Preenche
também `OPENAI_API_KEY` e `ANTHROPIC_API_KEY` com suas chaves reais.
Salva com `Ctrl+O`, `Enter`, `Ctrl+X`.

### A.6 — O token do YouTube (o passo que precisa da sua máquina local)

O login do YouTube abre um navegador — isso não existe num servidor sem
tela. Solução: gera o token **no seu Mac** (onde já funciona hoje) e
copia pro servidor.

**No seu Mac**, dentro da pasta do projeto:

```bash
python3 -m publish.auth
```

Isso vai gerar/atualizar o `youtube_token.json` local. Copia ele (e o
`client_secret.json`) pro servidor:

```bash
scp -i ~/Downloads/sua-chave.key youtube_token.json client_secret.json ubuntu@SEU_IP_PUBLICO:~/youtube-study-agent/
```

**Os vídeos de identidade também** (`login-bg.mp4` e `fechamento.mp4`)
— eles ficam de propósito **fora do git** (são asset pessoal, não
código; o `login-bg.mp4` sozinho tem ~17MB, pesado demais pro
repositório). Copia manualmente, uma vez:

```bash
scp -i ~/Downloads/sua-chave.key static/video/login-bg.mp4 static/video/fechamento.mp4 ubuntu@SEU_IP_PUBLICO:~/youtube-study-agent/static/video/
```

### A.7 — Subir tudo

**No servidor**:

```bash
cd ~/youtube-study-agent
docker compose -f docker-compose.prod.yml up -d --build
```

A primeira vez demora (baixa as imagens, instala o Whisper etc — pode
levar 10-15 minutos numa máquina ARM). Acompanha com:

```bash
docker compose -f docker-compose.prod.yml logs -f web
```

Quando aparecer algo tipo `Running on http://0.0.0.0:5000`, testa no
navegador:

```
http://SEU_IP_PUBLICO:5001
```

### A.8 — Checklist final

- [ ] Login funciona (usuário/senha do `.env`)
- [ ] `/obs` carrega (Observabilidade)
- [ ] Gera um Short de teste com um vídeo curto
- [ ] `docker compose -f docker-compose.prod.yml ps` — todos os serviços
      "healthy" ou "running" (o `mpt-api` nem aparece na lista — ele foi
      removido do compose de produção de propósito, é opcional; o
      Módulo Criador de vídeo fica indisponível até você configurar
      isso depois, o resto do app funciona normal)

---

## Parte B — Se o Oracle não der certo: Hetzner (pago, ~€7-8/mês)

1. Cria conta em https://www.hetzner.com/cloud
2. Cria um servidor: imagem **Ubuntu 24.04**, tipo **CX33** (4 vCPU / 8GB —
   esse era chamado "CX32" antes da Hetzner reorganizar a linha em 2026;
   mesma especificação, ficou mais barato)
3. Adiciona sua chave SSH na criação (ou usa senha, se preferir)
4. O resto é **idêntico aos passos A.3 até A.8** — só troca o IP pelo que
   o Hetzner te dar. Hetzner já libera todas as portas por padrão (não
   precisa da etapa A.2 de Security List) — mas se quiser, pode
   restringir depois no firewall deles.

---

## Depois que tiver um domínio (mais pra frente)

Quando comprar um domínio, aponta o DNS (registro tipo **A**) pro IP do
servidor, e me chama de volta que a gente configura HTTPS de verdade
(certificado grátis via Let's Encrypt/Certbot, redirecionamento
automático de HTTP pra HTTPS). Sem isso, o site funciona, só fica sem o
cadeado verde — para uso pessoal/teste não é bloqueante, mas não é o
ideal pra produção de verdade.

---

## CI/CD — testes e deploy automáticos

Isso é opcional (o deploy manual das partes A/B acima sempre funciona
sozinho), mas facilita muito depois da primeira vez: toda mudança que
você mandar passa pelos testes automaticamente, e o deploy vira 1 clique
em vez de repetir os passos A.4-A.7 na mão.

### O que já está pronto no projeto

- `.github/workflows/ci.yml` — roda a suíte de testes + auditoria de
  segurança em todo push/PR pro GitHub.
- `.github/workflows/cd-hetzner.yml` e `cd-oracle.yml` — deploy manual
  (você aperta um botão no GitHub, não dispara sozinho a cada push) —
  só roda se o CI passar primeiro.

### O que você precisa fazer (só uma vez)

**1. Criar o repositório no GitHub** (se ainda não tem):
   - Vai em https://github.com/new, cria um repositório (pode ser
     privado — CI/CD funciona igual, com minutos grátis suficientes
     pra um projeto solo).
   - No seu Mac, dentro da pasta do projeto:
     ```bash
     git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git
     git add .
     git commit -m "Primeiro commit"
     git push -u origin main
     ```

**2. No servidor (Hetzner e/ou Oracle), trocar de zip pra `git clone`** —
   o deploy automático usa `git pull`, que só funciona numa pasta que
   veio de um `git clone` (não de um zip descompactado). Se você já
   subiu pela Parte A/B com zip, é só apagar a pasta e clonar de novo:
   ```bash
   cd ~
   rm -rf youtube-study-agent   # se já existir da tentativa com zip
   git clone https://github.com/SEU_USUARIO/SEU_REPO.git youtube-study-agent
   cd youtube-study-agent
   # os passos A.5 (.env) e A.6 (token do YouTube) continuam iguais —
   # esses arquivos NUNCA vão pro GitHub (estão no .gitignore), então
   # precisam ser recriados/recopiados aqui manualmente, sempre.
   ```

**3. Gerar uma chave SSH SÓ pra esse deploy** (não reaproveita a sua
   pessoal), no seu Mac:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/studyflow_deploy -N ""
   # copia a chave PÚBLICA pro servidor autorizar:
   ssh-copy-id -i ~/.ssh/studyflow_deploy.pub ubuntu@SEU_IP_DO_SERVIDOR
   ```

**4. Cadastrar os segredos no GitHub** — no repositório, vá em
   **Settings → Secrets and variables → Actions → New repository
   secret**. Cadastre (pro Hetzner, e repita com prefixo `ORACLE_` se
   for usar o Oracle também):
   - `HETZNER_HOST` — o IP público do servidor
   - `HETZNER_USER` — `ubuntu` (ou o usuário que você usa no SSH)
   - `HETZNER_SSH_KEY` — o conteúdo da chave PRIVADA gerada no passo 3
     (`cat ~/.ssh/studyflow_deploy` — copia tudo, incluindo as linhas
     `-----BEGIN...-----` e `-----END...-----`)

### Usando depois de configurado

- **Testes automáticos**: todo `git push` já roda o CI sozinho — vê o
  resultado na aba **Actions** do repositório no GitHub.
- **Deploy**: aba **Actions** → escolhe `Deploy Hetzner` (ou `Deploy
  Oracle`) → **Run workflow** → espera terminar (uns 5-15 min,
  dependendo da máquina) → confere no navegador que atualizou.

### Por que o deploy é manual, não automático a cada push

De propósito — um push que ainda está sendo testado não deveria
derrubar/reiniciar o servidor de produção sozinho, ainda mais no meio
de um job de vídeo em andamento. Se um dia quiser deploy automático
mesmo assim, troca `workflow_dispatch:` por
`push: {branches: [main]}` no início dos arquivos `cd-*.yml` — mas
recomendo manual pra esse estágio do projeto.

## Problemas comuns

**"Out of capacity" no Oracle** — tenta outro horário ou outra região
(ver A.1, passo 5).

**Container fica reiniciando (`docker compose ps` mostra "Restarting")**
— olha o log: `docker compose -f docker-compose.prod.yml logs <nome_do_servico>`.
Na maioria das vezes é `.env` com alguma senha/chave faltando.

**"connection refused" tentando acessar pelo navegador** — confere se a
porta está liberada na Security List (Oracle) ou firewall (Hetzner) —
passo A.2.

**Servidor MUITO lento** — o Oracle Free (2 OCPU/12GB compartilhado, ARM)
é bem mais fraco que seu Mac. Vídeos longos podem demorar mais do que
você está acostumado localmente. Se ficar inviável, é hora de migrar pro
Hetzner (Parte B).
