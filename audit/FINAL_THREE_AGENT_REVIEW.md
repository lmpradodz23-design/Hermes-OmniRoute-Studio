# FINAL_THREE_AGENT_REVIEW

Auditoria independente de `feature/hermes-omniroute-studio` @ `8a5e3d4`
(base upstream `e30388e`), 2026-08-22.

Três revisores trabalharam em paralelo, sem ver as conclusões uns dos outros
antes de terminar:

| | escopo | achados |
|---|---|---|
| **A** | Arquitetura/Engenharia | 5 HIGH · 6 MEDIUM · 6 LOW · 3 IMPROVEMENT |
| **B** | Segurança/DevSecOps (postura ofensiva) | 2 HIGH · 1 MEDIUM · 1 LOW · 1 IMPROVEMENT |
| **C** | Produto/QA/UX | 1 CRITICAL · 6 HIGH · 13 MEDIUM · 4 LOW |

Regra aplicada a todos: **reproduza antes de reportar**. Achado sem PoC
executável foi rebaixado a `SUSPEITA` ou descartado. Nenhum auditor teve
permissão de escrita no repositório.

O que segue é o consolidado, com o estado de cada item.

---

## CRITICAL

### C-1 · Mission Control prometia "todas as sessões" e só via as abertas — **CORRIGIDO**

O painel novo lia `$statusItemsBySession`, alimentado exclusivamente por eventos
de sessões montadas nesta janela. Consequências reproduzidas pelo auditor:

- cinco sessões trabalhando, uma aberta → o painel mostrava **uma**;
- reiniciar o app com processos vivos → **"Nada em execução"**, para sempre;
- clicar em Atualizar nesse estado → **nada**, porque o handler iterava uma
  lista vazia.

