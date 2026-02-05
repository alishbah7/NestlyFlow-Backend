from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from models import User
from schemas import TodoResponse, TodoCreate, TodoUpdate
from dependencies import get_db, get_current_user
import crud

router = APIRouter()

@router.get("/todos", response_model=List[TodoResponse])
def read_todos(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.get_todos(db=db, user_id=current_user.id, skip=skip, limit=limit)

@router.post("/todos", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
def create_todo(todo: TodoCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.create_user_todo(db=db, todo=todo, user_id=current_user.id)

@router.get("/todos/{id}", response_model=TodoResponse)
def read_todo(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.get_todo(db=db, id=id, user_id=current_user.id)

@router.put("/todos/{id}", response_model=TodoResponse)
def update_todo(id: int, todo: TodoUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.update_user_todo(db=db, id=id, todo=todo, user_id=current_user.id)

@router.delete("/todos/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.delete_user_todo(db=db, id=id, user_id=current_user.id)
