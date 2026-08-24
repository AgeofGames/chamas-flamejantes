# 🔥 CHAMAS FLAMEJANTES V10.2 — MESTRE DO X1 + MAPAS PRO

**Esta versão foi construída diretamente em cima da V9 Railway funcional.**

O banco continua no mesmo Volume:
`/app/persistent/tournament.sqlite`

Os uploads existentes continuam em:
`/app/persistent/uploads`

Os mapas novos ficam em:
`/app/persistent/maps`

## Novidades
- Biblioteca pública de mapas com preview, criador, categoria e downloads.
- Admin de mapas com upload de arquivo + imagem.
- WhatsApp, Discord e Telegram oficiais editáveis pelo admin.
- Arena pública de Duelos X1.
- Apenas jogadores que já existem em `players` e têm AoMStats podem solicitar duelo.
- Apenas um duelo pendente/em curso por vez.
- Admin aprova/recusa e registra o vencedor.
- Histórico público de duelos.
- Ranking acumulado: vitórias, derrotas, win rate e sequência atual.
- Primeiro colocado recebe **Mestre do X1**.
- Perfil público de cada jogador.
- Botão **DESAFIAR JOGADOR** no perfil.
- Busca AoMStats na tela de desafio.

## Como atualizar no Railway
Substitua os arquivos no repositório, faça Commit + Push e aguarde o deploy.
**Não remova o Volume.**

Confirme em `/health`:
- `version`: `10.2-mestre-x1`
- `persistent_storage`: `true`

No log de deploy deve aparecer:
`CHAMAS FLAMEJANTES V10.2 - MESTRE DO X1 + MAPAS PRO`

---

# 🔥 CHAMAS FLAMEJANTES V9 — RAILWAY + SQLITE PERSISTENTE

Esta versão mantém a base da **V7.5** e troca apenas a infraestrutura de hospedagem.

**Não usa Firestore.**

Para publicar 24h sem deixar o PC ligado, use:
**GitHub + Railway + Railway Volume**.

Leia primeiro: `GUIA_RAILWAY.md`.

## Configuração obrigatória no Railway

Adicione um Volume ao serviço com:

`Mount Path: /app/persistent`

A aplicação usa automaticamente esse Volume para:

- `tournament.sqlite`
- fotos manuais dos jogadores;
- fotos de patrocinadores;
- avatares em cache.

Se estiver no Railway sem Volume, a aplicação não inicia, evitando perda de dados.

---

# 🔥 CHAMAS FLAMEJANTES V6 — Age of Mythology: Retold

A V6 transforma o projeto em uma plataforma de **múltiplos torneios simultâneos**, mantendo o sistema anterior, SQLite local, fotos AoMStats/Steam e todas as inscrições.

## O que mudou na V6

Você não fica mais preso a um único torneio de cada modalidade. No painel administrativo é possível clicar em **Criar novo torneio** e abrir quantos eventos quiser ao mesmo tempo — inclusive dois FFA, três 2x2 ou vários MD3 simultaneamente.

A página pública agora separa automaticamente:

- **Torneios Abertos** — estão recebendo inscrições.
- **Em Andamento** — inscrições encerradas e confrontos acontecendo.
- **Histórico** — torneios finalizados, campeão e confrontos preservados.

## Modalidades disponíveis

1. **FFA — Sem Regras**
   - 12 jogadores por padrão.
   - Pode ter um ou vários vencedores.
   - O prêmio é dividido entre os vencedores.

2. **FOOD WOOD GOLD — 3x3**
   - Até 12 equipes por padrão.
   - FOOD + WOOD + GOLD.
   - Eliminação direta.

3. **1v1 — Todos Contra Todos**
   - Até 32 jogadores.
   - Todos enfrentam todos.
   - Classificação por vitórias.

4. **2x2 — Eliminação**
   - Duplas em mata-mata.
   - Perdeu, está fora.

5. **Melhor de 3 — 1x1**
   - Mata-mata MD3.
   - Primeiro a 2 vitórias avança.
   - Placares válidos: 2x0 ou 2x1.

6. **Melhor de 3 — 2x2**
   - Duplas.
   - Cada confronto é uma série MD3.

7. **Melhor de 3 — 3x3**
   - Equipes de três.
   - Cada confronto é uma série MD3.

