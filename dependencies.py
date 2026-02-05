# backend/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User
from auth import decode_access_token
from schemas import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    token_data = TokenData(username=username)
    
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

from typing import Optional
from fastapi import Request # Import Request

def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    token = request.headers.get("Authorization")
    print(f"DEBUG: get_current_user_optional - Authorization header: {token}") # Debug print
    if token:
        token = token.replace("Bearer ", "") # Remove "Bearer " prefix
    else:
        print("DEBUG: get_current_user_optional - No Authorization header found.") # Debug print
        return None

    try:
        payload = decode_access_token(token)
        if payload is None:
            print("DEBUG: get_current_user_optional - Payload is None after decode.") # Debug print
            return None
        username: str = payload.get("sub")
        if username is None:
            print("DEBUG: get_current_user_optional - Username is None in payload.") # Debug print
            return None
        token_data = TokenData(username=username)
        
        user = db.query(User).filter(User.username == token_data.username).first()
        print(f"DEBUG: get_current_user_optional - User found: {user.username if user else 'None'}") # Debug print
        return user
    except Exception as e: # Catch any exception during token decoding or user fetching
        print(f"DEBUG: get_current_user_optional - Exception during token decoding or user fetching: {e}") # Debug print
        return None
