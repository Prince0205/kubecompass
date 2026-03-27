"""
REST API endpoints for authentication
Used by React frontend for login/logout/register
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from passlib.hash import bcrypt
from app.db import users
from typing import Optional, Dict, Any

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class LoginResponse(BaseModel):
    success: bool
    message: str
    user: Optional[Dict[str, Any]] = None


@router.post("/login", response_model=LoginResponse)
def api_login(request: Request, payload: LoginRequest):
    """
    REST API login endpoint for React frontend
    Sets session cookie and returns user info
    """
    try:
        user = users.find_one({"email": payload.email})

        if not user or not bcrypt.verify(payload.password[:72], user["password"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Set session
        request.session["user"] = {
            "email": user["email"],
            "role": user.get("role", "view"),
        }

        return LoginResponse(
            success=True,
            message="Login successful",
            user={"email": user["email"], "role": user.get("role", "view")},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@router.post("/register")
def api_register(payload: RegisterRequest):
    """
    REST API register endpoint for React frontend
    Creates new user in MongoDB
    """
    try:
        existing_user = users.find_one({"email": payload.email})
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        password_hash = bcrypt.hash(payload.password[:72])
        new_user = {
            "email": payload.email,
            "password": password_hash,
            "name": payload.name or "",
            "role": "view",
        }
        users.insert_one(new_user)

        return {"success": True, "message": "Registration successful. Please login."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.post("/logout")
def api_logout(request: Request):
    """
    REST API logout endpoint
    Clears session and returns success
    """
    request.session.clear()
    return {"success": True, "message": "Logout successful"}


@router.get("/me")
def get_current_user(request: Request):
    """
    Get current authenticated user info
    Returns user data or null if not authenticated
    """
    user_session = request.session.get("user")
    if not user_session:
        return {"authenticated": False, "user": None}

    return {"authenticated": True, "user": user_session}
