# Fase 2 — Administração da Plataforma (Super Admin)

Painel de proprietário da plataforma para controlar quais barbearias podem usar o CRM, com
cadastro por aprovação e gestão de status (pendente, ativa, suspensa, rejeitada).
Mantém intacto todo o CRM atual e o isolamento de dados entre barbearias.

## Para quem é
- Para você, dono da plataforma (Super Admin): aprova, rejeita, suspende e reativa barbearias,
  e acompanha quantas estão ativas, pendentes e suspensas.
- Para o responsável pela barbearia: solicita acesso e só entra no CRM após aprovação.
- Para o cliente final: continua se cadastrando pelo código da barbearia, sem aprovação, e
  apenas em barbearias ativas.

## Funcionalidades e experiência

### 1. Solicitação de acesso da barbearia (substitui "Criar minha barbearia")
- O botão passa a ser "Solicitar acesso para minha barbearia".
- Formulário pede: nome da barbearia, nome do responsável, CPF ou CNPJ, telefone, e-mail e senha.
- CPF/CNPJ é validado (formato e dígitos verificadores) e precisa ser único entre as barbearias.
- A barbearia nasce com status PENDENTE. O responsável vê uma tela "Cadastro em análise —
  aguardando aprovação" e não acessa nenhuma função administrativa do CRM enquanto não for aprovado.
- Ao solicitar, o sistema não entrega o código da barbearia ainda; o código passa a valer
  (para cadastro de clientes) somente quando a barbearia for aprovada/ativada.

### 2. Painel exclusivo do Super Admin (separado do CRM)
- Acesso por endereço próprio e oculto (ex.: `/plataforma`), com login independente do CRM
  (não usa código de barbearia).
- Lista todas as barbearias com status, responsável, contato, CPF/CNPJ (protegido/mascarado na
  listagem) e data de cadastro; com filtros por status e busca.
- Fila de solicitações pendentes com ações Aprovar e Rejeitar.
- Ações de Suspender e Reativar barbearias já existentes.
- Ao rejeitar ou suspender, há um campo de motivo (opcional) guardado no histórico, junto de
  quem fez a ação e quando.
- Indicadores no topo: total de barbearias ativas, pendentes, suspensas e rejeitadas.
- Espaço preparado para, no futuro, gerir planos de assinatura e pagamentos (apenas a área;
  a cobrança em si fica para fase posterior).

### 3. Efeito do status no acesso
- PENDENTE ou REJEITADA: responsável vê a tela de aviso; CRM bloqueado. Clientes não conseguem
  se cadastrar nem agendar.
- ATIVA: CRM liberado para o responsável e sua equipe; clientes podem se cadastrar e agendar.
- SUSPENSA: responsável vê aviso de suspensão; CRM bloqueado; clientes bloqueados. Os dados são
  preservados e voltam ao normal na reativação.

### 4. Segurança (reforços desta fase)
- Papel de Super Admin é separado dos administradores de barbearia e não pertence a nenhuma
  barbearia.
- A conta de Super Admin tem senha armazenada com hash seguro; não é recriada nem tem a senha
  redefinida a cada inicialização (criada apenas se ainda não existir).
- Em produção, nenhuma barbearia é ativada automaticamente por ausência de status: cadastros sem
  status explícito são tratados como pendentes e exigem aprovação do Super Admin. A DEMO01 segue
  ativa somente no ambiente de testes.
- Somente o Super Admin aprova, rejeita, suspende ou reativa; todas as rotas administrativas são
  protegidas por autorização no backend (não apenas escondidas na interface).
- Ninguém pode se autopromover a Super Admin nem a admin de outra barbearia; mudança de papel
  por conta própria é bloqueada.
- Barbearias pendentes, rejeitadas ou suspensas não acessam recursos protegidos, mesmo chamando
  a API diretamente.
- Limitação de tentativas de login e de solicitações de cadastro (proteção contra abuso/força bruta).
- Registro de auditoria das decisões (aprovou/rejeitou/suspendeu/reativou): quem, quando e motivo.
- Dados pessoais (CPF/CNPJ, telefone, e-mail) protegidos: nunca retornados em telas públicas,
  mascarados em listagens e acessíveis por completo apenas ao Super Admin quando necessário.
- Testes automatizados cobrindo: hash e não-redefinição da senha do Super Admin a cada start;
  tratamento de barbearias sem status como pendentes em produção; proteção de todas as rotas
  administrativas; e bloqueio de autopromoção de papel.

### 5. Cadastro de clientes (mantido)
- Continua separado do cadastro de barbearias e sem aprovação.
- Cliente informa o código da barbearia para se vincular; só consegue em barbearia ativa.
- Isolamento de dados entre barbearias preservado.

### 6. Preservação do sistema
- Nada do que existe é removido: agendamentos, clientes, barbeiros, planos, fidelidade,
  relatórios, comissões, WhatsApp e e-mails seguem funcionando.
- Compatibilidade com MongoDB Atlas e Vercel mantida.

