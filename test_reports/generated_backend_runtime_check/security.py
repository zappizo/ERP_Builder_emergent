from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User


def get_current_user(
    x_user_id: str | None = Header(default=None, alias="x-user-id"),
    x_role: str | None = Header(default=None, alias="x-role"),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not x_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing x-user-id header.")

    user = db.query(User).filter(User.id == x_user_id, User.active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user session.")

    if x_role and x_role.strip().lower() != user.role.strip().lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role header does not match the user.")

    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}