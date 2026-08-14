import pytest, httpx
from config import TARGETS, auth_headers, endpoint

@pytest.mark.parametrize("target", TARGETS.keys())
def test_list_records_returns_200(target):
    cfg = TARGETS[target]
    r = httpx.get(endpoint(cfg, "records"), headers=auth_headers(cfg))
    assert r.status_code == 200

@pytest.mark.parametrize("target", TARGETS.keys())
def test_create_record_returns_201_with_expected_shape(target):
    cfg = TARGETS[target]
    payload = {"status": "open", "payload": {}}
    if target == "supabase":
        payload["org_id"] = cfg["org_a_id"]
    headers = auth_headers(cfg)
    headers["Prefer"] = "return=representation"  # PostgREST defaults to an empty body otherwise
    r = httpx.post(endpoint(cfg, "records"), json=payload, headers=headers)
    assert r.status_code in (200, 201)
    body = r.json()[0] if isinstance(r.json(), list) else r.json()
    assert {"id", "status", "payload"} <= body.keys()

@pytest.mark.parametrize("target", TARGETS.keys())
def test_unauthenticated_request_is_rejected(target):
    cfg = TARGETS[target]
    headers = {"apikey": cfg["apikey"]} if cfg.get("apikey") else {}
    r = httpx.get(endpoint(cfg, "records"), headers=headers)
    if target == "supabase":
        assert r.status_code == 200
        assert r.json() == []
    else:
        assert r.status_code in (401, 403)

@pytest.mark.parametrize("target", TARGETS.keys())
def test_report_view_returns_expected_fields(target):
    cfg = TARGETS[target]
    r = httpx.get(endpoint(cfg, "report_view"), headers=auth_headers(cfg))
    assert r.status_code == 200
    assert {"org_id", "total_records"} <= r.json()[0].keys()
