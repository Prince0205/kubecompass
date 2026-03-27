"""Minimal models placeholder.

This project currently uses MongoDB documents directly in many places.
Keep a small models file to hold future Pydantic models and shared types.
"""

from pydantic import BaseModel
from typing import Optional


class User(BaseModel):
    email: str
    role: Optional[str] = "view"
