from django.urls import path

from . import views

urlpatterns = [
    path('', views.home_redirect, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Admin
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('setup-session/', views.setup_session, name='setup_session'),
    path('session/<int:session_id>/', views.session_detail, name='session_detail'),
    path('session/<int:session_id>/toggle/', views.toggle_session, name='toggle_session'),
    path('session/<int:session_id>/auto-allocate/', views.auto_allocate_seating, name='auto_allocate_seating'),
    path('session/<int:session_id>/hall-tickets/', views.download_hall_tickets, name='download_hall_tickets'),
    path('hall/<int:hall_id>/assign-invigilator/', views.assign_invigilator, name='assign_invigilator'),
    path('upload-mapping/', views.upload_mapping, name='upload_mapping'),
    path('users/', views.manage_users, name='manage_users'),
    path('users/<int:user_id>/toggle/', views.toggle_user_active, name='toggle_user_active'),

    # Invigilator
    path('invigilator/', views.invigilator_dashboard, name='invigilator_dashboard'),
    path('api/hall-roster/', views.hall_roster_json, name='hall_roster_json'),
    path('api/verify-seat/', views.verify_seat, name='verify_seat'),
    path('raise-alert/', views.raise_alert, name='raise_alert'),

    # Control room
    path('control-room/', views.control_room, name='control_room'),
    path('api/update-alert/<int:alert_id>/', views.update_alert, name='update_alert'),
    path('reports/', views.reports, name='reports'),
    path('reports/<int:session_id>/export/', views.export_session_report, name='export_session_report'),
]
