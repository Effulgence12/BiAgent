-- MySQL pre-aggregated tables for high-frequency Olist BI queries.
USE agentic_bi_olist;

DROP TABLE IF EXISTS mv_monthly_sales;
CREATE TABLE mv_monthly_sales AS
SELECT
  DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS `year_month`,
  COUNT(DISTINCT o.order_id) AS total_orders,
  COUNT(DISTINCT c.customer_unique_id) AS unique_customers,
  SUM(oi.price + oi.freight_value) AS total_gmv,
  SUM(oi.price + oi.freight_value) / NULLIF(COUNT(DISTINCT o.order_id), 0) AS avg_basket,
  AVG(oi.price) AS avg_price,
  SUM(oi.freight_value) AS total_freight
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_status = 'delivered'
GROUP BY `year_month`;
CREATE INDEX idx_mv_monthly_sales_year_month ON mv_monthly_sales (`year_month`);

DROP TABLE IF EXISTS mv_state_sales;
CREATE TABLE mv_state_sales AS
SELECT
  DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS `year_month`,
  c.customer_state,
  COUNT(DISTINCT o.order_id) AS total_orders,
  COUNT(DISTINCT c.customer_unique_id) AS unique_customers,
  SUM(oi.price + oi.freight_value) AS total_gmv,
  SUM(oi.price + oi.freight_value) / NULLIF(COUNT(DISTINCT o.order_id), 0) AS avg_order_value
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_status = 'delivered'
GROUP BY `year_month`, c.customer_state;
CREATE INDEX idx_mv_state_sales_month_state ON mv_state_sales (`year_month`, customer_state);

DROP TABLE IF EXISTS mv_category_sales;
CREATE TABLE mv_category_sales AS
SELECT
  DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS `year_month`,
  COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS product_category_name,
  COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS product_category_english,
  COUNT(DISTINCT o.order_id) AS total_orders,
  COUNT(*) AS total_items,
  AVG(oi.price) AS avg_price,
  SUM(oi.price + oi.freight_value) AS total_gmv
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
LEFT JOIN products p ON oi.product_id = p.product_id
LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
WHERE o.order_status = 'delivered'
GROUP BY `year_month`, COALESCE(t.product_category_name_english, p.product_category_name, 'unknown');
CREATE INDEX idx_mv_category_sales_month_category ON mv_category_sales (`year_month`, product_category_name);

DROP TABLE IF EXISTS mv_delivery_perf;
CREATE TABLE mv_delivery_perf AS
SELECT
  DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS `year_month`,
  c.customer_state,
  COUNT(DISTINCT o.order_id) AS total_orders,
  AVG(TIMESTAMPDIFF(DAY, o.order_purchase_timestamp, o.order_delivered_customer_date)) AS avg_delivery_days,
  SUM(o.order_delivered_customer_date > o.order_estimated_delivery_date) AS late_orders,
  SUM(o.order_delivered_customer_date > o.order_estimated_delivery_date) AS delayed_orders,
  SUM(o.order_delivered_customer_date <= o.order_estimated_delivery_date) AS on_time_orders,
  SUM(o.order_delivered_customer_date > o.order_estimated_delivery_date) / NULLIF(COUNT(DISTINCT o.order_id), 0) AS late_rate,
  SUM(o.order_delivered_customer_date <= o.order_estimated_delivery_date) / NULLIF(COUNT(DISTINCT o.order_id), 0) AS on_time_rate
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
GROUP BY `year_month`, c.customer_state;
CREATE INDEX idx_mv_delivery_perf_month_state ON mv_delivery_perf (`year_month`, customer_state);

DROP TABLE IF EXISTS mv_seller_perf;
CREATE TABLE mv_seller_perf AS
SELECT
  DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS `year_month`,
  s.seller_id,
  s.seller_state,
  COUNT(DISTINCT o.order_id) AS total_orders,
  SUM(oi.price + oi.freight_value) AS total_gmv,
  COUNT(DISTINCT r.review_id) AS total_reviews,
  COUNT(DISTINCT CASE WHEN r.review_score <= 2 THEN r.review_id END) AS negative_reviews,
  COUNT(DISTINCT CASE WHEN r.review_score <= 2 THEN r.review_id END) / NULLIF(COUNT(DISTINCT r.review_id), 0) AS negative_rate,
  AVG(r.review_score) AS avg_review_score
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN sellers s ON oi.seller_id = s.seller_id
LEFT JOIN order_reviews r ON o.order_id = r.order_id
WHERE o.order_status = 'delivered'
GROUP BY `year_month`, s.seller_id, s.seller_state;
CREATE INDEX idx_mv_seller_perf_month_seller ON mv_seller_perf (`year_month`, seller_id);

DROP TABLE IF EXISTS mv_payment_dist;
CREATE TABLE mv_payment_dist AS
SELECT
  DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS `year_month`,
  op.payment_type,
  op.payment_installments,
  COUNT(*) AS payment_count,
  COUNT(*) AS total_transactions,
  AVG(op.payment_installments) AS avg_installments,
  SUM(op.payment_value) AS payment_value
FROM orders o
JOIN order_payments op ON o.order_id = op.order_id
WHERE o.order_status = 'delivered'
GROUP BY `year_month`, op.payment_type, op.payment_installments;
CREATE INDEX idx_mv_payment_dist_month_type ON mv_payment_dist (`year_month`, payment_type, payment_installments);

