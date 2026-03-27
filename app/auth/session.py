from fastapi import Request, HTTPException
from app.db import users


def get_current_user(request: Request):
    user_session = request.session.get("user")

    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Handle both dict and string session values for backwards compatibility
    if isinstance(user_session, dict):
        email = user_session.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Not authenticated")
    else:
        email = user_session

    user = users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
