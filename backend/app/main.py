from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, time, timedelta
from app.core.database import engine, Base, AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.models import (
    School, User, Course, Group, Enrollment, Schedule, Grade, Invoice, RoleEnum
)
from app.api.v1 import auth, data

async def seed_data():
    async with AsyncSessionLocal() as db:
        # Check if already seeded
        result = await db.execute(select(School).where(School.slug == "demo"))
        if result.scalar_one_or_none():
            return

        # School
        school = School(name="Lumos Demo School", slug="demo")
        db.add(school)
        await db.flush()

        # Users
        owner = User(
            school_id=school.id,
            email="owner@demo.uz",
            hashed_password=get_password_hash("owner123"),
            full_name="Алишер Каримов",
            role=RoleEnum.OWNER,
            preferred_lang="ru"
        )
        teacher = User(
            school_id=school.id,
            email="teacher@demo.uz",
            hashed_password=get_password_hash("teacher123"),
            full_name="Нигора Рахимова",
            role=RoleEnum.TEACHER,
            preferred_lang="uz"
        )
        student1 = User(
            school_id=school.id,
            email="student@demo.uz",
            hashed_password=get_password_hash("student123"),
            full_name="Жасур Усманов",
            role=RoleEnum.STUDENT,
            preferred_lang="ru"
        )
        student2 = User(
            school_id=school.id,
            email="madina@demo.uz",
            hashed_password=get_password_hash("student123"),
            full_name="Мадина Тошматова",
            role=RoleEnum.STUDENT,
            preferred_lang="uz"
        )
        db.add_all([owner, teacher, student1, student2])
        await db.flush()

        # Courses
        course1 = Course(school_id=school.id, title="Английский язык", description="General English", price_per_month=450000)
        course2 = Course(school_id=school.id, title="Робототехника", description="LEGO + Arduino", price_per_month=550000)
        course3 = Course(school_id=school.id, title="Математика", description="Олимпиадная математика", price_per_month=400000)
        db.add_all([course1, course2, course3])
        await db.flush()

        # Groups
        group1 = Group(school_id=school.id, course_id=course1.id, name="English A1", teacher_id=teacher.id)
        group2 = Group(school_id=school.id, course_id=course2.id, name="Robotics Kids", teacher_id=teacher.id)
        group3 = Group(school_id=school.id, course_id=course3.id, name="Math Olymp", teacher_id=teacher.id)
        db.add_all([group1, group2, group3])
        await db.flush()

        # Enrollments
        today = date.today()
        enr1 = Enrollment(school_id=school.id, student_id=student1.id, group_id=group1.id, start_date=today - timedelta(days=60))
        enr2 = Enrollment(school_id=school.id, student_id=student1.id, group_id=group2.id, start_date=today - timedelta(days=30))
        enr3 = Enrollment(school_id=school.id, student_id=student2.id, group_id=group1.id, start_date=today - timedelta(days=45))
        enr4 = Enrollment(school_id=school.id, student_id=student2.id, group_id=group3.id, start_date=today - timedelta(days=20))
        db.add_all([enr1, enr2, enr3, enr4])
        await db.flush()

        # Schedules
        schedules = [
            Schedule(school_id=school.id, group_id=group1.id, day_of_week=0, start_time=time(16, 0), end_time=time(17, 30), room="101"),
            Schedule(school_id=school.id, group_id=group1.id, day_of_week=2, start_time=time(16, 0), end_time=time(17, 30), room="101"),
            Schedule(school_id=school.id, group_id=group2.id, day_of_week=1, start_time=time(15, 0), end_time=time(16, 30), room="Lab-2"),
            Schedule(school_id=school.id, group_id=group2.id, day_of_week=4, start_time=time(15, 0), end_time=time(16, 30), room="Lab-2"),
            Schedule(school_id=school.id, group_id=group3.id, day_of_week=2, start_time=time(17, 0), end_time=time(18, 30), room="203"),
            Schedule(school_id=school.id, group_id=group3.id, day_of_week=5, start_time=time(10, 0), end_time=time(11, 30), room="203"),
        ]
        db.add_all(schedules)

        # Grades
        grades = [
            Grade(school_id=school.id, enrollment_id=enr1.id, date=today - timedelta(days=10), value="5", comment="Отличная работа", teacher_id=teacher.id),
            Grade(school_id=school.id, enrollment_id=enr1.id, date=today - timedelta(days=5), value="4", comment="Хорошо", teacher_id=teacher.id),
            Grade(school_id=school.id, enrollment_id=enr2.id, date=today - timedelta(days=7), value="5", comment="Супер!", teacher_id=teacher.id),
            Grade(school_id=school.id, enrollment_id=enr3.id, date=today - timedelta(days=8), value="5", comment="A'lo", teacher_id=teacher.id),
            Grade(school_id=school.id, enrollment_id=enr4.id, date=today - timedelta(days=3), value="4", comment="Yaxshi", teacher_id=teacher.id),
        ]
        db.add_all(grades)

        # Invoices
        invoices = [
            Invoice(school_id=school.id, student_id=student1.id, enrollment_id=enr1.id, amount=450000, due_date=today - timedelta(days=5), status="overdue", description="Английский язык — октябрь"),
            Invoice(school_id=school.id, student_id=student1.id, enrollment_id=enr2.id, amount=550000, due_date=today + timedelta(days=10), status="pending", description="Робототехника — октябрь"),
            Invoice(school_id=school.id, student_id=student2.id, enrollment_id=enr3.id, amount=450000, due_date=today + timedelta(days=5), status="pending", description="Английский язык — октябрь"),
            Invoice(school_id=school.id, student_id=student2.id, enrollment_id=enr4.id, amount=400000, due_date=today - timedelta(days=15), status="overdue", description="Математика — сентябрь"),
        ]
        db.add_all(invoices)

        await db.commit()
        print("✅ Demo data seeded successfully!")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Seed
    await seed_data()
    yield

app = FastAPI(title="Lumos API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(data.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Lumos API is running", "docs": "/docs"}
