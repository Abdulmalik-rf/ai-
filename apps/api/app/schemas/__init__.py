"""Pydantic schemas (DTOs) used at API boundaries.

Models live in `app.models`; schemas in `app.schemas`. The two never reach
across — everything that crosses the HTTP boundary is a schema.
"""
from app.schemas.auth import (
    AcceptInviteRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SessionRead,
    SignupRequest,
    TokenPair,
    TokenRefreshRequest,
    VerifyEmailRequest,
)
from app.schemas.case import CaseCreate, CaseRead, CaseUpdate
from app.schemas.chat import (
    ChatMessageRead,
    ChatRequest,
    ChatResponse,
    ConversationRead,
)
from app.schemas.client import ClientCreate, ClientRead, ClientUpdate
from app.schemas.contract import (
    ContractFinding,
    ContractReviewResponse,
    ContractSuggestion,
)
from app.schemas.document import (
    DocumentRead,
    DocumentUploadResponse,
    DraftRequest,
    DraftResponse,
)
from app.schemas.subscription import (
    ChangePlanRequest,
    CheckoutRequest,
    CheckoutResponse,
    PlanRead,
    SubscriptionRead,
    UsageMetric,
    UsageRead,
)
from app.schemas.tenant import TenantRead, TenantUpdate
from app.schemas.user import UserRead, UserUpdate
from app.schemas.whatsapp import (
    AgentProfileRead,
    AgentProfileUpdate,
    AgentPromptPreview,
    AllowedSenderCreate,
    AllowedSenderRead,
    BridgeInboundMessage,
    BridgeInboundReply,
    BridgeSessionUpdate,
    SessionStatusRead,
)

__all__ = [
    "CaseCreate",
    "CaseRead",
    "CaseUpdate",
    "ChatMessageRead",
    "ChatRequest",
    "ChatResponse",
    "CheckoutRequest",
    "CheckoutResponse",
    "ClientCreate",
    "ClientRead",
    "ClientUpdate",
    "ContractFinding",
    "ContractReviewResponse",
    "ContractSuggestion",
    "ConversationRead",
    "DocumentRead",
    "DocumentUploadResponse",
    "DraftRequest",
    "DraftResponse",
    "LoginRequest",
    "PlanRead",
    "SignupRequest",
    "SubscriptionRead",
    "TenantRead",
    "TenantUpdate",
    "TokenPair",
    "TokenRefreshRequest",
    "UserRead",
    "UserUpdate",
    "AgentProfileRead",
    "AgentProfileUpdate",
    "AgentPromptPreview",
    "AllowedSenderCreate",
    "AllowedSenderRead",
    "BridgeInboundMessage",
    "BridgeInboundReply",
    "BridgeSessionUpdate",
    "SessionStatusRead",
]
