-- Solo objetos de devoluciones_db. Ejecutar conectado como devoluciones_user a devoluciones_db.
CREATE TABLE IF NOT EXISTS devolucion (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tipo ENUM('CLIENTE', 'PROVEEDOR') NOT NULL,
  fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  motivo VARCHAR(200) NOT NULL,
  bodega_id INT NOT NULL COMMENT 'ID remoto, sin FK a otras BD',
  proveedor_id INT NULL COMMENT 'ID informativo remoto',
  documento_ref VARCHAR(40) NULL,
  estado_inventario ENUM('PENDIENTE', 'APLICADA') NOT NULL DEFAULT 'PENDIENTE',
  usuario_id INT NULL COMMENT 'Identificador remoto derivado del Gateway',
  INDEX idx_devolucion_tipo_estado_fecha (tipo, estado_inventario, fecha),
  INDEX idx_devolucion_fecha (fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS devolucion_detalle (
  id INT AUTO_INCREMENT PRIMARY KEY,
  devolucion_id INT NOT NULL,
  producto_id INT NOT NULL COMMENT 'ID remoto, sin FK a otras BD',
  cantidad INT NOT NULL,
  condicion ENUM('BUEN_ESTADO', 'DEFECTUOSO') NULL,
  operacion_id CHAR(36) NULL UNIQUE COMMENT 'Idempotencia en Inventario, NULL para defectuosos',
  CONSTRAINT fk_devolucion_detalle FOREIGN KEY (devolucion_id) REFERENCES devolucion(id),
  CONSTRAINT chk_cantidad_devolucion CHECK (cantidad > 0),
  INDEX idx_detalle_producto (producto_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
