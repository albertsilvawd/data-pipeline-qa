-- Analytics event validation on `thelook_ecommerce.events` (web clickstream).
-- Every query returns violating rows. Zero rows = check passed.

-- 1. Event types must belong to the tracking plan
SELECT event_type, COUNT(*) AS events
FROM `bigquery-public-data.thelook_ecommerce.events`
WHERE event_type NOT IN ('home', 'department', 'product', 'cart', 'purchase', 'cancel')
GROUP BY event_type;

-- 2. Required event fields
SELECT id, session_id, sequence_number, created_at, event_type
FROM `bigquery-public-data.thelook_ecommerce.events`
WHERE session_id IS NULL OR sequence_number IS NULL
   OR created_at IS NULL OR event_type IS NULL;

-- 3. Sequence integrity: no repeated sequence_number inside a session
SELECT session_id, sequence_number, COUNT(*) AS duplicates
FROM `bigquery-public-data.thelook_ecommerce.events`
GROUP BY session_id, sequence_number
HAVING COUNT(*) > 1;

-- 4. Funnel logic: a purchase should come after a cart event in the same session
WITH sessions AS (
  SELECT
    session_id,
    MIN(IF(event_type = 'cart', sequence_number, NULL))     AS first_cart,
    MIN(IF(event_type = 'purchase', sequence_number, NULL)) AS first_purchase
  FROM `bigquery-public-data.thelook_ecommerce.events`
  GROUP BY session_id
)
SELECT session_id, first_cart, first_purchase
FROM sessions
WHERE first_purchase IS NOT NULL
  AND (first_cart IS NULL OR first_cart > first_purchase);
