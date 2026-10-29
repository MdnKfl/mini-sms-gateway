import threading
import requests
import sqlite3

BASE = "http://127.0.0.1:8000"
EMAIL = "race@test.com"
PASSWORD = "pass123"
DB_PATH = "sms.db"

# 1. Register (ignore if exists)
requests.post(f"{BASE}/register", json={"email": EMAIL, "password": PASSWORD})

# 2. Set balance = 10 AND zero out route failures
conn = sqlite3.connect(DB_PATH)
conn.execute("UPDATE users SET balance = 10 WHERE email = ?", (EMAIL,))
conn.execute("UPDATE routes SET failure_rate = 0")
conn.commit()
conn.close()
print(f"Set {EMAIL} balance = 10, routes = 0% failure")

# 3. Login
r = requests.post(f"{BASE}/login", data={"username": EMAIL, "password": PASSWORD})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 4. Fire 20 parallel
results = []
lock = threading.Lock()

def send_one():
    r = requests.post(
        f"{BASE}/sms/send",
        json={"to": ["9841234567"], "message": "hi"},
        headers=headers,
    )
    with lock:
        results.append(r.status_code)

threads = [threading.Thread(target=send_one) for _ in range(20)]
for t in threads: t.start()
for t in threads: t.join()

# 5. Report
successes = results.count(201)
insufficient = results.count(402)

conn = sqlite3.connect(DB_PATH)
final_balance = conn.execute(
    "SELECT balance FROM users WHERE email = ?", (EMAIL,)
).fetchone()[0]
# Reset routes to normal for future runs
conn.execute("UPDATE routes SET failure_rate = 0.30 WHERE name = 'ROUTE_A'")
conn.execute("UPDATE routes SET failure_rate = 0.10 WHERE name = 'ROUTE_B'")
conn.commit()
conn.close()

print(f"Success (201):       {successes}")
print(f"Insufficient (402):  {insufficient}")
print(f"Final balance:       {final_balance}")

assert successes == 10, f"Expected 10 successes, got {successes}"
assert insufficient == 10, f"Expected 10 rejects, got {insufficient}"
assert final_balance == 0, f"Expected balance 0, got {final_balance}"
print("PASSED: no overspend.")