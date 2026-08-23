# Third-Party Notices — Hermes OmniRoute Studio

Hermes OmniRoute Studio é uma **evolução/fork** do Hermes Agent da Nous Research,
distribuída sob os termos abaixo. Esta é uma auditoria de licenças de boa-fé, não
aconselhamento jurídico. Itens marcados `LEGAL_REVIEW_REQUIRED` precisam de
revisão jurídica antes de qualquer distribuição que os empacote.

## Upstream

| componente | licença | relação | atribuição |
|---|---|---|---|
| **Hermes Agent** (`NousResearch/hermes-agent`) | **MIT** — Copyright (c) 2025 Nous Research | upstream deste fork | `LICENSE` preservado; copyright e notices mantidos |

Hermes OmniRoute Studio adiciona OmniRoute, Workspace U1, provedores, memória,
segurança e automação **sobre** o Hermes Agent. A licença MIT do upstream é
preservada em `LICENSE`; este projeto não remove autoria upstream.

## Componentes externos (NÃO empacotados — runtime/adapter desacoplado)

Estes NÃO são copiados para dentro da árvore do Hermes nem redistribuídos no
instalador; são detectados/instalados à parte e acessados por adapter.

| componente | licença | posição | observação |
|---|---|---|---|
| **RAPTOR** (`gadievron/raptor`) | MIT (3.0.0) | Security Research via `security_research/adapter.py` | checkout externo isolado; não bundlado. Ver `docs/RAPTOR_LICENSE_AUDIT.md` |
| **CodeQL** | GitHub CodeQL Terms | provider **opcional**, desligado por padrão | **NÃO permite uso comercial** → `BLOCKED_BY_LICENSE_CONSTRAINT` para bundling/obrigatoriedade |
| **Semgrep** | LGPL 2.1 | scanner invocado como processo externo | não linkado; detectado por preflight |
| **OpenWA** (`@open-wa/wa-automate`) | **H-DNH** (Hippocratic + Do No Harm) | WhatsApp Provider via runtime EXTERNO | `LEGAL_REVIEW_REQUIRED` — cláusula de propagação + restrições éticas. NÃO bundlar. Ver `docs/OPENWA_LICENSE_AUDIT.md` |
| Coccinelle / radare2 / GDB / rr / AFL++ / Frida | GPL/LGPL/Apache/wxWindows | opcionais do RAPTOR, invocados como binários externos | não redistribuídos |

## Decisões de distribuição

- O instalador do Hermes **não empacota** scanners de terceiros nem o CodeQL.
- RAPTOR e OpenWA permanecem **externos/desacoplados** (adapter/provider), por
  engenharia **e** por licença.
- Qualquer mudança que passe a **empacotar** OpenWA altera as obrigações do
  projeto e exige revisão jurídica (H-DNH) antes.

## Dependências (JS/Python)

As dependências diretas estão em `package.json` / `pyproject.toml` e seus
lockfiles. Um inventário SBOM completo será gerado nas releases oficiais
(`SBOM` + `SHA256SUMS`). Até lá, consulte os lockfiles para o grafo exato.

## Como reportar um problema de licença

Abra uma issue ou contate os mantenedores (ver `SECURITY.md` para canais). Este
documento é atualizado conforme dependências e componentes externos mudam.
