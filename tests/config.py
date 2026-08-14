import os
from dotenv import load_dotenv

load_dotenv()

TARGETS = {
    "supabase": {
        "base_url": f"{os.environ['SUPABASE_URL']}/rest/v1",
        "token": os.environ["SUPABASE_USER_JWT"],
        "user_a_token": os.environ["SUPABASE_USER_JWT"],
        "org_a_id": os.environ["SUPABASE_TEST_ORG_ID"],
        "other_org_record_id": os.environ.get("SUPABASE_OTHER_ORG_RECORD_ID", ""),
        "apikey": os.environ["SUPABASE_ANON_KEY"],
        "trailing_slash": False,   # PostgREST: /records, not /records/
        "org_field": "org_id",
    },
    "django": {
        "base_url": os.environ["DJANGO_BASE_URL"],
        "token": os.environ["DJANGO_USER_JWT"],
        "user_a_token": os.environ["DJANGO_USER_JWT"],
        "org_a_id": os.environ["DJANGO_TEST_ORG_ID"],
        "other_org_record_id": os.environ.get("DJANGO_OTHER_ORG_RECORD_ID", ""),
        "apikey": None,
        "trailing_slash": True,    # DRF router: /records/, required
        "org_field": "org",
    },
}

def auth_headers(cfg, token_key="token"):
    headers = {"Authorization": f"Bearer {cfg[token_key]}"}
    if cfg.get("apikey"):
        headers["apikey"] = cfg["apikey"]
    return headers

def endpoint(cfg, resource):
    return f"{cfg['base_url']}/{resource}/" if cfg["trailing_slash"] else f"{cfg['base_url']}/{resource}"
