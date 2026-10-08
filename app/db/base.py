from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Import all 8 models so SQLAlchemy/Alembic registers them
from app.models.user import User  # noqa
from app.models.auth import Role, UserRole, RefreshToken, RevokedToken # noqa
from app.models.concert import Concert  # noqa
from app.models.invoice import Invoice  # 
from app.models.comment import Comment  # noqa