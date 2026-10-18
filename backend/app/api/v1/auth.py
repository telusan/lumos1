from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.common import SchoolRegister
from app.models.models import User, School, RoleEnum
from app.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(School).where(School.slug == data.school_slug.lower()))
    school = result.scalar_one_or_none()
    if not school:
        raise HTTPException(status_code=401, detail="School not found")

    result = await db.execute(
        select(User).where(User.email == data.email.lower(), User.school_id == school.id)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({
        "sub": str(user.id),
        "school_id": user.school_id,
        "role": user.role.value
    })

    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "school_id": user.school_id,
            "preferred_lang": user.preferred_lang
        }
    )

@router.post("/register-school")
async def register_school(data: SchoolRegister, db: AsyncSession = Depends(get_db)):
    slug = data.school_slug.lower().strip().replace(" ", "-")
    result = await db.execute(select(School).where(School.slug == slug))
    if result.scalar_one_or_none():
        raise HTTPException(400, "School slug already exists")

    school = School(name=data.school_name, slug=slug)
    db.add(school)
    await db.flush()

    owner = User(
        school_id=school.id,
        email=data.owner_email.lower(),
        hashed_password=get_password_hash(data.owner_password),
        full_name=data.owner_full_name,
        role=RoleEnum.OWNER,
        preferred_lang="ru"
    )
    db.add(owner)
    await db.commit()

    return {"message": "School created", "slug": slug, "email": data.owner_email}

@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "school_id": current_user.school_id,
        "preferred_lang": current_user.preferred_lang
    }
