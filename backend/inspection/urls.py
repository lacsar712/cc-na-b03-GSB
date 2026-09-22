from django.urls import path

from inspection import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.list_view, name="list"),
    path("inspections/new/", views.create_view, name="create"),
    path("inspections/<int:pk>/", views.detail_view, name="detail"),
    path("schemes/<int:pk>/apply/", views.scheme_apply_view, name="scheme_apply"),
    path("schemes/clear/", views.scheme_clear_view, name="scheme_clear"),
    path("schemes/new/", views.scheme_create_view, name="scheme_create"),
    path("schemes/<int:pk>/rename/", views.scheme_rename_view, name="scheme_rename"),
    path("schemes/<int:pk>/delete/", views.scheme_delete_view, name="scheme_delete"),
]
