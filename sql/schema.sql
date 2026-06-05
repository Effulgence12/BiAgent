-- MySQL schema for the Olist Agentic BI project.
-- Load raw CSV data into these base tables before refreshing mv_* aggregate tables.

CREATE DATABASE IF NOT EXISTS agentic_bi_olist
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;
USE agentic_bi_olist;

CREATE TABLE IF NOT EXISTS customers (
  customer_id VARCHAR(64) PRIMARY KEY,
  customer_unique_id VARCHAR(64),
  customer_zip_code_prefix INT,
  customer_city VARCHAR(128),
  customer_state CHAR(2),
  INDEX idx_customers_state (customer_state)
);

CREATE TABLE IF NOT EXISTS orders (
  order_id VARCHAR(64) PRIMARY KEY,
  customer_id VARCHAR(64) NOT NULL,
  order_status VARCHAR(32),
  order_purchase_timestamp DATETIME,
  order_approved_at DATETIME NULL,
  order_delivered_carrier_date DATETIME NULL,
  order_delivered_customer_date DATETIME NULL,
  order_estimated_delivery_date DATETIME NULL,
  INDEX idx_orders_customer (customer_id),
  INDEX idx_orders_purchase_status (order_purchase_timestamp, order_status),
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);

CREATE TABLE IF NOT EXISTS products (
  product_id VARCHAR(64) PRIMARY KEY,
  product_category_name VARCHAR(128),
  product_name_length INT NULL,
  product_description_length INT NULL,
  product_photos_qty INT NULL,
  product_weight_g INT NULL,
  product_length_cm INT NULL,
  product_height_cm INT NULL,
  product_width_cm INT NULL,
  INDEX idx_products_category (product_category_name)
);

CREATE TABLE IF NOT EXISTS sellers (
  seller_id VARCHAR(64) PRIMARY KEY,
  seller_zip_code_prefix INT,
  seller_city VARCHAR(128),
  seller_state CHAR(2),
  INDEX idx_sellers_state (seller_state)
);

CREATE TABLE IF NOT EXISTS geolocation (
  geolocation_zip_code_prefix INT,
  geolocation_lat DECIMAL(10, 7),
  geolocation_lng DECIMAL(10, 7),
  geolocation_city VARCHAR(128),
  geolocation_state CHAR(2),
  INDEX idx_geolocation_zip (geolocation_zip_code_prefix),
  INDEX idx_geolocation_state (geolocation_state)
);

CREATE TABLE IF NOT EXISTS product_category_name_translation (
  product_category_name VARCHAR(128) PRIMARY KEY,
  product_category_name_english VARCHAR(128)
);

CREATE TABLE IF NOT EXISTS order_items (
  order_id VARCHAR(64) NOT NULL,
  order_item_id INT NOT NULL,
  product_id VARCHAR(64),
  seller_id VARCHAR(64),
  shipping_limit_date DATETIME NULL,
  price DECIMAL(12, 2),
  freight_value DECIMAL(12, 2),
  PRIMARY KEY (order_id, order_item_id),
  INDEX idx_items_product (product_id),
  INDEX idx_items_seller (seller_id),
  CONSTRAINT fk_items_order FOREIGN KEY (order_id) REFERENCES orders (order_id),
  CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products (product_id),
  CONSTRAINT fk_items_seller FOREIGN KEY (seller_id) REFERENCES sellers (seller_id)
);

CREATE TABLE IF NOT EXISTS order_payments (
  order_id VARCHAR(64) NOT NULL,
  payment_sequential INT NOT NULL,
  payment_type VARCHAR(32),
  payment_installments INT,
  payment_value DECIMAL(12, 2),
  PRIMARY KEY (order_id, payment_sequential),
  INDEX idx_payments_type_installments (payment_type, payment_installments),
  CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES orders (order_id)
);

CREATE TABLE IF NOT EXISTS order_reviews (
  review_id VARCHAR(64),
  order_id VARCHAR(64) NOT NULL,
  review_score INT,
  review_comment_title TEXT NULL,
  review_comment_message TEXT NULL,
  review_creation_date DATETIME NULL,
  review_answer_timestamp DATETIME NULL,
  PRIMARY KEY (review_id, order_id),
  INDEX idx_reviews_order (order_id),
  INDEX idx_reviews_score (review_score),
  INDEX idx_reviews_creation_date (review_creation_date),
  CONSTRAINT fk_reviews_order FOREIGN KEY (order_id) REFERENCES orders (order_id)
);
