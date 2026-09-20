from django.urls import path

from . import views

urlpatterns = [
    path('', views.home_redirect, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Admin — exam periods (the roster + hall catalog live here)
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('period/<int:period_id>/', views.period_detail, name='period_detail'),
    path('period/<int:period_id>/upload-roster/', views.upload_roster, name='upload_roster'),
    path('period/<int:period_id>/upload-timetable/', views.upload_timetable, name='upload_timetable'),
    path('period/<int:period_id>/hall-tickets/', views.download_hall_tickets, name='download_hall_tickets'),

    # Admin — a single exam session: halls, invigilators, auto-assign
    path('exam-session/<int:session_id>/', views.exam_session_detail, name='exam_session_detail'),
    path('exam-session/<int:session_id>/add-hall/', views.add_exam_hall, name='add_exam_hall'),
    path('exam-session/<int:session_id>/auto-assign/', views.auto_assign_students, name='auto_assign_students'),
    path('exam-session/<int:session_id>/confirm/', views.confirm_allocation, name='confirm_allocation'),
    path('exam-session/<int:session_id>/cancel/', views.cancel_exam_session, name='cancel_exam_session'),
    path('exam-hall/<int:exam_hall_id>/remove/', views.remove_exam_hall, name='remove_exam_hall'),
    path('exam-hall/<int:exam_hall_id>/assign-invigilator/', views.assign_exam_hall_invigilator, name='assign_exam_hall_invigilator'),

    # Admin — staff accounts
    path('users/', views.manage_users, name='manage_users'),
    path('users/<int:user_id>/toggle/', views.toggle_user_active, name='toggle_user_active'),

    # Invigilator
    path('invigilator/', views.invigilator_dashboard, name='invigilator_dashboard'),
    path('api/hall-roster/', views.hall_roster_json, name='hall_roster_json'),
    path('api/verify-qr/', views.verify_qr, name='verify_qr'),
    path('raise-alert/', views.raise_alert, name='raise_alert'),

    # Control room
    path('control-room/', views.control_room, name='control_room'),
    path('api/update-alert/<int:alert_id>/', views.update_alert, name='update_alert'),
    path('reports/', views.reports, name='reports'),
    path('reports/<int:session_id>/export/', views.export_session_report, name='export_session_report'),
]
