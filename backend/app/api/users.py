"""Users API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from app.schemas import UserProfile, UserUpdate
from app.security import get_current_user, require_admin
from app.database import get_db
from datetime import datetime, timezone

router = APIRouter()

@router.get("/", response_model=list[UserProfile])
async def list_users(
    role: str = Query(None),
    current_user: dict = Depends(require_admin),
    db=Depends(get_db)
):
    """List all users — admin only"""
    query = {}
    if role:
        query["role"] = role
    users = await db.users.find(query).to_list(100)
    return [UserProfile(**{**u, "id": str(u["_id"])}) for u in users]

@router.get("/{user_id}", response_model=UserProfile)
async def get_user(user_id: str, current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfile(**{**user, "id": str(user["_id"])})

@router.put("/me", response_model=UserProfile)
async def update_profile(
    update_data: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Update own profile"""
    fields = {k: v for k, v in update_data.model_dump().items() if v is not None}
    fields["updated_at"] = datetime.now(timezone.utc)
    await db.users.update_one({"_id": ObjectId(current_user["id"])}, {"$set": fields})
    updated = await db.users.find_one({"_id": ObjectId(current_user["id"])})
    return UserProfile(**{**updated, "id": str(updated["_id"])})
