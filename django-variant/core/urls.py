from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RecordViewSet, OrganisationViewSet, FileUploadViewSet, ReportView
from .views_auth import LoginView

router = DefaultRouter()
router.register("records", RecordViewSet, basename="record")
router.register("organisations", OrganisationViewSet, basename="organisation")
router.register("files", FileUploadViewSet, basename="fileupload")

urlpatterns = [
    path("token/", LoginView.as_view()),
    path("report_view/", ReportView.as_view()),
    path("", include(router.urls)),
]
