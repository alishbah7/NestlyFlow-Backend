# backend/routes/auth.py
import resend
from datetime import timedelta, datetime, timezone
import secrets
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import os
from dotenv import load_dotenv

load_dotenv()

import auth
import models
import schemas
from dependencies import get_db, get_current_user

router = APIRouter()

ACCESS_TOKEN_EXPIRE_MINUTES = 30
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
if not RESEND_API_KEY:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="RESEND_API_KEY is not configured.",
    )
resend.api_key = RESEND_API_KEY


@router.post("/signup", response_model=schemas.UserWithToken, status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        username=user.username, email=user.email, hashed_password=hashed_password
    )
    db.add(db_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )
    db.refresh(db_user)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": db_user.username}, expires_delta=access_token_expires
    )

    return {
        "id": db_user.id,
        "username": db_user.username,
        "email": db_user.email,
        "todos": db_user.todos,
        "access_token": access_token,
        "token_type": "bearer",
    }

@router.post("/login", response_model=schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    # Try to find the user by username or email
    user = db.query(models.User).filter(
        (models.User.username == form_data.username) | (models.User.email == form_data.username)
    ).first()

    # If no user is found
    if not user:
        # Check if the input was an email
        if "@" in form_data.username:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account with that email does not exist",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account with that username does not exist",
            )

    # If user is found, verify the password
    if not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # If password is correct, create and return token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
def logout():
    return {"message": "Logout successful"}


@router.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.patch("/users/me", response_model=schemas.UserWithToken)
def update_user_me(
    user_update: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Ensure only username is being updated
    if user_update.dict(exclude_unset=True).keys() - {"username"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only username can be updated",
        )

    if user_update.username is not None and user_update.username != current_user.username:
        # Check if the new username is already taken
        if (
            db.query(models.User)
            .filter(models.User.username == user_update.username)
            .first()
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )
        current_user.username = user_update.username
        db.add(current_user)
        db.commit()
        db.refresh(current_user)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": current_user.username}, expires_delta=access_token_expires
    )

    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "todos": current_user.todos,
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/users/me/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    passwords: schemas.PasswordReset,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not auth.verify_password(passwords.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )
    current_user.hashed_password = auth.get_password_hash(passwords.new_password)
    db.add(current_user)
    db.commit()
    return


@router.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_me(
    user_delete: schemas.UserDelete,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not auth.verify_password(user_delete.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
        )

    # Delete associated tasks
    db.query(models.Todo).filter(models.Todo.owner_id == current_user.id).delete(
        synchronize_session=False
    )

    # Delete the user
    db.delete(current_user)
    db.commit()
    return

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(
    request_body: schemas.ForgotPassword,
    request: Request,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.email == request_body.email).first()
    if not user:
        # Still return a 200 OK to not reveal if an email is registered
        return {"message": "If your email is registered, a password reset link has been sent."}

    # Generate a secure token
    token = secrets.token_urlsafe(32)
    
    # Set expiration for the token (e.g., 1 hour from now)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
    # Store the token in the database
    reset_token = models.PasswordResetToken(
        user_id=user.id, token=token, expires_at=expires_at
    )
    db.add(reset_token)
    db.commit()

    # Get the base URL from the request
    base_url = "http://localhost:3000/"
    # Construct the reset link
    reset_link = f"{base_url}reset-password?token={token}"

    # Send the email using Resend
    try:
        email_params = {
            "from": "onboarding@resend.dev",
            "to": user.email,
            "subject": "Password Reset Request",
            "html": f"<p>Hi {user.username},</p>"
                    f"<p>You requested a password reset. Click the link below to reset your password:</p>"
                    f'<a href="{reset_link}">Reset Password</a>'
                    f"<p>If you did not request this, please ignore this email.</p>",
        }
        resend.Emails.send(email_params)
    except Exception as e:
        # Log the error, but don't expose it to the client
        print(f"Failed to send email: {e}")
        # Even if email fails, we don't want to let the user know
        # as it could be a security risk.
    
    return {"message": "If your email is registered, a password reset link has been sent."}

@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password_confirm(
    token: str,
    request_body: schemas.ResetPassword,
    db: Session = Depends(get_db),
):
    # Find the token in the database
    reset_token = db.query(models.PasswordResetToken).filter(models.PasswordResetToken.token == token).first()

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    # Check if the token has expired
    if reset_token.expires_at < datetime.utcnow():
        db.delete(reset_token)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    # Find the user associated with the token
    user = db.query(models.User).filter(models.User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    # Hash the new password and update the user's record
    hashed_password = auth.get_password_hash(request_body.new_password)
    user.hashed_password = hashed_password
    db.add(user)
    
    # Delete the used token
    db.delete(reset_token)
    db.commit()

    return