A promessa da própria tela ("um processo que morreu numa sessão fechada não
aparece em lugar nenhum") era exatamente o caso que continuava aberto.

**Correção**: `process.list_all` novo no gateway (`tui_gateway/methods_tools.py`
+ `_all_processes` em `server.py`), devolvendo cada processo com o
`session_key` do dono — o registro já era global, só a projeção era escopada.
No desktop, `refreshAllBackgroundProcesses()` hidrata na montagem e no botão
Atualizar. Matar e dispensar continuam escopados por sessão de propósito: ver o
trabalho alheio não é a mesma permissão que ceifá-lo.

**Testes**: 25 em `apps/desktop/src/app/mission-control/`, incluindo a
hidratação inicial e o Atualizar no estado vazio.

---

## HIGH

### B-1 · ANSI-C quoting furava o piso hardline — `rm -rf /` sob yolo — **CORRIGIDO**

`$'...'` é reduzido pelo bash a caracteres literais **antes** de o comando
rodar. `rm -rf $'/'`, `$'\x2f'` e `$'\057'` chegavam ao shell como `rm -rf /` e
passavam: o `$` inicial quebrava o ramo de aspas (que espera `["']`) e o token
não começava com `/`, então o ramo simples também errava.

O peso disto é específico: o piso hardline é a **única** defesa que sobrevive ao
`--yolo`. PoC do auditor, com `HERMES_YOLO_MODE=1`:

```
hardline=True   approved=False   rm -rf /            <- controle
hardline=False  approved=True    rm -rf $'\x2f'      <- BYPASS
hardline=False  approved=True    rm -rf $'\057'      <- BYPASS
hardline=False  approved=True    rm -rf $'/'         <- BYPASS
```

**Correção**: `_expand_ansi_c_quotes` no normalizador, posicionado **antes** do
strip genérico de backslash (que dissolveria `\x2f` em `x2f`) e antes dos folds
de home. Cobre `\xHH`, `\NNN`, `\uXXXX` e os escapes nomeados. Depois da
correção, `$'\x72\x65\x62\x6f\x6f\x74'` também é pego.

### B-2 · DoS e `RecursionError` no guard de comandos — **CORRIGIDO**

`"$(" * n + "id" + ")" * n` é livre de separadores, minúsculo, e passava por
todos os tetos existentes. Medido pelo auditor: 302 chars → 2,5 s; 362 → 4,2 s;
608 → ~15 s; ~3000 chars → `RecursionError` **dentro** da checagem que decide se
um comando é seguro, sem `try/except` no sítio de chamada.

**Correção**: tetos de quantidade e profundidade de substituição de comando em
`_command_parser_limit_exceeded`, e `try/except RecursionError` em
`check_all_command_guards` que **falha fechado**. Depois: 15 002 chars decididos
em 0,000 s; `echo $(date)` e afins intocados.

### A-1 · `npx <pacote> --no` desligava o detector de execução remota — **CORRIGIDO**

A checagem de "forma local" varria **todos** os tokens, inclusive os argumentos
do pacote executado. Qualquer `--no` na linha silenciava a detecção inteira — e
comando não flagrado é **auto-aprovado sem prompt**.

**Correção**: `_pkg_runner_is_local_only` só aceita a flag enquanto ela for
opção do próprio runner (antes do primeiro operando).

### A-2 · `npx -p <pacote> -c '<cmd>'` escapava — **CORRIGIDO**

`-p` é `--package` no npx: o nome do que será baixado. A tabela global de flags
consumia o valor, a lista de operandos ficava vazia, nada era reportado.
(`tools/osv_check.py` já sabia disso; `approval.py` não.)

**Correção**: `_PKG_PACKAGE_NAMING_FLAGS` — para essas flags o valor não é
descartado, é o que interessa. De quebra, o prompt passa a nomear o **pacote**
e não o binário local (achado A-13), o que importa porque um humano aprova
olhando para o nome que lê.

### A-3 · O bloqueio "incondicional" de malware era condicional — **CORRIGIDO**

`check_install_command_for_malware` fazia `shlex.split` do comando inteiro e
olhava só `tokens[0]`. `true && npm install <malware>` e
`cd /tmp; npm install <malware>` passavam inteiros; `python3.12 -m pip` não era
reconhecido como pip; `--target .` fazia o extrator devolver `.` e desistir.

**Correção**: segmentação de shell reusando `_iter_top_level_shell_segments`,
regex de interpretador versionado, e tabela de flags que consomem valor.

### A-4 · A detecção de estagnação era inerte — e o teste escondia isso — **CORRIGIDO**

O achado mais desconfortável desta auditoria, porque é sobre código escrito
nesta mesma missão.

`classify_progress` tratava qualquer mudança de `workspace_fingerprint()` como
progresso. Só que o fingerprint era medido **depois** de rodar os gates, então
os artefatos do próprio gate (relatório de cobertura, `dist/`, qualquer arquivo
não ignorado) contavam como trabalho do agente. `workspace_moved` dava `True`
todo turno, os contadores nunca subiam, e o caso motivador — gate vermelho com
`max_retries` alto — queimava o orçamento inteiro.

O teste que cobria isso passava porque `workspace_fingerprint` estava
**patcheado para uma constante**: o mock removia exatamente a variável que
quebrava.

**Correção em três camadas**, cada uma revelada pela anterior:

1. medir uma vez por turno, antes dos gates — **não bastou**: o artefato escrito
   no turno N ainda está lá no início do turno N+1;
2. separar o que se **compara** (fingerprint do início do turno) do que se
   **guarda** (fingerprint do fim, pós-gate) — o delta atribuível ao agente;
3. `workspace_fingerprint` passou a ser sensível a **conteúdo** (`git diff HEAD`
   + tamanho/mtime dos não rastreados que o porcelain já lista).

O item 3 corrigiu um bug **upstream** independente: `git status --porcelain`
devolve ` M src.py` na primeira edição e na décima, então o pulo de gate
("workspace inalterado desde a última falha") não re-rodava a suíte depois de o
agente editar um arquivo já modificado — **a correção nunca era testada**, a
falha antiga era reproduzida, e o contador de tentativas avançava sozinho.

**Testes**: três novos usando um repositório git **de verdade**, sem mock de
fingerprint. Canário: desfazendo a separação compara-vs-guarda, o teste reprova.

### A-5 · A assinatura de falha do judge era texto livre — **CORRIGIDO**

`reason` vem verbatim do modelo auxiliar ("<one sentence>"), e qualquer
diferença de bytes lia como "a falha mudou ⇒ o diagnóstico andou". Com um judge
real (temperatura > 0), isso zerava os contadores quase sempre.

**Correção**: a assinatura passou a ser o **veredito**, não a frase. No caminho
do judge o progresso depende do que é objetivamente verificável: o workspace
mudou ou não mudou. Teste: sete reformulações da mesma ressalva sobre workspace
intocado agora escalam.

### C-2 · pt-BR com dano de tradução automática em dezenas de telas — **CORRIGIDO**

Executando o catálogo final, 16 funções produziam texto quebrado:

| chave | antes | agora |
|---|---|---|
| `composer.attachments` | "2 anexoé" | "2 anexos" |
| `settings.toolsets.modelCount` | "2 modeloé" | "2 modelos" |
| `skills.hub.resultCount` | "2 resultadoé em 2senhora" | "2 resultados em 2 ms" |
| `cron.tabs.jobs` | "Empregos" | "Tarefas" |
| `settings.about.branchCommit` | "Filial X · Comprometer-se Y" | "Branch X · Commit Y" |
| 12 chaves | "…compositor" | "…editor de mensagem" |

**Causa raiz**: `generate-pt-br-locale.mjs` extraía cada literal isolado e
mandava traduzir. Em `${n} model${n === 1 ? '' : 's'}`, o sufixo `'s'` virava
string traduzível própria e voltava como `'é'`; `'ms'` virava `'senhora'`.

**Por que ninguém viu**: `pt-br.test.ts` mede cobertura com um `flatten` que
**ignora valores função** — são 388 chaves-função, nenhuma verificada. A métrica
dizia 98,5% enquanto a tela dizia "2 anexoé".

**Correção**: as 16 curadas à mão, mais `pt-br-plurals.test.ts`, que **chama**
cada função com 1 e 2 e exige plural real; e um detector de chave duplicada por
caminho completo — porque um bloco `skills:` novo inserido antes de um já
existente é descartado pelo JavaScript sem erro nenhum (aconteceu duas vezes
durante esta própria correção).

### C-3 · "Toggle Mission Control" não fazia nada abaixo de 768px — **CORRIGIDO**

Em viewport estreita um pane `collapsible` sai da grid e só volta pelo
`PANE_TOGGLE_REVEAL_EVENT`. O toggle novo lia a árvore (que diz "visível"), o
usuário não via nada, e o segundo aperto fechava algo que ele nunca viu. A
janela mínima do Electron é 400px.

**Correção**: `toggleNarrowAwarePane` em `store/layout.ts`, o mesmo caminho que
a sidebar, o file browser e o review já usavam.

### C-4 · O script de build só funcionava na máquina do autor — **CORRIGIDO**

`$repo = 'C:\Users\you\Documents\Codex\Hermes-OmniRoute'` fazia
`BUILD-E-INSTALAR.bat` abortar para qualquer pessoa que clonasse o projeto — e
vazava o nome de usuário num repositório que vai a público.

**Correção**: o repositório passa a ser o diretório do próprio script.

### C-5 · A tela mais destrutiva do app estava 100% em inglês — **CORRIGIDO**

"Danger zone", "Uninstall everything — Remove the app, the agent, and all user
data", "This can't be undone" apareciam em inglês mesmo com a interface em
português. É a única ação irreversível do produto, e a que o usuário tinha
menos chance de entender.

**Correção**: `settings.uninstall.*` em en, pt-BR e zh; componente ligado ao
i18n.

### C-6 · Mission Control comunicava estado só por cor — **CORRIGIDO**

O ícone era escolhido pelo **tipo** e o estado entrava só como classe CSS de
cor. `Codicon` renderiza `aria-hidden="true"` sempre, então para leitor de tela
não havia indicação nenhuma de rodando/concluído/falhou: um usuário cego lia
"npm run build" e "pytest -q" sem saber qual morreu. WCAG 1.4.1 e 1.3.1.

**Correção**: texto `sr-only` por linha, `title=` nos truncamentos, exit code
rotulado (`exit 1` em vez de um `1` solto), e o nome da sessão dentro do
`aria-label` do cabeçalho — que antes o **substituía**, fazendo cinco sessões
soarem como cinco "Abrir esta sessão" idênticos.

### A-11 · Fold de home de um componente (`/root`) — **CORRIGIDO**

`_home_prefix_fold_regex` exigia dois componentes, então `/root` nunca era
normalizado: `cat key >> /root/.ssh/authorized_keys` passava enquanto o
`~/.ssh` idêntico era pego. Rodar como root não é exótico — Docker, CI e a
própria skill de supervisão de contêiner fazem isso. **A suíte do repositório
estava vermelha por causa disto.**

**Correção**: um componente basta; o tail continua obrigatório, então um HOME
degenerado (`/`, `C:\`) segue rejeitado.

### R5-02 · Vazamento de segredo em `GET /api/env` — **CORRIGIDO** (herdado do upstream)

Encontrado antes desta rodada, no caminho da varredura Python. A linha de chave
custom era montada com `is_password` False — logo `redacted_value` recebia o
valor **cru** — e só depois o dicionário era marcado como senha. A UI mascarava
e oferecia "revelar" um segredo que já tinha saído do servidor em texto puro,
exatamente para as chaves que aquele bloco existe para tratar como segredo por
não reconhecê-las. Presente em `e30388e`: **não** foi o fork que introduziu.

---

## MEDIUM

| # | achado | estado |
|---|---|---|
| B-3 | `find / -delete`, `shred /dev/sda`, `/proc/sysrq-trigger`, `systemctl isolate poweroff.target`, `loginctl poweroff` eram só "perigosos" — o yolo passava | **CORRIGIDO**: promovidos ao piso, com 8 casos de trabalho normal provados intocados |
| A-7 | `SHA256SUMS.txt` e `BUILD-PROVENANCE.json` eram gerados e **descartados** pelo upload do CI | **CORRIGIDO**: adicionados ao `path` |
| A-8 | `/goal resume` depois de gate esgotado re-pausava na hora — o botão que o commit anterior consertou, no caso vizinho | **CORRIGIDO**: `resume()` zera `gate.attempts` |
| A-9 / C-7 | PWA sob prefixo de proxy: `importScripts('/sw-policy.js')` absoluto abortava a instalação do SW; manifest com `scope: "/"` | **CORRIGIDO**: relativos |
| A-10 | Mission Control fazia poll de rede ignorando `usePaneVisible`, e goal ativo mantinha `process.list` batendo para sempre | **CORRIGIDO**: só processo de fundo vivo, e só com o painel visível |
| C-8 | Web nunca lia `navigator.language`: usuário brasileiro via inglês apesar dos catálogos completos | **CORRIGIDO**: `matchBrowserLocale()` com aliases pt→pt-br, zh-TW→zh-hant |
| C-9 | Mission Control 100% em inglês em ja, ar e zh-hant | **CORRIGIDO**: traduzido nos três |
| C-10 | Rótulo do comando e aba do pane sem i18n ("Toggle Mission Control", "mission") | **CORRIGIDO** |
| A-6 | `buildWsUrl` monta URL sem sentido quando há origem de gateway configurada (WS do APK) | **ABERTO** — latente hoje (`setGatewayOrigin` só é chamado em teste), mas no caminho de produção |
| C-11 | Telas sem i18n: billing, memory, computer-use, searchable-select, onboarding | **ABERTO** |
| C-12 | Documentação não tem passo de instalação do fork; README instala o **upstream** | **ABERTO** |
| A-15 | Portão de proveniência não confere `upstreamBaseCommit` contra o git | **ABERTO** |
| A-16 | `FAILURE_LINGER_MS = 12s` auto-dispensa a falha — contradiz a premissa de ordenação do painel | **ABERTO** |

## LOW / IMPROVEMENT

| # | achado | estado |
|---|---|---|
| A-12 | Fork bomb citado como texto (`grep 'x(){ x\|x& }'`) travava o agente sem recurso — hardline ignora yolo | **CORRIGIDO**: âncora de posição de comando |
| A-14 | `deno run ./script.ts` rotulado como "remote package execution" | **CORRIGIDO**: só URL/`npm:`/`jsr:` |
| B-4 | Denylist de download não cobre `id_rsa`, `.aws/credentials`, `*.pem` | **ABERTO** |
| B-5 / A-18 | `.gitleaks.toml`: allowlists por caminho inteiro (`vendor/`) contra a própria regra do cabeçalho | **ABERTO** |
| A-17 | Telemetria de estagnação é write-only; nenhuma superfície lê `last_progress_at` | **ABERTO** |
| A-18 | `secret-scan.yml` baixa gitleaks sem verificar checksum; actions com tag flutuante | **ABERTO** |
| C-13 | Botão Atualizar sem retorno visual | **CORRIGIDO**: estado `aria-busy` + spinner |

---

## Blocker externo confirmado pelos três

### `<<PREENCHER>>` em `SECURITY.md` e `CODE_OF_CONDUCT.md`

`BLOCKED_BY_EXTERNAL_DEPENDENCY`. Um pesquisador que encontra falha no fork lê a
tabela de roteamento e chega num marcador; o documento explicitamente o proíbe
de usar o canal do upstream. Não há endereço que eu possa inventar — é decisão
do dono do projeto. Idem para o canal de denúncia do Código de Conduta.

O mesmo vale para o remote do fork: `origin` ainda aponta para
`NousResearch/hermes-agent`, inclusive no push. Sem um destino autorizado, R2
(publicação) não tem para onde ir, e nenhuma auditoria de release tem o que
validar.

---

## O que os auditores examinaram e consideraram são

Registrado porque é tão útil quanto os achados — diz onde **não** mexer:

- **`rows.ts` do Mission Control**: projeção pura, `compareGroups` total e
  determinístico, `canStop`/`canDismiss` recusando-se a mostrar botão que
  mentiria. O problema do painel era a fonte de dados e a apresentação; a
  projeção não precisou de conserto.
- **Serialização de `GoalState`**: os sete campos novos têm default e coerção
  defensiva; linhas antigas de `state_meta` carregam limpas.
- **Precedência de guardas**: o contador por gate é avaliado antes da detecção
  de estagnação — quem chega primeiro decide, e o teste reflete o comportamento
  real.
- **Autenticação do dashboard**: `hmac.compare_digest` em todos os caminhos,
  tickets de uso único com TTL, middleware contra DNS-rebinding,
  `PUBLIC_API_PATHS` mínimo. Sem bypass encontrado.
- **Evasões de `approval.py` tentadas e frustradas**: `$IFS`, `r\m`,
  `git st""atus`, `"/"`, `${HOME}`, `$(echo /)`, `${NOPE:-/}`, path Windows,
  `sudo -S`, `bash -c reboot`, `pip install --target .`, tarball-URL, e todas as
  grafias de `hermes capabilities update`. As únicas que passaram viraram B-1 e
  B-3.
- **`sw-policy.js`**: default fecha, navegação sempre vai à rede, `index.html`
  fora do precache porque carrega token de uso único, e a decisão custosa ("o
  app não abre offline") assumida por escrito.
- **`normalizeGatewayOrigin`**: recusa esquema não-http(s), credenciais
  embutidas, path/query/fragment e cleartext para host público.
- **`web/src/i18n/pt-br.test.ts`**: o melhor teste de i18n do repositório —
  herda pt-BR de pt em vez de duplicar 634 strings e varre lusitanismos no
  catálogo **final**, pós-merge. Foi dele que saiu o desenho do teste novo do
  desktop.
- **`apps/mobile/README.md`**: tabela "Estado real, sem maquiagem" que marca
  `❌ não executado` no APK. Documentação que se recusa a mentir sobre o próprio
  estado é rara.

---

## Estado dos gates após o fix loop

```
CRITICAL = 0   (1 encontrado, 1 corrigido)
HIGH     = 0   (13 encontrados, 13 corrigidos)
MEDIUM   = 5 abertos (de 13)
LOW      = 4 abertos (de 11)
BLOCKERS_INTERNAL = 0
BLOCKERS_EXTERNAL = 2  (canal de segurança, remote do fork)
```

Nenhum achado foi fechado por opinião: cada correção tem teste que reprova
quando a correção é desfeita.

Os MEDIUM/LOW abertos estão registrados acima com arquivo e linha. Nenhum deles
é caminho de dados destrutivo, vazamento de credencial ou bypass de
autenticação — as três classes que travariam publicação.