## Torneios Abertos

Acesse:

`http://127.0.0.1:5000/torneios`

Todo torneio com status `inscricoes`, marcado como público e com inscrições abertas aparece automaticamente para os jogadores.

## Histórico

Acesse:

`http://127.0.0.1:5000/historico`

O histórico mostra:

- nome e modalidade do torneio;
- campeão ou campeões;
- quantidade de jogadores/equipes;
- quantidade de confrontos;
- link para o resumo final;
- link **Quem lutou com quem**, com todas as rodadas e placares.

Os confrontos ficam gravados na tabela `matches` do SQLite e não desaparecem quando o torneio termina.

## Como criar vários torneios

1. Abra `http://127.0.0.1:5000/admin`.
2. Entre como administrador.
3. No topo, abra **Criar novo torneio**.
4. Escolha a modalidade.
5. Informe nome, prêmio, quantidade de vagas, data e mapa.
6. Clique em **Criar e abrir inscrições**.
7. Repita quantas vezes quiser.

Cada torneio recebe um `slug` e um ID próprios no banco. Portanto, vários eventos da mesma modalidade funcionam ao mesmo tempo sem misturar inscrições, equipes ou resultados.

## Melhor de 3

Nos modos MD3, o painel não precisa de um seletor de vencedor. Basta informar o placar da série:

- `2 x 0`
- `2 x 1`
- `0 x 2`
- `1 x 2`

O sistema identifica automaticamente o vencedor, avança a equipe/jogador na chave e, quando a final termina, publica o campeão no histórico.

## Banco SQLite

Banco principal:

`data\tournament.sqlite`

Principais tabelas:

- `tournaments` — cada evento criado, modalidade, status, MD3 e configurações.
- `players` — jogadores globais.
- `teams` — equipes de cada torneio.
- `team_members` — integrantes das equipes.
- `tournament_entries` — inscrições por torneio.
- `matches` — confrontos, rodadas, adversários e placares.
- `tournament_winners` — campeões e premiação.

## Atualizar da V4 sem perder os dados

A V6 possui migração automática.

1. Extraia a V6 em uma pasta nova.
2. **Antes de iniciar**, copie da V4 o arquivo:
   `data\tournament.sqlite`
3. Cole em `data\` da V6, substituindo o banco vazio.
4. Copie também `static\uploads\` se tiver fotos manuais.
5. Execute `INICIAR.bat`.

Na primeira inicialização, o sistema adiciona os campos V6 e os três modos MD3 sem apagar o FFA, participantes, equipes, resultados ou administrador existentes.

## Instalação limpa

1. Instale Python 3.11 ou superior e marque **Add Python to PATH**.
2. Execute `INSTALAR.bat` uma vez.
3. Execute `INICIAR.bat`.
4. Site: `http://127.0.0.1:5000`
5. Admin: `http://127.0.0.1:5000/admin`

## Publicar na internet

O `PUBLICAR_INTERNET.bat` continua funcionando com `cloudflared.exe` na pasta do projeto. Mantenha `INICIAR.bat` aberto e depois execute `PUBLICAR_INTERNET.bat`.

## Backup

Use **BACKUP SQLITE** no painel ou execute `BACKUP_LOCAL.bat`. Para preservar fotos manuais, mantenha também uma cópia de `static\uploads\`.


## Novidades da V6

- Novos torneios ficam **fechados por padrão**. Nada aparece em **Torneios Abertos** até o administrador abrir as inscrições.
- As 7 modalidades são modelos de criação; elas não aparecem mais como 7 torneios automaticamente abertos.
- Prêmios podem ser **dinheiro, objeto ou os dois**. Use o campo **Nome do prêmio / objeto** para escrever, por exemplo: `Troféu Chamas Flamejantes`, `Teclado Gamer`, `Booster Pokémon` ou qualquer outro item.
- O campeão ganha destaque **neon**, inclusive nome, avatar e link AoMStats.
- Área pública e administrativa de **Patrocinadores Oficiais**.
- Nova página `/comunidade` com o **Elo da Comunidade**.
- Apenas o administrador cadastra os jogadores do ranking da comunidade.
- O maior Elo recebe o destaque **Melhor da Comunidade**.
- O menor Elo recebe o destaque **Pior Fracassado**.
- O ranking da comunidade aceita Nick, Elo, Discord, AoMStats, foto Steam direta ou upload manual.

### Atualizando da V5

Você pode copiar seu `data/tournament.sqlite` antigo para a V6. A migração cria os novos campos e tabelas sem apagar torneios, inscritos, partidas ou histórico. Instâncias padrão vazias da V5 são removidas para que a área de Torneios Abertos comece corretamente.


## V6.1 — Elo da Comunidade sincronizado pelo AoMStats

O cadastro do **Elo da Comunidade** agora funciona da mesma forma que a inscrição normal:

1. Entre no painel administrativo.
2. Abra **Elo da Comunidade**.
3. Cole o link `https://aomstats.io/profile/ID`.
4. Clique em **BUSCAR DADOS** para visualizar Nick, Elo Sup 1v1 e foto.
5. Clique em **CADASTRAR NA COMUNIDADE**.

