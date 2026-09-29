import datetime

import pytest


def create_workout(client, date, workout_type, pieces, notes=None):
    payload = {"date": date, "workout_type": workout_type, "pieces": pieces}
    if notes is not None:
        payload["notes"] = notes
    response = client.post("/workouts", json=payload)
    assert response.status_code == 201
    return response.json()


def expected_week_starts():
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    return [
        (monday - datetime.timedelta(weeks=ago)).isoformat() for ago in range(7, -1, -1)
    ]


def test_stats_empty_db(client):
    response = client.get("/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["total_workouts"] == 0
    assert body["total_pieces"] == 0
    assert body["total_tests"] == 0
    assert body["total_meters"] == 0
    assert body["total_time_seconds"] == 0
    assert body["avg_hr"] is None
    assert body["best_tests"] == []
    weeks = body["weekly_meters"]
    assert len(weeks) == 8
    assert [week["week_start"] for week in weeks] == expected_week_starts()
    assert all(week["meters"] == 0 for week in weeks)


def test_stats_totals_weekly_and_weighted_hr(client):
    today = datetime.date.today()
    this_monday = today - datetime.timedelta(days=today.weekday())
    past_monday = this_monday - datetime.timedelta(weeks=3)

    create_workout(
        client,
        this_monday.isoformat(),
        "intervals",
        [
            {"meters": 1000, "time_seconds": 250.0, "avg_hr": 150},
            {"meters": 5000, "time_seconds": 1250.0, "avg_hr": 160},
        ],
    )
    create_workout(
        client,
        (past_monday + datetime.timedelta(days=2)).isoformat(),
        "steady_state",
        [{"meters": 2000, "time_seconds": 600.0}],
    )

    response = client.get("/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["total_workouts"] == 2
    assert body["total_pieces"] == 3
    assert body["total_tests"] == 0
    assert body["total_meters"] == 8000
    assert body["total_time_seconds"] == pytest.approx(2100.0)
    assert body["avg_hr"] == pytest.approx((150 * 250.0 + 160 * 1250.0) / 1500.0)
    assert body["avg_hr"] == pytest.approx(158.3333, abs=1e-3)

    weeks = body["weekly_meters"]
    assert [week["week_start"] for week in weeks] == expected_week_starts()
    assert weeks[-1]["meters"] == 6000
    assert weeks[4]["meters"] == 2000
    assert all(
        week["meters"] == 0 for i, week in enumerate(weeks) if i not in (4, 7)
    )
    assert body["best_tests"] == []


def test_stats_best_tests_per_distance(client):
    for payload in (
        {"date": "2026-01-05", "distance_meters": 2000, "time_seconds": 480.0},
        {"date": "2026-02-10", "distance_meters": 2000, "time_seconds": 470.0},
        {"date": "2026-02-20", "distance_meters": 6000, "time_seconds": 1440.0},
    ):
        response = client.post("/erg-tests", json=payload)
        assert response.status_code == 201

    response = client.get("/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["total_tests"] == 3
    assert body["total_pieces"] == 0
    assert body["total_meters"] == 0
    assert body["avg_hr"] is None
    best = body["best_tests"]
    assert len(best) == 2
    assert [test["distance_meters"] for test in best] == [2000, 6000]
    assert best[0]["time_seconds"] == 470.0
    assert best[0]["split_formatted"] == "1:57.5"
    assert best[1]["split_formatted"] == "2:00.0"
