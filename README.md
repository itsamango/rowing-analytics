# rowing-analytics

Personal rowing training analytics REST API: workouts with interval pieces, real erg test scores, pace projections, and all-time/weekly stats. Built with FastAPI + SQLAlchemy (SQLite).

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

Interactive API docs at http://127.0.0.1:8000/docs.

The SQLite database lives at `data/rowing.db` (created at startup). Override the location with `ROWING_DB_PATH` (absolute path, or relative to the project root):

```bash
ROWING_DB_PATH=/tmp/rowing.db uvicorn app.main:app --reload
```

## Concepts

- **Workout** — a dated session (`steady_state`, `intervals`, `test`, `other`) with zero or more **interval pieces**. Each piece stores `meters`, `time_seconds`, and optional `avg_hr`, `max_hr`, `spm`, `notes`; its sequence number reflects order within the workout.
- **Splits** are never stored. Pieces store meters + time; every split (time per 500m), formatted split, and watts figure in responses is derived on the fly.
- **Erg test** — a real, raced score: a date, a single `distance_meters` (2k, 6k, …), and `time_seconds`. Tests are separate from workouts and power the "best score" and projections features.
- **Quick-log** — a shortcut for one-piece steady sessions: POST a single meters/time (or meters/split) pair with optional HR instead of assembling a pieces array. Provide exactly one of `time_seconds` or `split`; `time = split × meters / 500`.

## API reference

All requests/responses are JSON unless noted. Shared examples used below:

- a 4x500m interval workout (declining splits, rising HR)
- a 10k steady state at 2:15.0 / 150 bpm
- a 2k erg test in 8:00.0

### Health

#### `GET /health`

Liveness check.

```bash
curl http://127.0.0.1:8000/health
```

```json
{"status": "ok"}
```

### Workouts

#### `POST /workouts`

Create a workout with ordered pieces. `pieces[].sequence` is assigned 1, 2, 3… from array order.

```bash
curl -X POST http://127.0.0.1:8000/workouts \
  -H "Content-Type: application/json" \
  -d '{
        "date": "2026-09-28",
        "workout_type": "intervals",
        "notes": "4x500m, rolling starts",
        "pieces": [
          {"meters": 500, "time_seconds": 118.0, "avg_hr": 162, "max_hr": 171, "spm": 30},
          {"meters": 500, "time_seconds": 117.5, "avg_hr": 163, "max_hr": 172, "spm": 31},
          {"meters": 500, "time_seconds": 117.0, "avg_hr": 165, "max_hr": 173, "spm": 31},
          {"meters": 500, "time_seconds": 116.8, "avg_hr": 166, "max_hr": 174, "spm": 32}
        ]
      }'
```

```json
{
  "id": 1,
  "date": "2026-09-28",
  "workout_type": "intervals",
  "notes": "4x500m, rolling starts",
  "pieces": [
    {"id": 1, "sequence": 1, "meters": 500, "time_seconds": 118.0, "avg_hr": 162, "max_hr": 171, "spm": 30.0, "notes": null, "split_seconds": 118.0, "split_formatted": "1:58.0", "watts": 427.53},
    {"id": 2, "sequence": 2, "meters": 500, "time_seconds": 117.5, "avg_hr": 163, "max_hr": 172, "spm": 31.0, "notes": null, "split_seconds": 117.5, "split_formatted": "1:57.5", "watts": 433.0},
    {"id": 3, "sequence": 3, "meters": 500, "time_seconds": 117.0, "avg_hr": 165, "max_hr": 173, "spm": 31.0, "notes": null, "split_seconds": 117.0, "split_formatted": "1:57.0", "watts": 438.56},
    {"id": 4, "sequence": 4, "meters": 500, "time_seconds": 116.8, "avg_hr": 166, "max_hr": 174, "spm": 32.0, "notes": null, "split_seconds": 116.8, "split_formatted": "1:56.8", "watts": 440.78}
  ],
  "total_meters": 2000,
  "total_time_seconds": 469.3
}
```

