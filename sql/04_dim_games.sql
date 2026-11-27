CREATE TABLE IF NOT EXISTS twitch.dim_games
(
    game_id            UInt64,
    game_name          String,
    igdb_id            UInt64,
    igdb_name          String,
    first_release_date Nullable(Date),
    genres             Array(String),
    themes             Array(String),
    genre_source       LowCardinality(String),
    updated_at         DateTime
)
ENGINE = MergeTree
ORDER BY game_id;