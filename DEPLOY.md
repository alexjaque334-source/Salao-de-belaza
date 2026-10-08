# BarberStudio — Deploy na Vercel + MongoDB Atlas

App multi-barbearia: React (frontend, build em `build/`) + FastAPI (serverless em `/api`) +
MongoDB. Isolamento total de dados por barbearia.

## 1) MongoDB Atlas (M0 grátis)
1. Crie um cluster M0 em https://cloud.mongodb.com
2. Database Access → crie um usuário/senha de banco.
3. Network Access → libere `0.0.0.0/0` (ou os IPs da Vercel).
4. Connect → Drivers → copie a connection string, ex:
   `mongodb+srv://USUARIO:SENHA@cluster0.xxxx.mongodb.net/?retryWrites=true&w=majority`

## 2) Conta Resend (e-mail)
1. Crie conta em https://resend.com e verifique um domínio (ou use o remetente de teste).
2. API Keys → gere uma chave (`re_...`).
3. Defina o remetente, ex: `BarberStudio <contato@seudominio.com>`.

## 3) Vercel
1. Importe o repositório do GitHub em https://vercel.com (framework: Other; o `vercel.json` cuida do build).
2. Em Settings → Environment Variables, cadastre as variáveis abaixo (como Secrets).
3. Deploy. O site compila e a API sobe como função serverless. O Vercel Cron chamará
   `/api/cron/reminders` 1x/dia (configurado no `vercel.json`).

## Variáveis de ambiente (Vercel)
| Variável | Exemplo | Descrição |
|---|---|---|
| `MONGO_URL` | `mongodb+srv://...` | String do Atlas |
| `DB_NAME` | `barberstudio` | Nome do banco |
| `JWT_SECRET` | (64 hex aleatórios) | Assinatura dos tokens |
| `ADMIN_EMAIL` | `voce@email.com` | Dono da barbearia de exemplo |
| `ADMIN_PASSWORD` | (senha forte) | Senha do dono de exemplo |
| `DEMO_SHOP_CODE` | `DEMO01` | Código da barbearia de exemplo |
| `RESEND_API_KEY` | `re_...` | Chave da sua conta Resend |
| `RESEND_FROM` | `BarberStudio <contato@seudominio.com>` | Remetente verificado |
| `EMAIL_REPLY_TO` | `voce@email.com` | (opcional) Responder-para |
| `APP_URL` | `https://seuapp.vercel.app` | URL pública (links dos e-mails) |
| `WEBHOOK_CRON_SECRET` | (32+ chars aleatórios) | Protege `/api/cron/reminders` |
| `CRON_SECRET` | (= WEBHOOK_CRON_SECRET) | Usado pelo Vercel Cron no header Authorization |
| `CORS_ORIGINS` | `https://seuapp.vercel.app` | Origens permitidas |

No frontend (prefixo `REACT_APP_`): defina `REACT_APP_BACKEND_URL` como a própria URL do app
(ex: `https://seuapp.vercel.app`), pois a API fica no mesmo domínio sob `/api`.

## Observações
- Banco começa vazio; no primeiro acesso é criada a "Barbearia Exemplo" (código `DEMO01`) com
  o dono `ADMIN_EMAIL`. Crie novas barbearias pela tela "Criar minha barbearia".
- Login usa **código da barbearia + e-mail + senha** (o mesmo e-mail pode existir em barbearias
  diferentes).
- Confirmação de e-mail é enviada na hora do agendamento; o lembrete do dia seguinte é enviado
  pelo Vercel Cron (1x/dia; no plano Hobby o mínimo é diário).
- Plano Hobby da Vercel é para uso não comercial; para operação real use o Pro.

## Arquivos de deploy adicionados/alterados
- `vercel.json` — build do site + roteamento `/api` → função + SPA fallback + cron diário.
- `api/index.py` — entrypoint ASGI da Vercel (importa `backend/server.py`).
- `requirements.txt` (raiz) — dependências de runtime da função serverless.
- `backend/server.py` — isolamento multi-barbearia em todos os endpoints.
- `backend/email_service.py` — envio via sua conta Resend (variáveis de ambiente).
- `frontend/src/pages/Login.jsx` — telas de login/cadastro por código e "Criar barbearia".
- `frontend/src/components/Shell.jsx` — exibe a barbearia atual e o código.