#### `POST /workouts/quick-log`

Log a single-piece session. `date` defaults to today, `workout_type` to `steady_state`. Provide exactly one of `time_seconds` or `split` (e.g. `"2:15.0"`).

```bash
curl -X POST http://127.0.0.1:8000/workouts/quick-log \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-09-26", "meters": 10000, "split": "2:15.0", "avg_hr": 150, "max_hr": 158, "spm": 22, "notes": "easy aerobic 10k"}'
```

```json
{
  "id": 2,
  "date": "2026-09-26",
  "workout_type": "steady_state",
  "notes": "easy aerobic 10k",
  "pieces": [
    {"id": 5, "sequence": 1, "meters": 10000, "time_seconds": 2700.0, "avg_hr": 150, "max_hr": 158, "spm": 22.0, "notes": null, "split_seconds": 135.0, "split_formatted": "2:15.0", "watts": 286.04}
  ],
  "total_meters": 10000,
  "total_time_seconds": 2700.0
}
```

#### `GET /workouts`

List workouts, newest first.

| Param | Type | Default | Notes |
|---|---|---|---|
| `type` | string | — | filter by workout type |
| `since` | date | — | inclusive lower bound on `date` |
| `until` | date | — | inclusive upper bound on `date` |
| `limit` | int | 50 | max 200 |

```bash
curl "http://127.0.0.1:8000/workouts?type=steady_state&since=2026-09-01&limit=10"
```

#### `GET /workouts/{workout_id}`

Fetch one workout. `404` if unknown.

```bash
curl http://127.0.0.1:8000/workouts/1
```

#### `PUT /workouts/{workout_id}`

Replace a workout (date, type, notes, pieces) with the same body shape as `POST /workouts`.

```bash
curl -X PUT http://127.0.0.1:8000/workouts/1 \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-09-28", "workout_type": "intervals", "notes": "4x500m, rolling starts", "pieces": [{"meters": 500, "time_seconds": 116.0, "avg_hr": 165, "spm": 31}]}'
```

#### `DELETE /workouts/{workout_id}`

Delete a workout and its pieces. Returns `204`, no body.

```bash
curl -X DELETE http://127.0.0.1:8000/workouts/1
```

### Erg tests

#### `POST /erg-tests`

Record a real score.

```bash
curl -X POST http://127.0.0.1:8000/erg-tests \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-09-27", "distance_meters": 2000, "time_seconds": 480.0, "avg_hr": 178, "max_hr": 186, "notes": "season opener 2k"}'
```

```json
{"id": 1, "date": "2026-09-27", "distance_meters": 2000, "time_seconds": 480.0, "avg_hr": 178, "max_hr": 186, "notes": "season opener 2k", "split_formatted": "2:00.0"}
```

#### `GET /erg-tests`

List tests, newest first.

| Param | Type | Default | Notes |
|---|---|---|---|
| `distance` | int | — | filter by exact distance (e.g. `2000`) |

```bash
curl "http://127.0.0.1:8000/erg-tests?distance=2000"
```

#### `GET /erg-tests/best?distance={meters}`

Best (lowest-time) test at a given distance. `404` if no test at that distance.

```bash
curl "http://127.0.0.1:8000/erg-tests/best?distance=2000"
```

#### `GET /erg-tests/{erg_test_id}`

Fetch one test; `404` if unknown.

```bash
curl http://127.0.0.1:8000/erg-tests/1
```

#### `PUT /erg-tests/{erg_test_id}`

Replace a test with the same body shape as `POST /erg-tests`.

```bash
curl -X PUT http://127.0.0.1:8000/erg-tests/1 \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-09-27", "distance_meters": 2000, "time_seconds": 477.5, "avg_hr": 179, "max_hr": 187, "notes": "corrected 2k"}'
```

#### `DELETE /erg-tests/{erg_test_id}`

Delete a test. Returns `204`, no body.

```bash
curl -X DELETE http://127.0.0.1:8000/erg-tests/1
```

### Projections

#### `GET /projections`

Pace projections for standard distances (or one distance).

