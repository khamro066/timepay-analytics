import getpass
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.user import User


def main() -> None:
    Base.metadata.create_all(bind=engine)

    username = input("Username: ").strip()
    if not username:
        print("Username cannot be empty.")
        sys.exit(1)

    password = getpass.getpass("Password: ")
    password_confirm = getpass.getpass("Confirm password: ")
    if password != password_confirm:
        print("Passwords do not match.")
        sys.exit(1)
    if len(password.encode("utf-8")) < 8:
        print("Password must be at least 8 characters.")
        sys.exit(1)
    if len(password.encode("utf-8")) > 72:
        print("Password must be at most 72 bytes (bcrypt's limit).")
        sys.exit(1)

    is_admin = input("Is admin? (y/N): ").strip().lower() == "y"

    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            print(f"A user named '{username}' already exists.")
            sys.exit(1)

        user = User(username=username, hashed_password=hash_password(password), is_admin=is_admin)
        db.add(user)
        db.commit()
        print(f"Created user '{username}' (admin={is_admin}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
