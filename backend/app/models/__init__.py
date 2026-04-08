"""SQLAlchemy models — import all so Alembic can discover them."""

from app.models.base import Base, UUIDMixin, TimestampMixin  # noqa: F401
from app.models.user import User, GarminCredential  # noqa: F401
from app.models.health import DailyStat, Activity, SleepRecord, HeartRateRecord, SyncLog  # noqa: F401
from app.models.sharing import DoctorPatientLink, MedicalRecord, DoctorAnnotation, AuditLog  # noqa: F401
from app.models.billing import Subscription, UsageRecord  # noqa: F401
from app.models.chat import ChatMessage  # noqa: F401
from app.models.garmin_extended import (  # noqa: F401
    HrvRecord, TrainingReadinessRecord, BodyCompositionRecord,
    StressDetailRecord, PerformanceMetric,
)
from app.models.meal import MealLog  # noqa: F401