Mesmo que o administrador não clique em **BUSCAR DADOS**, o backend consulta novamente o perfil AoMStats ao cadastrar. O Nick, Elo Sup 1v1 e avatar Steam/AoMStats são sincronizados automaticamente. Discord e observação continuam sendo campos manuais.

Se o jogador já existir por ter participado de outro torneio, o mesmo cadastro de jogador é reutilizado e atualizado.


## V6.2 — Patrocinadores pelo AoMStats

Agora o cadastro dos **Patrocinadores Oficiais** funciona pelo AoMStats:

1. Abra o painel administrativo.
2. Vá em **Patrocinadores Oficiais**.
3. Cole o perfil `https://aomstats.io/profile/ID`.
4. Clique em **BUSCAR DADOS**.
5. O site mostra uma prévia com **Nick e foto Steam/AoMStats**.
6. Clique em **CADASTRAR PATROCINADOR**.

O backend consulta o perfil novamente no momento do cadastro. A URL Steam exibida pelo AoMStats é gravada e usada diretamente no site, com cache local como reserva.

Na página inicial cada patrocinador aparece com:
- foto de perfil;
- nome;
- botão para AoMStats;
- site/Instagram opcional.

Cada patrocinador no painel possui **ATUALIZAR AOMSTATS** para sincronizar novamente o nome e a foto.


## V6.3 — Cadastro administrativo dos torneios pelo AoMStats

A opção **Adicionar jogador/equipe manualmente** foi substituída por **Adicionar pelo AoMStats**.

### Torneios individuais
Para FFA, 1x1 e MD3 1x1:
1. Cole o perfil AoMStats.
2. Clique em **BUSCAR DADOS**.
3. O painel mostra Nick, Elo e foto.
4. Clique em **CADASTRAR JOGADOR**.

### Torneios em equipe
Para 2x2, 3x3, Food Wood Gold e MD3 em equipes:
- Informe o nome da equipe.
- Cada jogador recebe um campo AoMStats separado.
- Cada integrante possui seu próprio botão **BUSCAR DADOS**.
- Nick, Elo e foto de cada jogador são consultados individualmente.
- O servidor consulta todos os perfis novamente antes de salvar.

O Elo utilizado respeita a configuração da modalidade (`Sup 1v1` ou `Sup Team`).


## V6.4 — Correção visual do “Aguardando perfil”

Corrigido o bug visual mostrado no painel em:
- Elo da Comunidade;
- Patrocinadores Oficiais;
- cadastro de jogadores em torneios;
- cadastro dos integrantes de equipes 2x2 / 3x3 / Food Wood Gold.

Antes da busca, somente o círculo/ícone padrão aparece.
A tag de imagem permanece completamente oculta até uma foto válida terminar de carregar.

Se a URL do avatar falhar:
- a imagem é escondida;
- o `src` inválido é removido;
- o placeholder volta automaticamente;
- não aparece mais o ícone nativo de “imagem quebrada”.


## V7 — fundos, fotos manuais e jogadores SEM ELO

### Fundo diferente em cada página
As páginas agora recebem cenários diferentes de **Age of Mythology: Retold**, usando artes e screenshots hospedadas em páginas oficiais do Xbox, PlayStation e Steam. Torneios e subpáginas também variam o cenário.

