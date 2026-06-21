from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..database import users
from ..models import (
    PasswordReset,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserOut,
    UserProfileUpdate,
    UserRegister,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(doc: dict) -> UserOut:
    return UserOut(
        id=str(doc["_id"]),
        login=doc["login"],
        name=doc.get("name", ""),
        phone=doc.get("phone", "") or "",
        email=doc.get("email", "") or "",
        address=doc.get("address", "") or "",
        is_admin=bool(doc.get("is_admin")),
    )


def _ensure_admin(user: dict) -> None:
    if not user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")


@router.post("/register", response_model=TokenResponse)
async def register(payload: UserRegister) -> TokenResponse:
    login = payload.login.lower()
    existing = await users.find_one({"login": login})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Login already taken")

    is_first = (await users.count_documents({})) == 0
    doc = {
        "login": login,
        "name": payload.name.strip(),
        "password_hash": hash_password(payload.password),
        "phone": "",
        "email": "",
        "address": "",
        "is_admin": is_first,
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


@router.patch("/me", response_model=UserOut)
async def update_me(payload: UserProfileUpdate, current=Depends(get_current_user)) -> UserOut:
    update = {k: v.strip() if isinstance(v, str) else v for k, v in payload.model_dump(exclude_none=True).items()}
    if not update:
        return _user_out(current)
    await users.update_one({"_id": current["_id"]}, {"$set": update})
    fresh = await users.find_one({"_id": current["_id"]})
    return _user_out(fresh)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(payload: PasswordReset, current=Depends(get_current_user)) -> None:
    await users.update_one(
        {"_id": current["_id"]},
        {"$set": {"password_hash": hash_password(payload.new_password)}},
    )


@router.get("/users", response_model=list[UserOut])
async def list_users(current=Depends(get_current_user)) -> list[UserOut]:
    _ensure_admin(current)
    cursor = users.find({}).sort("login", 1)
    return [_user_out(doc) async for doc in cursor]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, current=Depends(get_current_user)) -> UserOut:
    _ensure_admin(current)
    login = payload.login.lower()
    existing = await users.find_one({"login": login})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Login already taken")
    doc = {
        "login": login,
        "name": payload.name.strip(),
        "password_hash": hash_password(payload.password),
        "phone": (payload.phone or "").strip(),
        "email": (payload.email or "").strip(),
        "address": (payload.address or "").strip(),
        "is_admin": bool(payload.is_admin),
    }
    result = await users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _user_out(doc)


@router.delete("/users/{uid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(uid: str, current=Depends(get_current_user)) -> None:
    _ensure_admin(current)
    try:
        oid = ObjectId(uid)
    except Exception:
        raise HTTPException(status_code=404, detail="Not found")
    if oid == current["_id"]:
        raise HTTPException(status_code=400, detail="Нельзя удалить собственный аккаунт")
    result = await users.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")


@router.post("/users/{uid}/password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_user_password(
    uid: str,
    payload: PasswordReset,
    current=Depends(get_current_user),
) -> None:
    _ensure_admin(current)
    try:
        oid = ObjectId(uid)
    except Exception:
        raise HTTPException(status_code=404, detail="Not found")
    result = await users.update_one(
        {"_id": oid},
        {"$set": {"password_hash": hash_password(payload.new_password)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
