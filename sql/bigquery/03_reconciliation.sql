-- Reconciliation: does the header table agree with the detail table?
-- `orders.num_of_item` should equal the number of rows in `order_items`.

WITH items AS (
  SELECT order_id, COUNT(*) AS item_rows
  FROM `bigquery-public-data.thelook_ecommerce.order_items`
  GROUP BY order_id
)
SELECT o.order_id, o.num_of_item, i.item_rows
FROM `bigquery-public-data.thelook_ecommerce.orders` o
LEFT JOIN items i USING (order_id)
WHERE o.num_of_item <> IFNULL(i.item_rows, 0);

-- Daily totals: the kind of check run after every pipeline load,
-- comparing what a source reports with what landed in the warehouse.
SELECT
  DATE(created_at)            AS order_day,
  COUNT(DISTINCT order_id)    AS orders,
  COUNT(*)                    AS items,
  ROUND(SUM(sale_price), 2)   AS revenue
FROM `bigquery-public-data.thelook_ecommerce.order_items`
GROUP BY order_day
ORDER BY order_day DESC
LIMIT 30;
