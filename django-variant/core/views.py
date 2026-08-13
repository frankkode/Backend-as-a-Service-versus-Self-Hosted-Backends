from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, F
from django.db.models.functions import TruncMonth
from .models import Organisation, Record, FileUpload
from .serializers import RecordSerializer, OrganisationSerializer, FileUploadSerializer
from .permissions import IsOrgMember, IsOwnerOrCreator

class RecordViewSet(viewsets.ModelViewSet):
    serializer_class = RecordSerializer
    permission_classes = [IsAuthenticated, IsOrgMember, IsOwnerOrCreator]

    def get_queryset(self):
        return Record.objects.filter(org_id=self.request.user.org_id)

    def perform_create(self, serializer):
        serializer.save(org_id=self.request.user.org_id, created_by=self.request.user)

class OrganisationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrganisationSerializer
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get_queryset(self):
        return Organisation.objects.filter(id=self.request.user.org_id)

class FileUploadViewSet(viewsets.ModelViewSet):
    serializer_class = FileUploadSerializer
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get_queryset(self):
        return FileUpload.objects.filter(owner__org_id=self.request.user.org_id)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

class ReportView(APIView):
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get(self, request):
        qs = (
            Record.objects.filter(org_id=request.user.org_id)
            .annotate(period=TruncMonth("updated_at"))
            .values("org_id", "period")
            .annotate(total_records=Count("id"))
        )
        return Response(list(qs))
