import argparse, os, random, uuid
from dotenv import load_dotenv
from faker import Faker

load_dotenv()

SCENARIOS = {"small": (5, 50), "growing": (25, 2000), "peak": (100, 20000)}

def generate(scenario, seed=42):
    random.seed(seed)
    fake = Faker(); Faker.seed(seed)
    n_orgs, n_records = SCENARIOS[scenario]

    orgs = [{"id": str(uuid.uuid4()), "name": fake.company()} for _ in range(n_orgs)]

    users = []
    for org in orgs:
        n_users = random.randint(2, 8)
        for i in range(n_users):
            users.append({
                "local_id": str(uuid.uuid4()),
                "org_id": org["id"],
                "email": fake.unique.email(),
                "role": "owner" if i == 0 else "member",
                "password": f"seed-{uuid.uuid4().hex[:10]}",
            })

    records = []
    for org in orgs:
        org_users = [u for u in users if u["org_id"] == org["id"]]
        for _ in range(max(n_records // n_orgs, 1)):
            records.append({
                "id": str(uuid.uuid4()),
                "org_id": org["id"],
                "created_by_local": random.choice(org_users)["local_id"],
                "status": random.choice(["open", "closed", "pending"]),
                "payload": {"note": fake.sentence()},
            })

    return {"organisations": orgs, "users": users, "records": records}

def load_supabase(data):
    import requests  # imported here, not at module level, so the Django loader (which never calls
                      # this function) doesn't need `requests` installed in its own environment
    base_url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    rest_headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    r = requests.post(f"{base_url}/rest/v1/organisations", json=data["organisations"], headers=rest_headers)
    r.raise_for_status()

    id_map = {}
    for u in data["users"]:
        r = requests.post(
            f"{base_url}/auth/v1/admin/users",
            headers=rest_headers,
            json={
                "email": u["email"],
                "password": u["password"],
                "email_confirm": True,
                "user_metadata": {"org_id": u["org_id"], "role": u["role"]},
            },
        )
        r.raise_for_status()
        id_map[u["local_id"]] = r.json()["id"]

    records_payload = [
        {
            "id": rec["id"], "org_id": rec["org_id"], "created_by": id_map[rec["created_by_local"]],
            "status": rec["status"], "payload": rec["payload"],
        }
        for rec in data["records"]
    ]
    r = requests.post(f"{base_url}/rest/v1/records", json=records_payload, headers=rest_headers)
    r.raise_for_status()

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", choices=SCENARIOS, required=True)
    p.add_argument("--target", choices=["supabase", "django"], required=True)
    args = p.parse_args()

    data = generate(args.scenario)

    if args.target == "supabase":
        load_supabase(data)
    else:
        raise SystemExit(
            "For Django, seed via the ORM management command instead (faster, no HTTP round trips):\n"
            "  docker compose -f django-variant/docker-compose.yml run --rm web python manage.py seed_data --scenario " + args.scenario
        )

    primary = next(u for u in data["users"] if u["role"] == "owner")
    print(f"Generated {len(data['records'])} records across {len(data['organisations'])} orgs.")
    print(f"Primary test user -> email: {primary['email']}  password: {primary['password']}  org_id: {primary['org_id']}")
