from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('', views.login_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Makeup Classes
    path('makeup/', views.makeup_list, name='makeup_list'),
    path('makeup/schedule/', views.schedule_makeup, name='schedule_makeup'),
    path('makeup/<int:pk>/', views.makeup_detail, name='makeup_detail'),
    path('makeup/<int:pk>/activate/', views.activate_code, name='activate_code'),
    path('makeup/<int:pk>/complete/', views.complete_class, name='complete_class'),
    path('makeup/<int:pk>/regenerate-code/', views.regenerate_code, name='regenerate_code'),

    # Attendance
    path('attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('attendance/my/', views.my_attendance, name='my_attendance'),

    # Courses
    path('courses/', views.course_list, name='course_list'),
    path('courses/add/', views.add_course, name='add_course'),
    path('courses/enroll/', views.enroll_course, name='enroll_course'),

    # Notifications
    path('notifications/', views.notifications, name='notifications'),

    # AI Analytics
    path('ai-analytics/', views.ai_analytics, name='ai_analytics'),

    # API
    path('api/unread-count/', views.api_unread_count, name='api_unread_count'),
    path('api/attendance-chart/<int:makeup_pk>/', views.api_attendance_chart, name='api_attendance_chart'),
]
