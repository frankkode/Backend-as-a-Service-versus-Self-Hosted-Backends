import sys
sys.path.insert(0, "/shared/data-generator")
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from core.models import Organisation, UserAccount, Record
from seed import generate

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--scenario", required=True)

    def handle(self, *args, **options):
        data = generate(options["scenario"])
        Organisation.objects.bulk_create(
            [Organisation(id=o["id"], name=o["name"]) for o in data["organisations"]])
        UserAccount.objects.bulk_create(
            [UserAccount(id=u["local_id"], org_id=u["org_id"], email=u["email"], role=u["role"],
                          password_hash=make_password(u["password"])) for u in data["users"]])
        Record.objects.bulk_create(
            [Record(id=r["id"], org_id=r["org_id"], created_by_id=r["created_by_local"],
                    status=r["status"], payload=r["payload"]) for r in data["records"]])
        primary = next(u for u in data["users"] if u["role"] == "owner")
        self.stdout.write(f"Seeded {len(data['records'])} records.")
        self.stdout.write(
            f"Primary test user -> email: {primary['email']}  password: {primary['password']}  org_id: {primary['org_id']}"
        )
