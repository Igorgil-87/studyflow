# Publicar cortes no YouTube (camada `publish/`)

Publica um corte direto no seu canal pela **YouTube Data API v3**
(`videos.insert`). O upload é uma **ação explícita** (botão "Publicar no
YouTube" em cada corte), nunca automática.

> **Importante sobre direitos autorais:** publicar cortes feitos a partir de
> vídeos de **terceiros** pode ser bloqueado/monetizado pelo Content ID. Publique
> conteúdo seu, ou com autorização. Para demonstração, o default é **privado**.

---

## Passo a passo do OAuth (uma vez)

### 1. Projeto + API no Google Cloud

1. Acesse <https://console.cloud.google.com> e crie um projeto.
2. Em **APIs e serviços → Biblioteca**, procure **YouTube Data API v3** e clique
   em **Ativar**.

### 2. Tela de consentimento OAuth

1. **APIs e serviços → Tela de permissão OAuth**.
2. Tipo de usuário: **Externo**. Preencha nome do app, e-mail de suporte e
   e-mail do desenvolvedor.
3. Em **Escopos**, adicione `.../auth/youtube.upload`.
4. Em **Usuários de teste**, adicione o seu próprio e-mail do Google (enquanto o
   app estiver em modo de teste, só esses usuários conseguem autorizar).

### 3. Credenciais (client_secret.json)

1. **APIs e serviços → Credenciais → Criar credenciais → ID do cliente OAuth**.
2. Tipo de aplicativo: **App para computador** (Desktop app).
3. Baixe o JSON e salve como **`client_secret.json`** na raiz do projeto
   (ou aponte `YOUTUBE_CLIENT_SECRETS` para o caminho dele no `.env`).

### 4. Autorizar (abre o navegador)

```bash
python -m publish.auth
```

O navegador abre, você faz login e autoriza. O token é salvo em
`youtube_token.json`. Pronto — o app renova esse token sozinho daqui pra frente.

---

## Publicar

1. Rode o app e gere cortes no módulo **Youtuber**.
2. Em cada corte aparece **▶ Publicar no YouTube**. Clique, confirme, e o vídeo
   sobe com título, descrição (hook + #Shorts + hashtags) e tags já preenchidos.
3. O link do vídeo aparece embaixo do botão.

Privacidade pelo `.env` (`YOUTUBE_PRIVACY`): `private` (default) · `unlisted` ·
`public`.

---

## Sobre publicar como PÚBLICO (verificação do Google)

Enquanto o app OAuth está em **modo de teste**, o YouTube força o upload para
**privado**, mesmo que você peça `public`. Para publicar de fato como público:

1. Na **Tela de permissão OAuth**, clique em **Publicar app** (sai do modo de
   teste).
2. Como o escopo `youtube.upload` é sensível, o Google pede **verificação do
   app** (vídeo demonstrando o uso, política de privacidade, etc.). Até a
   verificação concluir, mantenha `unlisted` ou `private`.

Para a apresentação, `unlisted` é o melhor custo-benefício: o vídeo sobe de
verdade e você compartilha o link, sem depender da verificação.

---

## Segurança

`client_secret.json` e `youtube_token.json` são **segredos** e já estão no
`.gitignore`. Nunca os versione nem os compartilhe.

---

## O que está testado

`_publish_test.py` valida, sem rede nem credencial: construção dos metadados
(título truncado em 100, `#Shorts`, tags limpas, privacidade), o upload com um
serviço falso injetado, e o erro claro quando o arquivo não existe.

```bash
python _publish_test.py
```

O fluxo OAuth real e o upload de verdade você roda na sua máquina, com a sua
conta — o código não autentica nem publica por você.

---

## Limite honesto / próximo passo

O token é de um único canal (o seu). Para multiusuário, o passo seguinte é
guardar um token por usuário (no store) em vez de um arquivo único — a interface
em `publish/auth.py` isola isso.
