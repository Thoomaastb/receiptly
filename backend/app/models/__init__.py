"""Zentraler Import aller Modelle, damit Alembic sie über Base.metadata findet."""

from app.models.ai_settings import AISettings, AIProviderType  # noqa: F401
from app.models.ai_usage_event import AIUsageEvent  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.bucket import Bucket, BucketAccess  # noqa: F401
from app.models.household import Household  # noqa: F401
from app.models.household_security_settings import HouseholdSecuritySettings  # noqa: F401
from app.models.item import Item  # noqa: F401
from app.models.merchant import Merchant  # noqa: F401
from app.models.product import Product  # noqa: F401
from app.models.receipt import Receipt  # noqa: F401
from app.models.smtp_settings import SmtpSettings  # noqa: F401
from app.models.totp_recovery_code import TotpRecoveryCode  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.webauthn_credential import WebauthnCredential  # noqa: F401