## Fluxo de uso

### Responsável pela barbearia
1. Acessa a tela de entrada → "Solicitar acesso para minha barbearia".
2. Preenche os dados (incl. CPF/CNPJ) e envia → recebe a mensagem de "aguardando aprovação".
3. Enquanto PENDENTE, ao logar vê apenas o aviso; sem CRM.
4. Após aprovação, ao logar entra no CRM normalmente e passa a usar o código para seus clientes.

### Super Admin (você)
1. Acessa `/plataforma` e faz login próprio.
2. Vê os indicadores e a fila de pendentes.
3. Aprova (barbearia vira ativa e o código passa a valer) ou rejeita (com motivo opcional).
4. Suspende ou reativa barbearias já existentes quando necessário; tudo fica registrado no histórico.

### Cliente
1. Cadastra-se informando o código de uma barbearia ativa.
2. Agenda, acumula fidelidade e recebe e-mails/WhatsApp — sem mudança em relação a hoje.

## Sensação de uso (UI/UX)
- Mesmo tema escuro com dourado do CRM atual.
- Tela de solicitação mais completa (com CPF/CNPJ) e a tela de "aguardando aprovação" com visual
  claro e tranquilizador.
- Painel do Super Admin com identidade própria (cabeçalho "Administração da Plataforma"),
  cartões de indicadores no topo, tabela de barbearias com selos de status coloridos
  (pendente/ativa/suspensa/rejeitada) e ações diretas por linha, além de um painel lateral com
  o histórico de decisões.

## Fases de implementação

### Fase 1 — MVP (feito agora)
- Papel de Super Admin separado, criado no primeiro start a partir de variáveis de ambiente
  (e-mail/senha do dono da plataforma), com rota/login próprios em `/plataforma`.
- Cadastro de barbearia convertido em "Solicitar acesso", com CPF/CNPJ validado e único, e
  status inicial PENDENTE; tela de "aguardando aprovação" e bloqueio do CRM fora do status ativo.
- Painel do Super Admin: listagem com filtros/busca, fila de pendentes, aprovar/rejeitar,
  suspender/reativar, indicadores por status e histórico de decisões (quem/quando/motivo).
- Regras de acesso por status aplicadas de ponta a ponta (barbearia e clientes), com todas as
  operações sensíveis protegidas no backend e impossibilidade de autopromoção de papel.
- Senha do Super Admin com hash seguro e idempotente no start (não recria nem redefine a cada
  inicialização); em produção, barbearias sem status são tratadas como pendentes.
- Limitação de tentativas de login e de solicitações de cadastro.
- Proteção de dados pessoais (mascarados em listagens; completos só para o Super Admin).
- Preservação integral do CRM atual e do isolamento multi-barbearia.
- Testes automatizados de permissões, aprovação, rejeição, suspensão e reativação.

### Fase 2 — Planos de assinatura e cobrança
- Definição de planos da plataforma (valores, ciclos) e vínculo de cada barbearia a um plano.
- Cobrança recorrente e controle de inadimplência (suspensão automática por falta de pagamento),
  com um provedor de pagamento a ser escolhido.
- Avisos por e-mail de aprovação, vencimento e suspensão.

### Fase 3 — Operação e escala
- Relatórios da plataforma (crescimento, receita por barbearia, churn).
- Comunicados do Super Admin para as barbearias e trilha de auditoria ampliada.
- Autoatendimento de reativação/upgrade pela própria barbearia.

## Suposições
- O acesso do Super Admin é por rota separada e oculta (`/plataforma`) com login próprio; o
  Super Admin não pertence a nenhuma barbearia e não usa código.
- A conta de Super Admin é criada no primeiro start via variáveis de ambiente; não há
  autocadastro de Super Admin pela interface.
- Barbearia PENDENTE (ou rejeitada/suspensa): o responsável vê apenas a tela de aviso, sem
  acesso ao CRM nem mesmo em leitura.
- CPF/CNPJ é validado (formato e dígitos) e deve ser único entre barbearias; fica visível por
  completo apenas ao Super Admin e mascarado nas listagens.
- Rejeitar/suspender aceita um motivo opcional, guardado no histórico com autor e data/hora.
- O código da barbearia só passa a permitir cadastro de clientes quando a barbearia está ativa;
  em qualquer outro status, clientes não se cadastram nem agendam.
- A barbearia de exemplo atual (DEMO01) permanece ativa apenas no ambiente de testes.
- Em produção, nenhuma barbearia recebe status ATIVA automaticamente por falta de status
  definido: cadastros sem status são tratados como PENDENTE e exigem revisão/aprovação do
  Super Admin. (No ambiente de testes, apenas a DEMO01 é tratada como ativa para não interromper
  os testes existentes.)
- Cobrança/pagamento de assinatura não entra agora (fica para a Fase 2); nesta fase existe apenas
  o espaço preparado no painel.
- Limites de tentativa (login/cadastro) usam valores padrão razoáveis definidos por nós, sem
  necessidade de configuração pelo usuário.
