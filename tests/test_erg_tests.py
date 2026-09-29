def create_erg_test(client, date, distance_meters, time_seconds, **extra):
    payload = {
        "date": date,
        "distance_meters": distance_meters,
        "time_seconds": time_seconds,
    }
    payload.update(extra)
    response = client.post("/erg-tests", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_erg_test(client):
    body = create_erg_test(
        client, "2026-01-10", 2000, 480.0, avg_hr=178, max_hr=192, notes="season opener"
    )
    assert body["date"] == "2026-01-10"
    assert body["distance_meters"] == 2000
    assert body["time_seconds"] == 480.0
    assert body["avg_hr"] == 178
    assert body["max_hr"] == 192
    assert body["notes"] == "season opener"
    assert body["split_formatted"] == "2:00.0"


def test_list_erg_tests_order_and_distance_filter(client):
    create_erg_test(client, "2026-02-01", 2000, 490.0)
    create_erg_test(client, "2026-03-01", 5000, 1140.0)
    create_erg_test(client, "2026-03-10", 2000, 500.0)

    response = client.get("/erg-tests")
    assert response.status_code == 200
    assert [t["date"] for t in response.json()] == [
        "2026-03-10",
        "2026-03-01",
        "2026-02-01",
    ]

    twok = client.get("/erg-tests", params={"distance": 2000})
    assert [t["distance_meters"] for t in twok.json()] == [2000, 2000]

    empty = client.get("/erg-tests", params={"distance": 6000})
    assert empty.json() == []


def test_best_erg_test(client):
    slower = create_erg_test(client, "2026-02-01", 2000, 510.0)
    faster = create_erg_test(client, "2026-01-01", 2000, 480.0)

    best = client.get("/erg-tests/best", params={"distance": 2000})
    assert best.status_code == 200
    assert best.json()["id"] == faster["id"]
    assert best.json()["time_seconds"] == 480.0
    assert best.json()["id"] != slower["id"]

    missing = client.get("/erg-tests/best", params={"distance": 500})
    assert missing.status_code == 404
    assert missing.json()["detail"] == "no erg test at distance 500"


def test_get_erg_test_detail_and_404(client):
    created = create_erg_test(client, "2026-02-01", 2000, 480.0)
    detail = client.get(f"/erg-tests/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == created["id"]
    assert detail.json()["distance_meters"] == 2000
    assert detail.json()["split_formatted"] == "2:00.0"

    missing = client.get("/erg-tests/999999")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "erg test not found"


def test_replace_erg_test(client):
    created = create_erg_test(client, "2026-02-01", 2000, 500.0)
    response = client.put(
        f"/erg-tests/{created['id']}",
        json={
            "date": "2026-02-02",
            "distance_meters": 5000,
            "time_seconds": 1140.0,
            "notes": "updated",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["date"] == "2026-02-02"
    assert body["distance_meters"] == 5000
    assert body["time_seconds"] == 1140.0
    assert body["notes"] == "updated"
    assert body["split_formatted"] == "1:54.0"

    refetched = client.get(f"/erg-tests/{created['id']}").json()
    assert refetched["distance_meters"] == 5000

    missing = client.put(
        "/erg-tests/999999",
        json={"date": "2026-02-02", "distance_meters": 2000, "time_seconds": 480.0},
    )
    assert missing.status_code == 404


def test_delete_erg_test(client):
    created = create_erg_test(client, "2026-05-01", 2000, 480.0)
    deleted = client.delete(f"/erg-tests/{created['id']}")
    assert deleted.status_code == 204
    assert deleted.text == ""

    missing = client.get(f"/erg-tests/{created['id']}")
    assert missing.status_code == 404

    again = client.delete(f"/erg-tests/{created['id']}")
    assert again.status_code == 404
