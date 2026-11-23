-- Base compras_db creada por docker/mysql/init/01-crear-bases.sql de Edwin.
CREATE TABLE IF NOT EXISTS proveedor (
 id INT PRIMARY KEY AUTO_INCREMENT,
 nit VARCHAR(20) NOT NULL UNIQUE,
 razon_social VARCHAR(150) NOT NULL,
 contacto VARCHAR(100) NULL,
 email VARCHAR(120) NULL,
 telefono VARCHAR(30) NULL,
 direccion VARCHAR(150) NULL,
 proveedor_activo BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS producto_proveedor (
 id INT PRIMARY KEY AUTO_INCREMENT,
 proveedor_id INT NOT NULL,
 producto_id INT NOT NULL,
 costo_referencia DECIMAL(12,2) NOT NULL,
 UNIQUE KEY uk_proveedor_producto (proveedor_id, producto_id),
 FOREIGN KEY (proveedor_id) REFERENCES proveedor(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS orden_compra (
 id INT PRIMARY KEY AUTO_INCREMENT,
 numero VARCHAR(20) UNIQUE,
 proveedor_id INT NOT NULL,
 bodega_destino_id INT NOT NULL,
 estado ENUM('CREADA','PARCIALMENTE_RECIBIDA','RECIBIDA','CANCELADA') NOT NULL DEFAULT 'CREADA',
 total DECIMAL(14,2) NOT NULL DEFAULT 0,
 usuario_registrador_id INT NULL,
 fecha_creacion_orden DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (proveedor_id) REFERENCES proveedor(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS orden_detalle (
 id INT PRIMARY KEY AUTO_INCREMENT,
 orden_id INT NOT NULL,
 producto_id INT NOT NULL,
 cantidad_solicitada INT NOT NULL,
 cantidad_recibida INT NOT NULL DEFAULT 0,
 costo_unitario DECIMAL(12,2) NOT NULL,
 FOREIGN KEY (orden_id) REFERENCES orden_compra(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS recepcion (
 id INT PRIMARY KEY AUTO_INCREMENT,
 orden_id INT NOT NULL,
 fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 usuario_receptor_id INT NULL,
 estado ENUM('SINCRONIZADA','PENDIENTE_DE_SINCRONIZAR','RECHAZADA') NOT NULL DEFAULT 'PENDIENTE_DE_SINCRONIZAR',
 FOREIGN KEY (orden_id) REFERENCES orden_compra(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS recepcion_detalle (
 id INT PRIMARY KEY AUTO_INCREMENT,
 recepcion_id INT NOT NULL,
 orden_detalle_id INT NOT NULL,
 cantidad_recibida INT NOT NULL,
 operacion_id CHAR(36) NOT NULL UNIQUE,
 aplicada BOOLEAN NOT NULL DEFAULT FALSE,
 FOREIGN KEY (recepcion_id) REFERENCES recepcion(id),
 FOREIGN KEY (orden_detalle_id) REFERENCES orden_detalle(id)
) ENGINE=InnoDB;
