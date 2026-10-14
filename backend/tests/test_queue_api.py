import asyncio
import json

from app.models.queue_log import QueueLog
from app.services import queue_service


def join(client, name="Alice", phone="9999999999", branch_id="ENT", service_type="ent"):
    response = client.post("/join-queue", json={
        "name": name,
        "phone": phone,
        "branch_id": branch_id,
        "service_type": service_type,
    })
    assert response.status_code == 200
    return response.json()["user_id"]


def run(coro):
    return asyncio.run(coro)


def test_health_endpoints(client):
    assert client.get("/health-check").json() == {"message": "QTrack backend is working!"}
    root = client.get("/").json()
    assert root["message"].startswith("QTrack API v2.0")


def test_join_queue_adds_patient_and_logs(client, fake_redis, session_factory):
    user_id = join(client)

    assert user_id.startswith("user_")
    assert run(fake_redis.lrange("queue:ent", 0, -1)) == [user_id]
    user = run(fake_redis.hgetall(f"user:{user_id}"))
    assert user["name"] == "Alice"
    assert user["status"] == "waiting"
    assert user["service_type"] == "ent"
    assert run(fake_redis.xlen("queue_stream:ent")) == 1

    with session_factory() as db:
        log = db.query(QueueLog).filter_by(user_id=user_id).one()
        assert log.status == "waiting"
        assert log.branch_id == "ENT"


def test_general_service_falls_back_to_branch(client, fake_redis):
    user_id = join(client, branch_id="North", service_type="general")
    assert run(fake_redis.lrange("queue:north", 0, -1)) == [user_id]


def test_live_queue_empty(client):
    response = client.get("/live-queue/ENT")
    assert response.status_code == 200
    assert response.json() == {"service_type": "ENT", "message": "No tokens in queue"}


def test_live_queue_lists_patients_in_order(client):
    first = join(client, name="First")
    second = join(client, name="Second")

    body = client.get("/live-queue/ENT").json()
    assert body["service_type"] == "ENT"
    assert [p["user_id"] for p in body["queue"]] == [first, second]
    assert body["queue"][0] == {
        "user_id": first,
        "name": "First",
        "service_type": "ent",
        "branch_id": "ENT",
        "joined_at": body["queue"][0]["joined_at"],
        "status": "waiting",
    }


def test_live_queue_merges_legacy_uppercase_key(client, fake_redis):
    run(fake_redis.rpush("queue:ENT", "user_legacy"))
    run(fake_redis.hset("user:user_legacy", mapping={"name": "Legacy", "status": "waiting"}))
    modern = join(client)

    ids = [p["user_id"] for p in client.get("/live-queue/ENT").json()["queue"]]
    assert ids == [modern, "user_legacy"]


def test_update_status(client, fake_redis):
    user_id = join(client)

    response = client.put("/update-status", json={"user_id": user_id, "new_status": "called"})
    assert response.status_code == 200
    assert response.json() == {"message": f"Status for {user_id} updated to called"}
    assert run(fake_redis.hget(f"user:{user_id}", "status")) == "called"
    assert run(fake_redis.xlen("queue_stream:ent")) == 2


def test_update_status_unknown_user(client):
    response = client.put("/update-status", json={"user_id": "user_missing", "new_status": "called"})
    assert response.status_code == 404
    assert response.json() == {"detail": "User not found in queue"}


def test_update_status_user_without_branch(client, fake_redis):
    run(fake_redis.hset("user:user_nobranch", mapping={"name": "X"}))
    response = client.put("/update-status", json={"user_id": "user_nobranch", "new_status": "called"})
    assert response.status_code == 400
    assert response.json() == {"detail": "Branch ID not found for user"}


def test_remove_from_queue(client, fake_redis):
    user_id = join(client)

    response = client.delete("/remove-from-queue", params={"branch_id": "ENT", "user_id": user_id})
    assert response.status_code == 200
    assert response.json() == {"message": f"{user_id} removed from queue", "removed_count": 1}
    assert run(fake_redis.exists(f"user:{user_id}")) == 0
    assert client.get("/live-queue/ENT").json()["message"] == "No tokens in queue"


def test_remove_from_queue_unknown_user(client):
    response = client.delete("/remove-from-queue", params={"branch_id": "ENT", "user_id": "user_missing"})
    assert response.status_code == 404
    assert response.json() == {"detail": "user_missing not found in queue"}


def test_remove_from_queue_user_not_in_any_queue(client, fake_redis):
    run(fake_redis.hset("user:user_orphan", mapping={"name": "Orphan", "service_type": "ent"}))
    response = client.delete("/remove-from-queue", params={"branch_id": "ENT", "user_id": "user_orphan"})
    assert response.status_code == 404


def test_remove_log(client, session_factory):
    user_id = join(client)

    response = client.delete("/remove-log", params={"user_id": user_id})
    assert response.status_code == 200
    assert response.json() == {"message": f"Log for {user_id} removed"}
    with session_factory() as db:
        assert db.query(QueueLog).filter_by(user_id=user_id).count() == 0


def test_remove_log_missing(client):
    response = client.delete("/remove-log", params={"user_id": "user_missing"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Entry not found"}


def test_event_stream_sends_initial_snapshot(client, fake_redis):
    user_id = join(client)

    async def first_event():
        stream = queue_service.queue_event_stream(fake_redis, "ENT")
        try:
            return await anext(stream)
        finally:
            await stream.aclose()

    event = run(first_event())
    assert event.startswith("data: ") and event.endswith("\n\n")
    payload = json.loads(event[len("data: "):])
    assert payload["service_type"] == "ENT"
    assert [p["user_id"] for p in payload["queue"]] == [user_id]
