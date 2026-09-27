from django.urls import path

from . import api_views, views

urlpatterns = [
    path('', views.home_redirect, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Admin — exam periods & workflow
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('setup-session/', views.setup_session, name='setup_session'),
    path('upload-mapping/', views.upload_mapping, name='upload_mapping'),
    path('period/<int:period_id>/', views.period_detail, name='period_detail'),
    path('period/<int:period_id>/edit/', views.edit_period, name='edit_period'),
    path('period/<int:period_id>/stop/', views.stop_period, name='stop_period'),
    path('period/<int:period_id>/delete/', views.delete_period, name='delete_period'),
    path('period/<int:period_id>/upload-roster/', views.upload_roster, name='upload_roster'),
    path('period/<int:period_id>/upload-timetable/', views.upload_timetable, name='upload_timetable'),
    path('period/<int:period_id>/hall-tickets/', views.download_hall_tickets, name='download_hall_tickets'),
    path('period/<int:period_id>/add-student/', views.add_student, name='add_student'),

    # Admin — student roster management
    path('student/<int:student_id>/edit/', views.edit_student, name='edit_student'),
    path('student/<int:student_id>/toggle/', views.toggle_student_active, name='toggle_student_active'),
    path('student/<int:student_id>/delete/', views.delete_student, name='delete_student'),

    # Admin — section/hall manager (global)
    path('halls/', views.hall_manager, name='hall_manager'),
    path('halls/<int:hall_id>/edit/', views.edit_hall, name='edit_hall'),
    path('halls/<int:hall_id>/stop/', views.stop_hall, name='stop_hall'),
    path('halls/<int:hall_id>/delete/', views.delete_hall, name='delete_hall'),

    # Admin — a single exam session: halls, invigilators, auto-assign
    path('exam-session/<int:session_id>/', views.exam_session_detail, name='exam_session_detail'),
    path('exam-session/<int:session_id>/edit/', views.edit_exam_session, name='edit_exam_session'),
    path('exam-session/<int:session_id>/add-hall/', views.add_exam_hall, name='add_exam_hall'),
    path('exam-session/<int:session_id>/auto-assign/', views.auto_assign_students, name='auto_assign_students'),
    path('exam-session/<int:session_id>/confirm/', views.confirm_allocation, name='confirm_allocation'),
    path('exam-session/<int:session_id>/stop/', views.stop_exam_session, name='stop_exam_session'),
    path('exam-session/<int:session_id>/delete/', views.delete_exam_session, name='delete_exam_session'),
    path('exam-hall/<int:exam_hall_id>/remove/', views.remove_exam_hall, name='remove_exam_hall'),
    path('exam-hall/<int:exam_hall_id>/capacity/', views.edit_exam_hall_capacity, name='edit_exam_hall_capacity'),
    path('exam-hall/<int:exam_hall_id>/assign-invigilator/', views.assign_exam_hall_invigilator, name='assign_exam_hall_invigilator'),

    # Admin — staff accounts
    path('users/', views.manage_users, name='manage_users'),
    path('users/<int:user_id>/toggle/', views.toggle_user_active, name='toggle_user_active'),

    # Invigilator web
    path('invigilator/', views.invigilator_dashboard, name='invigilator_dashboard'),
    path('api/hall-roster/', views.hall_roster_json, name='hall_roster_json'),
    path('api/verify-qr/', views.verify_qr, name='verify_qr'),
    path('raise-alert/', views.raise_alert, name='raise_alert'),

    # Invigilator Mobile REST API
    path('api/invigilator/login/', api_views.api_invigilator_login, name='api_invigilator_login'),
    path('api/invigilator/logout/', api_views.api_invigilator_logout, name='api_invigilator_logout'),
    path('api/invigilator/dashboard/', api_views.api_invigilator_dashboard, name='api_invigilator_dashboard'),
    path('api/invigilator/roster/', api_views.api_invigilator_roster, name='api_invigilator_roster'),
    path('api/invigilator/verify-qr/', api_views.api_invigilator_verify_qr, name='api_invigilator_verify_qr'),
    path('api/invigilator/raise-alert/', api_views.api_invigilator_raise_alert, name='api_invigilator_raise_alert'),
    path('api/invigilator/alert-types/', api_views.api_invigilator_alert_types, name='api_invigilator_alert_types'),

    # Control room
    path('control-room/', views.control_room, name='control_room'),
    path('api/update-alert/<int:alert_id>/', views.update_alert, name='update_alert'),
    path('reports/', views.reports, name='reports'),
    path('reports/<int:session_id>/export/', views.export_session_report, name='export_session_report'),
]
