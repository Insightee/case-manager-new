from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.schemas.address import AddressRead, ServiceAddressUpdate


class ParentChildRead(BaseModel):
    id: int
    first_name: str
    last_name: str
    full_name: str


class ParentChildUpdate(BaseModel):
    id: int
    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)


class ParentChildCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(default="", max_length=128)


class ParentServiceRead(BaseModel):
    case_id: int
    case_code: str
    service_type: str
    product_module: str
    child_name: str


class ParentHomecareCaseRead(BaseModel):
    case_id: int
    case_code: str
    child_name: str
    service_address: Optional[AddressRead] = None
    service_address_summary: Optional[str] = None


class ParentProfileRead(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    home_address: Optional[AddressRead] = None
    children: list[ParentChildRead] = []
    services: list[ParentServiceRead] = []
    homecare_cases: list[ParentHomecareCaseRead] = []


class ParentServiceAddressPatch(BaseModel):
    case_id: int
    address: ServiceAddressUpdate


class ParentProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=32)
    home_address_line1: Optional[str] = None
    home_address_line2: Optional[str] = None
    home_city: Optional[str] = None
    home_state: Optional[str] = None
    home_pincode: Optional[str] = None
    home_landmark: Optional[str] = None
    home_latitude: Optional[float] = None
    home_longitude: Optional[float] = None
    children: Optional[list[ParentChildUpdate]] = None
    service_address: Optional[ParentServiceAddressPatch] = None
