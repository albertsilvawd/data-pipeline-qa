-- Data quality checks on BigQuery's public dataset `thelook_ecommerce`.
-- Run in the free BigQuery sandbox: https://console.cloud.google.com/bigquery
-- Every query returns the rows that BREAK a rule. Zero rows = check passed.

-- 1. Primary key uniqueness: each order_id must appear once
SELECT order_id, COUNT(*) AS occurrences
FROM `bigquery-public-data.thelook_ecommerce.orders`
GROUP BY order_id
HAVING COUNT(*) > 1;

-- 2. Required fields must not be null
SELECT order_id, user_id, status, created_at
FROM `bigquery-public-data.thelook_ecommerce.orders`
WHERE order_id IS NULL OR user_id IS NULL OR status IS NULL OR created_at IS NULL;

-- 3. Null profile across key columns (one row summary, useful for a report)
SELECT
  COUNT(*)                                  AS total_rows,
  COUNTIF(email IS NULL)                    AS null_email,
  COUNTIF(country IS NULL)                  AS null_country,
  COUNTIF(created_at IS NULL)               AS null_created_at,
  ROUND(100 * COUNTIF(email IS NULL) / COUNT(*), 2) AS pct_null_email
FROM `bigquery-public-data.thelook_ecommerce.users`;
