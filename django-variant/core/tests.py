from django.test import TestCase
from unittest.mock import Mock
from core.permissions import IsOrgMember, IsOwnerOrCreator

class PermissionTests(TestCase):
    def test_org_member_matches_same_org(self):
        request = Mock(user=Mock(org_id="org-1"))
        obj = Mock(org_id="org-1")
        self.assertTrue(IsOrgMember().has_object_permission(request, None, obj))

    def test_org_member_rejects_different_org(self):
        request = Mock(user=Mock(org_id="org-1"))
        obj = Mock(org_id="org-2")
        self.assertFalse(IsOrgMember().has_object_permission(request, None, obj))

    def test_owner_can_update_anyones_record(self):
        request = Mock(user=Mock(id="u1", role="owner"), method="PATCH")
        obj = Mock(created_by_id="u2")
        self.assertTrue(IsOwnerOrCreator().has_object_permission(request, None, obj))

    def test_member_cannot_update_someone_elses_record(self):
        request = Mock(user=Mock(id="u1", role="member"), method="PATCH")
        obj = Mock(created_by_id="u2")
        self.assertFalse(IsOwnerOrCreator().has_object_permission(request, None, obj))