### Foto manual em todos os cadastros AoMStats
Além da foto Steam/AoMStats, agora é possível enviar JPG/PNG/WebP do próprio computador em:
- inscrição pública individual;
- inscrição pública de equipes;
- cadastro administrativo de jogadores;
- jogadores 2x2/3x3/Food Wood Gold;
- Elo da Comunidade;
- Patrocinadores Oficiais.

Se uma foto manual for enviada, ela tem prioridade e não é apagada quando o perfil AoMStats é sincronizado.

### SEM ELO
Um jogador sem Elo ranqueado não precisa mais inventar um valor. O site mostra **SEM ELO**.

No **Elo da Comunidade**:
1. qualquer jogador com Elo ranqueado fica acima de todos os SEM ELO;
2. jogadores com Elo são ordenados pelo Elo Sup 1v1;
3. jogadores SEM ELO são ordenados pelo nível calculado a partir de Customs/Quickplay;
4. em empate de nível: taxa de vitória, número de vitórias e menor número de derrotas desempata.

### Partidas normais do AoMStats
O site consulta `?leaderboard=0`, que corresponde ao filtro **Customs/Quickplay** no perfil do AoMStats, e lê o resumo de vitórias e derrotas.

### Cálculo do nível SEM ELO
Nível de 1 a 100:
`nível = 5 × raiz(vitórias) + 50 × taxa_de_vitória`, limitado entre 1 e 100.

Faixas:
- 1–19: Novato
- 20–39: Aprendiz
- 40–59: Guerreiro
- 60–79: Veterano
- 80–94: Mestre
- 95–100: Lenda

Importante: o AoMStats alerta que os dados não ranqueados anteriores a **8 de março de 2025** podem não ser precisos.


## V7.1 — Administrador padrão

A versão já vem com a conta administrativa pronta.

**Usuário:** `yukinochannyan`  
**Senha:** `yukinochannyan60`

Painel:

`http://127.0.0.1:5000/admin`

Não é necessário criar uma conta em `/setup`.

Dentro do painel, abra **Alterar senha** para mudar a senha padrão quando quiser.

### Compatibilidade com bancos anteriores

Se você usar um banco antigo e ele não tiver nenhum administrador, a V7.1 cria automaticamente o admin padrão na inicialização.

Se o banco já tiver uma conta administrativa, ela é preservada e não é substituída.


## V7.2 — Correção do Internal Server Error no painel

Foi localizado e corrigido o erro da V7.1.

O template administrativo possuía o formulário **Alterar senha**, que chamava a rota:

`admin_change_password`

Durante a evolução para a V7 essa rota havia sido removida acidentalmente. O login funcionava, mas ao abrir `/admin` o Flask tentava gerar a URL dessa rota inexistente e retornava **Internal Server Error (500)**.

A V7.2 restaura a rota e mantém:

**Usuário padrão:** `yukinochannyan`  
**Senha padrão:** `yukinochannyan60`

A senha pode ser alterada normalmente pelo painel.

A V7.2 também valida os `url_for()` usados nos templates para impedir que outra página seja entregue referenciando uma rota inexistente.


## V7.4 — Wallpaper limpo

A V7.4 volta ao visual de cards da V7.2:

- imagens de Age of Mythology: Retold aparecem **somente como papel de parede da página**;
- cards, tabelas, painéis, patrocinadores e blocos administrativos **não possuem imagens internas**;
- cada aba continua recebendo um cenário diferente;
- o wallpaper ficou mais claro e visível;
- os cards ficaram levemente transparentes para o cenário aparecer por trás;
- o cabeçalho e o rodapé também voltaram ao estilo limpo, sem fotos próprias;
- no celular a imagem continua visível, com um pouco mais de escurecimento para facilitar a leitura.


## V7.5 — Frases pessoais e edição do Elo da Comunidade

- Fundo da página **Elo da Comunidade** mais escuro.
- Cada jogador possui uma frase pessoal de até 220 caracteres.
- A frase pode ser cadastrada em inscrições públicas, cadastro administrativo, equipes e Elo da Comunidade.
- A frase acompanha o perfil global do jogador e aparece nas páginas públicas.
- No Elo da Comunidade existe **EDITAR FOTO E FRASE**.
- É possível trocar a foto do PC quando quiser ou voltar para a foto do AoMStats/Steam.
- A frase também pode ser alterada pelo editor do jogador dentro de um torneio.
