import datetime

import pytest


def create_workout(client, date, workout_type, pieces=None, notes=None):
    payload = {"date": date, "workout_type": workout_type, "pieces": pieces or []}
    if notes is not None:
        payload["notes"] = notes
    response = client.post("/workouts", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_workout_with_pieces(client):
    response = client.post(
        "/workouts",
        json={
            "date": "2026-01-10",
            "workout_type": "intervals",
            "notes": "hard session",
            "pieces": [
                {"meters": 2000, "time_seconds": 500.0},
                {"meters": 500, "time_seconds": 125.0, "avg_hr": 160, "spm": 28},
            ],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["date"] == "2026-01-10"
    assert body["workout_type"] == "intervals"
    assert body["notes"] == "hard session"
    assert [piece["sequence"] for piece in body["pieces"]] == [1, 2]
    first = body["pieces"][0]
    assert first["meters"] == 2000
    assert first["time_seconds"] == 500.0
    assert first["split_seconds"] == 125.0
    assert first["split_formatted"] == "2:05.0"
    assert first["watts"] == pytest.approx(179.2)
    assert body["total_meters"] == 2500
    assert body["total_time_seconds"] == 625.0


def test_create_workout_empty_pieces(client):
    response = client.post(
        "/workouts",
        json={"date": "2026-01-11", "workout_type": "other", "pieces": []},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["pieces"] == []
    assert body["total_meters"] is None
    assert body["total_time_seconds"] is None


def test_quick_log_with_split(client):
    response = client.post(
        "/workouts/quick-log",
        json={"meters": 10000, "split": "2:05.0", "avg_hr": 155},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["workout_type"] == "steady_state"
    assert body["date"] == datetime.date.today().isoformat()
    piece = body["pieces"][0]
    assert piece["sequence"] == 1
    assert piece["meters"] == 10000
    assert piece["time_seconds"] == 2500.0
    assert piece["split_seconds"] == 125.0
    assert piece["split_formatted"] == "2:05.0"
    assert body["total_meters"] == 10000
    assert body["total_time_seconds"] == 2500.0


def test_quick_log_with_time_seconds(client):
    response = client.post(
        "/workouts/quick-log",
        json={"meters": 2000, "time_seconds": 500.0},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["pieces"][0]["split_formatted"] == "2:05.0"


def test_quick_log_validation_errors(client):
    both = client.post(
        "/workouts/quick-log",
        json={"meters": 10000, "time_seconds": 2500.0, "split": "2:05.0"},
    )
    assert both.status_code == 422
    assert "exactly one" in both.text

    neither = client.post("/workouts/quick-log", json={"meters": 10000})
    assert neither.status_code == 422
    assert "exactly one" in neither.text

    invalid = client.post(
        "/workouts/quick-log", json={"meters": 10000, "split": "banana"}
    )
    assert invalid.status_code == 422


def test_list_workouts_filters_and_order(client):
    create_workout(client, "2026-03-01", "intervals", [{"meters": 1000, "time_seconds": 250.0}])
    create_workout(client, "2026-03-05", "steady_state", [{"meters": 5000, "time_seconds": 1250.0}])
    create_workout(client, "2026-03-10", "steady_state", [{"meters": 8000, "time_seconds": 2000.0}])
    create_workout(client, "2026-04-01", "steady_state", [{"meters": 6000, "time_seconds": 1500.0}])

    all_workouts = client.get("/workouts")
    assert all_workouts.status_code == 200
    assert [w["date"] for w in all_workouts.json()] == [
        "2026-04-01",
        "2026-03-10",
        "2026-03-05",
        "2026-03-01",
    ]

    steady = client.get("/workouts", params={"type": "steady_state"})
    assert [w["date"] for w in steady.json()] == [
        "2026-04-01",
        "2026-03-10",
        "2026-03-05",
    ]

    march = client.get(
        "/workouts", params={"since": "2026-03-01", "until": "2026-03-10"}
    )
    assert [w["date"] for w in march.json()] == [
        "2026-03-10",
        "2026-03-05",
        "2026-03-01",
    ]

    steady_march = client.get(
        "/workouts",
        params={"type": "steady_state", "since": "2026-03-01", "until": "2026-03-31"},
    )
    assert [w["date"] for w in steady_march.json()] == ["2026-03-10", "2026-03-05"]

    limited = client.get("/workouts", params={"limit": 2})
    assert [w["date"] for w in limited.json()] == ["2026-04-01", "2026-03-10"]


def test_get_workout_detail_and_404(client):
    created = create_workout(
        client, "2026-02-01", "test", [{"meters": 2000, "time_seconds": 500.0}]
    )
    detail = client.get(f"/workouts/{created['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == created["id"]
    assert len(body["pieces"]) == 1

    missing = client.get("/workouts/999999")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "workout not found"


def test_replace_workout(client):
    created = create_workout(
        client,
        "2026-02-01",
        "test",
        [
            {"meters": 2000, "time_seconds": 500.0},
            {"meters": 500, "time_seconds": 125.0},
        ],
    )
    response = client.put(
        f"/workouts/{created['id']}",
        json={
            "date": "2026-02-02",
            "workout_type": "intervals",
            "pieces": [
                {"meters": 1000, "time_seconds": 250.0},
                {"meters": 1000, "time_seconds": 240.0},
                {"meters": 500, "time_seconds": 120.0},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-02-02"
    assert body["workout_type"] == "intervals"
    assert [piece["sequence"] for piece in body["pieces"]] == [1, 2, 3]
    assert [piece["meters"] for piece in body["pieces"]] == [1000, 1000, 500]
    assert body["total_meters"] == 2500

    refetched = client.get(f"/workouts/{created['id']}").json()
    assert len(refetched["pieces"]) == 3

    missing = client.put(
        "/workouts/999999",
        json={"date": "2026-02-02", "workout_type": "test", "pieces": []},
    )
    assert missing.status_code == 404


def test_delete_workout(client):
    created = create_workout(client, "2026-05-01", "other", [{"meters": 1000, "time_seconds": 250.0}])
    deleted = client.delete(f"/workouts/{created['id']}")
    assert deleted.status_code == 204
    assert deleted.text == ""

    missing = client.get(f"/workouts/{created['id']}")
    assert missing.status_code == 404

    again = client.delete(f"/workouts/{created['id']}")
    assert again.status_code == 404
