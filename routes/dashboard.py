# backend/routes/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from models import User
from schemas import DashboardStats, TaskStats, PriorityStat, CategoryStat, DeadlineStat
from dependencies import get_db, get_current_user
import crud

router = APIRouter(
    # prefix="/api",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=DashboardStats)
def get_dashboard_data(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Retrieve aggregated data for the user's dashboard.
    """
    stats = crud.get_task_stats(db=db, user_id=current_user.id)
    priorities = crud.get_tasks_by_priority(db=db, user_id=current_user.id)
    categories = crud.get_tasks_by_category(db=db, user_id=current_user.id)
    deadlines = crud.get_upcoming_deadlines(db=db, user_id=current_user.id)
    
    # The user wants all 6 categories to be present, even if they have 0 tasks.
    all_categories = ["work", "personal", "shopping", "health", "education", "others"]
    category_map = {cat.category: cat.count for cat in categories}
    
    full_categories = [
        CategoryStat(category=cat_name, count=category_map.get(cat_name, 0))
        for cat_name in all_categories
    ]

    return DashboardStats(
        stats=stats,
        priorities=priorities,
        categories=full_categories,
        deadlines=deadlines,
    )