| Param | Type | Default | Notes |
|---|---|---|---|
| `distance` | int | all standard distances | single distance to project, e.g. `6000` |

```bash
curl "http://127.0.0.1:8000/projections?distance=6000"
```

```json
{
  "model": {"a": 110.0, "b": 4.7, "r2": 0.93, "n_points": 7, "n_distinct_distances": 3},
  "pauls_reference": {"id": 1, "date": "2026-09-27", "distance_meters": 2000, "split_seconds": 120.0},
  "rows": [
    {
      "meters": 6000,
      "regression_split_seconds": 122.4,
      "regression_split_formatted": "2:02.4",
      "regression_watts": 396.4,
      "pauls_split_seconds": 126.4,
      "pauls_split_formatted": "2:06.4",
      "pauls_watts": 361.5
    }
  ]
}
```

Each row compares two models at that distance (see [Projections](#projections-1) below). Rows carry `null` model fields when a model can't run.

### Stats

#### `GET /stats`

All-time and weekly training summary.

- `total_workouts`, `total_pieces`, `total_tests` — counts
- `total_meters`, `total_time_seconds` — sums over all pieces (0 if none)
- `avg_hr` — duration-weighted mean of piece `avg_hr` over pieces that have one (`null` if none do)
- `weekly_meters` — exactly the last 8 calendar weeks (Monday-start, oldest → newest), zero weeks included; a piece counts in the week of its **workout's** date
- `best_tests` — best (lowest-time) test per distinct distance, ordered by distance ascending

```bash
curl http://127.0.0.1:8000/stats
```

```json
{
  "total_workouts": 2,
  "total_pieces": 5,
  "total_tests": 1,
  "total_meters": 12000,
  "total_time_seconds": 3169.3,
  "avg_hr": 151.56,
  "weekly_meters": [
    {"week_start": "2026-08-10", "meters": 0},
    {"week_start": "2026-08-17", "meters": 0},
    {"week_start": "2026-08-24", "meters": 0},
    {"week_start": "2026-08-31", "meters": 0},
    {"week_start": "2026-09-07", "meters": 0},
    {"week_start": "2026-09-14", "meters": 0},
    {"week_start": "2026-09-21", "meters": 10000},
    {"week_start": "2026-09-28", "meters": 2000}
  ],
  "best_tests": [
    {"id": 1, "date": "2026-09-27", "distance_meters": 2000, "time_seconds": 480.0, "avg_hr": 178, "max_hr": 186, "notes": "season opener 2k", "split_formatted": "2:00.0"}
  ]
}
```

### Import

#### `POST /import/csv`

Bulk-load sessions from a UTF-8 CSV file (multipart upload) — see [CSV import](#csv-import) below.

```bash
curl -F "file=@sessions.csv" http://127.0.0.1:8000/import/csv
```

```json
{"workouts_created": 2, "tests_created": 1, "pieces_created": 5}
```

## Projections

Two models estimate your split at any distance from the data you've logged:

- **Regression model (yours):** fits `split = a + b·log2(meters)` over all pieces ≥ 100m and all erg tests. The slope `b` is *your* seconds-per-doubling of distance — how much your /500m pace slows each time the distance doubles. It's compared against **Paul's Law**, which assumes a fixed 5.0 seconds per doubling.
- **Paul's Law reference:** anchored on your **latest erg test** (`pauls_reference`): `split(d) = ref_split + 5.0 · log2(d / ref_distance)`. No reference test → no Paul's Law rows.

Notes on reading the output:

- The regression model needs pieces/tests at **≥ 2 distinct distances**; otherwise `model` is `null` and regression fields are `null`.
- `model.r2` tells you how much to trust the fit: near 1.0 means your logged data sits close to a single log-linear curve, low values mean noisy or inconsistent logging — weight the projections accordingly.
- `n_points` / `n_distinct_distances` show how much data went into the fit.
- Watts in each row are derived from the projected split for that distance.

## CSV import

`POST /import/csv` (multipart file upload) bulk-loads sessions from a UTF-8 CSV file. Column order is insensitive; header names and values are whitespace-stripped; empty trailing lines are ignored; unknown columns are rejected with a 422 listing them.

| Column | Required | Notes |
|---|---|---|
| `date` | yes | ISO `YYYY-MM-DD`; empty or unparseable → row error |
| `kind` | no | `workout` (default) or `test` |
| `workout_type` | no | one of `steady_state`, `intervals`, `test`, `other`; empty/missing → `other`; must be empty on `test` rows |
| `meters` | yes | integer > 0; the test distance on `test` rows |
| `time_seconds` | exactly one of `time_seconds` / `split` | float > 0 |
| `split` | exactly one of `time_seconds` / `split` | `2:05.0` formatted or raw seconds string; missing side is derived via `time = split × meters / 500` |
| `avg_hr` | no | integer; piece HR on workout rows, test HR on `test` rows |
| `max_hr` | no | integer; piece max HR on workout rows, test max HR on `test` rows |
| `spm` | no | float; workout rows only — must be empty on `test` rows |
| `notes` | no | piece notes on workout rows; test notes on `test` rows |
| `workout_notes` | no | workout-level notes, taken from the first row of a group that has one; must be empty on `test` rows |

### Grouping

- Consecutive rows with the same `date` and `workout_type` merge into one `Workout`; its pieces keep file order and are numbered `sequence` 1, 2, 3, …
- Non-consecutive rows with the same date form separate workouts (any intervening row breaks the run).
- `kind=test` rows are never grouped: each row becomes one `ErgTest`.

### Example

```csv
date,kind,workout_type,meters,split,avg_hr,max_hr,spm,notes,workout_notes
2026-03-01,workout,intervals,500,2:05.0,162,171,30,rep 1,4x500m
2026-03-01,workout,intervals,500,2:04.5,164,172,31,rep 2,
2026-03-01,workout,intervals,500,2:04.0,165,173,31,rep 3,
2026-03-01,workout,intervals,500,2:03.8,166,174,32,rep 4,
2026-03-02,workout,steady_state,10000,2:15.0,150,158,22,,easy aerobic 10k
2026-03-03,test,,2000,2:00.0,178,186,,season opener 2k,
```

```bash
curl -F "file=@sessions.csv" http://127.0.0.1:8000/import/csv
```

```json
{"workouts_created": 2, "tests_created": 1, "pieces_created": 5}
```

### Errors

Import is atomic and all-or-nothing: every row is validated before anything is written. If any row is invalid, the response is 422 with a `detail` like `"row 3: meters must be > 0"` (data rows are numbered from 1, excluding the header) and nothing is written to the database. An empty file or a headers-only file returns 200 with all-zero counts.

## Project structure

```
rowing-analytics/
├── app/
│   ├── main.py            FastAPI app + router registration
│   ├── models.py          SQLAlchemy models: Workout, IntervalPiece, ErgTest
│   ├── schemas.py         Pydantic request/response schemas
│   ├── database.py        engine/session, ROWING_DB_PATH resolution
│   ├── utils.py           split / watts / formatting helpers
│   ├── projections.py     pace-curve regression + Paul's Law
│   └── routers/
│       ├── health.py      GET /health
│       ├── workouts.py    /workouts CRUD + quick-log
│       ├── erg_tests.py   /erg-tests CRUD + best
│       ├── projections.py GET /projections
│       ├── stats.py       GET /stats
│       └── import_csv.py  POST /import/csv
├── tests/                 pytest suite (one file per router)
├── conftest.py            client fixture (tmp DB per test)
├── data/rowing.db         default SQLite DB (gitignored)
├── requirements.txt
├── requirements-dev.txt
└── pytest.ini
```

## Tests

```bash
.venv/bin/pytest
```

Each test runs against its own throwaway SQLite database via `ROWING_DB_PATH`, so the suite never touches your real data.

## Configuration

- `ROWING_DB_PATH`: SQLite database path (default `data/rowing.db`, created at startup). Relative paths resolve against the project root.
