from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.domain_models import User  # noqa: E402


def main() -> None:
    password = os.environ.get("WILDLIFE_ADMIN_RESET_PASSWORD")
    if not password or len(password) < 12:
        raise SystemExit("WILDLIFE_ADMIN_RESET_PASSWORD must contain at least 12 characters")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "admin"))
        if user is None:
            raise SystemExit("admin user does not exist")
        user.password_hash = hash_password(password)
        db.commit()
    print("admin_password_reset=ok")


if __name__ == "__main__":
    main()
