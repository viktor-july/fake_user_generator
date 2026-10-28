from pydantic import BaseModel, Field
from typing import List


class FakeUser(BaseModel):
    batch_position: int
    full_name: str
    address: str
    latitude: float
    longitude: float
    physical: str
    phone: str
    email: str


class GenerateRequest(BaseModel):
    locale: str = Field(default="en_US", pattern="^(en_US|de_DE)$")
    seed: int = Field(default=42, ge=0)
    batch_index: int = Field(default=0, ge=0)
    batch_size: int = Field(default=10, ge=1, le=100)


class GenerateResponse(BaseModel):
    users: List[FakeUser]
    locale: str
    seed: int
    batch_index: int