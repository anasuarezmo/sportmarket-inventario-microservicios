-- reportes_db: solo guarda las alertas de stock (RF09). Los informes se calculan al consultarlos.
CREATE TABLE IF NOT EXISTS alerta (
  id INT AUTO_INCREMENT PRIMARY KEY,
  producto_id INT NOT NULL,
  bodega_id INT NOT NULL,
  cantidad_disponible_al_generar INT NOT NULL,
  stock_minimo INT NOT NULL,
  estado_alerta ENUM('ACTIVA','ATENDIDA') NOT NULL DEFAULT 'ACTIVA',
  fecha_generacion_alerta DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atendida_en DATETIME NULL,
  usuario_atencion_id INT NULL,
  -- Solo puede haber una alerta ACTIVA por producto y bodega: la clave es nula cuando esta ATENDIDA
  clave_activa VARCHAR(40) GENERATED ALWAYS AS (IF(estado_alerta = 'ACTIVA', CONCAT(producto_id, '-', bodega_id), NULL)) STORED,
  UNIQUE KEY uq_alerta_activa (clave_activa),
  KEY ix_alerta_estado (estado_alerta),
  KEY ix_alerta_producto_bodega (producto_id, bodega_id)
);
