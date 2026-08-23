import { defineLocale } from "./define-locale";
import { pt } from "./pt";

/**
 * Português do Brasil.
 *
 * ── Por que herda de `pt` e não de `en` ─────────────────────────────────────
 *
 * O catálogo `pt` deste projeto é **português europeu**: "Guardar" e não
 * "Salvar", "A guardar…" e não "Salvando…", "ficheiro" e não "arquivo",
 * "registo" e não "registro", "ecrã" e não "tela". Para um usuário brasileiro
 * isso não é um detalhe de estilo — lê como um idioma estrangeiro parecido.
 *
 * Traduzir as 634 strings de novo do zero seria duplicar trabalho que já está
 * certo nas duas variantes na maior parte dos casos, e garantir que as duas
 * divirjam: toda correção feita em `pt` teria que ser repetida aqui à mão, e
 * não seria. Herdando de `pt`, este arquivo carrega só o que realmente muda.
 *
 * O que está aqui:
 *
 *   1. **Lusitanismos** — as formas que um brasileiro não usa. Medidas, não
 *      adivinhadas: 62 strings do catálogo `pt` casam com os padrões de pt-PT
 *      (gerúndio "A + infinitivo", "guardar", "ficheiro", "registo",
 *      "utilizador", "separador", "ligar/desligar" como conectar/desconectar).
 *   2. **As 79 chaves que faltavam em `pt`** — medidas contra `en`. Sem elas o
 *      componente cai no texto em inglês que está escrito no próprio JSX
 *      (`p.activeProfile ?? "Active profile"`), então o usuário via inglês no
 *      meio do português.
 *
 * Estas duas listas são verificadas por `pt-br.test.ts`, que falha **pelo nome
 * da chave** quando uma nova entra sem tradução.
 */
