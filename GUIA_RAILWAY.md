# 🔥 CHAMAS FLAMEJANTES V10.2 — RAILWAY + SQLITE

Esta é a versão da V7.5 adaptada para ficar online usando:

- Flask/Python
- SQLite
- Railway
- Railway Volume persistente
- Gunicorn
- GitHub para o código

O Firestore NÃO é usado.

---

# COMO FUNCIONA

No seu computador:

- Banco: `data/tournament.sqlite`
- Fotos: `static/uploads`

No Railway, depois de anexar o Volume:

- Banco: `/app/persistent/tournament.sqlite`
- Fotos: `/app/persistent/uploads`

O Railway informa automaticamente o caminho do Volume à aplicação.
A V10.2 detecta isso e usa o Volume sem você editar o código.

IMPORTANTE:
Se a aplicação perceber que está no Railway sem Volume, ela se recusa a iniciar.
Isso é proposital para impedir que torneios e fotos sejam gravados em armazenamento temporário.

---

# PASSO 1 — COLOCAR NO GITHUB

1. Crie um repositório no GitHub.
2. Pode chamar de:

   `chamas-flamejantes`

3. Envie TODO o conteúdo da pasta `CHAMAS_FLAMEJANTES_V9`.
4. O arquivo `railway.json` deve ficar na raiz do repositório, junto de `app.py`.

Não publique senhas novas em arquivos.
A senha padrão inicial continua funcionando, mas troque depois que o site ficar online.

---

# PASSO 2 — CRIAR O PROJETO NO RAILWAY

1. Entre em https://railway.com/
2. Faça login.
3. Clique em **New Project**.
4. Escolha **Deploy from GitHub repo**.
5. Autorize o GitHub, se for solicitado.
6. Selecione o repositório `chamas-flamejantes`.

É normal o primeiro deploy falhar se você ainda não adicionou o Volume.
A V10.2 bloqueia o modo Railway sem armazenamento persistente.

---

# PASSO 3 — ADICIONAR O VOLUME

Este é o passo MAIS IMPORTANTE.

No projeto Railway:

1. Selecione o serviço do Chamas Flamejantes.
2. Adicione um **Volume**.
3. Anexe esse Volume ao serviço.
4. No **Mount Path**, coloque EXATAMENTE:

   `/app/persistent`

Depois faça **Redeploy**.

Não monte o Volume em `/app`.
Use `/app/persistent`.

---

# PASSO 4 — SECRET KEY

No serviço, abra **Variables**.

Crie:

`FFA_SECRET_KEY`

Use uma senha aleatória grande, por exemplo 40+ caracteres.

Não use a senha do admin aqui.
Essa variável protege as sessões do Flask.

---

# PASSO 5 — GERAR O ENDEREÇO PÚBLICO

Depois do deploy ficar verde:

1. Abra o serviço.
2. Vá em **Settings**.
3. Vá em **Networking**.
4. Clique em **Generate Domain**.

O Railway fornecerá um endereço parecido com:

`https://chamas-flamejantes-production.up.railway.app`

---

# ADMIN

Usuário inicial:

`yukinochannyan`

Senha inicial:

`yukinochannyan60`

Depois de publicar, entre em `/admin` e altere a senha.

---

# COMO SABER SE O VOLUME ESTÁ FUNCIONANDO

Abra:

`https://SEU-DOMINIO/health`

Você deve ver:

`"persistent_storage": true`

Se aparecer `false`, NÃO use o site para dados importantes.

No Railway corretamente configurado, a aplicação nem inicia se o Volume estiver ausente.

---

# LEVAR SEU SQLITE ANTIGO PARA O RAILWAY

A V10.2 vem com o SQLite presente no pacote como banco inicial.

Se você quiser substituir pelo banco que está usando no seu computador:

## Método recomendado — Railway CLI

Instale/abra a Railway CLI, conecte o terminal ao projeto e ao serviço.

Com o Volume anexado, você pode usar os comandos de arquivos do Volume.

Primeiro faça backup do seu site.

Seu arquivo local é:

`data/tournament.sqlite`

No Volume, o destino é:

`/tournament.sqlite`

O Volume está montado na aplicação em `/app/persistent`, mas o navegador de arquivos
do próprio Volume usa `/` como raiz do Volume.

Você também pode usar:

`railway volume browse /`

para abrir o navegador interativo e enviar/baixar arquivos.

IMPORTANTE:
Pare/reinicie o serviço ao substituir manualmente um SQLite já em uso.

---

# BACKUP

O painel continua com o download do SQLite.

A rota administrativa de backup baixa diretamente o banco que estiver ativo,
inclusive o arquivo armazenado no Railway Volume.

Faça backups periódicos.

---

# FOTOS

As fotos escolhidas no PC também são persistentes.

Elas ficam no mesmo Volume em:

`/app/persistent/uploads`

Portanto, trocar a versão do código não apaga as fotos.

---

# POR QUE SÓ 1 WORKER?

SQLite é excelente para este projeto, mas é um banco de arquivo.

A V10.2 roda o Gunicorn com:

- 1 worker
- 8 threads

Isso permite várias requisições sem criar vários processos disputando o mesmo SQLite.

Também foi configurado:

- timeout do SQLite de 30 segundos;
- `busy_timeout`;
- WAL quando suportado.

Para um site comunitário/torneios, é uma configuração adequada.

---

# ARQUIVOS NOVOS DA V10.2

`railway.json`
Configuração oficial do deploy no Railway.

`railway_start.py`
Prepara o Volume, inicializa o banco e inicia o Gunicorn.

`Procfile`
Fallback do comando de inicialização.

`.gitignore`
Evita enviar arquivos locais desnecessários.

---

# ATUALIZAÇÕES FUTURAS

Depois que o GitHub estiver conectado ao Railway:

1. você altera o código;
2. envia as alterações para o GitHub;
3. Railway faz novo deploy;
4. SQLite e fotos continuam no Volume.

Código e dados ficam separados.

---

# CUIDADO

NÃO remova o Volume do serviço.
NÃO use "Wipe Volume" sem backup.
Isso apagaria seu SQLite e as fotos.

Antes de mudanças grandes:
- baixe o backup SQLite pelo admin;
- opcionalmente faça backup do Volume pelo Railway.

