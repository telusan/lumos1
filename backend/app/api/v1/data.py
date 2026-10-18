from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import date, datetime
from app.core.database import get_db
from app.core.security import get_password_hash
from app.deps import get_current_user, require_roles
from app.models.models import (
    User, Course, Group, Enrollment, Schedule, Grade, Invoice, Attendance, RoleEnum
)
from app.schemas.common import (
    CourseOut, CourseCreate, GroupOut, GroupCreate, StudentOut, StudentCreate,
    GradeOut, GradeCreate, ScheduleOut, ScheduleCreate, InvoiceOut,
    EnrollmentOut, EnrollmentCreate, AttendanceOut, AttendanceCreate
)

router = APIRouter(tags=["data"])

# ========== COURSES ==========
@router.get("/courses", response_model=list[CourseOut])
async def list_courses(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Course).where(Course.school_id == current_user.school_id, Course.is_active == True)
    )
    return result.scalars().all()

@router.post("/courses", response_model=CourseOut)
async def create_course(data: CourseCreate, db: AsyncSession = Depends(get_db),
                        current_user: User = Depends(require_roles(RoleEnum.OWNER))):
    course = Course(school_id=current_user.school_id, title=data.title,
                    description=data.description, price_per_month=data.price_per_month)
    db.add(course)
    await db.flush()
    # Auto-create default group so course appears in enroll/schedule dropdowns
    group = Group(
        school_id=current_user.school_id,
        course_id=course.id,
        name=f"{data.title} — группа 1",
        teacher_id=None,
    )
    db.add(group)
    await db.commit()
    await db.refresh(course)
    return course

