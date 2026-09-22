from django.urls import path

from inspection import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.list_view, name="list"),
    path("presets/create/", views.preset_create_view, name="preset_create"),
    path("presets/<int:pk>/rename/", views.preset_rename_view, name="preset_rename"),
    path("presets/<int:pk>/delete/", views.preset_delete_view, name="preset_delete"),
    path("inspections/new/", views.create_view, name="create"),
    path("inspections/<int:pk>/", views.detail_view, name="detail"),
]
