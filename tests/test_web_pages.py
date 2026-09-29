import datetime
import re


def seed_list_workouts(client):
    intervals = client.post(
        "/workouts",
        json={
            "date": "2026-09-20",
            "workout_type": "intervals",
            "notes": "hard session",
            "pieces": [
                {"meters": 2000, "time_seconds": 500.0, "avg_hr": 160},
                {"meters": 1000, "time_seconds": 250.0},
            ],
        },
    ).json()
    empty = client.post(
        "/workouts",
        json={"date": "2026-09-25", "workout_type": "steady_state", "pieces": []},
    ).json()
    return intervals, empty


def test_workouts_list_page_shows_rows_and_dash_cells(client):
    intervals, empty = seed_list_workouts(client)
    response = client.get("/ui/workouts")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert 'href="/ui/workouts/%d"' % intervals["id"] in body
    assert 'href="/ui/workouts/%d"' % empty["id"] in body
    assert body.index("2026-09-25") < body.index("2026-09-20")
    assert "2" in body
    assert "3000" in body
    assert "12:30" in body
    assert "160" in body
    assert "hard session" in body
    assert "0:00" in body
    assert "—" in body


def test_workouts_list_page_type_filter(client):
    intervals, empty = seed_list_workouts(client)
    response = client.get("/ui/workouts", params={"type": "intervals"})
    assert response.status_code == 200
    body = response.text
    assert 'href="/ui/workouts/%d"' % intervals["id"] in body
    assert 'href="/ui/workouts/%d"' % empty["id"] not in body
    assert '<a class="tab active" href="/ui/workouts?type=intervals">' in body


def test_workouts_list_page_empty_state(client):
    response = client.get("/ui/workouts")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "No workouts yet — log one on the Quick log page." in response.text


