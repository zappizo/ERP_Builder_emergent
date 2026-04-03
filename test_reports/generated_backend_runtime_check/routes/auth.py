from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import LoginRequest, LoginResponse
from security import get_current_user
from services import serialize_user

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email, User.active.is_(True)).first()
    if not user or user.password != payload.password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid demo credentials.")

    headers = {"x-user-id": user.id, "x-role": user.role}
    return LoginResponse(user=serialize_user(user), headers=headers, message="Login successful.")


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}