DROP TABLE IF EXISTS mv_weekly_sales;
CREATE TABLE mv_weekly_sales AS
SELECT
  DATE_SUB(DATE(o.order_purchase_timestamp), INTERVAL WEEKDAY(o.order_purchase_timestamp) DAY) AS week_start,
  COUNT(DISTINCT o.order_id) AS total_orders,
  SUM(oi.price + oi.freight_value) AS total_gmv,
  SUM(oi.price + oi.freight_value) / NULLIF(COUNT(DISTINCT o.order_id), 0) AS avg_order_value
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_status = 'delivered'
GROUP BY week_start;
CREATE INDEX idx_mv_weekly_sales_week ON mv_weekly_sales (week_start);

DROP TABLE IF EXISTS mv_state_geo;
CREATE TABLE mv_state_geo AS
WITH state_sales AS (
  SELECT
    customer_state,
    SUM(total_orders) AS total_orders,
    SUM(total_gmv) AS total_gmv,
    SUM(total_gmv) / NULLIF(SUM(total_orders), 0) AS avg_order_value
  FROM mv_state_sales
  GROUP BY customer_state
),
state_centroid AS (
  SELECT
    geolocation_state AS customer_state,
    AVG(CAST(geolocation_lat AS DECIMAL(10,6))) AS lat,
    AVG(CAST(geolocation_lng AS DECIMAL(10,6))) AS lng
  FROM geolocation
  WHERE geolocation_lat IS NOT NULL AND geolocation_lng IS NOT NULL
  GROUP BY geolocation_state
)
SELECT s.customer_state, g.lat, g.lng, s.total_orders, s.total_gmv, s.avg_order_value
FROM state_sales s
LEFT JOIN state_centroid g ON s.customer_state = g.customer_state;
CREATE INDEX idx_mv_state_geo_state ON mv_state_geo (customer_state);

DROP TABLE IF EXISTS mv_review_category_perf;
CREATE TABLE mv_review_category_perf AS
SELECT
  COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS product_category_name,
  COUNT(DISTINCT r.review_id) AS total_reviews,
  AVG(r.review_score) AS avg_review_score,
  SUM(CASE WHEN r.review_score <= 2 THEN 1 ELSE 0 END) AS negative_reviews,
  SUM(CASE WHEN r.review_score <= 2 THEN 1 ELSE 0 END) / NULLIF(COUNT(DISTINCT r.review_id), 0) AS negative_rate,
  SUM(CASE WHEN r.review_score <= 2 AND LOWER(COALESCE(r.review_comment_message, '')) LIKE '%atras%' THEN 1 ELSE 0 END) AS delay_complaints,
  SUM(CASE WHEN r.review_score <= 2 AND (
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%defeit%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%quebr%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%qualidade%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%ruim%'
  ) THEN 1 ELSE 0 END) AS quality_complaints,
  SUM(CASE WHEN r.review_score <= 2 AND (
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%errad%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%diferente%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%troca%'
  ) THEN 1 ELSE 0 END) AS wrong_item_complaints,
  SUM(CASE WHEN r.review_score <= 2 AND (
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%atend%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%respost%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%contat%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%comunic%'
  ) THEN 1 ELSE 0 END) AS service_complaints,
  SUM(CASE WHEN r.review_score <= 2 AND NOT (
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%atras%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%defeit%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%quebr%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%qualidade%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%ruim%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%errad%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%diferente%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%troca%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%atend%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%respost%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%contat%' OR
    LOWER(COALESCE(r.review_comment_message, '')) LIKE '%comunic%'
  ) THEN 1 ELSE 0 END) AS other_complaints
FROM order_reviews r
JOIN orders o ON r.order_id = o.order_id
JOIN order_items oi ON o.order_id = oi.order_id
LEFT JOIN products p ON oi.product_id = p.product_id
LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
GROUP BY COALESCE(t.product_category_name_english, p.product_category_name, 'unknown');
CREATE INDEX idx_mv_review_category_perf_rate ON mv_review_category_perf (negative_rate);

DROP TABLE IF EXISTS mv_weight_freight;
CREATE TABLE mv_weight_freight AS
SELECT
  CASE
    WHEN p.product_weight_g < 500 THEN '<0.5kg'
    WHEN p.product_weight_g < 2000 THEN '0.5-2kg'
    WHEN p.product_weight_g < 5000 THEN '2-5kg'
    WHEN p.product_weight_g < 10000 THEN '5-10kg'
    ELSE '10kg+'
  END AS weight_bucket,
  CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 'late' ELSE 'on_time' END AS delivery_status,
  COUNT(*) AS order_count,
  AVG(p.product_weight_g) AS avg_weight_g,
  AVG(p.product_length_cm * p.product_height_cm * p.product_width_cm) AS avg_volume_cm3,
  AVG(oi.freight_value) AS avg_freight,
  AVG(oi.price) AS avg_price
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p ON oi.product_id = p.product_id
WHERE o.order_status = 'delivered'
  AND p.product_weight_g IS NOT NULL
  AND oi.freight_value IS NOT NULL
GROUP BY weight_bucket, delivery_status;
CREATE INDEX idx_mv_weight_freight_bucket_status ON mv_weight_freight (weight_bucket, delivery_status);
