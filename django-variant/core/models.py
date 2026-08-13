import uuid
from django.db import models

class Organisation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

class UserAccount(models.Model):
    ROLE_CHOICES = [("owner", "Owner"), ("member", "Member")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="members")
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="member")
    created_at = models.DateTimeField(auto_now_add=True)

class Record(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="records")
    created_by = models.ForeignKey(UserAccount, on_delete=models.PROTECT)
    status = models.CharField(max_length=32, default="open")
    payload = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

class FileUpload(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name="uploads")
    path = models.CharField(max_length=512)
    uploaded_at = models.DateTimeField(auto_now_add=True)
