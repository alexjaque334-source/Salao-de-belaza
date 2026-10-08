# Hospedagem do BarberStudio na Vercel + Atlas + Multi-barbearia

Publicar o BarberStudio na Vercel usando o código do GitHub, com banco no MongoDB Atlas M0
(novo e vazio), e-mail por conta própria (Resend) e isolamento completo entre barbearias.

## Para quem é
Para o dono do projeto, que quer o app no ar na Vercel e, agora, poder operar/testar
**várias barbearias no mesmo sistema** com total separação de dados entre elas.

## Respostas às perguntas iniciais (mantidas)
- O MongoDB do preview é interno e **não** é acessível pela Vercel; **não** há URL pública dele.
- O caminho correto é um **MongoDB Atlas M0 gratuito**, que fornece string de conexão pública e segura.

## Diagnóstico de isolamento (estado atual)
Hoje o sistema é de **barbearia única**: todas as listagens (barbeiros, serviços, clientes,
agendamentos, planos, dashboard e relatórios) retornam todos os registros de forma global, e
qualquer conta admin enxerga e gerencia tudo. **Não há separação por barbearia.** Será criado
o conceito de "Barbearia" e todos os dados e consultas passarão a ser separados por barbearia.

## O que será construído (experiência)
### App no ar na Vercel
- Site React publicado em um endereço da Vercel; API FastAPI no mesmo domínio, sob `/api`,
  como função serverless.
- Banco no Atlas M0 (começa vazio; cadastro inicial recriado para a barbearia de exemplo).

### Isolamento multi-barbearia (novo)
- Cada **barbearia** tem nome e um **código/identificador único**.
- Cada barbearia tem seu(s) **admin(s)/dono** e seus próprios barbeiros, serviços, clientes,
  agendamentos, planos, assinaturas, fidelidade e relatórios — nada é compartilhado.
- Um admin só vê e gerencia a **própria** barbearia. Dashboard, relatórios e comissões são
  calculados apenas sobre os dados da barbearia dele.
- **Criar barbearia**: na tela de acesso haverá a opção "Criar minha barbearia", que cria a
  barbearia e a primeira conta de dono.
- **Cadastro de cliente**: o cliente informa em qual barbearia quer se cadastrar (por código
  da barbearia) e passa a pertencer a ela; só vê e agenda naquela barbearia.
- **E-mail repetível entre barbearias**: o mesmo e-mail pode existir em barbearias diferentes,
  com cadastros e dados totalmente separados. O e-mail é único **dentro** de cada barbearia,
  não globalmente.
- A verificação de horário indisponível e a disponibilidade dos barbeiros passam a considerar
  a barbearia, evitando qualquer cruzamento de agenda entre barbearias diferentes.

### Login que identifica a barbearia (ajuste aprovado)
- Como o e-mail pode se repetir, o login passa a usar **código da barbearia + e-mail + senha**.
  O cliente/admin informa a barbearia no login (pelo código), e o sistema autentica dentro
  daquela barbearia. Assim, o mesmo e-mail em barbearias diferentes é resolvido corretamente.

### E-mail por conta própria (Resend)
- O envio deixa de usar a integração gerenciada da Emergent e passa a usar a **sua conta
  Resend**, lendo a chave e o remetente de **variáveis de ambiente** (nada no código/chat).
- E-mail de **confirmação** enviado na hora do agendamento (sem tarefa em segundo plano,
  por limitação do serverless).
- **Lembrete** do dia seguinte disparado pelo agendador da própria Vercel (Vercel Cron).

### WhatsApp
- O botão "Enviar no WhatsApp" (lembrete manual) é preservado, sem custo e sem integração paga.

## Fluxo de uso
### Dono/admin
1. "Criar minha barbearia" → define nome e dados; recebe o código da barbearia e a conta de dono.
2. Login com código da barbearia + e-mail + senha.
3. Cadastra barbeiros (com horários e comissão), serviços e planos da sua barbearia.
4. Acompanha agenda, clientes, fidelidade, dashboard e relatórios — tudo só da sua barbearia.

### Cliente
1. Cadastra-se informando o código da barbearia desejada (mesmo e-mail pode ser usado em
   outra barbearia, como cadastro separado).
2. Login com código da barbearia + e-mail + senha.
3. Escolhe barbeiro, serviço, data e horário; o horário marcado fica indisponível.
4. Recebe e-mail de confirmação e, no dia anterior, o lembrete.

## Publicação (fluxo do dono, feito por você depois)
1. Criar cluster Atlas M0, usuário de banco e liberar o acesso de rede; copiar a string.
2. Conectar o repositório do GitHub à Vercel.
3. Cadastrar as variáveis de ambiente na Vercel (incluindo a string do Atlas e a chave Resend),
   todas como segredos.
4. Publicar. A Vercel compila o site e sobe a API como função serverless.

