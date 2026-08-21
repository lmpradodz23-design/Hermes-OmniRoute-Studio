// Generated from app/settings/constants.ts by scripts/generate-pt-br-locale.mjs.

import { defineFieldCopy } from '@/app/settings/field-copy'

export const PT_BR_FIELD_LABELS: Record<string, string> = defineFieldCopy({
  model: 'Modelo padr\u00E3o',
  modelContextLength: 'Janela de contexto',
  fallbackProviders: 'Modelos substitutos',
  toolsets: 'Conjuntos de ferramentas habilitados',
  timezone: 'Fuso hor\u00E1rio',
  display: {
    personality: 'Personalidade',
    showReasoning: 'Blocos de racioc\u00EDnio'
  },
  desktop: {
    repoScanEnabled: 'Descoberta autom\u00E1tica de reposit\u00F3rio',
    repoScanRoots: 'Ra\u00EDzes de descoberta de reposit\u00F3rio',
    repoScanExcludePaths: 'Caminhos de reposit\u00F3rio exclu\u00EDdos'
  },
  agent: {
    maxTurns: 'M\u00E1ximo de etapas do agente',
    imageInputMode: 'Anexos de imagem',
    apiMaxRetries: 'API Novas tentativas',
    serviceTier: 'N\u00EDvel de servi\u00E7o',
    toolUseEnforcement: 'Aplica\u00E7\u00E3o do uso de ferramentas'
  },
  terminal: {
    cwd: 'Diret\u00F3rio de trabalho',
    backend: 'Back-end de execu\u00E7\u00E3o',
    timeout: 'Tempo limite do comando',
    persistentShell: 'Shell persistente',
    envPassthrough: 'Passagem Ambiental',
    dockerImage: 'Imagem Docker',
    singularityImage: 'Imagem de Singularidade',
    modalImage: 'Imagem Modal',
    daytonaImage: 'Imagem de Daytona'
  },
  fileReadMaxChars: 'Limite de leitura de arquivo',
  toolOutput: {
    maxBytes: 'Limite de sa\u00EDda terminal',
    maxLines: 'Limite de p\u00E1ginas de arquivo',
    maxLineLength: 'Limite de comprimento de linha'
  },
  codeExecution: {
    mode: 'Modo de execu\u00E7\u00E3o de c\u00F3digo'
  },
  approvals: {
    mode: 'Modo de aprova\u00E7\u00E3o',
    timeout: 'Tempo limite de aprova\u00E7\u00E3o',
    mcpReloadConfirm: 'Confirmar MCP Recarregamentos'
  },
  commandAllowlist: 'Lista de permiss\u00F5es de comandos',
  security: {
    redactSecrets: 'Redigir segredos',
    allowPrivateUrls: 'Permitir URLs privados'
  },
  browser: {
    allowPrivateUrls: 'URLs privados do navegador',
    autoLocalForPrivateUrls: 'Navegador local para URLs privados'
  },
  checkpoints: {
    enabled: 'Pontos de verifica\u00E7\u00E3o de arquivo',
    maxSnapshots: 'Limite de pontos de verifica\u00E7\u00E3o'
  },
  voice: {
    recordKey: 'Atalho de voz',
    maxRecordingSeconds: 'Dura\u00E7\u00E3o m\u00E1xima de grava\u00E7\u00E3o',
    autoTts: 'Leia as respostas em voz alta'
  },
  stt: {
    enabled: 'Fala para texto',
    echoTranscripts: 'Transcri\u00E7\u00F5es de eco',
    provider: 'Provedor de fala para texto',
    local: {
      model: 'Modelo de transcri\u00E7\u00E3o local',
      language: 'Idioma de transcri\u00E7\u00E3o'
    },
    openai: {
      model: 'Modelo OpenAI STT'
    },
    groq: {
      model: 'Modelo Groq STT'
    },
    mistral: {
      model: 'Modelo Mistral STT'
    },
    elevenlabs: {
      modelId: 'Modelo ElevenLabs STT',
      languageCode: 'Idioma OnzeLabs',
      tagAudioEvents: 'Marcar eventos de \u00E1udio',
      diarize: 'Diariza\u00E7\u00E3o de alto-falante'
    }
  },
  tts: {
    provider: 'Provedor de texto para fala',
    edge: {
      voice: 'Voz de borda'
    },
    openai: {
      model: 'Modelo OpenAI TTS',
      voice: 'Voz OpenAI'
    },
    elevenlabs: {
      voiceId: 'Voz OnzeLabs',
      modelId: 'Modelo OnzeLabs'
    },
    xai: {
      voiceId: 'Voz xAI (Grok)',
      language: 'Linguagem xAI',
      speed: 'Velocidade de reprodu\u00E7\u00E3o xAI',
      autoSpeechTags: 'A descri\u00E7\u00E3o de xAI Auto Speech',
      optimizeStreamingLatency: 'Otimiza\u00E7\u00E3o de lat\u00EAncia de streaming xAI',
      sampleRate: 'Taxa de amostragem xAI',
      bitRate: 'Taxa de bits xAI'
    },
    minimax: {
      model: 'Modelo MiniMax TTS',
      voiceId: 'Voz MiniMax'
    },
    mistral: {
      model: 'Modelo Mistral TTS',
      voiceId: 'Voz Mistral'
    },
    gemini: {
      model: 'Modelo G\u00EAmeos TTS',
      voice: 'Voz de G\u00EAmeos'
    },
    neutts: {
      model: 'Modelo NeuTTS',
      device: 'Dispositivo NeuTTS'
    },
    kittentts: {
      model: 'Modelo gatinhoTTS',
      voice: 'Voz gatinhoTTS'
    },
    piper: {
      voice: 'Voz de gaiteiro'
    },
    deepinfra: {
      model: 'Modelo DeepInfra TTS',
      voice: 'Voz DeepInfra'
    }
  },
  memory: {
    memoryEnabled: 'Mem\u00F3ria Persistente',
    userProfileEnabled: 'Perfil de usu\u00E1rio',
    memoryCharLimit: 'Or\u00E7amento de mem\u00F3ria',
    userCharLimit: 'Or\u00E7amento do perfil',
    provider: 'Provedor de mem\u00F3ria'
  },
  context: {
    engine: 'Mecanismo de Contexto'
  },
  compression: {
    enabled: 'Autocompress\u00E3o',
    threshold: 'Limite de compress\u00E3o',
    targetRatio: 'Alvo de compress\u00E3o',
    protectLastN: 'Mensagens recentes protegidas'
  },
  delegation: {
    model: 'Modelo Subagente',
    provider: 'Provedor Subagente',
    maxIterations: 'Limite de Turno do Subagente',
    maxConcurrentChildren: 'Subagentes Paralelos',
    childTimeoutSeconds: 'Tempo limite do subagente',
    reasoningEffort: 'Esfor\u00E7o de racioc\u00EDnio do subagente'
  },
  updates: {
    nonInteractiveLocalChanges: 'Mudan\u00E7as locais de atualiza\u00E7\u00E3o no aplicativo'
  }
})

