# BarberStudio CRM — PRD

## Problem Statement (original, pt-BR)
CRM para uma barbearia com aba de agendamentos onde cada cliente agenda um horário com cada barbeiro disponível; horário marcado fica indisponível. Abas de planos e de clientes fidelizados. Depois: relatório por barbeiro, lembretes (e-mail + WhatsApp) e hospedagem na Vercel com isolamento multi-barbearia.

## User Choices
- Auth JWT (login por senha). Clientes se cadastram e agendam sozinhos.
- Cada barbeiro define seus horários; módulos: Agendamentos, Clientes, Barbeiros, Planos, Fidelizados, Dashboard, Relatórios.
- Sem pagamento online. Lembrete WhatsApp = link manual (wa.me).
- Deploy alvo: Vercel + MongoDB Atlas M0; e-mail por conta própria (Resend) via env.
- MULTI-BARBEARIA: isolamento total por barbearia; login = código da barbearia + e-mail + senha; e-mail único por barbearia (repetível entre barbearias).

## Architecture
- Backend FastAPI + MongoDB (motor), JWT Bearer (inclui shop_id). Todos os dados e queries escopados por `shop_id`.
- Frontend Vite + React 19 + Tailwind v4 + shadcn/ui; tema escuro âmbar.
- Coleções: shops (name, code único), users (admin+clients, shop_id, unique (shop_id,email)), barbers, services, appointments, plans, subscriptions — todas com shop_id.
- E-mail: email_service.py via Resend (RESEND_API_KEY/RESEND_FROM em env). Confirmação inline no agendamento; lembrete via cron.
- Deploy: vercel.json (build frontend em build/, /api -> api/index.py serverless, SPA fallback, cron diário), requirements.txt na raiz.

## Implemented
- MVP single-shop (agendamentos, barbeiros, clientes, fidelidade, planos, dashboard). [jun/2026]
- Relatório por barbeiro (receita/comissão/ticket). [jun/2026]
- Lembretes: e-mail confirmação + lembrete (cron) e botão WhatsApp manual. [jun/2026]
- Multi-barbearia com isolamento total + autorização cross-shop (404), login por código. [jun/2026]
- Adaptação Vercel serverless + Atlas + Resend próprio via env; DEPLOY.md. [jun/2026]
- Fase 2 Super Admin: painel /plataforma (login próprio), "Solicitar acesso" com CPF/CNPJ
  validado e único, status pending/active/suspended/rejected, gating de ponta a ponta,
  separação de papéis (CRM x plataforma -> 403 cruzado), histórico de decisões, rate limit,
  CPF mascarado em listagens, super admin idempotente. Testado 20/20 (iteration_3.json). [jun/2026]

## Backlog / Next
- P1 (Fase 2 do plano): Planos de assinatura da plataforma + cobrança recorrente (provedor a definir).
- P1: E-mails de aprovação/suspensão para o responsável da barbearia.
- P2: Relatórios da plataforma (crescimento, receita por barbearia, churn); comunicados.
- P2: Reaproveitamento de conexão Mongo p/ serverless; split de server.py em routers.
