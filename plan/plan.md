# Acesso do Super Admin — Verificação e Procedimento Seguro de Credenciais

Confirmar como entrar no painel do Super Admin (/plataforma) e garantir, de forma segura, qual
e-mail e senha usar — sem nunca exibir a senha no chat ou nos logs, sem alterar código e sem
recriar a conta.

## Para quem é
Para o dono da plataforma, que acessou a tela de login em /plataforma e precisa das credenciais
corretas e de um procedimento seguro para consultar ou definir a senha.

## Resultado esperado (o que fica resolvido)
- Fica claro qual é o e-mail do Super Admin (o mesmo e-mail já configurado por você).
- Fica claro onde consultar e, se quiser, alterar a senha com segurança — por conta própria,
  no painel de variáveis de ambiente/segredos do preview (o valor nunca é mostrado por aqui).
- Fica confirmado, por verificação somente-leitura no banco do preview, que existe exatamente
  uma conta de Super Admin e que o e-mail dela corresponde ao e-mail configurado (resposta do
  tipo "sim/não", sem expor senha nem o hash).
- Fica documentado como a senha é tratada: ela é gravada apenas na criação da conta e não é
  redefinida automaticamente a cada reinício (medida de segurança). Ou seja, editar a variável
  de ambiente depois que a conta já existe NÃO troca a senha sozinho.
- Para o caso de a senha guardada não corresponder mais ao valor da variável de ambiente, há um
  procedimento seguro e pontual de sincronização — executado somente com a sua confirmação
  explícita, sem criar conta nova e sem mexer no código.

## Núcleo da entrega e experiência
1. Identificação das credenciais
   - E-mail do Super Admin: o mesmo e-mail que você já configurou (sem mudança).
   - Senha: fica guardada na variável de ambiente de segredos do preview; você mesmo a consulta
     ou define por lá. Nada de senha é exibido no chat nem gravado em log.
2. Verificação somente-leitura (preview)
   - Checagem de que a conta de Super Admin existe e de que o e-mail bate com o configurado.
   - Relato objetivo (existe/está correto) sem revelar valores sensíveis.
3. Procedimento seguro de senha
   - Passo a passo de onde ver/editar a senha no painel de segredos do preview.
   - Aviso explícito: como a senha só é definida na criação, uma troca posterior exige a
     sincronização pontual descrita abaixo para passar a valer no login.
4. Sincronização pontual (opcional, só sob confirmação)
   - Caso você troque a senha e queira que ela passe a valer sem recriar a conta, uma ação única
     e controlada ajusta a credencial da conta existente a partir do valor definido por você na
     variável de ambiente. Sem exibir o valor, sem recriar a conta, sem alterar o código.
5. Produção (Vercel)
   - A senha de produção é definida por você nas variáveis de ambiente da Vercel. Orientação de
     onde colocar, mantendo o mesmo princípio de não expor o valor.

## Fluxo de uso
1. Você abre /plataforma.
2. Usa o e-mail já configurado como Super Admin.
3. Consulta a senha atual no painel de segredos do preview (por conta própria) e entra.
4. Se quiser outra senha: define o novo valor no painel de segredos e, em seguida, solicita a
   sincronização pontual para que passe a valer no login.
5. Em produção, define a senha nas variáveis de ambiente da Vercel antes de publicar.

## Sensação de uso (UI/UX)
Sem mudança visual. A tela de login do Super Admin permanece como está; a entrega é verificação
e orientação segura, não uma nova interface.

## Fases de implementação

### Fase 1 — MVP (feito agora)
- Confirmar o e-mail do Super Admin (o já configurado) e indicar, com clareza, onde consultar e
  definir a senha no painel de segredos do preview — sem exibir o valor.
- Verificação somente-leitura no banco do preview: existe uma conta de Super Admin e o e-mail
  corresponde ao configurado (relato sim/não, sem dados sensíveis).
- Documentar o comportamento de senha (definida só na criação; não redefinida a cada reinício) e
  o procedimento para produção na Vercel.
- Disponibilizar a sincronização pontual de senha para a conta existente, executada apenas se
  você confirmar e somente se for necessária (quando o valor da variável não corresponder ao
  guardado). Sem recriar conta e sem alterar código.

### Fase 2 — Troca de senha autosserviço
- Opção, dentro do painel do Super Admin, para o próprio Super Admin alterar a senha de forma
  guiada (senha atual + nova), eliminando a necessidade de mexer em variáveis de ambiente.

### Fase 3 — Reforços de segurança da conta
- Recuperação de acesso por e-mail e verificação em duas etapas (2FA) para o Super Admin, além
  de registro de auditoria de acessos e trocas de senha.

## Suposições
- O e-mail do Super Admin permanece o mesmo que você já configurou (é a conta de plataforma,
  separada da conta de administrador de barbearia, ainda que o endereço de e-mail possa coincidir).
- A senha do preview é gerida por você no painel de segredos/variáveis de ambiente; este canal
  nunca exibirá a senha nem o hash, e nada sensível irá para os logs.
- Nenhuma alteração de código e nenhuma recriação de conta na Fase 1; a única ação de escrita
  possível é a sincronização pontual da senha da conta existente, e somente com sua confirmação.
- Como a senha só é aplicada na criação da conta, editar a variável depois não altera o login por
  si só; por isso existe a sincronização pontual.
- A senha de produção é definida por você nas variáveis de ambiente da Vercel.
- A verificação de existência da conta é feita no ambiente de preview.
