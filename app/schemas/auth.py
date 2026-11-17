from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

class BusinessBase(BaseModel):
    name: str = Field(..., example="Toko Berkah Sejahtera")
    business_type: str = Field(..., example="ritel")
    address: Optional[str] = Field(None, example="Jl. Merdeka No. 10, Jakarta")

class BusinessResponse(BusinessBase):
    id: UUID
    code: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    name: str = Field(..., example="Budi Santoso")
    phone: Optional[str] = Field(None, example="081234567890")
    email: Optional[EmailStr] = Field(None, example="budi@example.com")

class UserResponse(UserBase):
    id: UUID
    business_id: Optional[UUID]
    role: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class RegisterRequest(BaseModel):
    # Business Profile
    business_name: str = Field(..., example="Toko Berkah Sejahtera")
    business_type: str = Field(..., example="ritel")
    business_address: Optional[str] = Field(None, example="Jl. Merdeka No. 10, Jakarta")
    
    # Owner Profile
    owner_name: str = Field(..., example="Budi Santoso")
    phone: Optional[str] = Field(None, example="081234567890")
    email: Optional[EmailStr] = Field(None, example="budi@example.com")
    password: str = Field(..., min_length=6, example="password123")

class LoginRequest(BaseModel):
    identifier: str = Field(..., example="budi@example.com", description="Email atau Nomor HP terdaftar")
    password: str = Field(..., example="password123")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    business: Optional[BusinessResponse]
