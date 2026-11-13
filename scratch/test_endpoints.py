import sys
import urllib.request
import json

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"

def test_api():
    print("1. Testing GET /api/health...")
    with urllib.request.urlopen(f"{BASE_URL}/api/health") as resp:
        res = json.loads(resp.read().decode())
        print(" -> Health:", res.get("status"))

    print("\n2. Testing GET /api/calendar/tasks...")
    with urllib.request.urlopen(f"{BASE_URL}/api/calendar/tasks") as resp:
        res = json.loads(resp.read().decode())
        print(" -> Total tasks:", res.get("total"), [t["title"][:30] for t in res.get("tasks", [])])

    print("\n3. Testing POST /api/calendar/tasks...")
    req_data = json.dumps({
        "title": "Bón phân đạm cá hữu cơ vi sinh",
        "due_date": "2026-11-15",
        "priority": "medium",
        "task_type": "fertilizing",
        "crop_id": "Tomato",
        "notes": "Pha tỷ lệ 1:500 tưới gốc lúc chiều mát"
    }).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/api/calendar/tasks", data=req_data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        task = res.get("task")
        print(" -> Created task id:", task.get("id"), task.get("title"))
        created_task_id = task.get("id")

    print("\n4. Testing POST /api/calendar/tasks/{id}/complete...")
    req_comp = urllib.request.Request(f"{BASE_URL}/api/calendar/tasks/{created_task_id}/complete", data=b"{}", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_comp) as resp:
        res = json.loads(resp.read().decode())
        print(" -> Completed task status:", res.get("task", {}).get("status"), res.get("task", {}).get("completed_at"))

    print("\n5. Testing GET /api/calendar/recommendations...")
    with urllib.request.urlopen(f"{BASE_URL}/api/calendar/recommendations?crop_id=Tomato") as resp:
        res = json.loads(resp.read().decode())
        print(" -> Recommendations:", len(res.get("recommendations", [])), res.get("recommendations", [])[0]["stage"])

    print("\n6. Testing POST /api/risk/alerts/1/acknowledge...")
    ack_data = json.dumps({
        "status": "inspecting",
        "user_observation": "Đã đi kiểm tra vườn Ba Vì sáng nay, chưa thấy đốm lá lây lan nhiều",
        "severity_observed": "thấp"
    }).encode("utf-8")
    req_ack = urllib.request.Request(f"{BASE_URL}/api/risk/alerts/1/acknowledge", data=ack_data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_ack) as resp:
        res = json.loads(resp.read().decode())
        print(" -> Risk Ack:", res.get("success"), res.get("message"))

    print("\n7. Testing GET /api/risk/acknowledgments...")
    with urllib.request.urlopen(f"{BASE_URL}/api/risk/acknowledgments") as resp:
        res = json.loads(resp.read().decode())
        print(" -> Risk acks count:", res.get("total"))

    print("\n8. Testing POST /api/notifications/mark-all-read...")
    req_mark = urllib.request.Request(f"{BASE_URL}/api/notifications/mark-all-read", data=b"{}", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_mark) as resp:
        res = json.loads(resp.read().decode())
        print(" -> Mark all read:", res.get("success"), "marked:", res.get("marked_count"))

    print("\nAll new backend endpoints verified successfully with HTTP 200!")

if __name__ == "__main__":
    test_api()
