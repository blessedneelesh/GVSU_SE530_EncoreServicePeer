# Import every model so SQLAlchemy and Alembic register them on Base.metadata.
from app.models.user import User  # noqa: F401
from app.models.auth import Role, UserRole, RefreshToken, RevokedToken  # noqa: F401
from app.models.concert import Concert  # noqa: F401
from app.models.invoice import Invoice  # noqa: F401
from app.models.comment import Comment  # noqa: F401