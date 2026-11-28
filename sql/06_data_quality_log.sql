CREATE TABLE IF NOT EXISTS twitch.data_quality_log
(
    checked_at DateTime('UTC'),
    check_name LowCardinality(String),
    value      Nullable(Float64),
    status     LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY (check_name, checked_at);