def test_workout_detail_page_formats_pieces_and_totals(client):
    created = client.post(
        "/workouts",
        json={
            "date": "2026-09-20",
            "workout_type": "intervals",
            "notes": "hard session",
            "pieces": [
                {
                    "meters": 2000,
                    "time_seconds": 500.0,
                    "avg_hr": 160,
                    "max_hr": 175,
                    "spm": 28,
                    "notes": "piece note",
                },
                {"meters": 1000, "time_seconds": 250.0},
            ],
        },
    ).json()
    response = client.get(f"/ui/workouts/{created['id']}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert "intervals" in body
    assert "hard session" in body
    assert "8:20.0" in body
    assert "4:10.0" in body
    assert "2:05.0" in body
    assert "179.2" in body
    assert "160" in body
    assert "175" in body
    assert "28" in body
    assert "piece note" in body
    assert "—" in body
    assert "3000" in body
    assert "12:30" in body


def test_workout_detail_page_saved_banner(client):
    created = client.post(
        "/workouts",
        json={"date": "2026-09-20", "workout_type": "other", "pieces": []},
    ).json()
    saved = client.get(f"/ui/workouts/{created['id']}?saved=1")
    assert saved.status_code == 200
    assert "Saved ✓" in saved.text
    unsaved = client.get(f"/ui/workouts/{created['id']}?saved=0")
    assert unsaved.status_code == 200
    assert "Saved ✓" not in unsaved.text


def test_workout_detail_page_404(client):
    response = client.get("/ui/workouts/999999")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert "Workout not found" in body
    assert "No workout with id 999999 exists." in body


def test_quick_log_get_form_defaults(client):
    response = client.get("/ui/quick-log")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    today = datetime.date.today().isoformat()
    assert body.count(f'value="{today}"') == 2
    assert 'action="/ui/quick-log"' in body
    assert 'action="/ui/erg-test"' in body
    assert '<option value="steady_state" selected>steady_state</option>' in body
    assert "Fill in Split OR Total time — exactly one." in body


def test_quick_log_post_valid_redirects_to_detail(client):
    response = client.post(
        "/ui/quick-log",
        data={
            "date": "2026-09-28",
            "workout_type": "steady_state",
            "meters": "10000",
            "split": "2:15.0",
            "avg_hr": "150",
        },
    )
    assert response.status_code == 200
    assert response.history[0].status_code == 303
    location = response.history[0].headers["location"]
    workout_id = int(re.search(r"/ui/workouts/(\d+)", location).group(1))
    assert location == f"/ui/workouts/{workout_id}?saved=1"
    body = response.text
    assert "Saved ✓" in body
    assert "10000" in body
    assert "2:15.0" in body
    assert "45:00" in body
    assert "150" in body

    detail = client.get(f"/workouts/{workout_id}").json()
    assert detail["date"] == "2026-09-28"
    assert detail["workout_type"] == "steady_state"
    piece = detail["pieces"][0]
    assert piece["sequence"] == 1
    assert piece["meters"] == 10000
    assert piece["time_seconds"] == 2700.0
    assert piece["avg_hr"] == 150
    assert detail["total_meters"] == 10000
    assert detail["total_time_seconds"] == 2700.0


def test_quick_log_post_invalid_renders_errors_and_preserves_values(client):
    both = client.post(
        "/ui/quick-log",
        data={
            "date": "2026-09-28",
            "workout_type": "steady_state",
            "meters": "10000",
            "split": "2:15.0",
            "total_time": "45:00",
        },
    )
    assert both.status_code == 200
    body = both.text
    assert "Could not save — please fix:" in body
    assert "Fill in Split or Total time, not both." in body
    assert 'value="10000"' in body
    assert 'value="2:15.0"' in body
    assert 'value="45:00"' in body

    neither = client.post(
        "/ui/quick-log",
        data={"date": "2026-09-28", "workout_type": "steady_state", "meters": "10000"},
    )
    assert neither.status_code == 200
    assert "Fill in Split or Total time — exactly one." in neither.text

    garbage = client.post(
        "/ui/quick-log",
        data={
            "date": "2026-09-28",
            "workout_type": "steady_state",
            "meters": "10000",
            "split": "banana",
        },
    )
    assert garbage.status_code == 200
    garbage_body = garbage.text
    assert "Could not read split" in garbage_body
    assert "banana" in garbage_body
    assert 'value="banana"' in garbage_body

    missing_meters = client.post(
        "/ui/quick-log",
        data={"date": "2026-09-28", "workout_type": "steady_state", "split": "2:00.0"},
    )
    assert missing_meters.status_code == 200
    assert "Meters is required." in missing_meters.text

    assert client.get("/workouts").json() == []


def test_erg_test_post_valid_redirects_to_dashboard(client):
    response = client.post(
        "/ui/erg-test",
        data={"date": "2026-09-28", "distance": "2000", "time": "7:52.5"},
    )
    assert response.status_code == 200
    assert response.history[0].status_code == 303
    assert response.history[0].headers["location"] == "/?saved=test"
    assert "Test saved ✓" in response.text

    tests = client.get("/erg-tests").json()
    assert len(tests) == 1
    assert tests[0]["date"] == "2026-09-28"
    assert tests[0]["distance_meters"] == 2000
    assert tests[0]["time_seconds"] == 472.5

    other_flag = client.get("/?saved=1")
    assert "Test saved ✓" not in other_flag.text


def test_erg_test_post_invalid_renders_errors_and_preserves_values(client):
    garbage = client.post(
        "/ui/erg-test",
        data={"date": "2026-09-28", "distance": "2000", "time": "banana"},
    )
    assert garbage.status_code == 200
    body = garbage.text
    assert "Could not save — please fix:" in body
    assert "Could not read time" in body
    assert "banana" in body
    assert 'value="2000"' in body

    missing_distance = client.post(
        "/ui/erg-test",
        data={"date": "2026-09-28", "time": "7:52.5"},
    )
    assert missing_distance.status_code == 200
    assert "Distance is required." in missing_distance.text

    assert client.get("/erg-tests").json() == []