export const PT_BR_FIELD_DESCRIPTIONS: Record<string, string> = defineFieldCopy({
  model: 'Usado para novos chats, a menos que voc\u00EA escolha um modelo diferente no compositor.',
  modelContextLength: 'Deixe em 0 para usar a janela de contexto detectada do modelo selecionado.',
  fallbackProviders: 'Provedor de backup: entradas de modelo para tentar se o modelo padr\u00E3o falhar.',
  display: {
    personality: 'Estilo de assistente padr\u00E3o para novas sess\u00F5es.',
    showReasoning: 'Mostre se\u00E7\u00F5es de racioc\u00EDnio quando o back-end as fornecer.'
  },
  desktop: {
    repoScanEnabled: 'Verifique as pastas locais em busca de reposit\u00F3rios Git para serem exibidos em Projetos.',
    repoScanRoots: 'Pastas para digitalizar. Deixe em branco para verificar seu diret\u00F3rio inicial.',
    repoScanExcludePaths: 'Pastas e seus descendentes a serem ignorados durante a descoberta do reposit\u00F3rio.'
  },
  timezone: 'IANA identificador de fuso hor\u00E1rio. Em branco usa o fuso hor\u00E1rio do sistema.',
  agent: {
    imageInputMode: 'Controla como os anexos de imagem s\u00E3o enviados ao modelo.',
    maxTurns: 'Limite superior para curvas de chamada de ferramenta antes que Hermes interrompa a corrida.'
  },
  terminal: {
    cwd: 'Pasta de projeto padr\u00E3o para trabalho de ferramenta e terminal.',
    persistentShell: 'Mantenha o estado do shell entre os comandos quando o back-end oferecer suporte.',
    envPassthrough: 'Vari\u00E1veis de ambiente a serem passadas para a execu\u00E7\u00E3o da ferramenta.',
    dockerImage: 'Imagem de cont\u00EAiner usada quando o back-end de execu\u00E7\u00E3o \u00E9 Docker.',
    singularityImage: 'Imagem usada quando o backend de execu\u00E7\u00E3o \u00E9 Singularity.',
    modalImage: 'Imagem usada quando o backend de execu\u00E7\u00E3o \u00E9 Modal.',
    daytonaImage: 'Imagem usada quando o backend de execu\u00E7\u00E3o \u00E9 Daytona.'
  },
  codeExecution: {
    mode: 'Qu\u00E3o estritamente a execu\u00E7\u00E3o do c\u00F3digo tem como escopo o projeto atual.'
  },
  fileReadMaxChars: 'M\u00E1ximo de caracteres que o Hermes pode ler de uma solicita\u00E7\u00E3o de arquivo.',
  approvals: {
    mode: 'Como o Hermes lida com comandos que precisam de aprova\u00E7\u00E3o expl\u00EDcita.',
    timeout: 'Quanto tempo os prompts de aprova\u00E7\u00E3o aguardam antes de expirarem.'
  },
  security: {
    redactSecrets: 'Oculte os segredos detectados do conte\u00FAdo vis\u00EDvel do modelo quando poss\u00EDvel.'
  },
  checkpoints: {
    enabled: 'Crie instant\u00E2neos de revers\u00E3o antes das edi\u00E7\u00F5es do arquivo.'
  },
  memory: {
    memoryEnabled: 'Guarde mem\u00F3rias dur\u00E1veis que podem ajudar sess\u00F5es futuras.',
    userProfileEnabled: 'Mantenha um perfil compacto das prefer\u00EAncias do usu\u00E1rio.'
  },
  context: {
    engine: 'Estrat\u00E9gia para gerenciar longas conversas pr\u00F3ximas ao limite do contexto.'
  },
  compression: {
    enabled: 'Resuma o contexto mais antigo quando as conversas ficarem grandes.'
  },
  voice: {
    autoTts: 'Fale automaticamente as respostas do assistente.'
  },
  tts: {
    xai: {
      voiceId: 'ID de voz xAI (por exemplo, v\u00E9spera) ou um ID de voz personalizado.',
      language:
        'C\u00F3digo do idioma falado (por exemplo, en, pt-BR) ou "auto" para detec\u00E7\u00E3o autom\u00E1tica.',
      speed: 'Velocidade de reprodu\u00E7\u00E3o. 0,7 = mais lento, 1,0 = normal, 1,5 = mais r\u00E1pido.',
      autoSpeechTags:
        'Deixe um LLM inserir tags de \u00E1udio expressivas ([risos], [suspiros]) no script antes da s\u00EDntese.',
      optimizeStreamingLatency: 'Lat\u00EAncia versus qualidade. 0 = melhor qualidade, 2 = menor lat\u00EAncia.',
      sampleRate: 'Taxa de amostragem de \u00E1udio em Hz. Maior = melhor qualidade, arquivos maiores.',
      bitRate: 'MP3 taxa de bits em bps. Aplica-se apenas quando o codec \u00E9 mp3.'
    },
    neutts: {
      device: 'Dispositivo de infer\u00EAncia local para NeuTTS.'
    }
  },
  stt: {
    enabled: 'Habilite a transcri\u00E7\u00E3o de fala local ou apoiada pelo provedor.',
    echoTranscripts: 'Poste a transcri\u00E7\u00E3o \uD83C\uDF99\uFE0F bruta das mensagens de voz de volta no chat.',
    elevenlabs: {
      languageCode:
        'C\u00F3digo de idioma opcional ISO-639-3. Em branco permite a detec\u00E7\u00E3o autom\u00E1tica do ElevenLabs.'
    }
  },
  updates: {
    nonInteractiveLocalChanges:
      'Quando o Hermes se atualizar a partir do aplicativo (sem prompt do terminal), mantenha as edi\u00E7\u00F5es da fonte local (esconderijo) ou jogue-as fora (descarte). As atualiza\u00E7\u00F5es do terminal sempre perguntam.'
  }
})
