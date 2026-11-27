CREATE DATABASE IF NOT EXISTS twitch;

CREATE TABLE IF NOT EXISTS twitch.stream_snapshots
(
    snapshot_ts  DateTime('UTC'),
    rank         UInt16,
    stream_id    UInt64,
    user_id      UInt64,
    user_login   String,
    game_id      UInt64,
    game_name    LowCardinality(String),
    language     LowCardinality(String),
    viewer_count UInt32,
    started_at   DateTime('UTC'),
    is_mature    Bool
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(snapshot_ts)
ORDER BY (game_id, snapshot_ts, rank);