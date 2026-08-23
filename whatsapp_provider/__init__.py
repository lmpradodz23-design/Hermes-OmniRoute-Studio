"""WhatsApp Provider — runtime de WhatsApp Web desacoplado para o Hermes.

Integra o OpenWA (`@open-wa/wa-automate`) como um WhatsApp Provider, SEM acoplar
o core do Hermes ao OpenWA. O OpenWA roda como PROCESSO EXTERNO (Easy API em
127.0.0.1), e o Hermes fala com ele por um contrato estável — nunca por dentro.

Duas decisões duras, ambas baseadas na auditoria do upstream (Wave 0):

  1. Licença H-DNH (Hippocratic + Do No Harm) do @open-wa/wa-automate tem
     cláusula de propagação (todo redistribuído fica sob os mesmos termos) e
     restrições éticas de uso. Empacotar o OpenWA no instalador do Hermes
     forçaria esses termos sobre toda a distribuição → runtime EXTERNO
     instalável, `BLOCKED_BY_LICENSE_CONSTRAINT` para bundling. Ver
     docs/OPENWA_LICENSE_AUDIT.md.

  2. OpenWA NÃO é a API oficial da Meta. É automação do WhatsApp Web. A
     identidade correta é "WhatsApp Web / OpenWA Provider" — nunca
     "WhatsApp Official API".

Toda mensagem recebida é ENTRADA NÃO CONFIÁVEL: nunca vira instrução nem
concede capability automaticamente. Este pacote é puro Python, sem OpenWA em
import time.
"""

from .session import SessionState, SessionStateMachine, InvalidSessionTransition
from .events import NormalizedEvent, EventType, normalize_openwa_event, EventDeduper
from .sending import OutgoingState, OutgoingMessage
from .provider import WhatsAppProvider, ProviderStatus, SendResult, assert_conforms
from .process_manager import ProcessManager, RestartPolicy, RuntimeStatus
from .validation import (
    WhatsAppValidationError,
    validate_chat_id,
    validate_text,
    validate_media_path,
)
from .capabilities import (
    WhatsAppCapability,
    WhatsAppGrants,
    WhatsAppCapabilityDenied,
)
from .mcp_tools import (
    ToolOutcome,
    ToolResult,
    ToolSpec,
    TOOL_ALLOWLIST,
    WhatsAppMcpDispatcher,
)
from .outbound_policy import (
    OutboundDecision,
    OutboundContext,
    OutboundPolicy,
    PRIVILEGED_ACTIONS,
)
from .cron_policy import (
    CronJobType,
    CronJob,
    CronGuard,
    CronPolicyError,
    ALLOWED_CRON_JOBS,
)
from .agent_bridge import (
    WhatsAppAgentBridge,
    BridgeResult,
    InboundAction,
    AgentCallable,
)
from .memory import (
    MemorySanitizer,
    MemoryRecord,
    MemoryLeakError,
    assert_no_secrets,
    SENSITIVE_KEYS,
    MAX_STORED_TEXT,
)
from .client import (
    EasyApiClient,
    EasyApiRequest,
    EasyApiResponse,
    EasyApiClientError,
    ENDPOINT_ALLOWLIST,
    API_KEY_HEADER,
)

__all__ = [
    "SessionState",
    "SessionStateMachine",
    "InvalidSessionTransition",
    "NormalizedEvent",
    "EventType",
    "normalize_openwa_event",
    "EventDeduper",
    "OutgoingState",
    "OutgoingMessage",
    "WhatsAppValidationError",
    "validate_chat_id",
    "validate_text",
    "validate_media_path",
    "WhatsAppProvider",
    "ProviderStatus",
    "SendResult",
    "assert_conforms",
    "ProcessManager",
    "RestartPolicy",
    "RuntimeStatus",
    # capabilities / gating
    "WhatsAppCapability",
    "WhatsAppGrants",
    "WhatsAppCapabilityDenied",
    # MCP tool surface
    "ToolOutcome",
    "ToolResult",
    "ToolSpec",
    "TOOL_ALLOWLIST",
    "WhatsAppMcpDispatcher",
    # outbound policy
    "OutboundDecision",
    "OutboundContext",
    "OutboundPolicy",
    "PRIVILEGED_ACTIONS",
    # cron policy
    "CronJobType",
    "CronJob",
    "CronGuard",
    "CronPolicyError",
    "ALLOWED_CRON_JOBS",
    # agent bridge (pipeline de entrada desacoplado)
    "WhatsAppAgentBridge",
    "BridgeResult",
    "InboundAction",
    "AgentCallable",
    # memória (fronteira única de persistência, sem segredos)
    "MemorySanitizer",
    "MemoryRecord",
    "MemoryLeakError",
    "assert_no_secrets",
    "SENSITIVE_KEYS",
    "MAX_STORED_TEXT",
    # cliente Easy API (auth local, transporte injetado)
    "EasyApiClient",
    "EasyApiRequest",
    "EasyApiResponse",
    "EasyApiClientError",
    "ENDPOINT_ALLOWLIST",
    "API_KEY_HEADER",
]
