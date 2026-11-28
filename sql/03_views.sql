CREATE OR REPLACE VIEW twitch.latest_snapshot AS
SELECT *
FROM twitch.stream_snapshots
WHERE snapshot_ts = (SELECT max(snapshot_ts) FROM twitch.stream_snapshots);

CREATE OR REPLACE VIEW twitch.last_day AS
SELECT *
FROM twitch.stream_snapshots
WHERE snapshot_ts > (SELECT max(snapshot_ts) FROM twitch.stream_snapshots) - INTERVAL 1 DAY;

CREATE OR REPLACE VIEW twitch.dq_latest AS
SELECT
    check_name,
    argMax(value, checked_at) AS last_value,
    argMax(status, checked_at) AS last_status,
    max(checked_at) AS last_checked_at
FROM twitch.data_quality_log
GROUP BY check_name;