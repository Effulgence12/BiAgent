-- MySQL pre-aggregated tables for high-frequency Olist BI queries.
USE agentic_bi_olist;

DROP TABLE IF EXISTS mv_monthly_sales;
CREATE TABLE mv_monthly_sales AS
SELECT
  DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS year_month,
  COUNT(DISTINCT o.order_id) AS total_orders,
  SUM(oi.price + oi.freight_value) AS total_gmv,
  AVG(oi.price) AS avg_price,
  SUM(oi.freight_value) AS total_freight
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_status = 'delivered'
GROUP BY year_month;
CREATE INDEX idx_mv_monthly_sales_year_month ON mv_monthly_sales (year_month);

DROP TABLE IF EXISTS mv_state_sales;
CREATE TABLE mv_state_sales AS
SELECT
  DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS year_month,
  c.customer_state,
  COUNT(DISTINCT o.order_id) AS total_orders,
  SUM(oi.price + oi.freight_value) AS total_gmv,
  SUM(oi.price + oi.freight_value) / NULLIF(COUNT(DISTINCT o.order_id), 0) AS avg_order_value
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_status = 'delivered'
GROUP BY year_month, c.customer_state;
CREATE INDEX idx_mv_state_sales_month_state ON mv_state_sales (year_month, customer_state);

DROP TABLE IF EXISTS mv_category_sales;
CREATE TABLE mv_category_sales AS
SELECT
  DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS year_month,
  COALESCE(p.product_category_name, 'unknown') AS product_category_name,
  COUNT(DISTINCT o.order_id) AS total_orders,
  COUNT(*) AS total_items,
  SUM(oi.price + oi.freight_value) AS total_gmv
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
LEFT JOIN products p ON oi.product_id = p.product_id
WHERE o.order_status = 'delivered'
GROUP BY year_month, COALESCE(p.product_category_name, 'unknown');
CREATE INDEX idx_mv_category_sales_month_category ON mv_category_sales (year_month, product_category_name);

DROP TABLE IF EXISTS mv_delivery_perf;
CREATE TABLE mv_delivery_perf AS
SELECT
  DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS year_month,
  c.customer_state,
  COUNT(DISTINCT o.order_id) AS total_orders,
  AVG(TIMESTAMPDIFF(DAY, o.order_purchase_timestamp, o.order_delivered_customer_date)) AS avg_delivery_days,
  SUM(o.order_delivered_customer_date > o.order_estimated_delivery_date) AS late_orders,
  SUM(o.order_delivered_customer_date > o.order_estimated_delivery_date) / NULLIF(COUNT(DISTINCT o.order_id), 0) AS late_rate
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
GROUP BY year_month, c.customer_state;
CREATE INDEX idx_mv_delivery_perf_month_state ON mv_delivery_perf (year_month, customer_state);

DROP TABLE IF EXISTS mv_seller_perf;
CREATE TABLE mv_seller_perf AS
SELECT
  DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS year_month,
  s.seller_id,
  s.seller_state,
  COUNT(DISTINCT o.order_id) AS total_orders,
  SUM(oi.price + oi.freight_value) AS total_gmv,
  AVG(r.review_score) AS avg_review_score
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN sellers s ON oi.seller_id = s.seller_id
LEFT JOIN order_reviews r ON o.order_id = r.order_id
WHERE o.order_status = 'delivered'
GROUP BY year_month, s.seller_id, s.seller_state;
CREATE INDEX idx_mv_seller_perf_month_seller ON mv_seller_perf (year_month, seller_id);

DROP TABLE IF EXISTS mv_payment_dist;
CREATE TABLE mv_payment_dist AS
SELECT
  DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS year_month,
  op.payment_type,
  op.payment_installments,
  COUNT(*) AS payment_count,
  SUM(op.payment_value) AS payment_value
FROM orders o
JOIN order_payments op ON o.order_id = op.order_id
WHERE o.order_status = 'delivered'
GROUP BY year_month, op.payment_type, op.payment_installments;
CREATE INDEX idx_mv_payment_dist_month_type ON mv_payment_dist (year_month, payment_type, payment_installments);