export const ptBr = defineLocale(
  {
    // ── 1. Lusitanismos: pt-PT → pt-BR ────────────────────────────────────
    common: {
      save: "Salvar",
      // "separador" é aba no Brasil.
      pluginLoadFailed:
        "Não foi possível carregar o script deste plugin. Veja a aba Network (dashboard-plugins/…) e o caminho do plugin no servidor.",
      saving: "Salvando…",
      loading: "Carregando…",
      creating: "Criando…",
      off: "Desligado",
      // Faltavam em `pt`.
      gateway: "Gateway",
      gatewayHint:
        "Plataformas de mensagens, o servidor de API e os webhooks são configurados na página Canais. Aqui ficam as configurações que valem para o gateway inteiro (modo proxy/relay e a lista de permissões global).",
    },

    app: {
      gatewayStrip: {
        off: "Desligado",
        running: "Em execução",
        starting: "Iniciando",
      },
      nav: {
        logs: "Registros",
      },
      openDocumentation: "Abrir a documentação em uma nova aba",
      // Faltavam em `pt`.
      managingProfile: "Gerenciando o perfil",
      currentProfileOption: "este painel ({name})",
      managingProfileBanner:
        "Gerenciando o perfil “{name}” — configuração, chaves, skills, MCPs, modelo e conversas novas se aplicam a esse perfil.",
      memoryOomRestartBanner:
        "Seu agente reiniciou sozinho, provavelmente por falta de memória. Sessões longas e muitas tarefas ao mesmo tempo aumentam o consumo.",
      memoryCriticalBanner:
        "Seu agente está quase sem memória e pode reiniciar. Feche sessões ociosas ou aumente a memória da máquina.",
      memoryElevatedBanner: "Seu agente está com pouca memória.",
      diskCriticalBanner:
        "O disco do seu agente está quase cheio. Mensagens, memórias e configurações novas podem falhar ao salvar.",
      diskElevatedBanner:
        "O disco do seu agente está enchendo. Limpe sessões antigas ou aumente o armazenamento.",
      dismiss: "Dispensar",
    },

    status: {
      disconnected: "Desconectado",
      notRunning: "Não está em execução",
      platformDisconnected: "desconectado",
      restartingGateway: "Reiniciando o gateway…",
      running: "Em execução",
      runningRemote: "Em execução (remoto)",
      starting: "Iniciando",
      startedInBackground: "Iniciado em segundo plano — acompanhe pelos registros",
      updatingHermes: "Atualizando o Hermes…",
      // Faltavam em `pt`.
      disabled: "Desativado",
      restartGatewayConfirmTitle: "Reiniciar o gateway?",
      restartGatewayConfirmMessage:
        "Isto reinicia o processo do gateway do Hermes. Os canais conectados e as sessões ativas se reconectam depois.",
      updateHermesConfirmTitle: "Atualizar o Hermes?",
      updateHermesConfirmMessage:
        "Isto executa o hermes update e reinicia o gateway ao terminar. As sessões ativas mantêm o cache de prompt até lá.",
      updateHermesConfirmNow: "Atualizar agora",
    },

    sessions: {
      selectSession: "Selecionar sessão",
      roles: {
        user: "Usuário",
      },
      selectAllOnPage: "Selecionar todas nesta página",
      selectedCount: "{count} selecionadas",
      deleteSelectedConfirmMessage:
        "Isto remove permanentemente {count} sessões selecionadas e todas as suas mensagens. Não dá para desfazer.",
      failedToDeleteSelected: "Falha ao excluir as sessões selecionadas",
    },

    logs: {
      title: "Registros",
      file: "Arquivo",
      noLogLines: "Nenhuma linha de registro encontrada",
    },

    cron: {
      delivery: {
        // Faltavam em `pt`.
        needsHomeChannel: "defina um canal padrão primeiro",
        noneConfigured:
          "Nenhuma plataforma de mensagens configurada. Configure uma em Canais para receber os relatórios.",
      },
    },

    profiles: {
      saveSoul: "Salvar SOUL",
      soulSaved: "SOUL.md salvo",
      // Faltavam em `pt`.
      activeProfile: "Perfil ativo",
      activeBadge: "ativo",
      setActive: "Tornar ativo",
      activeSet: "Perfil ativo definido",
      gatewayRunning: "Gateway em execução",
      gatewayStopped: "Gateway parado",
      gatewayRunningWarning: "O gateway deste perfil está em execução — ele será parado.",
      aliasBadge: "apelido",
      description: "Descrição",
      descriptionPlaceholder:
        "No que este perfil é bom? Serve para rotear tarefas do kanban por papel.",
      noDescription: "Sem descrição",
      editDescription: "Editar descrição",
      descriptionSaved: "Descrição salva",
      reviewBadge: "revisão",
      autoGenerate: "Gerar automaticamente",
      generating: "Gerando…",
      describeFailed: "Não foi possível gerar a descrição",
      distribution: "Distribuição",
      advancedOptions: "Opções avançadas",
      cloneAll: "Clonar tudo (memórias, sessões, skills, estado)",
      noSkillsOption: "Não instalar as skills empacotadas",
      descriptionOptional: "Descrição (opcional)",
      modelOptional: "Modelo (opcional)",
      modelInherit: "Herdar do clone / padrão",
      modelLoading: "Carregando modelos…",
      modelNone: "Nenhum provedor autenticado — defina uma chave primeiro",
      editModel: "Trocar de modelo",
      modelSaved: "Modelo atualizado",
      modelSelect: "Selecione um modelo",
      actions: "Ações",
    },

    skills: {
      // Faltavam em `pt`.
      profileSelector: "Perfil",
      currentProfile: "atual ({name})",
      managingProfile:
        "Gerenciando o perfil “{name}” — as alterações se aplicam a esse perfil, não ao deste painel.",
    },

    theme: {
      // Faltavam em `pt`.
      fontTitle: "Fonte",
      fontDefault: "Padrão do tema",
      fontDefaultHint: "Usar a fonte do tema ativo",
      fontSans: "Sem serifa",
      fontSerif: "Com serifa",
      fontMono: "Monoespaçada",
    },

    pluginsPage: {
      rescanHeading: "Registro de plugins SPA",
      noDashboardTab: "Sem aba no dashboard",
      removeHint:
        "Só dá para remover plugins que o usuário instalou em ~/.hermes/plugins.",
      rescanHint:
        "Reanalise depois de adicionar arquivos em disco para que a barra lateral encontre os novos manifestos.",
      saveProviders: "Salvar configurações do provedor",
      savedProviders: "Configurações do provedor salvas.",
    },

    config: {
      confirmResetScope:
        "Restaurar todas as configurações de {scope} para os valores padrão? Isto só atualiza o formulário — as alterações só vão para o config.yaml quando você clicar em Salvar.",
      configSaved: "Configuração salva",
      yamlConfigSaved: "Configuração YAML salva",
      failedToSave: "Falha ao salvar",
      failedToSaveYaml: "Falha ao salvar o YAML",
      invalidJson: "Arquivo JSON inválido",
      categories: {
        logging: "Registro",
        browser: "Navegador",
      },
    },

    env: {
      changesNote:
        "As alterações são salvas em disco na hora. As sessões ativas detectam chaves novas automaticamente.",
      confirmClearMessage:
        "O valor salvo para esta variável será removido do seu arquivo .env. Não dá para desfazer pela interface.",
      enterValue: "Digite o valor…",
    },

    oauth: {
      disconnect: "Desconectar",
      login: "Fazer login",
      description:
        "{connected} de {total} provedores OAuth conectados. Use Fazer login nos fluxos que o painel suporta; os comandos de CLI continuam disponíveis para configuração externa ou de emergência.",
      notConnected:
        "Não conectado. Use Fazer login quando estiver disponível, ou rode {command} num terminal.",
      enterCodePrompt: "Abrimos uma aba nova. Digite este código se ele for pedido:",
      pkceStep1: "Abrimos uma aba nova para o claude.ai. Faça login e clique em Authorize.",
      copyFailed: "Não foi possível copiar automaticamente. Selecione o código e copie à mão.",
      initiatingLogin: "Iniciando o fluxo de login…",
      connectedClosing: "Conectado! Fechando…",
    },

    achievements: {
      guide: {
        secret_body:
          "As secretas escondem o gatilho exato. Assim que o Hermes detectar um sinal relacionado, o cartão passa para Descoberta e mostra o requisito.",
      },
      scan: {
        building_headline: "Montando o perfil de conquistas…",
        starting_headline: "Iniciando a análise de conquistas…",
      },
      empty: {
        no_secrets_body:
          "Dica: as secretas costumam começar em padrões pouco comuns de falha ou de usuário avançado — conflito de porta, barreira de permissão, variável de ambiente faltando, erro de YAML, colisão de Docker, uso de rollback/checkpoint, acerto de cache, ou uma correção pequena depois de muito texto vermelho.",
      },
      share: {
        hint: "Compartilhar no X abre uma publicação preenchida em uma aba nova. Clique em Copiar imagem antes se quiser anexar o selo 1200×630 — o X aceita colar direto no compositor. Baixar PNG salva o arquivo para usar em qualquer lugar.",
      },
    },

    kanban: {
      loading: "Carregando o quadro Kanban…",
      renderingError: "A aba Kanban encontrou um erro de renderização",
      confirmDoneMany:
        "Marcar {n} tarefas como concluídas? As reservas dos workers são liberadas e as filhas dependentes ficam prontas.",
      confirmArchiveMany: "Arquivar {n} tarefas? Elas somem da visão padrão do quadro.",
      confirmBlockedMany: "Marcar {n} tarefas como bloqueadas? As reservas dos workers são liberadas.",
      completionSummary: "Resumo de conclusão de {label}. Vai ser salvo como o resultado da tarefa.",
      logTruncated: "(mostrando os últimos 100 KB — registro completo em ",
      loadFailedHint:
        "O backend cria o kanban.db sozinho na primeira leitura. Se continuar falhando, veja os registros do painel.",
      creating: "Criando…",
      selected: "selecionado(s)",
      loadingDetail: "Carregando…",
      workerLog: "Registro do worker",
      loadingLog: "Carregando registro…",
      noWorkerLog:
        "— ainda não há registro do worker (a tarefa não começou ou o registro foi rotacionado) —",
      save: "Salvar",
      sendingUpdates: "Enviando atualizações para",
      selectForBulk: "Selecionar para ações em lote",
      // Faltavam em `pt`.
      needsAssignee: "Falta responsável",
      needsAssigneeHint:
        "As dependências estão satisfeitas, mas o dispatcher pula esta tarefa até você atribuir um perfil.",
      confirmScheduled:
        "Mover esta tarefa para Agendada? Use para espera de tempo conhecida, não para bloqueio por pessoa.",
      newTaskTitle: "Nova tarefa — {column}",
      taskTitleLabel: "Título",
      assigneeLabel: "Responsável",
      assigneeLabelHint: "(em branco = o dispatcher escolhe)",
      skillsLabel: "Skills",
      skillsLabelHint: "(opcional, separadas por vírgula)",
      parentLabel: "Tarefa pai",
      parentLabelHint: "(a filha fica bloqueada até a pai terminar)",
      create: "Criar",
      boardSettings: "Configurações",
      boardSettingsTitle:
        "Configurações do quadro — nome, descrição e o diretório de projeto padrão que as tarefas novas herdam",
      boardSettingsTitleFor: "Configurações do quadro — {name}",
      projectDirectoryOverrideHint:
        "As tarefas novas herdam isto como espaço de trabalho padrão; cada tarefa ainda pode trocar na hora de criar.",
      saving: "Salvando…",
      commentHint:
        "Os comentários chegam ao worker na próxima execução dele ou no kanban_show() — não precisa bloquear a tarefa antes.",
      commentHintTitle:
        "Comentário é o canal para falar com o worker de uma tarefa. Ele aparece na thread na hora — não precisa bloquear a tarefa antes. Um worker em execução pega a thread no próximo kanban_show() ou ao ser recriado; bloquear serve só para quando você quer que ele PARE e espere você.",
      trash: {
        confirmTitle: "Excluir a tarefa?",
        confirmManyTitle: "Excluir {n} tarefas?",
      },
    },

  },
  pt
);
