-- Referential integrity and business rules on `thelook_ecommerce`.
-- Every query returns violating rows. Zero rows = check passed.

-- 1. Orphan records: order items whose order does not exist
SELECT oi.id, oi.order_id
FROM `bigquery-public-data.thelook_ecommerce.order_items` oi
LEFT JOIN `bigquery-public-data.thelook_ecommerce.orders` o USING (order_id)
WHERE o.order_id IS NULL;

-- 2. Orders whose customer does not exist
SELECT o.order_id, o.user_id
FROM `bigquery-public-data.thelook_ecommerce.orders` o
LEFT JOIN `bigquery-public-data.thelook_ecommerce.users` u ON u.id = o.user_id
WHERE u.id IS NULL;

-- 3. Accepted values for order status
SELECT status, COUNT(*) AS orders
FROM `bigquery-public-data.thelook_ecommerce.orders`
WHERE status NOT IN ('Processing', 'Shipped', 'Complete', 'Cancelled', 'Returned')
GROUP BY status;

-- 4. Timeline consistency: an order cannot ship before it was created
--    or be delivered before it shipped
SELECT order_id, created_at, shipped_at, delivered_at
FROM `bigquery-public-data.thelook_ecommerce.orders`
WHERE shipped_at < created_at
   OR delivered_at < shipped_at;

-- 5. Price sanity: sale price must be positive
SELECT id, order_id, sale_price
FROM `bigquery-public-data.thelook_ecommerce.order_items`
WHERE sale_price IS NULL OR sale_price <= 0;
