# Changelog

Todas as mudanças relevantes deste projeto ficam registradas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o
versionamento segue [SemVer](https://semver.org/lang/pt-BR/).

Este arquivo começa no fork. O histórico anterior ao fork é o do
[Hermes Agent](https://github.com/NousResearch/hermes-agent) upstream.

---

## [Não lançado]

_Sem mudanças ainda desde a Public Preview._

## [0.17.0-omniroute.1] - 2026-08-24

Primeira **Public Preview** (Windows) do Hermes OmniRoute Studio — um fork
derivado do [Hermes Agent](https://github.com/NousResearch/hermes-agent)
(MIT, © Nous Research). Instalador **não assinado** (NSIS + MSI); o Windows
SmartScreen exibirá um aviso esperado — veja o README para instruções e para o
SHA-256 de cada artefato.

### Destaques

- Edição desktop Windows lado a lado com roteamento **OmniRoute** nativo,
  ferramentas MCP, Product Studio, UI pt-BR, preview de projeto, guardrails e SSH.
- Modo **`LOCAL_ONLY`** fail-closed: memória e ferramentas restritas à máquina
  local e loopback (zero egress para nuvem); config ausente/ilegível falha
  **fechado**.
- Dependências de WhatsApp (OpenWA / Baileys) **não são empacotadas** no
  instalador — são obtidas em runtime na máquina do usuário. Atribuição upstream
  MIT preservada (`LICENSE`, `NOTICE-OMNIROUTE-STUDIO.md`, `THIRD_PARTY_NOTICES.md`).

### Segurança

- **`rm -rf $'/'` deixou de furar o piso hardline.** O bash reduz `$'...'` a
  caracteres literais antes de o comando rodar, então `$'/'`, `$'\x2f'` e
  `$'\057'` chegavam ao shell como `rm -rf /` e passavam — inclusive sob
  `--yolo`, que é justamente o modo em que o piso é a única defesa restante. O
  mesmo valia para `reboot` escrito em hexadecimal.
- **Alguns bytes de texto hostil travavam o guard de comandos.** `$(` aninhado é
  livre de separadores e minúsculo: 302 caracteres levavam 2,5 s, e ~3000
  levantavam `RecursionError` dentro da checagem que decide se um comando é
  seguro. Agora há teto de profundidade, e falha fechada.
- **Destruição irreversível saiu de "perigoso" e entrou no piso.**
  `find / -delete`, `shred /dev/sda`, `wipefs`, `blkdiscard`,
  `echo b > /proc/sysrq-trigger`, `systemctl isolate poweroff.target` e
  `loginctl poweroff` eram apenas "perigosos", ou seja: o `--yolo` os liberava.
  Confiar seus arquivos ao agente não é o mesmo que deixá-lo apagar o disco.
- **`npx <pacote> --no` deixou de desligar o detector de execução remota.** A
  checagem varria a linha inteira, então um `--no` que era argumento do PACOTE
  silenciava a detecção — e comando não flagrado é auto-aprovado, sem prompt. O
  mesmo com `npx -p <pacote> -c '<cmd>'`, em que o nome do pacote era engolido
  como valor de opção.
- **O bloqueio de malware deixou de ser contornável por prefixo de shell.**
  `true && npm install <pacote>` e `cd /tmp; npm install <pacote>` passavam
  inteiros por um bloqueio descrito no código como incondicional, porque o
  parser só olhava a primeira palavra do comando.
- **Escritas em `/root/...` passaram a ser vistas.** A normalização de caminho
  exigia dois componentes, então `cat key >> /root/.ssh/authorized_keys` passava
  enquanto o `~/.ssh` idêntico era pego. Rodar como root não é exótico: Docker,
  CI e a skill de supervisão de contêiner fazem isso.
- **`GET /api/env` deixou de devolver segredo em texto puro.** Toda chave `.env`
  não catalogada era montada como não-senha — o valor cru ia no campo — e só
  depois marcada como senha, então a interface mascarava e oferecia "revelar"
  algo que já tinha saído do servidor. Presente na base upstream; não introduzido
  por este fork.
- **Executores remotos de pacote passaram a ser detectados.** `npx`, `bunx`,
  `uvx`, `pnpm dlx`, `yarn dlx`, `npm exec` e `pipx run` baixam um pacote de um
  registro público e o executam em um passo. Nenhum disparava aprovação,
  enquanto `curl | sh` — a mesma operação — já era achado hardline. As formas
  garantidamente locais (`npx --no-install`, `npx --no`) continuam silenciosas.
- **`pip install --target . <pacote>` deixou de escapar da regra de
  supply-chain.** O grupo de opções do regex consumia `--target` mas não o valor
  da opção, e o pacote nunca era visto. Substituído por caminhamento de tokens.
- **A regra de fork bomb passou a casar a forma, não uma grafia.**
  `: (){ :|:& };:` (um espaço) e `bomb(){ bomb|bomb& };bomb` (qualquer outro
  nome) passavam pelo piso hardline.
- **O fallback do guardrail dz23 deixou de ser permissivo.** Quando
  `tools.approval` não importa, o plugin cai em um caminho degradado que se
  descrevia como "conservador" e não era: `r\m -rf`, `r''m -rf`, `$(rm -rf …)` e
  a forma com crase passavam. Corrigido e coberto por 14 testes que forçam o
  caminho degradado explicitamente.

### Corrigido

- **Fim de linha normalizado em toda a árvore.** `* text=auto eol=lf` virou
  regra padrão do `.gitattributes`. Sem ela, todo arquivo sem extensão ficava
  com atributo `unspecified` e acumulava CRLF em checkout Windows. Impacto real:
  `./hermes`, `docker/s6-rc.d/*/run`, `docker/cont-init.d/*` e
  `scripts/hermes-gateway` são executados por loader POSIX e estavam com CRLF —
  o shebang seria lido como `/usr/bin/env python3\r` e o container não subiria.
- **`windows-hermes-path.test.ts` deixou de depender do host.** O teste
  comparava com `path.join` (sabor do host) o que a função constrói com
  `path.win32.join`; falhava em POSIX por defeito de projeto do teste, não do
  código.
- **`omniroute-security.test.ts` deixou de falhar sem instalação local.** O
  teste de integração virou `test.skipIf` nomeado, então a ausência do
  `~/.omniroute/storage.sqlite` aparece como skip com motivo em vez de erro.
- **O português brasileiro parou de dizer "2 anexoé".** Dezesseis textos com
  plural saíam quebrados — "2 modeloé", "2 resultadoé em 2senhora", "Empregos"
  no lugar de "Tarefas", "Filial X · Comprometer-se Y" no lugar de
  "Branch X · Commit Y", e "compositor" onde se queria dizer "editor de
  mensagem". A causa era o gerador automático traduzindo cada pedaço de texto
  isolado: o "s" de plural virava "é" sozinho. A medida de cobertura não via
  nada disso porque não chegava a chamar esses textos.
- **A tela de desinstalação passou a falar português.** Era a única ação
  irreversível do produto e estava inteiramente em inglês, mesmo com a interface
  traduzida.
- **O app web passou a seguir o idioma do navegador.** Sem escolha salva, ele
  caía direto em inglês — um usuário brasileiro via inglês apesar de existirem
  catálogos pt-BR completos.
- **A instalação do preview deixou de exigir a máquina do autor.** O script
  tinha um caminho absoluto fixo e abortava para qualquer outra pessoa.
- **A PWA voltou a funcionar atrás de proxy com prefixo.** O service worker
  buscava um arquivo na raiz do host e a instalação abortava em silêncio: sem
  cache e sem página offline.
- **As somas SHA-256 passaram a ser publicadas junto dos instaladores.** Elas
  eram geradas corretamente e descartadas no envio dos artefatos, então
  "confira o hash" não tinha com o que ser conferido.

### Adicionado

- **Central de missões (Mission Control).** Um painel novo, ao lado do chat
  (⌘K → "Alternar Central de missões"), que responde "o que está rodando
  agora?" juntando processos de fundo, subagentes e objetivos de **todas** as
  sessões — inclusive as que esta janela nunca abriu. Antes essa informação
  vivia em quatro lugares e nenhum respondia a pergunta: a barra acima do
  campo de mensagem só enxerga a sessão aberta, o painel de agentes cobre a
  tela, a barra de status dá um número sem dizer de quê, e os pontinhos da
  lateral dão uma cor sem dizer por quê. Falha aparece antes de execução, porque
  falha não muda sozinha.
- **Detecção de estagnação no laço de objetivos.** O laço já pausava por falha
  de infraestrutura (juiz fora do ar, orçamento de turnos, gate sem tentativas);
  não cobria o caso em que nada quebra e nada anda. Três falhas equivalentes
  passam a exigir mudança de estratégia; cinco turnos sem progresso mensurável
  pausam pedindo outro par de olhos, em vez de queimar o orçamento inteiro.
- **A skill `autonomous-mission-loop` no catálogo nativo**, descoberta,
  pesquisável, desativável pela lista `skills.disabled` e documentada em
  `docs/autonomous-mission-loop.md`.
- `CODE_OF_CONDUCT.md`, `CHANGELOG.md` e o bloco de roteamento de segurança do
  fork em `SECURITY.md`.
- `tests/tools/test_package_fetch_guard.py` — 86 testes.
- `tests/plugins/test_dz23_guardrail_fallback.py` — 14 testes.
- `BUILD-E-INSTALAR.bat` / `build-and-install-preview.ps1` — build e instalação
  do preview sem tocar no worktree, com verificação de identidade, backup de
  perfil e conferência de paridade pós-instalação.

---

## Como escrever uma entrada aqui

Uma entrada útil diz **o que mudou para quem usa**, não o que mudou no arquivo.
"Corrige regex em approval.py" não ajuda ninguém; "`pip install --target .`
deixou de escapar da regra de supply-chain" ajuda. Quando a mudança é de
segurança, diga qual era o comportamento antes — quem lê precisa saber se estava
exposto.
