"""REST API URL config (separate from HTML urls.py)."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from listings.api_views import ListingViewSet

router = DefaultRouter()
router.register("listings", ListingViewSet, basename="listing")

urlpatterns = [path("", include(router.urls))]
