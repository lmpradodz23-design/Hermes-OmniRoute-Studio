# Inventário de licenças das skills empacotadas

> **Este arquivo é um retrato; o portão é o teste.**
> `tests/skills/test_skill_provenance.py` falha se alguma skill não declarar
> proveniência, se uma fonte não nomear licença, se um `localPaths` apontar
> para o vazio, ou se o texto da licença não estiver no disco. Regenerar esta
> tabela à mão sem rodar o teste não prova nada.

**Gerado em** 2026-08-22 · **HEAD** `ae2008d` · **base do fork** `e30388e`

---

## 1. Resumo

| | Quantidade |
|---|---:|
| Skills empacotadas (diretórios com `SKILL.md`) | **227** |
| Herdadas do upstream Hermes Agent, cobertas pela `LICENSE` MIT da raiz | 199 |
| Escritas neste repositório | 1 |
| Vendorizadas de terceiros, com fonte declarada | 27 |

Nenhuma skill sem proveniência declarada. Verificado por teste, não por leitura.

## 2. Terceiros

| Skill (caminho aqui) | Origem | Commit | Licença | Texto da licença no disco |
|---|---|---|---|---|
| `skills/creative/design-toolkit/frontend-design` | [anthropics/skills](https://github.com/anthropics/skills) | `3b3fad96af16` | See frontend-design/LICENSE.txt | `skills/creative/design-toolkit/frontend-design/LICENSE.txt` |
| `skills/creative/design-toolkit/impeccable` | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | `56f44523f76e` | Apache-2.0 | `skills/creative/design-toolkit/LICENSE.impeccable` |
| `skills/creative/design-toolkit/ui-designer` | [daymade/claude-code-skills](https://github.com/daymade/claude-code-skills) | `d0e673cf1310` | MIT | `skills/creative/design-toolkit/LICENSE.daymade` |
| `skills/creative/design-toolkit/ui-ux-pro-max`<br>`skills/creative/design-toolkit/design`<br>`skills/creative/design-toolkit/banner-design` | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | `bc826e2267a3` | MIT | `skills/creative/design-toolkit/LICENSE.nextlevelbuilder` |
| `skills/creative/gsap/gsap-core`<br>`skills/creative/gsap/gsap-timeline`<br>`skills/creative/gsap/gsap-scrolltrigger`<br>`skills/creative/gsap/gsap-plugins`<br>`skills/creative/gsap/gsap-utils`<br>`skills/creative/gsap/gsap-react`<br>`skills/creative/gsap/gsap-performance`<br>`skills/creative/gsap/gsap-frameworks` | [greensock/gsap-skills](https://github.com/greensock/gsap-skills) | `aed9cfd32777` | MIT | `skills/creative/gsap/LICENSE` |
| `skills/creative/img2threejs` | [img2threejs/img2threejs](https://github.com/img2threejs/img2threejs) | `d6673386f896` | Apache-2.0 | `skills/creative/img2threejs/LICENSE` |
| `skills/creative/motion-design` | [LottieFiles/motion-design-skill](https://github.com/LottieFiles/motion-design-skill) | `f9a8a041b851` | MIT | `skills/creative/motion-design/LICENSE` |
| `skills/software-development/superpowers/brainstorming`<br>`skills/software-development/superpowers/dispatching-parallel-agents`<br>`skills/software-development/superpowers/executing-plans`<br>`skills/software-development/superpowers/finishing-a-development-branch`<br>`skills/software-development/superpowers/receiving-code-review`<br>`skills/software-development/superpowers/subagent-driven-development`<br>`skills/software-development/superpowers/using-git-worktrees`<br>`skills/software-development/superpowers/using-superpowers`<br>`skills/software-development/superpowers/verification-before-completion`<br>`skills/software-development/superpowers/writing-plans`<br>`skills/software-development/superpowers/writing-skills` | [obra/superpowers](https://github.com/obra/superpowers) | `b36e0829c6d0` | MIT | `skills/software-development/superpowers/LICENSE` |

Todas as licenças acima são permissivas (MIT ou Apache-2.0) e permitem
redistribuição, inclusive comercial, desde que o aviso de copyright acompanhe
a cópia — que é exatamente o que a última coluna verifica.

## 3. Modificações sobre o material de terceiro

Toda licença permissiva pede que a modificação seja identificável:

**ui-ux-pro-max-suite** · https://github.com/nextlevelbuilder/ui-ux-pro-max-skill

- ui-ux-pro-max/SKILL.md: replaced Claude-only paths and documented Hermes path resolution
- design/SKILL.md: replaced Claude-only paths and documented Hermes tool mapping
- banner-design/SKILL.md: documented safe Hermes tool mapping for Claude-only examples

**ui-designer** · https://github.com/daymade/claude-code-skills

- ui-designer/SKILL.md: documented Hermes delegation fallback

## 4. Primeira parte

- `skills/software-development/product-studio` — autor DZ23 / Hermes Agent, MIT

## 5. O risco que foi conferido e não se materializou

GSAP era o risco jurídico mais provável de um bundle de skills criativas: por
anos os plugins do GSAP foram pagos para uso comercial. Depois da aquisição
pela Webflow o repositório declara MIT e documenta que **todos** os plugins são
livres, inclusive comercialmente, sem chave e sem membership. Conferido no
`skills/creative/gsap/LICENSE` que veio junto.

## 6. Como declarar uma skill nova

```jsonc
// skills/<categoria>/SOURCES.json
{
  "version": 1,
  "sources": [{
    "id": "nome-curto",
    "repository": "https://github.com/dono/repo",
    "commit": "sha completo de onde saiu",
    "license": "MIT",
    "paths":      ["caminho/no/repositorio/DE/ORIGEM"],
    "localPaths": ["skills/categoria/onde-caiu-aqui"],
    "modifiedFiles": ["arquivo: o que mudou e por quê"]
  }]
}
```

`paths` rastreia de onde saiu; `localPaths` diz onde caiu **aqui**. Os dois são
necessários e não são a mesma coisa — foi por confundir os dois que
`img2threejs`, declarado com `paths: ["."]`, parecia não ter proveniência.

E traga o arquivo de licença junto: citar `"MIT"` num JSON não cumpre a MIT,
que exige que o aviso acompanhe a cópia redistribuída. O teste verifica isso.

## 7. Ao mergear do upstream

Skills novas que vierem do Hermes Agent entram em `upstreamInherited` de
`skills/PROVENANCE.json` **no mesmo commit do merge**. O teste aponta quais,
pelo nome do diretório. Isso é atrito de propósito: puxar 30 skills novas sem
olhar é como o bundle vira uma pergunta jurídica sem resposta.
