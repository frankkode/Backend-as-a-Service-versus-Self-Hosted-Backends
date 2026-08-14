import pytest, httpx
from config import TARGETS, auth_headers, endpoint

@pytest.mark.parametrize("target", TARGETS.keys())
def test_user_cannot_read_other_orgs_record(target):
    """
    Supabase (PostgREST) and Django express "you can't see this" differently, and both are
    correct for their own model: PostgREST applies RLS as a row filter, so a blocked row simply
    isn't in the result set (200, empty list). Django's get_queryset() filtering means the object
    genuinely isn't found for this user, so DRF raises a real 404.
    """
    cfg = TARGETS[target]
    if not cfg["other_org_record_id"]:
        pytest.skip("other_org_record_id not set in .env yet")
    headers = auth_headers(cfg, "user_a_token")
    if target == "supabase":
        r = httpx.get(f"{cfg['base_url']}/records?id=eq.{cfg['other_org_record_id']}&select=*", headers=headers)
        assert r.status_code == 200
        assert r.json() == []
    else:
        r = httpx.get(f"{cfg['base_url']}/records/{cfg['other_org_record_id']}/", headers=headers)
        assert r.status_code == 404

@pytest.mark.parametrize("target", TARGETS.keys())
def test_list_never_leaks_other_orgs_rows(target):
    cfg = TARGETS[target]
    r = httpx.get(endpoint(cfg, "records"), headers=auth_headers(cfg, "user_a_token"))
    assert r.status_code == 200
    assert all(row[cfg["org_field"]] == cfg["org_a_id"] for row in r.json())
