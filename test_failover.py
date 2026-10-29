import requests

BASE = "http://127.0.0.1:8000"
EMAIL = "failover@test.com"
PASSWORD = "pass123"


def set_failure(route_name, rate):
    requests.post(
        f"{BASE}/demo/set-failure-rate",
        params={"route_name": route_name, "rate": rate},
    )


def register_and_login():
    requests.post(f"{BASE}/register", json={"email": EMAIL, "password": PASSWORD})
    token = requests.post(
        f"{BASE}/login",
        data={"username": EMAIL, "password": PASSWORD},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def show_balance(headers):
    print(f"  Balance: {requests.get(f'{BASE}/me', headers=headers).json()['balance']}")


def send_one(headers):
    return requests.post(
        f"{BASE}/sms/send",
        json={"to": ["9841234567"], "message": "hi"},
        headers=headers,
    ).json()["messages"]


headers = register_and_login()

print("=== 1. Normal send ===")
set_failure("ROUTE_A", 0.0)
set_failure("ROUTE_B", 0.0)
show_balance(headers)
print(f"  -> {send_one(headers)}")
show_balance(headers)

print("\n=== 2. ROUTE_A fails, falls over to ROUTE_B ===")
set_failure("ROUTE_A", 1.0)
set_failure("ROUTE_B", 0.0)
show_balance(headers)
print(f"  -> {send_one(headers)}")
show_balance(headers)

print("\n=== 3. All routes fail -> refund ===")
set_failure("ROUTE_A", 1.0)
set_failure("ROUTE_B", 1.0)
show_balance(headers)
print(f"  -> {send_one(headers)}")
show_balance(headers)

# Reset for next demo runs
set_failure("ROUTE_A", 0.30)
set_failure("ROUTE_B", 0.10)
print("\nRoutes reset.")