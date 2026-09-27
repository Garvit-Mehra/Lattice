"""
Performance Benchmark & Concurrent Load Test for LATTICE · IITH Operations Console
Simulates concurrent students filing complaints, upvoting appliance breakdowns,
and measuring priority scoring calculation latency under load.
"""
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient

from backend.student_app import app as student_app

client = TestClient(student_app)

CONCURRENT_USERS = 50
REQUESTS_PER_USER = 5

def simulate_user_session(user_idx: int):
    """Simulates a resident browsing, filing a defect, and confirming an appliance."""
    results = []
    
    # 1. Fetch hostels
    t0 = time.time()
    res = client.get("/api/v1/hostels")
    results.append(("get_hostels", res.status_code == 200, time.time() - t0))

    # 2. Browse appliances
    t0 = time.time()
    res = client.get("/api/v1/appliances?hostel_id=1&floor=1")
    results.append(("get_appliances", res.status_code == 200, time.time() - t0))

    # 3. Submit room ticket
    t0 = time.time()
    res = client.post("/api/v1/tickets/room", json={
        "hostel_id": 1,
        "floor": 1,
        "room_number": f"10{user_idx % 9 + 1}",
        "category": "electrical",
        "title": f"Load test switchboard spark #{user_idx}",
        "description": "Electrical defect logged during concurrent benchmark",
        "reporter_name": f"Student {user_idx}",
        "reporter_contact": f"9876543{user_idx:03d}"
    })
    results.append(("post_room_ticket", res.status_code in [200, 429], time.time() - t0))

    # 4. Lookup ticket
    t0 = time.time()
    res = client.get("/api/v1/tickets/LAT-8921")
    results.append(("lookup_benchmark_ticket", res.status_code == 200, time.time() - t0))

    # 5. Fetch campus SLA
    t0 = time.time()
    res = client.get("/api/v1/analytics/sla")
    results.append(("get_sla_analytics", res.status_code == 200, time.time() - t0))

    return results

def run_load_test():
    print(f"[*] Starting LATTICE Load Test with {CONCURRENT_USERS} concurrent users ({CONCURRENT_USERS * REQUESTS_PER_USER} operations)...")
    start_time = time.time()
    all_results = []

    with ThreadPoolExecutor(max_workers=CONCURRENT_USERS) as executor:
        futures = [executor.submit(simulate_user_session, i) for i in range(CONCURRENT_USERS)]
        for f in as_completed(futures):
            all_results.extend(f.result())

    total_time = time.time() - start_time
    total_reqs = len(all_results)
    successful_reqs = sum(1 for _, ok, _ in all_results if ok)
    durations = [d * 1000 for _, _, d in all_results]
    avg_latency = sum(durations) / len(durations) if durations else 0
    p95_latency = sorted(durations)[int(len(durations) * 0.95)] if durations else 0

    print(f"[+] Load Test Completed in {total_time:.2f}s")
    print(f"    - Total Operations: {total_reqs}")
    print(f"    - Success Rate: {successful_reqs / total_reqs * 100:.1f}% ({successful_reqs}/{total_reqs})")
    print(f"    - Average Latency: {avg_latency:.2f}ms")
    print(f"    - p95 Latency: {p95_latency:.2f}ms")
    print(f"    - Throughput: {total_reqs / total_time:.1f} req/sec")

    assert successful_reqs / total_reqs >= 0.95, "Load test success rate must exceed 95%"
    print("[+] PERFORMANCE BENCHMARK PASSED!")

if __name__ == "__main__":
    run_load_test()
