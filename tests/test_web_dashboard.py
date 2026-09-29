import datetime
import json
import re

import pytest


def seed_dashboard_data(client):
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    interval_workout = {
        "date": monday.isoformat(),
        "workout_type": "intervals",
        "pieces": [
            {"meters": 500, "time_seconds": 125.0, "avg_hr": 150},
            {"meters": 500, "time_seconds": 122.0, "avg_hr": 155},
            {"meters": 500, "time_seconds": 120.0, "avg_hr": 160},
            {"meters": 500, "time_seconds": 118.0, "avg_hr": 165},
        ],
    }
    response = client.post("/workouts", json=interval_workout)
    assert response.status_code == 201
    steady_workout = {
        "date": (monday - datetime.timedelta(weeks=1)).isoformat(),
        "workout_type": "steady_state",
        "pieces": [{"meters": 10000, "time_seconds": 2500.0, "avg_hr": 145}],
    }
    response = client.post("/workouts", json=steady_workout)
    assert response.status_code == 201
    erg_test = {"date": "2026-02-10", "distance_meters": 2000, "time_seconds": 470.0}
    response = client.post("/erg-tests", json=erg_test)
    assert response.status_code == 201
    return monday


def extract_chart_data(body):
    match = re.search(
        r'<script id="chart-data"[^>]*>(.*?)</script>', body, re.DOTALL
    )
    assert match is not None
    return json.loads(match.group(1))


def expected_week_starts():
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    return [
        (monday - datetime.timedelta(weeks=ago)).isoformat() for ago in range(7, -1, -1)
    ]


def test_dashboard_renders_stats_and_chart_data(client):
    monday = seed_dashboard_data(client)
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert "Rowing Analytics" in body
    assert "Total meters" in body
    assert "12000" in body
    assert "Total workouts" in body
    assert "Best 2k" in body
    assert "1:57.5" in body

    chart_data = extract_chart_data(body)
    weekly = chart_data["weekly_meters"]
    assert len(weekly["labels"]) == 8
    assert sum(weekly["values"]) == 12000
    assert weekly["values"][-1] == 2000
    assert weekly["values"][-2] == 10000

    hr_points = chart_data["hr_vs_split"]
    assert len(hr_points) == 5
    assert any(
        point["date"] == monday.isoformat()
        and point["meters"] == 500
        and point["split_seconds"] == 125.0
        and point["avg_hr"] == 150
        and point["split_formatted"] == "2:05.0"
        for point in hr_points
    )

    progression = chart_data["test_progression"]
    assert progression == [
        {
            "distance_meters": 2000,
            "label": "2k",
            "points": [
                {
                    "date": "2026-02-10",
                    "split_seconds": 117.5,
                    "split_formatted": "1:57.5",
                    "time_seconds": 470.0,
                    "time_formatted": "7:50.0",
                }
            ],
        }
    ]


def test_dashboard_empty_db(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert "Rowing Analytics" in body
    assert "No HR data yet" in body
    assert "No tests yet" in body
    assert "—" in body

    chart_data = extract_chart_data(body)
    assert len(chart_data["weekly_meters"]["values"]) == 8
    assert all(value == 0 for value in chart_data["weekly_meters"]["values"])
    assert chart_data["hr_vs_split"] == []
    assert chart_data["test_progression"] == []


def test_dashboard_serves_static_assets(client):
    for path in ("/static/style.css", "/static/app.js", "/static/vendor/chart.umd.js"):
        response = client.get(path)
        assert response.status_code == 200
    vendor = client.get("/static/vendor/chart.umd.js")
    assert len(vendor.content) > 100000
    assert b"Chart.js" in vendor.content


def test_stats_json_unchanged_after_refactor(client):
    seed_dashboard_data(client)
    response = client.get("/stats")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "total_workouts",
        "total_pieces",
        "total_tests",
        "total_meters",
        "total_time_seconds",
        "avg_hr",
        "weekly_meters",
        "best_tests",
    }
    assert body["total_workouts"] == 2
    assert body["total_pieces"] == 5
    assert body["total_tests"] == 1
    assert body["total_meters"] == 12000
    assert body["total_time_seconds"] == pytest.approx(2985.0)
    assert body["avg_hr"] == pytest.approx(
        (150 * 125.0 + 155 * 122.0 + 160 * 120.0 + 165 * 118.0 + 145 * 2500.0) / 2985.0
    )
    weeks = body["weekly_meters"]
    assert [week["week_start"] for week in weeks] == expected_week_starts()
    assert weeks[-1]["meters"] == 2000
    assert weeks[-2]["meters"] == 10000
    best = body["best_tests"]
    assert len(best) == 1
    assert set(best[0]) == {
        "id",
        "date",
        "distance_meters",
        "time_seconds",
        "avg_hr",
        "max_hr",
        "notes",
        "split_formatted",
    }
    assert best[0]["date"] == "2026-02-10"
    assert best[0]["distance_meters"] == 2000
    assert best[0]["time_seconds"] == 470.0
    assert best[0]["split_formatted"] == "1:57.5"
