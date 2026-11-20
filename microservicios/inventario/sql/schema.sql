-- Esquema de inventario_db (diseño de la Entrega 2). Se aplica al arrancar el servicio.
-- producto_id y bodega_id son identificadores de otros servicios (sin llave foránea).
CREATE TABLE IF NOT EXISTS saldo (
  id INT AUTO_INCREMENT PRIMARY KEY,
  producto_id INT NOT NULL,
  bodega_id INT NOT NULL,
  cantidad_disponible INT NOT NULL DEFAULT 0,
  stock_minimo INT NOT NULL DEFAULT 0,
  fecha_actualizacion_saldo DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT uq_saldo_producto_bodega UNIQUE (producto_id, bodega_id),
  CONSTRAINT ck_saldo_cantidad CHECK (cantidad_disponible >= 0),
  CONSTRAINT ck_saldo_minimo CHECK (stock_minimo >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS movimiento (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  operacion_id CHAR(36) NOT NULL,
  tipo_movimiento ENUM('ENTRADA','SALIDA','AJUSTE','TRASLADO') NOT NULL,
  producto_id INT NOT NULL,
  bodega_origen_id INT NULL,
  bodega_destino_id INT NULL,
  cantidad_movimiento INT NOT NULL,
  saldo_resultante INT NOT NULL,
  motivo_movimiento VARCHAR(200) NULL,
  origen_movimiento ENUM('MANUAL','COMPRA','DEVOLUCION') NOT NULL,
  documento_ref VARCHAR(40) NULL,
  usuario_id INT NULL,
  fecha_registro_movimiento DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_movimiento_operacion UNIQUE (operacion_id),
  INDEX idx_mov_producto (producto_id),
  INDEX idx_mov_origen (bodega_origen_id),
  INDEX idx_mov_destino (bodega_destino_id),
  INDEX idx_mov_fecha (fecha_registro_movimiento)
) ENGINE=InnoDB;