## Pontos que merecem sua atenção
1. **Tamanho da mudança.** O isolamento multi-barbearia altera praticamente todo o backend e
   os fluxos de cadastro/login. É a maior parte deste trabalho — maior que a adaptação à Vercel.
2. **Login por barbearia.** Passa a ser necessário informar o código da barbearia ao entrar
   (além de e-mail e senha), consequência de permitir e-mail repetido entre barbearias.
3. **Plano da Vercel.** O gratuito (Hobby) é para uso não comercial; para operação real de um
   CRM de barbearia o adequado é o Pro. Dá para testar no gratuito.
4. **Resend.** Você precisa criar a conta Resend e verificar um remetente/domínio; a chave e o
   e-mail remetente ficam em variáveis de ambiente na Vercel (não no código).
5. **Comportamento em serverless.** Confirmação enviada na hora (pequena espera a mais) e
   lembrete uma vez ao dia pelo agendador da Vercel (no plano gratuito, no máximo diário).
6. **vercel.json e caminhos.** O build do frontend sai na pasta `build/`; o `vercel.json`
   servirá esse conteúdo estático e direcionará `/api` para a função FastAPI, com retorno ao
   `index.html` para as rotas internas do site (SPA).

## Sensação de uso (UI/UX)
Mesmo tema escuro com dourado e as mesmas telas. Acrescenta-se: tela "Criar minha barbearia",
o campo de código da barbearia no cadastro e no login, e a identificação da barbearia atual no
painel. Nada mais muda visualmente.

## Fases de implementação

### Fase 1 — MVP (feito agora)
- Criar o conceito de Barbearia e separar **todos** os dados e consultas por barbearia
  (barbeiros, serviços, clientes, agendamentos, planos, assinaturas, fidelidade, dashboard,
  relatórios, disponibilidade e verificação de horário).
- E-mail repetível entre barbearias (único por barbearia) e **login por código da barbearia +
  e-mail + senha**, identificando corretamente a barbearia.
- Fluxos de "Criar barbearia" (dono) e cadastro de cliente por código da barbearia; cada
  admin restrito à própria barbearia.
- Adaptar o backend para rodar como função serverless na Vercel e apontar para o Atlas M0
  (banco novo e vazio; barbearia de exemplo recriada no primeiro uso).
- Trocar o e-mail para a conta própria (Resend) via variáveis de ambiente; confirmação na
  hora do agendamento; lembrete diário pelo agendador da Vercel.
- Adicionar o `vercel.json` e os ajustes de caminho (frontend em `build/`, API sob `/api`).
- Preservar login, dashboard, clientes, barbeiros, agendamentos, planos, fidelidade,
  relatórios, comissões e o botão de WhatsApp.
- **Testes de isolamento e autorização entre barbearias (obrigatório nesta fase):** verificar,
  inclusive acessando diretamente os endpoints da API com o token de uma barbearia, que
  nenhum admin ou cliente consegue ler ou modificar dados de outra barbearia — listagens,
  detalhes, edição, exclusão, disponibilidade, relatórios e dashboard. A verificação é feita
  pelo agente de testes antes de concluir.
- Entregar documentação das variáveis de ambiente e da lista de arquivos alterados.

### Fase 2 — Ajustes e robustez
- Afinar a reutilização de conexão com o Atlas para serverless (limites de conexão, tempos de
  espera) e reduzir efeitos de cold start.
- Domínio próprio, páginas de erro amigáveis e acompanhamento de logs.

### Fase 3 — Opcional
- Página pública de agendamento por barbearia (link/slug), sem exigir login prévio.
- Lembrete por WhatsApp 100% automático (Twilio) no lugar do link manual.
- Caso os limites do serverless incomodem, mover o backend para um host em container
  mantendo o site na Vercel.

## Suposições
- Projeto único na Vercel servindo site e API no mesmo domínio.
- **E-mail repetível entre barbearias**; a unicidade é por barbearia. O login usa **código da
  barbearia + e-mail + senha**; cada cadastro pertence a uma barbearia.
- Clientes se vinculam a uma barbearia pelo **código** da barbearia no cadastro.
- A conta admin existente (alexjaque334@gmail.com) vira dona de uma barbearia de exemplo,
  criada no primeiro uso; a senha é definida por você na Vercel (não fica no código).
- Banco começa vazio; nenhum dado do preview é migrado.
- E-mail de confirmação na hora do agendamento; lembrete uma vez ao dia via Vercel Cron.
- Chave Resend e e-mail remetente ficam em variáveis de ambiente na Vercel; nenhum valor é
  colocado no código ou exposto no chat.
- Botão de WhatsApp permanece como link manual.
- Nenhuma alteração será feita agora no banco atual da Emergent; o projeto **não** será
  publicado nesta etapa.
- As mudanças serão feitas no código do projeto; o envio ao GitHub é feito por você (ou sob
  sua confirmação), e eu informo ao final o que mudou.
