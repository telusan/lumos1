from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date, time
from app.models.models import RoleEnum

class CourseOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    price_per_month: float
    is_active: bool
    class Config:
        from_attributes = True

class CourseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    price_per_month: float

class GroupOut(BaseModel):
    id: int
    name: str
    course_id: int
    teacher_id: Optional[int]
    course_title: Optional[str] = None
    class Config:
        from_attributes = True

class GroupCreate(BaseModel):
    name: str
    course_id: int
    teacher_id: Optional[int] = None

class StudentOut(BaseModel):
    id: int
    full_name: str
    email: str
    role: RoleEnum
    class Config:
        from_attributes = True

class StudentCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str = "student123"

class GradeOut(BaseModel):
    id: int
    enrollment_id: int
    date: date
    value: str
    comment: Optional[str]
    teacher_id: int
    student_name: Optional[str] = None
    course_title: Optional[str] = None
    class Config:
        from_attributes = True

class GradeCreate(BaseModel):
    enrollment_id: int
    date: date
    value: str
    comment: Optional[str] = None

class ScheduleOut(BaseModel):
    id: int
    group_id: int
    day_of_week: int
    start_time: time
    end_time: time
    room: Optional[str]
    group_name: Optional[str] = None
    course_title: Optional[str] = None
    class Config:
        from_attributes = True

class ScheduleCreate(BaseModel):
    group_id: int
    day_of_week: int
    start_time: time
    end_time: time
    room: Optional[str] = None

class InvoiceOut(BaseModel):
    id: int
    student_id: int
    amount: float
    due_date: date
    status: str
    description: Optional[str]
    student_name: Optional[str] = None
    course_title: Optional[str] = None
    class Config:
        from_attributes = True

class EnrollmentOut(BaseModel):
    id: int
    student_id: int
    group_id: int
    start_date: date
    is_active: bool
    student_name: Optional[str] = None
    group_name: Optional[str] = None
    course_title: Optional[str] = None
    class Config:
        from_attributes = True

class EnrollmentCreate(BaseModel):
    student_id: int
    group_id: int

class AttendanceOut(BaseModel):
    id: int
    enrollment_id: int
    date: date
    status: str
    student_name: Optional[str] = None
    course_title: Optional[str] = None
    class Config:
        from_attributes = True

class AttendanceCreate(BaseModel):
    enrollment_id: int
    date: date
    status: str

class SchoolRegister(BaseModel):
    school_name: str
    school_slug: str
    owner_full_name: str
    owner_email: EmailStr
    owner_password: str