@router.delete("/courses/{course_id}")
async def delete_course(course_id: int, db: AsyncSession = Depends(get_db),
                        current_user: User = Depends(require_roles(RoleEnum.OWNER))):
    result = await db.execute(select(Course).where(Course.id == course_id, Course.school_id == current_user.school_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(404, "Course not found")
    course.is_active = False
    await db.commit()
    return {"ok": True}

# ========== GROUPS ==========
@router.get("/groups", response_model=list[GroupOut])
async def list_groups(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Group).options(selectinload(Group.course)).where(Group.school_id == current_user.school_id)
    )
    groups = result.scalars().all()
    return [GroupOut(id=g.id, name=g.name, course_id=g.course_id, teacher_id=g.teacher_id,
                     course_title=g.course.title if g.course else None) for g in groups]

@router.post("/groups", response_model=GroupOut)
async def create_group(data: GroupCreate, db: AsyncSession = Depends(get_db),
                       current_user: User = Depends(require_roles(RoleEnum.OWNER))):
    group = Group(school_id=current_user.school_id, name=data.name,
                  course_id=data.course_id, teacher_id=data.teacher_id)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return GroupOut(id=group.id, name=group.name, course_id=group.course_id, teacher_id=group.teacher_id)

# ========== STUDENTS ==========
@router.get("/students", response_model=list[StudentOut])
async def list_students(db: AsyncSession = Depends(get_db),
                        current_user: User = Depends(require_roles(RoleEnum.OWNER, RoleEnum.TEACHER))):
    result = await db.execute(
        select(User).where(User.school_id == current_user.school_id, User.role == RoleEnum.STUDENT, User.is_active == True)
    )
    return result.scalars().all()

@router.post("/students", response_model=StudentOut)
async def create_student(data: StudentCreate, db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(require_roles(RoleEnum.OWNER))):
    result = await db.execute(
        select(User).where(User.email == data.email.lower(), User.school_id == current_user.school_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(400, "Email already exists in this school")
    user = User(
        school_id=current_user.school_id,
        email=data.email.lower(),
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        role=RoleEnum.STUDENT
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@router.delete("/students/{student_id}")
async def delete_student(student_id: int, db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(require_roles(RoleEnum.OWNER))):
    result = await db.execute(
        select(User).where(User.id == student_id, User.school_id == current_user.school_id, User.role == RoleEnum.STUDENT)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Student not found")
    user.is_active = False
    # deactivate enrollments
    enrs = await db.execute(select(Enrollment).where(Enrollment.student_id == student_id))
    for e in enrs.scalars().all():
        e.is_active = False
    await db.commit()
    return {"ok": True}

# ========== ENROLLMENTS ==========
@router.get("/enrollments", response_model=list[EnrollmentOut])
async def list_enrollments(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = select(Enrollment).options(
        selectinload(Enrollment.group).selectinload(Group.course)
    ).where(Enrollment.school_id == current_user.school_id, Enrollment.is_active == True)
    if current_user.role == RoleEnum.STUDENT:
        query = query.where(Enrollment.student_id == current_user.id)
    result = await db.execute(query)
    enrollments = result.scalars().all()
    student_ids = {e.student_id for e in enrollments}
    students = {}
    if student_ids:
        res = await db.execute(select(User).where(User.id.in_(student_ids)))
        students = {u.id: u.full_name for u in res.scalars().all()}
    return [
        EnrollmentOut(
            id=e.id, student_id=e.student_id, group_id=e.group_id,
            start_date=e.start_date, is_active=e.is_active,
            student_name=students.get(e.student_id),
            group_name=e.group.name if e.group else None,
            course_title=e.group.course.title if e.group and e.group.course else None
        ) for e in enrollments
    ]

@router.post("/enrollments", response_model=EnrollmentOut)
async def create_enrollment(data: EnrollmentCreate, db: AsyncSession = Depends(get_db),
                            current_user: User = Depends(require_roles(RoleEnum.OWNER))):
    # Validate group belongs to school
    gres = await db.execute(
        select(Group).options(selectinload(Group.course)).where(
            Group.id == data.group_id, Group.school_id == current_user.school_id
        )
    )
    group = gres.scalar_one_or_none()
    if not group:
        raise HTTPException(404, "Group not found")

    enr = Enrollment(
        school_id=current_user.school_id,
        student_id=data.student_id,
        group_id=data.group_id,
        start_date=date.today()
    )
    db.add(enr)
    await db.flush()

    # Auto-create invoice for current month
    course = group.course
    price = float(course.price_per_month) if course else 0
    today = date.today()
    # due in 14 days
    from datetime import timedelta
    due = today + timedelta(days=14)
    title = course.title if course else "Course"
    inv = Invoice(
        school_id=current_user.school_id,
        student_id=data.student_id,
        enrollment_id=enr.id,
        amount=price,
        due_date=due,
        status="pending",
        description=f"{title} — {today.strftime('%m.%Y')}",
    )
    db.add(inv)
    await db.commit()
    await db.refresh(enr)
    return EnrollmentOut(id=enr.id, student_id=enr.student_id, group_id=enr.group_id,
                         start_date=enr.start_date, is_active=enr.is_active)

@router.delete("/enrollments/{enr_id}")
async def delete_enrollment(enr_id: int, db: AsyncSession = Depends(get_db),
                            current_user: User = Depends(require_roles(RoleEnum.OWNER))):
    result = await db.execute(
        select(Enrollment).where(Enrollment.id == enr_id, Enrollment.school_id == current_user.school_id)
    )
    enr = result.scalar_one_or_none()
    if not enr:
        raise HTTPException(404, "Not found")
    enr.is_active = False
    await db.commit()
    return {"ok": True}

# ========== SCHEDULES ==========
@router.get("/schedules", response_model=list[ScheduleOut])
async def list_schedules(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Schedule).options(selectinload(Schedule.group).selectinload(Group.course))
        .where(Schedule.school_id == current_user.school_id)
    )
    schedules = result.scalars().all()
    return [
        ScheduleOut(
            id=s.id, group_id=s.group_id, day_of_week=s.day_of_week,
            start_time=s.start_time, end_time=s.end_time, room=s.room,
            group_name=s.group.name if s.group else None,
            course_title=s.group.course.title if s.group and s.group.course else None
        ) for s in schedules
    ]

@router.post("/schedules", response_model=ScheduleOut)
async def create_schedule(data: ScheduleCreate, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(require_roles(RoleEnum.OWNER))):
    s = Schedule(
        school_id=current_user.school_id, group_id=data.group_id,
        day_of_week=data.day_of_week, start_time=data.start_time,
        end_time=data.end_time, room=data.room
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return ScheduleOut(id=s.id, group_id=s.group_id, day_of_week=s.day_of_week,
                       start_time=s.start_time, end_time=s.end_time, room=s.room)

@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: int, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(require_roles(RoleEnum.OWNER))):
    result = await db.execute(
        select(Schedule).where(Schedule.id == schedule_id, Schedule.school_id == current_user.school_id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Not found")
    await db.delete(s)
    await db.commit()
    return {"ok": True}

# ========== GRADES ==========
@router.get("/grades", response_model=list[GradeOut])
async def list_grades(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = select(Grade).options(
        selectinload(Grade.enrollment).selectinload(Enrollment.group).selectinload(Group.course)
    ).where(Grade.school_id == current_user.school_id)
    if current_user.role == RoleEnum.STUDENT:
        subq = select(Enrollment.id).where(Enrollment.student_id == current_user.id)
        query = query.where(Grade.enrollment_id.in_(subq))
    result = await db.execute(query)
    grades = result.scalars().all()
    student_ids = set()
    for g in grades:
        if g.enrollment:
            student_ids.add(g.enrollment.student_id)
    students = {}
    if student_ids:
        res = await db.execute(select(User).where(User.id.in_(student_ids)))
        students = {u.id: u.full_name for u in res.scalars().all()}
    return [
        GradeOut(
            id=g.id, enrollment_id=g.enrollment_id, date=g.date,
            value=g.value, comment=g.comment, teacher_id=g.teacher_id,
            student_name=students.get(g.enrollment.student_id) if g.enrollment else None,
            course_title=g.enrollment.group.course.title if g.enrollment and g.enrollment.group and g.enrollment.group.course else None
        ) for g in grades
    ]

@router.post("/grades", response_model=GradeOut)
async def create_grade(data: GradeCreate, db: AsyncSession = Depends(get_db),
                       current_user: User = Depends(require_roles(RoleEnum.TEACHER, RoleEnum.OWNER))):
    result = await db.execute(
        select(Enrollment).where(Enrollment.id == data.enrollment_id, Enrollment.school_id == current_user.school_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Enrollment not found")
    grade = Grade(
        school_id=current_user.school_id, enrollment_id=data.enrollment_id,
        date=data.date, value=data.value, comment=data.comment, teacher_id=current_user.id
    )
    db.add(grade)
    await db.commit()
    await db.refresh(grade)
    return GradeOut(id=grade.id, enrollment_id=grade.enrollment_id, date=grade.date,
                    value=grade.value, comment=grade.comment, teacher_id=grade.teacher_id)

# ========== ATTENDANCE ==========
@router.get("/attendance", response_model=list[AttendanceOut])
async def list_attendance(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = select(Attendance).options(
        selectinload(Attendance.enrollment).selectinload(Enrollment.group).selectinload(Group.course)
    ).where(Attendance.school_id == current_user.school_id)
    if current_user.role == RoleEnum.STUDENT:
        subq = select(Enrollment.id).where(Enrollment.student_id == current_user.id)
        query = query.where(Attendance.enrollment_id.in_(subq))
    result = await db.execute(query)
    items = result.scalars().all()
    student_ids = set()
    for a in items:
        if a.enrollment:
            student_ids.add(a.enrollment.student_id)
    students = {}
    if student_ids:
        res = await db.execute(select(User).where(User.id.in_(student_ids)))
        students = {u.id: u.full_name for u in res.scalars().all()}
    return [
        AttendanceOut(
            id=a.id, enrollment_id=a.enrollment_id, date=a.date, status=a.status,
            student_name=students.get(a.enrollment.student_id) if a.enrollment else None,
            course_title=a.enrollment.group.course.title if a.enrollment and a.enrollment.group and a.enrollment.group.course else None
        ) for a in items
    ]

@router.post("/attendance", response_model=AttendanceOut)
async def create_attendance(data: AttendanceCreate, db: AsyncSession = Depends(get_db),
                            current_user: User = Depends(require_roles(RoleEnum.TEACHER, RoleEnum.OWNER))):
    result = await db.execute(
        select(Enrollment).where(Enrollment.id == data.enrollment_id, Enrollment.school_id == current_user.school_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Enrollment not found")
    att = Attendance(
        school_id=current_user.school_id, enrollment_id=data.enrollment_id,
        date=data.date, status=data.status, marked_by=current_user.id
    )
    db.add(att)
    await db.commit()
    await db.refresh(att)
    return AttendanceOut(id=att.id, enrollment_id=att.enrollment_id, date=att.date, status=att.status)

# ========== INVOICES ==========
@router.get("/invoices", response_model=list[InvoiceOut])
async def list_invoices(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = select(Invoice).where(Invoice.school_id == current_user.school_id)
    if current_user.role == RoleEnum.STUDENT:
        query = query.where(Invoice.student_id == current_user.id)
    result = await db.execute(query)
    invoices = result.scalars().all()
    today = date.today()
    for inv in invoices:
        if inv.status == "pending" and inv.due_date < today:
            inv.status = "overdue"
    await db.commit()
    student_ids = {i.student_id for i in invoices}
    students = {}
    if student_ids:
        res = await db.execute(select(User).where(User.id.in_(student_ids)))
        students = {u.id: u.full_name for u in res.scalars().all()}
    return [
        InvoiceOut(
            id=i.id, student_id=i.student_id, amount=float(i.amount),
            due_date=i.due_date, status=i.status, description=i.description,
            student_name=students.get(i.student_id), course_title=i.description
        ) for i in invoices
    ]

@router.post("/invoices/{invoice_id}/pay")
async def pay_invoice(invoice_id: int, db: AsyncSession = Depends(get_db),
                      current_user: User = Depends(require_roles(RoleEnum.OWNER))):
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.school_id == current_user.school_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    inv.status = "paid"
    inv.paid_at = datetime.utcnow()
    await db.commit()
    return {"ok": True, "status": "paid"}

@router.post("/invoices")
async def create_invoice(student_id: int, amount: float, description: str, due_date: date,
                         db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(require_roles(RoleEnum.OWNER))):
    inv = Invoice(
        school_id=current_user.school_id, student_id=student_id,
        amount=amount, due_date=due_date, description=description, status="pending"
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return {"id": inv.id, "status": inv.status}


# ========== STUDENT PROFILE ==========
@router.get("/students/{student_id}/profile")
async def student_profile(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.OWNER, RoleEnum.TEACHER)),
):
    result = await db.execute(
        select(User).where(
            User.id == student_id,
            User.school_id == current_user.school_id,
            User.role == RoleEnum.STUDENT,
        )
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student not found")

    # Enrollments / courses
    enr_q = await db.execute(
        select(Enrollment)
        .options(selectinload(Enrollment.group).selectinload(Group.course))
        .where(
            Enrollment.student_id == student_id,
            Enrollment.school_id == current_user.school_id,
            Enrollment.is_active == True,
        )
    )
    enrollments = enr_q.scalars().all()
    enr_ids = [e.id for e in enrollments]
    courses = [
        {
            "enrollment_id": e.id,
            "group_id": e.group_id,
            "group_name": e.group.name if e.group else None,
            "course_title": e.group.course.title if e.group and e.group.course else None,
            "start_date": str(e.start_date),
        }
        for e in enrollments
    ]

    # Grades
    grades_out = []
    if enr_ids:
        gq = await db.execute(
            select(Grade)
            .options(selectinload(Grade.enrollment).selectinload(Enrollment.group).selectinload(Group.course))
            .where(Grade.enrollment_id.in_(enr_ids), Grade.school_id == current_user.school_id)
            .order_by(Grade.date.desc())
        )
        for g in gq.scalars().all():
            grades_out.append({
                "id": g.id,
                "date": str(g.date),
                "value": g.value,
                "comment": g.comment,
                "course_title": (
                    g.enrollment.group.course.title
                    if g.enrollment and g.enrollment.group and g.enrollment.group.course
                    else None
                ),
            })

    # Attendance
    att_out = []
    if enr_ids:
        aq = await db.execute(
            select(Attendance)
            .options(selectinload(Attendance.enrollment).selectinload(Enrollment.group).selectinload(Group.course))
            .where(Attendance.enrollment_id.in_(enr_ids), Attendance.school_id == current_user.school_id)
            .order_by(Attendance.date.desc())
        )
        for a in aq.scalars().all():
            att_out.append({
                "id": a.id,
                "date": str(a.date),
                "status": a.status,
                "course_title": (
                    a.enrollment.group.course.title
                    if a.enrollment and a.enrollment.group and a.enrollment.group.course
                    else None
                ),
            })

    # Invoices
    iq = await db.execute(
        select(Invoice).where(
            Invoice.student_id == student_id,
            Invoice.school_id == current_user.school_id,
        )
    )
    invoices = iq.scalars().all()
    today = date.today()
    for inv in invoices:
        if inv.status == "pending" and inv.due_date < today:
            inv.status = "overdue"
    await db.commit()

    debts = {
        "paid": [],
        "pending": [],
        "overdue": [],
    }
    for inv in invoices:
        item = {
            "id": inv.id,
            "amount": float(inv.amount),
            "due_date": str(inv.due_date),
            "status": inv.status,
            "description": inv.description,
        }
        if inv.status == "paid":
            debts["paid"].append(item)
        elif inv.status == "overdue":
            debts["overdue"].append(item)
        else:
            debts["pending"].append(item)

    return {
        "id": student.id,
        "full_name": student.full_name,
        "email": student.email,
        "role": student.role.value,
        "courses": courses,
        "grades": grades_out,
        "attendance": att_out,
        "debts": debts,
    }
