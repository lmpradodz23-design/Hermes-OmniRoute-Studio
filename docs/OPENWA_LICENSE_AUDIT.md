# OpenWA — Auditoria de Licença

Alvo: `@open-wa/wa-automate` (github.com/open-wa/wa-automate-nodejs).
Pergunta: o Hermes OmniRoute Studio, que é distribuído, pode **empacotar** o
OpenWA no seu instalador? Resposta curta: **não com segurança** — a licença
força runtime externo.

## Constatação central

O `@open-wa/wa-automate` é licenciado sob **Hippocratic + Do No Harm (H-DNH)**,
não MIT/Apache:

| versão | npm dist-tag | licença (verificada) |
|---|---|---|
| 4.76.0 | `latest` (estável) | `H-DNH V1.0` (`npm view @open-wa/wa-automate@4.76.0 license`) |
| 5.0.0-alpha.8 | `alpha` | pacotes-chave `H-DNH V1.0` (wa-automate-types-only, plugin-sdk, socket-client) |

O `package.json` da **raiz do monorepo** declara `Apache-2.0`, mas isso é o
metadado da ferramenta de monorepo — **não** a licença da biblioteca publicada.
O arquivo `LICENSE.md` do repositório é H-DNH v1.1, copyright Mohammed Shah. A
discrepância está registrada como achado; a licença que vale para a biblioteca
distribuída é **H-DNH**.

## Fatos vs. questão jurídica (correção metodológica)

Separo o que é verificável do que exige parecer jurídico. Não sou advogado; o
que segue não é conclusão jurídica.

**FACT** — `@open-wa/wa-automate@4.76.0` (npm `latest`) reporta `license = H-DNH V1.0`;
v5-alpha reporta H-DNH nos pacotes-chave. Verificado via `npm view`.

**LICENSE_TEXT** — o `LICENSE.md` do repositório é H-DNH v1.1. Condição 1
(textual): "All redistribution of source code or binary form, including any
modifications must be under these terms... You must inform recipients." Condição
3 (textual): proíbe uso por organizações que derivam receita majoritária de uma
lista de atividades (tráfico, jogo, tabaco, armas, etc.).

**PACKAGE_METADATA** — o `package.json` da raiz do monorepo declara
`Apache-2.0`, conflitando com o `LICENSE.md`. Discrepância real, não resolvida
pelo upstream.

**LEGAL_QUESTION** (`LEGAL_REVIEW_REQUIRED`) — se, e em que forma concreta de
distribuição, a condição 1 faria a H-DNH se propagar sobre o restante de uma
distribuição que apenas *acompanha* o OpenWA. Isto depende de: (a) qual metadado
governa a biblioteca publicada (H-DNH vs Apache-2.0), (b) o que conta como
"redistribution" na forma de empacotamento escolhida, (c) jurisdição e uso
comercial pretendido. **Não determinável tecnicamente. Requer parecer jurídico.**

```
LICENSE_RISK=CONFIRMED
WHOLE_DISTRIBUTION_LICENSE_PROPAGATION=REQUIRES_LEGAL_REVIEW
```

**ARCHITECTURAL_DECISION** — independente da resposta jurídica, a decisão
conservadora é a mesma e não exige resolver a questão legal: **runtime externo,
sem bundling no instalador nesta fase.** Isso minimiza a superfície de licença
seja qual for o parecer, e coincide com a melhor arquitetura de engenharia
(isolamento de crash, atualização independente, troca de provider). Ou seja: a
escolha de arquitetura é robusta a qualquer que seja a conclusão jurídica — é
por isso que ela pode ser tomada agora, sem esperar o parecer.

## Não é a API oficial da Meta

O OpenWA automatiza o **WhatsApp Web**. Não é a API oficial WhatsApp/Meta e não
tem vínculo com a Meta. A integração se identifica como
**"WhatsApp Web / OpenWA Provider"**, nunca como "WhatsApp Official API". O uso
está sujeito aos Termos do WhatsApp — risco que é do operador, e a UI deixa isso
explícito.

## Blockers de licença

```
BLOCKER-ID=OPENWA-LIC-1
TYPE=LEGAL_REVIEW_REQUIRED
COMPONENT=@open-wa/wa-automate (H-DNH)
REASON=condição de propagação + restrições de uso; o EFEITO sobre uma
       distribuição que acompanha o OpenWA é questão jurídica, não técnica
WHAT_WAS_VERIFIED=npm view license = H-DNH V1.0 (v4 e v5); LICENSE.md = H-DNH v1.1;
       package.json do monorepo = Apache-2.0 (discrepância)
MITIGATION_ADOTADA=runtime externo, sem bundling — robusta a qualquer parecer
UNBLOCK=parecer jurídico do dono do projeto antes de considerar bundling

```
BLOCKER-ID=OPENWA-LIC-2
TYPE=BLOCKED_BY_EXTERNAL_DEPENDENCY
COMPONENT=discrepância de licença no upstream (LICENSE.md H-DNH vs package.json Apache-2.0)
REASON=metadado do monorepo conflita com o arquivo de licença
UNBLOCK=confirmar com o upstream qual governa a biblioteca publicada (assumido H-DNH, conservador)
```
