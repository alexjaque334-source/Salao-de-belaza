# BarberStudio CRM — PRD

## Problem Statement (original, pt-BR)
CRM para uma barbearia com aba de agendamentos onde cada cliente agenda um horário com cada barbeiro disponível; horário marcado fica indisponível. Abas de planos e de clientes fidelizados.

## User Choices
- Auth: JWT (login por senha). Clientes também se cadastram e agendam sozinhos.
- Cada barbeiro define seus próprios horários de trabalho.
- Módulos: Agendamentos, Clientes, Barbeiros, Planos, Clientes Fidelizados, Dashboard.
- Sem pagamento online (apenas cadastro de planos e assinantes).

## Architecture
- Backend: FastAPI + MongoDB (motor). JWT Bearer (PyJWT + bcrypt). Routes under /api.
- Frontend: Vite + React 19 + Tailwind v4 + shadcn/ui. Dark amber "luxury barbershop" theme.
- Collections: users (admin+clients, loyalty points/tier), barbers (working_hours per weekday), services, appointments, plans, subscriptions.

## Personas
- Admin/Staff (dono): gerencia agenda, barbeiros, clientes, fidelidade, planos, dashboard.
- Cliente: cadastra-se, agenda horário, vê seus agendamentos, assina planos, acompanha fidelidade.

## Implemented (2026-06)
- JWT auth (admin seed alexjaque334@gmail.com/admin123 + client self-register).
- Agendamentos: wizard barbeiro→serviço→data→slot; slot booked fica indisponível (409 em duplicado); availability gerada a partir dos horários do barbeiro.
- Barbeiros CRUD com horário de trabalho semanal, foto, especialidade, contador de cortes.
- Clientes CRM (busca, tier, pontos, visitas, plano).
- Clientes Fidelizados: pontos (10/atendimento concluído), tiers Bronze/Silver/Gold/VIP Black, resgate 100pts = corte grátis.
- Planos: CRUD + assinantes ativos; cliente assina sozinho.
- Dashboard: KPIs, receita 7 dias (recharts), top barbeiro, próximos atendimentos.
- Tested end-to-end (iteration_1.json): 100% core flows.

## Backlog / Next
- P1: Visão de calendário/timeline por barbeiro na aba Agendamentos.
- P1: Notificações/lembretes (email via Resend) de agendamento.
- P2: Relatórios por barbeiro e comissões.
- P2: Pagamento online dos planos (Stripe) se desejado.
