CREATE OR REPLACE VIEW twitch.latest_snapshot AS
SELECT *
FROM twitch.stream_snapshots
WHERE snapshot_ts = (SELECT max(snapshot_ts) FROM twitch.stream_snapshots);

CREATE OR REPLACE VIEW twitch.last_day AS
SELECT *
FROM twitch.stream_snapshots
WHERE snapshot_ts > (SELECT max(snapshot_ts) FROM twitch.stream_snapshots) - INTERVAL 1 DAY;