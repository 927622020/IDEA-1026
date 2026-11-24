import json
from datetime import date, datetime, time, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

TENANT_ID = "1bb3a9f9-1b23-4f0a-8583-bf32a89490b9"
LOCATION_ID = "74920a2c-8934-42dc-b7c0-71c3e37cf114"
PRODUCT_ID = "5834570a-f728-4407-b341-fed73612259b"

API_URL = "http://localhost:8000/api/v1/sales"
TIMEZONE = ZoneInfo("Asia/Kolkata")

START_DATE = date(2026, 10, 27)
END_DATE = date(2026, 11, 23)

WEEKDAY_DEMAND = [85, 105, 95, 120, 110, 175, 210]

created = 0
current_date = START_DATE

while current_date <= END_DATE:
    quantity = WEEKDAY_DEMAND[current_date.weekday()]
    quantity += (current_date.day * 7) % 25

    sold_at = datetime.combine(
        current_date, time(12, 0), tzinfo=TIMEZONE
    )

    payload = {
        "location_id": LOCATION_ID,
        "product_id": PRODUCT_ID,
        "quantity": quantity,
        "sold_at": sold_at.isoformat(),
        "external_reference": (
            f"SYNTHETIC-DEMO-TN-{current_date.isoformat()}"
        ),
        "idempotency_key": (
            f"synthetic-tn-mango-{current_date.isoformat()}"
        ),
    }

    request = Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Tenant-ID": TENANT_ID,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            created += 1
            print(
                f"Confirmed: {current_date} | "
                f"Quantity: {quantity} | ID: {result['id']}"
            )
    except HTTPError as error:
        print(f"HTTP error {error.code}: {error.read().decode()}")
        raise SystemExit(1)
    except URLError as error:
        print(f"Connection error: {error}")
        raise SystemExit(1)

    current_date += timedelta(days=1)

print(f"\nCompleted: {created} sales records confirmed.")
print("Classification: SYNTHETIC HACKATHON DEMO DATA")
print("Inventory deduction: NONE")
