from django.db import models
from django.contrib.auth.models import User
import random
import string
from datetime import timedelta
from django.utils import timezone


def generate_remedial_code():
    """Generate a unique 8-character alphanumeric remedial code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


class UserProfile(models.Model):
    ROLE_CHOICES = [('faculty', 'Faculty'), ('student', 'Student')]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    department = models.CharField(max_length=100, blank=True)
    student_id = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    face_encoding = models.TextField(blank=True, null=True)  # JSON encoded face data

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.role})"

    class Meta:
        verbose_name = "User Profile"


class Course(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    faculty = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='courses_taught', limit_choices_to={'profile__role': 'faculty'}
    )
    students = models.ManyToManyField(User, related_name='enrolled_courses', blank=True)
    department = models.CharField(max_length=100, blank=True)
    semester = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class MakeUpClass(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='makeup_classes')
    faculty = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scheduled_makeup_classes')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    scheduled_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    venue = models.CharField(max_length=200)
    remedial_code = models.CharField(max_length=20, unique=True, default=generate_remedial_code)
    code_expiry = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    reason = models.TextField(blank=True, help_text="Reason for makeup class")
    max_attendance = models.IntegerField(default=100)
    ai_recommendations = models.TextField(blank=True, null=True)  # AI generated notes
    predicted_attendance = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.course.code} - {self.title} ({self.scheduled_date})"

    def save(self, *args, **kwargs):
        if not self.code_expiry and self.scheduled_date and self.end_time:
            import datetime
            dt = datetime.datetime.combine(self.scheduled_date, self.end_time)
            self.code_expiry = timezone.make_aware(dt) + timedelta(hours=1)
        super().save(*args, **kwargs)

    @property
    def is_code_valid(self):
        if self.status == 'active' and self.code_expiry:
            return timezone.now() < self.code_expiry
        return False

    @property
    def attendance_count(self):
        return self.attendance_records.filter(is_present=True).count()


class AttendanceRecord(models.Model):
    VERIFICATION_CHOICES = [
        ('code', 'Remedial Code'),
        ('face', 'Face Recognition'),
        ('manual', 'Manual'),
    ]
    makeup_class = models.ForeignKey(MakeUpClass, on_delete=models.CASCADE, related_name='attendance_records')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='makeup_attendance')
    is_present = models.BooleanField(default=False)
    marked_at = models.DateTimeField(auto_now_add=True)
    verification_method = models.CharField(max_length=20, choices=VERIFICATION_CHOICES, default='code')
    remarks = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    face_confidence = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ['makeup_class', 'student']
        verbose_name = "Attendance Record"

    def __str__(self):
        status = "Present" if self.is_present else "Absent"
        return f"{self.student.get_full_name()} - {self.makeup_class.title} [{status}]"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('makeup_scheduled', 'Makeup Class Scheduled'),
        ('code_generated', 'Remedial Code Generated'),
        ('attendance_marked', 'Attendance Marked'),
        ('reminder', 'Reminder'),
        ('alert', 'Alert'),
        ('ai_suggestion', 'AI Suggestion'),
    ]
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    related_class = models.ForeignKey(MakeUpClass, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} -> {self.recipient.username}"


class AIInsight(models.Model):
    INSIGHT_TYPE = [
        ('rush_prediction', 'Class Rush Prediction'),
        ('schedule_recommendation', 'Schedule Recommendation'),
        ('attendance_pattern', 'Attendance Pattern'),
    ]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='ai_insights')
    insight_type = models.CharField(max_length=30, choices=INSIGHT_TYPE)
    insight_data = models.JSONField()
    confidence_score = models.FloatField(default=0.0)
    generated_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.course.code} - {self.insight_type} ({self.confidence_score:.0%})"
