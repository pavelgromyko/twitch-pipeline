-- Virtual datasets of Superset (SQL Lab -> Save dataset). Kept here so dashboards can be rebuilt.

-- Dataset: language_share
SELECT
    language,
    sum(viewer_count) AS viewers,
    round(100 * sum(viewer_count) / (SELECT sum(viewer_count) FROM twitch.latest_snapshot), 1) AS share_pct
FROM twitch.latest_snapshot
GROUP BY language
ORDER BY viewers DESC
LIMIT 10;

-- Dataset: game_concentration
SELECT
    game_name,
    sum(viewer_count) AS viewers,
    count() AS streams,
    round(100 * arraySum(arraySlice(arrayReverseSort(groupArray(viewer_count)), 1, 3))
          / sum(viewer_count), 1) AS top3_share_pct
FROM twitch.latest_snapshot
WHERE game_id != 0
GROUP BY game_name
HAVING streams >= 5
ORDER BY viewers DESC
LIMIT 10;

-- Dataset: genre_audience
-- A game with several genres is counted under its most common genre in the IGDB catalog.
WITH
    genre_freq AS (
        SELECT genre, count() AS games
        FROM twitch.dim_games
        ARRAY JOIN genres AS genre
        GROUP BY genre
    ),
    main_genre AS (
        SELECT g.game_id AS game_id, argMax(g.genre, f.games) AS genre
        FROM (SELECT game_id, genre FROM twitch.dim_games ARRAY JOIN genres AS genre) AS g
        INNER JOIN genre_freq AS f ON g.genre = f.genre
        GROUP BY g.game_id
    )
SELECT
    if(m.genre = '', 'Unknown', m.genre) AS genre_name,
    sum(s.viewer_count) AS viewers,
    round(100 * sum(s.viewer_count) / (SELECT sum(viewer_count) FROM twitch.latest_snapshot), 1) AS share_pct
FROM twitch.latest_snapshot AS s
LEFT JOIN main_genre AS m ON s.game_id = m.game_id
GROUP BY genre_name
ORDER BY viewers DESC;

-- Datasets on views (no SQL): latest_snapshot, last_day (see 03_views.sql)
-- Custom metric on the "Last 24 hours" dashboard, name viewers_per_snapshot:
--   SUM(viewer_count) / COUNT(DISTINCT snapshot_ts)