from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.views.decorators.http import require_POST
import json

from .models import (
    UserProfile, Course, MakeUpClass, AttendanceRecord, Notification, AIInsight
)
from .forms import (
    CustomLoginForm, RegisterForm, MakeUpClassForm, AttendanceCodeForm, CourseForm
)
from .ai_service import AIService


# ─── Auth Views ────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = CustomLoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect('dashboard')
    return render(request, 'attendance_app/login.html', {'form': form})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.first_name = form.cleaned_data['first_name']
        user.last_name = form.cleaned_data['last_name']
        user.email = form.cleaned_data['email']
        user.save()
        UserProfile.objects.create(
            user=user,
            role=form.cleaned_data['role'],
            department=form.cleaned_data.get('department', ''),
            student_id=form.cleaned_data.get('student_id', ''),
            phone=form.cleaned_data.get('phone', ''),
        )
        login(request, user)
        messages.success(request, f'Welcome, {user.first_name}! Account created successfully.')
        return redirect('dashboard')
    return render(request, 'attendance_app/register.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


# ─── Dashboard ─────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    if profile.role == 'faculty':
        return faculty_dashboard(request, profile, unread_count)
    return student_dashboard(request, profile, unread_count)


def faculty_dashboard(request, profile, unread_count):
    courses = Course.objects.filter(faculty=request.user)
    upcoming = MakeUpClass.objects.filter(
        faculty=request.user,
        status__in=['scheduled', 'active'],
        scheduled_date__gte=timezone.now().date()
    ).order_by('scheduled_date', 'start_time')[:5]
    recent = MakeUpClass.objects.filter(
        faculty=request.user, status='completed'
    ).order_by('-scheduled_date')[:5]
    total_makeup = MakeUpClass.objects.filter(faculty=request.user).count()
    total_students = sum(c.students.count() for c in courses)

    ctx = {
        'profile': profile,
        'courses': courses,
        'upcoming_classes': upcoming,
        'recent_classes': recent,
        'total_makeup': total_makeup,
        'total_students': total_students,
        'unread_count': unread_count,
    }
    return render(request, 'attendance_app/faculty_dashboard.html', ctx)


def student_dashboard(request, profile, unread_count):
    enrolled_courses = request.user.enrolled_courses.all()
    upcoming = MakeUpClass.objects.filter(
        course__in=enrolled_courses,
        status__in=['scheduled', 'active'],
        scheduled_date__gte=timezone.now().date()
    ).order_by('scheduled_date')[:5]

    my_attendance = AttendanceRecord.objects.filter(
        student=request.user, is_present=True
    ).count()
    total_possible = MakeUpClass.objects.filter(
        course__in=enrolled_courses, status='completed'
    ).count()

    ctx = {
        'profile': profile,
        'enrolled_courses': enrolled_courses,
        'upcoming_classes': upcoming,
        'my_attendance': my_attendance,
        'total_possible': total_possible,
        'attendance_rate': round((my_attendance / total_possible * 100) if total_possible else 0, 1),
        'unread_count': unread_count,
    }
    return render(request, 'attendance_app/student_dashboard.html', ctx)


# ─── Makeup Class Views ────────────────────────────────────────────────────────

@login_required
def schedule_makeup(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    if profile.role != 'faculty':
        messages.error(request, 'Only faculty members can schedule makeup classes.')
        return redirect('dashboard')

    form = MakeUpClassForm(request.POST or None, faculty=request.user)
    ai_recommendations = None

    if request.method == 'POST' and form.is_valid():
        makeup = form.save(commit=False)
        makeup.faculty = request.user
        makeup.save()

        # AI: generate alerts automatically
        count = AIService.generate_auto_alerts(makeup)

        # AI: predict attendance
        prediction = AIService.predict_attendance(
            makeup.course, makeup.scheduled_date, makeup.start_time
        )
        makeup.predicted_attendance = prediction['predicted_count']
        makeup.save()

        messages.success(
            request,
            f'Makeup class scheduled! Remedial Code: <strong>{makeup.remedial_code}</strong>. '
            f'{count} students notified.'
        )
        return redirect('makeup_detail', pk=makeup.pk)

    # AI scheduling recommendations
    course_id = request.GET.get('course')
    if course_id:
        try:
            course = Course.objects.get(pk=course_id, faculty=request.user)
            ai_recommendations = AIService.get_schedule_recommendations(course)
        except Course.DoesNotExist:
            pass

    return render(request, 'attendance_app/schedule_makeup.html', {
        'form': form,
        'profile': profile,
        'ai_recommendations': ai_recommendations,
    })


@login_required
def makeup_list(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')

    if profile.role == 'faculty':
        qs = MakeUpClass.objects.filter(faculty=request.user)
    else:
        enrolled = request.user.enrolled_courses.all()
        qs = MakeUpClass.objects.filter(course__in=enrolled)

    if status_filter:
        qs = qs.filter(status=status_filter)
    if search:
        qs = qs.filter(
            Q(title__icontains=search) | Q(course__name__icontains=search) |
            Q(course__code__icontains=search)
        )

    qs = qs.order_by('-scheduled_date', '-start_time')
    return render(request, 'attendance_app/makeup_list.html', {
        'classes': qs, 'profile': profile,
        'status_filter': status_filter, 'search': search,
    })


@login_required
def makeup_detail(request, pk):
    makeup = get_object_or_404(MakeUpClass, pk=pk)
    profile = get_object_or_404(UserProfile, user=request.user)

    # Check access
    if profile.role == 'faculty' and makeup.faculty != request.user:
        messages.error(request, 'Access denied.')
        return redirect('makeup_list')
    if profile.role == 'student' and not makeup.course.students.filter(pk=request.user.pk).exists():
        messages.error(request, 'You are not enrolled in this course.')
        return redirect('dashboard')

    attendance_records = AttendanceRecord.objects.filter(makeup_class=makeup).select_related('student')
    enrolled_count = makeup.course.students.count()

    ai_insights = None
    if profile.role == 'faculty':
        ai_insights = AIService.analyze_attendance_patterns(makeup.course)
        prediction = AIService.predict_attendance(makeup.course, makeup.scheduled_date, makeup.start_time)
    else:
        prediction = None
        my_record = AttendanceRecord.objects.filter(makeup_class=makeup, student=request.user).first()

    return render(request, 'attendance_app/makeup_detail.html', {
        'makeup': makeup,
        'profile': profile,
        'attendance_records': attendance_records,
        'enrolled_count': enrolled_count,
        'ai_insights': ai_insights,
        'prediction': prediction,
        'my_record': my_record if profile.role == 'student' else None,
    })


@login_required
@require_POST
def activate_code(request, pk):
    makeup = get_object_or_404(MakeUpClass, pk=pk, faculty=request.user)
    makeup.status = 'active'
    makeup.save()
    AIService.send_code_notification(makeup)
    messages.success(request, f'Remedial code <strong>{makeup.remedial_code}</strong> is now ACTIVE. Students have been notified.')
    return redirect('makeup_detail', pk=pk)


@login_required
@require_POST
def complete_class(request, pk):
    makeup = get_object_or_404(MakeUpClass, pk=pk, faculty=request.user)
    makeup.status = 'completed'
    makeup.save()
    messages.success(request, 'Class marked as completed.')
    return redirect('makeup_detail', pk=pk)


@login_required
@require_POST
def regenerate_code(request, pk):
    profile = get_object_or_404(UserProfile, user=request.user)
    if profile.role != 'faculty':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    makeup = get_object_or_404(MakeUpClass, pk=pk, faculty=request.user)
    from .models import generate_remedial_code
    makeup.remedial_code = generate_remedial_code()
    makeup.save()
    return JsonResponse({'code': makeup.remedial_code, 'success': True})


# ─── Attendance Views ──────────────────────────────────────────────────────────

@login_required
def mark_attendance(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    if profile.role != 'student':
        messages.error(request, 'Only students can mark attendance.')
        return redirect('dashboard')

    form = AttendanceCodeForm(request.POST or None)
    result = None

    if request.method == 'POST' and form.is_valid():
        code = form.cleaned_data['remedial_code']
        try:
            makeup = MakeUpClass.objects.get(remedial_code=code)
            enrolled = makeup.course.students.filter(pk=request.user.pk).exists()

            if not enrolled:
                result = {'status': 'error', 'message': 'You are not enrolled in this course.'}
            elif not makeup.is_code_valid:
                result = {'status': 'error', 'message': f'This code is not currently active. Class status: {makeup.get_status_display()}.'}
            elif AttendanceRecord.objects.filter(makeup_class=makeup, student=request.user).exists():
                result = {'status': 'warning', 'message': f'You have already marked attendance for "{makeup.title}".'}
            else:
                x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
                ip = x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR')

                AttendanceRecord.objects.create(
                    makeup_class=makeup,
                    student=request.user,
                    is_present=True,
                    verification_method='code',
                    ip_address=ip,
                )
                Notification.objects.create(
                    recipient=makeup.faculty,
                    notification_type='attendance_marked',
                    title='Attendance Marked',
                    message=f'{request.user.get_full_name()} marked attendance for "{makeup.title}".',
                    related_class=makeup,
                )
                result = {
                    'status': 'success',
                    'message': f'Attendance marked successfully for "{makeup.title}" — {makeup.course.code}!',
                    'class': makeup.title,
                }
        except MakeUpClass.DoesNotExist:
            result = {'status': 'error', 'message': 'Invalid remedial code. Please check and try again.'}

    return render(request, 'attendance_app/mark_attendance.html', {
        'form': form, 'result': result, 'profile': profile
    })


@login_required
def my_attendance(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    records = AttendanceRecord.objects.filter(
        student=request.user
    ).select_related('makeup_class', 'makeup_class__course').order_by('-marked_at')

    course_filter = request.GET.get('course', '')
    if course_filter:
        records = records.filter(makeup_class__course__code=course_filter)

    courses = request.user.enrolled_courses.all()
    return render(request, 'attendance_app/my_attendance.html', {
        'records': records, 'profile': profile, 'courses': courses, 'course_filter': course_filter
    })


# ─── Course Views ──────────────────────────────────────────────────────────────

@login_required
def course_list(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    if profile.role == 'faculty':
        courses = Course.objects.filter(faculty=request.user)
    else:
        courses = request.user.enrolled_courses.all()
    return render(request, 'attendance_app/course_list.html', {'courses': courses, 'profile': profile})


@login_required
def add_course(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    if profile.role != 'faculty':
        return redirect('dashboard')

    form = CourseForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        course = form.save(commit=False)
        course.faculty = request.user
        course.save()
        messages.success(request, f'Course "{course.name}" created successfully.')
        return redirect('course_list')

    return render(request, 'attendance_app/add_course.html', {'form': form, 'profile': profile})


@login_required
@require_POST
def enroll_course(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    if profile.role != 'student':
        return JsonResponse({'error': 'Only students can enroll'}, status=403)
    course_code = request.POST.get('course_code', '').strip().upper()
    try:
        course = Course.objects.get(code=course_code)
        course.students.add(request.user)
        return JsonResponse({'success': True, 'course': course.name, 'code': course.code})
    except Course.DoesNotExist:
        return JsonResponse({'error': 'Course not found with that code.'}, status=404)


# ─── Notification Views ────────────────────────────────────────────────────────

@login_required
def notifications(request):
    notifs = Notification.objects.filter(recipient=request.user).select_related('related_class')
    notifs.filter(is_read=False).update(is_read=True)
    return render(request, 'attendance_app/notifications.html', {
        'notifications': notifs,
        'profile': get_object_or_404(UserProfile, user=request.user),
    })


# ─── AI / Analytics Views ──────────────────────────────────────────────────────

@login_required
def ai_analytics(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    if profile.role != 'faculty':
        return redirect('dashboard')

    courses = Course.objects.filter(faculty=request.user)
    selected_course_id = request.GET.get('course')
    insights = None
    recommendations = None
    prediction = None

    if selected_course_id:
        try:
            course = courses.get(pk=selected_course_id)
            insights = AIService.analyze_attendance_patterns(course)
            recommendations = AIService.get_schedule_recommendations(course)
            # Aggregate stats
            from datetime import date
            import datetime
            future_date = date.today() + datetime.timedelta(days=7)
            future_time = datetime.time(9, 0)
            prediction = AIService.predict_attendance(course, future_date, future_time)
        except Course.DoesNotExist:
            pass

    return render(request, 'attendance_app/ai_analytics.html', {
        'profile': profile,
        'courses': courses,
        'selected_course_id': selected_course_id,
        'insights': insights,
        'recommendations': recommendations,
        'prediction': prediction,
    })


# ─── API Endpoints ─────────────────────────────────────────────────────────────

@login_required
def api_unread_count(request):
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'count': count})


@login_required
def api_attendance_chart(request, makeup_pk):
    makeup = get_object_or_404(MakeUpClass, pk=makeup_pk)
    records = AttendanceRecord.objects.filter(makeup_class=makeup)
    present = records.filter(is_present=True).count()
    enrolled = makeup.course.students.count()
    absent = enrolled - present
    return JsonResponse({
        'present': present,
        'absent': max(absent, 0),
        'enrolled': enrolled,
        'rate': round(present / enrolled * 100, 1) if enrolled else 0,
    })
