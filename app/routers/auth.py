from fastapi import APIRouter, Depends, HTTPException, status
from ..auth import create_session_token, get_current_user, hash_password, verify_password
from ..database import db_session
from ..models import UserLogin, UserRegister

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister):
    email = payload.email.strip().lower()
    pw_hash = hash_password(payload.password)
    with db_session() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, full_name, gstin) VALUES (?, ?, ?, ?)",
            (email, pw_hash, payload.full_name.strip(), payload.gstin.strip()),
        )
        user_id = cur.lastrowid
    token = create_session_token(user_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "email": email,
            "full_name": payload.full_name.strip(),
            "plan_tier": "starter",
            "gstin": payload.gstin.strip(),
        },
    }


@router.post("/login")
def login(payload: UserLogin):
    email = payload.email.strip().lower()
    with db_session() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_session_token(user["id"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "plan_tier": user["plan_tier"],
            "gstin": user["gstin"],
        },
    }


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user
