HEADERS = "date,kind,workout_type,meters,time_seconds,split,avg_hr,max_hr,spm,notes,workout_notes"


def upload(client, csv_text):
    return client.post(
        "/import/csv", files={"file": ("sessions.csv", csv_text, "text/csv")}
    )


def test_grouping_consecutive_rows_same_date_and_type(client):
    csv_text = (
        "date,workout_type,meters,split,avg_hr,workout_notes\n"
        "2026-01-10,intervals,500,2:05.0,162,4x500m\n"
        "2026-01-10,intervals,500,2:04.5,163,\n"
        "2026-01-10,intervals,500,2:06.0,161,\n"
        "2026-01-12,steady_state,10000,2:15.0,150,easy 10k\n"
    )
    response = upload(client, csv_text)
    assert response.status_code == 200
    assert response.json() == {
        "workouts_created": 2,
        "tests_created": 0,
        "pieces_created": 4,
    }
    workouts = client.get("/workouts").json()
    assert len(workouts) == 2
    intervals = next(
        w for w in workouts if w["workout_type"] == "intervals"
    )
    steady = next(
        w for w in workouts if w["workout_type"] == "steady_state"
    )
    assert [piece["sequence"] for piece in intervals["pieces"]] == [1, 2, 3]
    assert intervals["notes"] == "4x500m"
    assert len(steady["pieces"]) == 1
    assert steady["pieces"][0]["sequence"] == 1


def test_non_consecutive_same_date_rows_are_separate_workouts(client):
    csv_text = (
        "date,workout_type,meters,time_seconds\n"
        "2026-01-10,intervals,500,125.0\n"
        "2026-01-10,steady_state,5000,1250.0\n"
        "2026-01-10,intervals,500,124.0\n"
    )
    response = upload(client, csv_text)
    assert response.status_code == 200
    assert response.json()["workouts_created"] == 3
    workouts = client.get("/workouts").json()
    assert len(workouts) == 3
    assert all(len(workout["pieces"]) == 1 for workout in workouts)


def test_kind_test_creates_erg_test_with_derived_time(client):
    csv_text = (
        "date,kind,meters,split,avg_hr,max_hr,notes\n"
        "2026-02-01,test,2000,2:05.0,178,186,season 2k\n"
    )
    response = upload(client, csv_text)
    assert response.status_code == 200
    assert response.json() == {
        "workouts_created": 0,
        "tests_created": 1,
        "pieces_created": 0,
    }
    tests = client.get("/erg-tests").json()
    assert len(tests) == 1
    erg_test = tests[0]
    assert erg_test["date"] == "2026-02-01"
    assert erg_test["distance_meters"] == 2000
    assert erg_test["time_seconds"] == 500.0
    assert erg_test["avg_hr"] == 178
    assert erg_test["max_hr"] == 186
    assert erg_test["notes"] == "season 2k"


def test_atomicity_nothing_written_on_invalid_row(client):
    csv_text = (
        "date,workout_type,meters,split\n"
        "2026-01-10,intervals,500,2:05.0\n"
        "2026-01-10,intervals,500,banana\n"
    )
    response = upload(client, csv_text)
    assert response.status_code == 422
    assert "row 2" in response.json()["detail"]
    assert client.get("/workouts").json() == []


def test_row_error_numbering_uses_data_rows(client):
    csv_text = (
        "date,workout_type,meters,split\n"
        "2026-01-10,intervals,500,2:05.0\n"
        "2026-01-10,intervals,500,2:05.0\n"
        "2026-01-11,intervals,0,2:05.0\n"
    )
    response = upload(client, csv_text)
    assert response.status_code == 422
    assert response.json()["detail"] == "row 3: meters must be > 0"
    assert client.get("/workouts").json() == []


def test_time_seconds_and_split_mutually_exclusive(client):
    headers = "date,workout_type,meters,time_seconds,split\n"
    both = headers + "2026-01-10,intervals,500,125.0,2:05.0\n"
    response = upload(client, both)
    assert response.status_code == 422
    assert "time_seconds or split" in response.json()["detail"]
    neither = headers + "2026-01-10,intervals,500,,\n"
    response = upload(client, neither)
    assert response.status_code == 422
    assert "time_seconds or split" in response.json()["detail"]


def test_headers_only_and_zero_byte_files_return_zeros(client):
    response = upload(client, HEADERS + "\n")
    assert response.status_code == 200
    assert response.json() == {
        "workouts_created": 0,
        "tests_created": 0,
        "pieces_created": 0,
    }
    response = upload(client, "")
    assert response.status_code == 200
    assert response.json() == {
        "workouts_created": 0,
        "tests_created": 0,
        "pieces_created": 0,
    }


def test_unknown_column_rejected(client):
    csv_text = "date,meters,time_seconds,color\n2026-01-10,1000,250.0,red\n"
    response = upload(client, csv_text)
    assert response.status_code == 422
    assert "color" in response.json()["detail"]


def test_empty_date_rejected(client):
    csv_text = "date,meters,time_seconds\n,1000,250.0\n"
    response = upload(client, csv_text)
    assert response.status_code == 422
    assert response.json()["detail"] == "row 1: date is required"


def test_forbidden_columns_on_test_rows_rejected(client):
    csv_text = (
        "date,kind,meters,time_seconds,spm\n"
        "2026-02-01,test,2000,480.0,30\n"
    )
    response = upload(client, csv_text)
    assert response.status_code == 422
    assert "spm not allowed on test rows" in response.json()["detail"]
