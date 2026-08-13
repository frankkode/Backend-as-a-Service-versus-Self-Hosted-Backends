from rest_framework import serializers
from .models import Organisation, UserAccount, Record, FileUpload

class RecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = Record
        fields = ["id", "org", "created_by", "status", "payload", "updated_at"]
        read_only_fields = ["id", "created_by", "updated_at"]

class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = ["id", "name", "created_at"]
        read_only_fields = fields

class FileUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileUpload
        fields = ["id", "owner", "path", "uploaded_at"]
        read_only_fields = ["id", "owner", "uploaded_at"]
