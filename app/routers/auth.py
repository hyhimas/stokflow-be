import re
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.user import User
from app.models.business import Business
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse, BusinessResponse
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Autentikasi & Akun (Auth)"])

def generate_business_code(name: str) -> str:
    cleaned = re.sub(r'[^A-Za-z0-9]', '', name).upper()
    prefix = cleaned[:4] if len(cleaned) >= 4 else (cleaned + "BIZ")[:4]
    unique_suffix = uuid.uuid4().hex[:4].upper()
    return f"{prefix}-{unique_suffix}"

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrasi Pemilik Usaha (Owner) & Profil Toko Baru",
    description="Mendaftarkan toko/bisnis baru beserta akun Owner. Mengembalikan token akses JWT."
)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    # Validasi email / nomor hp minimal ada salah satu (FR-01)
    if not req.email and not req.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wajib menyertakan minimal Email atau Nomor HP."
        )

    # Cek apakah email sudah terdaftar
    if req.email:
        existing_email = db.query(User).filter(User.email == str(req.email)).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email sudah terdaftar. Silakan login atau gunakan email lain."
            )

    # Cek apakah phone sudah terdaftar
    if req.phone:
        existing_phone = db.query(User).filter(User.phone == req.phone).first()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nomor HP sudah terdaftar. Silakan login atau gunakan nomor lain."
            )

    # 1. Buat entitas bisnis baru
    business_code = generate_business_code(req.business_name)
    new_business = Business(
        id=uuid.uuid4(),
        code=business_code,
        name=req.business_name,
        business_type=req.business_type,
        address=req.business_address,
        status="ACTIVE"
    )
    db.add(new_business)
    db.flush()

    # 2. Buat akun OWNER
    new_user = User(
        id=uuid.uuid4(),
        business_id=new_business.id,
        name=req.owner_name,
        phone=req.phone,
        email=str(req.email) if req.email else None,
        password_hash=hash_password(req.password),
        role="OWNER",
        status="ACTIVE"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    db.refresh(new_business)

    # 3. Generate JWT Token
    token_payload = {
        "sub": str(new_user.id),
        "business_id": str(new_business.id),
        "role": new_user.role,
        "name": new_user.name
    }
    access_token = create_access_token(token_payload)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user),
        business=BusinessResponse.model_validate(new_business)
    )

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login Pemilik Usaha (Owner)",
    description="Masuk menggunakan Email atau Nomor HP beserta Password. Mengembalikan JWT Bearer token."
)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    # Cari pengguna berdasarkan email atau phone
    user = db.query(User).filter(
        or_(User.email == req.identifier, User.phone == req.identifier)
    ).first()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identitas (Email/No HP) atau kata sandi salah."
        )

    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun Anda dinonaktifkan. Hubungi admin."
        )

    # Ambil info bisnis
    business = None
    if user.business_id:
        business = db.query(Business).filter(Business.id == user.business_id).first()
        if not business or business.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Layanan bisnis toko Anda berstatus nonaktif atau ditangguhkan."
            )

    # Perbarui last_login_at
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    # Buat JWT
    token_payload = {
        "sub": str(user.id),
        "business_id": str(user.business_id) if user.business_id else None,
        "role": user.role,
        "name": user.name
    }
    access_token = create_access_token(token_payload)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
        business=BusinessResponse.model_validate(business) if business else None
    )

@router.get(
    "/me",
    response_model=TokenResponse,
    summary="Profil Pengguna yang Sedang Login",
    description="Mendapatkan data pengguna & profil bisnis yang terautentikasi."
)
def get_me(current_user: User = Depends(get_current_user)):
    token_payload = {
        "sub": str(current_user.id),
        "business_id": str(current_user.business_id) if current_user.business_id else None,
        "role": current_user.role,
        "name": current_user.name
    }
    access_token = create_access_token(token_payload)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(current_user),
        business=BusinessResponse.model_validate(current_user.current_business) if hasattr(current_user, "current_business") else None
    )
