#!/usr/bin/env python
"""
Setup script to initialize the EduTrack database with sample data.
Run: python setup_demo.py
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'makeup_project.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User
from attendance_app.models import UserProfile, Course, MakeUpClass, AttendanceRecord
from datetime import date, time, timedelta

print("🎓 Setting up EduTrack demo data...")

# Create superuser
if not User.objects.filter(username='admin').exists():
    admin = User.objects.create_superuser('admin', 'admin@college.edu', 'admin123')
    UserProfile.objects.create(user=admin, role='faculty', department='Administration')
    print("✅ Admin user created: admin / admin123")

# Create faculty
if not User.objects.filter(username='faculty1').exists():
    fac = User.objects.create_user('faculty1', 'faculty1@college.edu', 'pass123')
    fac.first_name = 'Dr. Sarah'
    fac.last_name = 'Johnson'
    fac.save()
    UserProfile.objects.create(user=fac, role='faculty', department='Computer Science')
    print("✅ Faculty created: faculty1 / pass123")
else:
    fac = User.objects.get(username='faculty1')

# Create students
students = []
for i in range(1, 4):
    username = f'student{i}'
    if not User.objects.filter(username=username).exists():
        s = User.objects.create_user(username, f'{username}@college.edu', 'pass123')
        s.first_name = f'Student{i}'
        s.last_name = 'Smith'
        s.save()
        UserProfile.objects.create(user=s, role='student', student_id=f'CS-2024-{i:03d}', department='Computer Science')
        print(f"✅ Student created: {username} / pass123")
    else:
        s = User.objects.get(username=username)
    students.append(s)

# Create course
course, created = Course.objects.get_or_create(
    code='CS301',
    defaults={'name': 'Data Structures & Algorithms', 'faculty': fac, 'department': 'Computer Science', 'semester': 'Spring 2025'}
)
if created:
    course.students.set(students)
    print("✅ Course CS301 created")

# Create sample makeup classes
today = date.today()
classes_data = [
    ('Linked Lists Review', today + timedelta(days=3), time(9, 0), time(10, 30), 'Room 301', 'scheduled'),
    ('Trees & Graphs', today + timedelta(days=7), time(14, 0), time(15, 30), 'Room 205', 'scheduled'),
    ('Sorting Algorithms', today - timedelta(days=5), time(10, 0), time(11, 30), 'Room 301', 'completed'),
]

for title, sched_date, start, end, venue, status in classes_data:
    if not MakeUpClass.objects.filter(title=title, course=course).exists():
        mc = MakeUpClass.objects.create(
            course=course, faculty=fac, title=title,
            scheduled_date=sched_date, start_time=start, end_time=end,
            venue=venue, status=status,
            reason='Original class cancelled due to faculty conference'
        )
        if status == 'completed':
            # Add attendance records
            for student in students[:2]:
                AttendanceRecord.objects.get_or_create(
                    makeup_class=mc, student=student,
                    defaults={'is_present': True, 'verification_method': 'code'}
                )
        print(f"✅ Makeup class created: {title}")

print("\n🚀 Setup complete!")
print("=" * 50)
print("Login credentials:")
print("  Admin:    admin / admin123")
print("  Faculty:  faculty1 / pass123")
print("  Students: student1, student2, student3 / pass123")
print("\nRun server: python manage.py runserver")
print("Admin:      http://127.0.0.1:8000/admin/")
print("App:        http://127.0.0.1:8000/")
