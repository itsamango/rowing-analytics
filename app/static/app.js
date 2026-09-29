(function () {
  "use strict";

  function formatSplit(seconds) {
    if (seconds === null || seconds === undefined || seconds < 0) return "";
    var tenths = Math.round(seconds * 10);
    var minutes = Math.floor(tenths / 600);
    var rest = tenths - minutes * 600;
    var whole = Math.floor(rest / 10);
    var tenth = rest - whole * 10;
    return minutes + ":" + (whole < 10 ? "0" : "") + whole + "." + tenth;
  }

  function toTimestamp(isoDate) {
    return new Date(isoDate + "T00:00:00").getTime();
  }

  function formatTimestamp(timestamp) {
    return new Date(timestamp).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric"
    });
  }

  function formatIsoDate(isoDate) {
    return new Date(isoDate + "T00:00:00").toLocaleDateString(undefined, {
      month: "short",
      day: "numeric"
    });
  }

  function readChartData() {
    var element = document.getElementById("chart-data");
    if (!element) return null;
    return JSON.parse(element.textContent);
  }

  function buildWeeklyMetersChart(data) {
    var canvas = document.getElementById("weekly-meters");
    if (!canvas) return;
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: data.labels,
        datasets: [
          {
            label: "Meters",
            data: data.values,
            backgroundColor: "rgba(37, 99, 235, 0.7)"
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (item) {
                return item.parsed.y.toLocaleString() + " m";
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            title: { display: true, text: "Meters" }
          }
        }
      }
    });
  }

  function buildHrVsSplitChart(points) {
    var canvas = document.getElementById("hr-vs-split");
    if (!canvas || !points.length) return;
    new Chart(canvas, {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "HR vs split",
            data: points.map(function (point) {
              return {
                x: point.split_seconds,
                y: point.avg_hr,
                point: point
              };
            }),
            backgroundColor: "rgba(220, 38, 38, 0.8)",
            pointRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: function (items) {
                return items[0].raw.point.date;
              },
              label: function (item) {
                var point = item.raw.point;
                return [
                  point.workout_type,
                  point.meters.toLocaleString() + " m",
                  "Split " + point.split_formatted,
                  "HR " + point.avg_hr + " bpm"
                ];
              }
            }
          }
        },
        scales: {
          x: {
            type: "linear",
            title: { display: true, text: "Split (per 500m)" },
            ticks: {
              callback: function (value) {
                return formatSplit(value);
              }
            }
          },
          y: {
            title: { display: true, text: "Avg HR (bpm)" }
          }
        }
      }
    });
  }

  function buildTestProgressionChart(series) {
    var canvas = document.getElementById("test-progression");
    if (!canvas || !series.length) return;
    var datasets = series.map(function (entry) {
      var points = entry.points.map(function (point) {
        return {
          x: toTimestamp(point.date),
          y: point.split_seconds,
          point: point
        };
      });
      if (points.length >= 2) {
        return {
          type: "line",
          label: entry.label,
          data: points,
          tension: 0.2,
          pointRadius: 3,
          borderWidth: 2
        };
      }
      return {
        type: "scatter",
        label: entry.label,
        data: points,
        pointRadius: 4
      };
    });
    new Chart(canvas, {
      type: "scatter",
      data: { datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom" },
          tooltip: {
            callbacks: {
              title: function (items) {
                var raw = items[0].raw;
                return raw && raw.point ? formatIsoDate(raw.point.date) : "";
              },
              label: function (item) {
                var point = item.raw.point;
                return (
                  item.dataset.label +
                  ": " +
                  point.split_formatted +
                  " split (" +
                  point.time_formatted +
                  ")"
                );
              }
            }
          }
        },
        scales: {
          x: {
            type: "linear",
            title: { display: true, text: "Date" },
            ticks: {
              callback: function (value) {
                return formatTimestamp(value);
              }
            }
          },
          y: {
            title: { display: true, text: "Split (per 500m)" },
            ticks: {
              callback: function (value) {
                return formatSplit(value);
              }
            }
          }
        }
      }
    });
  }

  function init() {
    var data = readChartData();
    if (!data) return;
    buildWeeklyMetersChart(data.weekly_meters);
    buildHrVsSplitChart(data.hr_vs_split);
    buildTestProgressionChart(data.test_progression);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
