from django.urls import path

from listings import views

app_name = "listings"

urlpatterns = [
    path("", views.ListingListView.as_view(), name="list"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("<int:pk>/", views.ListingDetailView.as_view(), name="detail"),
]
