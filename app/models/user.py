from sqlalchemy import Boolean, Column, ForeignKey, Integer, String

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, nullable=False, default=False)
    # Nullable, unused today — no admin account is tracked as an Employee.
    # Exists so the self-correction guard in the corrections API is a real,
    # enforced check rather than a no-op: the day a User account does get
    # linked to an Employee record, that admin is immediately blocked from
    # correcting their own attendance without any further code changes.
    linked_employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
