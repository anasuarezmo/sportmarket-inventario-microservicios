CREATE DATABASE IF NOT EXISTS usuarios_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'usuarios_user'@'%' IDENTIFIED BY 'dev_password';
GRANT ALL PRIVILEGES ON usuarios_db.* TO 'usuarios_user'@'%';

CREATE DATABASE IF NOT EXISTS bodegas_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'bodegas_user'@'%' IDENTIFIED BY 'dev_password';
GRANT ALL PRIVILEGES ON bodegas_db.* TO 'bodegas_user'@'%';

CREATE DATABASE IF NOT EXISTS catalogo_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'catalogo_user'@'%' IDENTIFIED BY 'dev_password';
GRANT ALL PRIVILEGES ON catalogo_db.* TO 'catalogo_user'@'%';

CREATE DATABASE IF NOT EXISTS inventario_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'inventario_user'@'%' IDENTIFIED BY 'dev_password';
GRANT ALL PRIVILEGES ON inventario_db.* TO 'inventario_user'@'%';

CREATE DATABASE IF NOT EXISTS compras_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'compras_user'@'%' IDENTIFIED BY 'dev_password';
GRANT ALL PRIVILEGES ON compras_db.* TO 'compras_user'@'%';

CREATE DATABASE IF NOT EXISTS devoluciones_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'devoluciones_user'@'%' IDENTIFIED BY 'dev_password';
GRANT ALL PRIVILEGES ON devoluciones_db.* TO 'devoluciones_user'@'%';

CREATE DATABASE IF NOT EXISTS reportes_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'reportes_user'@'%' IDENTIFIED BY 'dev_password';
GRANT ALL PRIVILEGES ON reportes_db.* TO 'reportes_user'@'%';

FLUSH PRIVILEGES;
