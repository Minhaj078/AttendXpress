from django.contrib import admin
from .models import UserProfile, Course, MakeUpClass, AttendanceRecord, Notification, AIInsight


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'department', 'student_id']
    list_filter = ['role']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'faculty', 'department']


@admin.register(MakeUpClass)
class MakeUpClassAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'faculty', 'scheduled_date', 'status', 'remedial_code']
    list_filter = ['status', 'scheduled_date']
    search_fields = ['title', 'course__name', 'remedial_code']


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ['student', 'makeup_class', 'is_present', 'verification_method', 'marked_at']
    list_filter = ['is_present', 'verification_method']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'recipient', 'notification_type', 'is_read', 'created_at']


@admin.register(AIInsight)
class AIInsightAdmin(admin.ModelAdmin):
    list_display = ['course', 'insight_type', 'confidence_score', 'generated_at']
