-- Run this once with a local MySQL administrator account.
-- Replace the placeholder password before executing. Do not commit a real password.

CREATE DATABASE IF NOT EXISTS shop_support_dev
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS shop_support_test
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'shop_support_app'@'localhost'
  IDENTIFIED BY 'REPLACE_WITH_A_STRONG_PASSWORD';
CREATE USER IF NOT EXISTS 'shop_support_app'@'127.0.0.1'
  IDENTIFIED BY 'REPLACE_WITH_A_STRONG_PASSWORD';

GRANT ALL PRIVILEGES ON shop_support_dev.* TO 'shop_support_app'@'localhost';
GRANT ALL PRIVILEGES ON shop_support_dev.* TO 'shop_support_app'@'127.0.0.1';
GRANT ALL PRIVILEGES ON shop_support_test.* TO 'shop_support_app'@'localhost';
GRANT ALL PRIVILEGES ON shop_support_test.* TO 'shop_support_app'@'127.0.0.1';

FLUSH PRIVILEGES;
