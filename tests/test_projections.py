import math

import pytest

STANDARD_DISTANCES = [500, 1000, 2000, 5000, 6000, 10000, 21097, 42195]


def quick_log(client, meters, split, date="2026-01-01"):
    response = client.post(
        "/workouts/quick-log",
        json={"date": date, "meters": meters, "split": split},
    )
    assert response.status_code == 201
    return response.json()


def post_erg_test(client, date, distance_meters, time_seconds):
    response = client.post(
        "/erg-tests",
        json={
            "date": date,
            "distance_meters": distance_meters,
            "time_seconds": time_seconds,
        },
    )
    assert response.status_code == 201
    return response.json()


def rows_by_distance(body):
    return {row["meters"]: row for row in body["rows"]}


def assert_row_all_null(row):
    assert row["regression_split_seconds"] is None
    assert row["regression_split_formatted"] is None
    assert row["regression_watts"] is None
    assert row["pauls_split_seconds"] is None
    assert row["pauls_split_formatted"] is None
    assert row["pauls_watts"] is None


def test_perfect_two_point_fit(client):
    quick_log(client, 2000, "2:00.0")
    quick_log(client, 4000, "2:05.0")
    post_erg_test(client, "2026-01-05", 2000, 480.0)

    response = client.get("/projections")
    assert response.status_code == 200
    body = response.json()

    model = body["model"]
    assert model is not None
    assert model["b"] == pytest.approx(5.0)
    assert model["r2"] == pytest.approx(1.0)
    assert model["n_points"] == 3
    assert model["n_distinct_distances"] == 2
    assert model["a"] + model["b"] * math.log2(2000) == pytest.approx(120.0)

    rows = rows_by_distance(body)
    assert set(rows) == set(STANDARD_DISTANCES)
    row = rows[1000]
    assert row["regression_split_seconds"] == pytest.approx(115.0)
    assert row["regression_split_formatted"] == "1:55.0"
    assert row["regression_watts"] == pytest.approx(2.8 / (115.0 / 500.0) ** 3)


def test_insufficient_data_single_distance(client):
    quick_log(client, 50, "1:40.0")
    quick_log(client, 2000, "2:00.0")
    quick_log(client, 2000, "2:04.0")

    response = client.get("/projections")
    assert response.status_code == 200
    body = response.json()

    assert body["model"] is None
    assert body["pauls_reference"] is None
    assert [row["meters"] for row in body["rows"]] == STANDARD_DISTANCES
    for row in body["rows"]:
        assert_row_all_null(row)


def test_pauls_law_uses_latest_erg_test(client):
    post_erg_test(client, "2026-01-01", 2000, 500.0)
    newer = post_erg_test(client, "2026-03-01", 2000, 480.0)

    response = client.get("/projections")
    assert response.status_code == 200
    body = response.json()

    assert body["model"] is None

    reference = body["pauls_reference"]
    assert reference["id"] == newer["id"]
    assert reference["date"] == "2026-03-01"
    assert reference["distance_meters"] == 2000
    assert reference["split_seconds"] == pytest.approx(120.0)

    rows = rows_by_distance(body)
    assert rows[500]["pauls_split_seconds"] == pytest.approx(110.0)
    assert rows[500]["pauls_split_formatted"] == "1:50.0"
    assert rows[500]["pauls_watts"] == pytest.approx(2.8 / (110.0 / 500.0) ** 3)
    assert rows[6000]["pauls_split_seconds"] == pytest.approx(
        120.0 + 5.0 * math.log2(3.0)
    )


def test_empty_database(client):
    response = client.get("/projections")
    assert response.status_code == 200
    body = response.json()
    assert body["model"] is None
    assert body["pauls_reference"] is None
    assert [row["meters"] for row in body["rows"]] == STANDARD_DISTANCES
    for row in body["rows"]:
        assert_row_all_null(row)


def test_distance_query_param_single_row(client):
    quick_log(client, 2000, "2:00.0")
    quick_log(client, 4000, "2:05.0")

    response = client.get("/projections", params={"distance": 6000})
    assert response.status_code == 200
    body = response.json()
    assert [row["meters"] for row in body["rows"]] == [6000]

    row = body["rows"][0]
    expected = 120.0 + 5.0 * math.log2(6000 / 2000)
    assert row["regression_split_seconds"] == pytest.approx(expected)
    assert row["regression_split_formatted"] == "2:07.9"
    assert row["pauls_split_seconds"] is None
