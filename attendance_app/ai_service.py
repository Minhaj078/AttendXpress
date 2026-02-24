"""
AI Integration Service
- Class rush prediction based on historical patterns
- Smart scheduling recommendations
- Automated alerts
- Face recognition (optional, requires face_recognition library)
"""
import json
import random
from datetime import datetime, timedelta
from django.utils import timezone
from collections import defaultdict


class AIService:
    """AI-powered insights for makeup class scheduling and attendance."""

    @staticmethod
    def predict_attendance(course, scheduled_date, start_time):
        """
        Predict expected attendance for a makeup class.
        Uses historical attendance data + day/time factors.
        """
        from .models import MakeUpClass, AttendanceRecord

        # Get historical data for this course
        past_classes = MakeUpClass.objects.filter(
            course=course, status='completed'
        ).order_by('-scheduled_date')[:10]

        enrolled_count = course.students.count() or 30
        base_rate = 0.75

        if past_classes.exists():
            total_rate = 0
            for cls in past_classes:
                if enrolled_count > 0:
                    rate = cls.attendance_count / enrolled_count
                    total_rate += rate
            base_rate = total_rate / past_classes.count()

        # Day-of-week factor
        day = scheduled_date.weekday()
        day_factors = {0: 0.85, 1: 0.90, 2: 0.88, 3: 0.92, 4: 0.80, 5: 0.60, 6: 0.45}
        day_factor = day_factors.get(day, 0.80)

        # Time-of-day factor
        hour = start_time.hour
        if 9 <= hour <= 11:
            time_factor = 0.95
        elif 14 <= hour <= 16:
            time_factor = 0.90
        elif 17 <= hour <= 19:
            time_factor = 0.75
        else:
            time_factor = 0.65

        predicted_rate = base_rate * day_factor * time_factor
        predicted_count = int(enrolled_count * predicted_rate)

        rush_level = 'low'
        if predicted_rate > 0.85:
            rush_level = 'high'
        elif predicted_rate > 0.65:
            rush_level = 'medium'

        return {
            'predicted_count': predicted_count,
            'enrolled_count': enrolled_count,
            'predicted_rate': round(predicted_rate * 100, 1),
            'rush_level': rush_level,
            'confidence': round(min(0.95, 0.5 + past_classes.count() * 0.05), 2),
        }

    @staticmethod
    def get_schedule_recommendations(course, preferred_date_range=None):
        """
        Suggest optimal time slots for makeup classes.
        """
        from .models import MakeUpClass

        existing_classes = MakeUpClass.objects.filter(
            course=course, status__in=['scheduled', 'active']
        ).values_list('scheduled_date', 'start_time')

        booked_slots = [(d.isoformat(), t.strftime('%H:%M')) for d, t in existing_classes]

        recommendations = []
        base = timezone.now().date() + timedelta(days=1)

        slots = [('09:00', '10:30'), ('10:30', '12:00'), ('14:00', '15:30'), ('15:30', '17:00')]
        good_days = [0, 1, 2, 3]  # Mon-Thu

        for i in range(14):
            check_date = base + timedelta(days=i)
            if check_date.weekday() in good_days:
                for start, end in slots:
                    if (check_date.isoformat(), start) not in booked_slots:
                        score = AIService._score_slot(check_date, start)
                        recommendations.append({
                            'date': check_date.isoformat(),
                            'day': check_date.strftime('%A'),
                            'start_time': start,
                            'end_time': end,
                            'score': score,
                            'reason': AIService._slot_reason(check_date, start),
                        })
                if len(recommendations) >= 5:
                    break

        recommendations.sort(key=lambda x: x['score'], reverse=True)
        return recommendations[:5]

    @staticmethod
    def _score_slot(date, time_str):
        hour = int(time_str.split(':')[0])
        day = date.weekday()
        score = 100
        if day in [1, 2, 3]:
            score += 10
        if 9 <= hour <= 11:
            score += 20
        elif 14 <= hour <= 16:
            score += 15
        return score

    @staticmethod
    def _slot_reason(date, time_str):
        hour = int(time_str.split(':')[0])
        day = date.weekday()
        reasons = []
        if day in [1, 2]:
            reasons.append("Mid-week slots see higher attendance")
        if 9 <= hour <= 11:
            reasons.append("Morning sessions have best engagement")
        elif 14 <= hour <= 16:
            reasons.append("Afternoon slots are well-attended")
        return '; '.join(reasons) if reasons else "Good availability window"

    @staticmethod
    def analyze_attendance_patterns(course):
        """Analyze attendance trends and generate insights."""
        from .models import MakeUpClass, AttendanceRecord

        classes = MakeUpClass.objects.filter(course=course, status='completed')
        if not classes.exists():
            return {'message': 'Not enough data for analysis yet.', 'insights': []}

        insights = []
        enrolled = course.students.count() or 1

        # Day analysis
        day_stats = defaultdict(list)
        for cls in classes:
            day = cls.scheduled_date.strftime('%A')
            rate = cls.attendance_count / enrolled * 100
            day_stats[day].append(rate)

        best_day = max(day_stats, key=lambda d: sum(day_stats[d]) / len(day_stats[d]), default=None)
        if best_day:
            avg = sum(day_stats[best_day]) / len(day_stats[best_day])
            insights.append({
                'type': 'best_day',
                'icon': '📅',
                'text': f'{best_day} shows the highest average attendance ({avg:.1f}%)',
                'severity': 'success'
            })

        # Overall trend
        rates = [cls.attendance_count / enrolled * 100 for cls in classes.order_by('scheduled_date')]
        if len(rates) >= 3:
            recent_avg = sum(rates[-3:]) / 3
            older_avg = sum(rates[:3]) / 3
            trend = 'improving' if recent_avg > older_avg else 'declining'
            emoji = '📈' if trend == 'improving' else '📉'
            insights.append({
                'type': 'trend',
                'icon': emoji,
                'text': f'Attendance is {trend} (recent: {recent_avg:.1f}% vs earlier: {older_avg:.1f}%)',
                'severity': 'info' if trend == 'improving' else 'warning'
            })

        return {'insights': insights, 'total_classes': classes.count()}

    @staticmethod
    def generate_auto_alerts(makeup_class):
        """Generate automated notifications for a makeup class."""
        from .models import Notification

        alerts = []
        enrolled_students = makeup_class.course.students.all()

        # Alert all enrolled students
        for student in enrolled_students:
            notif = Notification(
                recipient=student,
                notification_type='makeup_scheduled',
                title=f'Makeup Class: {makeup_class.course.code}',
                message=(
                    f'A makeup class "{makeup_class.title}" has been scheduled for '
                    f'{makeup_class.scheduled_date.strftime("%B %d, %Y")} at '
                    f'{makeup_class.start_time.strftime("%I:%M %p")} in {makeup_class.venue}. '
                    f'Your remedial code will be shared before the session.'
                ),
                related_class=makeup_class,
            )
            alerts.append(notif)

        if alerts:
            Notification.objects.bulk_create(alerts)

        return len(alerts)

    @staticmethod
    def send_code_notification(makeup_class):
        """Notify students when remedial code is activated."""
        from .models import Notification

        enrolled_students = makeup_class.course.students.all()
        alerts = []
        for student in enrolled_students:
            notif = Notification(
                recipient=student,
                notification_type='code_generated',
                title=f'Attendance Code Active: {makeup_class.course.code}',
                message=(
                    f'The remedial code for "{makeup_class.title}" is now active. '
                    f'Use code: {makeup_class.remedial_code} to mark your attendance. '
                    f'Code expires at {makeup_class.code_expiry.strftime("%I:%M %p") if makeup_class.code_expiry else "end of session"}.'
                ),
                related_class=makeup_class,
            )
            alerts.append(notif)

        if alerts:
            Notification.objects.bulk_create(alerts)
        return len(alerts)
