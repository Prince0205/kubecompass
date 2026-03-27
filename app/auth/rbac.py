from fastapi import Depends, HTTPException
from app.auth.session import get_current_user

def require_role(allowed_roles):
    def checker(user=Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return checker
