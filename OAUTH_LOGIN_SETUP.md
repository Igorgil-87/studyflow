# Login profissional — configuração

O sistema de login tem: **e-mail/senha** (funciona já, guardado em banco com
senha em hash) e **login social** Google / LinkedIn / Instagram (cada um precisa
de um app OAuth seu). Os botões sociais aparecem sempre; cada um só *funciona*
depois que você preencher as credenciais no `.env`.

Defina sempre um `SECRET_KEY` forte no `.env` (a sessão depende dele).

---

## E-mail + senha (já funciona, zero config)

Abra `/login` → "Criar agora" → cadastre. A senha é salva com hash PBKDF2
(Werkzeug), nunca em texto. O usuário fica em `output/users.db`. O admin antigo
do `.env` (`APP_USER`/`APP_PASS`) continua valendo como atalho.

---

## Google (o mais fácil — comece por ele)

1. https://console.cloud.google.com → crie um projeto.
2. **APIs e serviços → Tela de consentimento OAuth** → External → preencha o básico.
3. **Credenciais → Criar credenciais → ID do cliente OAuth → Aplicativo da Web**.
4. Em **URIs de redirecionamento autorizados**, adicione exatamente:
   `http://localhost:5000/auth/google/callback`
   (e a versão de produção, com seu domínio, quando publicar).
5. Copie o Client ID e o Client Secret para o `.env`:
   ```properties
   GOOGLE_OAUTH_CLIENT_ID=...
   GOOGLE_OAUTH_CLIENT_SECRET=...
   ```
6. Reinicie o app. O botão "Continuar com Google" passa a funcionar.

## LinkedIn (médio)

1. https://www.linkedin.com/developers → Create app (precisa de uma Company Page).
2. Na aba **Products**, habilite **"Sign In with LinkedIn using OpenID Connect"**.
3. Na aba **Auth**, em "Authorized redirect URLs", adicione:
   `http://localhost:5000/auth/linkedin/callback`
4. Copie Client ID / Secret:
   ```properties
   LINKEDIN_CLIENT_ID=...
   LINKEDIN_CLIENT_SECRET=...
   ```
   O escopo usado é `openid profile email` (traz nome e e-mail).

## Instagram (o mais chato — honestidade total)

O login com Instagram é **bem restrito**. Pontos a saber antes de investir tempo:
- Vai pelo **Meta for Developers** (https://developers.facebook.com), produto
  **Instagram Basic Display** (ou Instagram API com Login).
- Exige conta de teste e, para uso público, **revisão do app pela Meta**.
- **Não retorna e-mail** — só `id` e `username`. Por isso, no nosso banco, o
  usuário do Instagram entra com o username como nome e sem e-mail (tratado).
- Redirect URI: `http://localhost:5000/auth/instagram/callback`
   ```properties
   INSTAGRAM_CLIENT_ID=...
   INSTAGRAM_CLIENT_SECRET=...
   ```

Recomendação honesta: deixe Google e LinkedIn prontos para a apresentação
(funcionam bem) e trate o Instagram como "configurável" — o botão está lá e o
código funciona, mas a liberação da Meta pode levar dias. Se não configurar, o
botão mostra uma mensagem amigável de "ainda não configurado".

---

## Como o código se comporta

- `auth/users.py` — banco de usuários (e-mail/senha + OAuth) com hash de senha.
- `auth/oauth.py` — registra **só** os provedores com credenciais no `.env`
  (via Authlib). Sem credenciais → botão informa que não está configurado.
- Rotas: `/login`, `/signup`, `/auth/<provider>`, `/auth/<provider>/callback`,
  `/logout`.
- O vídeo de fundo do login vai em `static/video/login-bg.mp4` (se faltar, um
  fundo animado em gradiente aparece no lugar — nada quebra).

## O que está testado

`_auth_test.py` cobre, com um banco temporário: cadastro local, normalização de
e-mail, senha em hash, login certo/errado, e-mail duplicado barrado, validações,
e o upsert de OAuth (idempotente, vínculo por e-mail, Instagram sem e-mail).

> Transparência: os fluxos OAuth de verdade (redirect → provedor → callback) eu
> não consigo exercitar aqui, pois dependem de credenciais e de navegador. A
> lógica de usuários está coberta por testes; o ida-e-volta com cada provedor
> você valida na sua máquina após criar os apps acima.
