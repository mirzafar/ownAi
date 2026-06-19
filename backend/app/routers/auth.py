from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..database import users
from ..models import TokenResponse, UserLogin, UserOut, UserRegister

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(doc: dict) -> UserOut:
    return UserOut(id=str(doc["_id"]), login=doc["login"], name=doc["name"])


@router.post("/register", response_model=TokenResponse)
async def register(payload: UserRegister) -> TokenResponse:
    login = payload.login.lower()
    existing = await users.find_one({"login": login})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Login already taken")

    doc = {
        "login": login,
        "name": payload.name.strip(),
        "password_hash": hash_password(payload.password),
    }
    result = await users.insert_one(doc)
    doc["_id"] = result.inserted_id
    user = _user_out(doc)
    return TokenResponse(access_token=create_access_token(user.id), user=user)


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    doc = await users.find_one({"login": form.username.lower()})
    if not doc or not verify_password(form.password, doc["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user = _user_out(doc)
    return TokenResponse(access_token=create_access_token(user.id), user=user)


@router.post("/login-json", response_model=TokenResponse)
async def login_json(payload: UserLogin) -> TokenResponse:
    doc = await users.find_one({"login": payload.login.lower()})
    if not doc or not verify_password(payload.password, doc["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user = _user_out(doc)
    return TokenResponse(access_token=create_access_token(user.id), user=user)


@router.get("/me", response_model=UserOut)
async def me(current=Depends(get_current_user)) -> UserOut:
    return _user_out(current)
