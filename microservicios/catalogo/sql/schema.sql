-- Esquema de catalogo_db (diseño de la Entrega 2). Se aplica al arrancar el servicio (CREATE ... IF NOT EXISTS).
CREATE TABLE IF NOT EXISTS categoria (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(80) NOT NULL,
  descripcion VARCHAR(200) NULL,
  categoria_padre_id INT NULL,
  categoria_activa BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT fk_categoria_padre FOREIGN KEY (categoria_padre_id) REFERENCES categoria (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS producto (
  id INT AUTO_INCREMENT PRIMARY KEY,
  codigo_producto VARCHAR(40) NOT NULL,
  nombre_producto VARCHAR(120) NOT NULL,
  descripcion_producto TEXT NULL,
  categoria_id INT NOT NULL,
  unidad_medida VARCHAR(20) NOT NULL,
  precio_venta DECIMAL(12,2) NOT NULL,
  proveedor_principal_id INT NULL,
  producto_activo BOOLEAN NOT NULL DEFAULT TRUE,
  fecha_creacion_producto DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_actualizacion_producto DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT uq_producto_codigo UNIQUE (codigo_producto),
  CONSTRAINT fk_producto_categoria FOREIGN KEY (categoria_id) REFERENCES categoria (id),
  INDEX idx_producto_nombre (nombre_producto),
  INDEX idx_producto_categoria (categoria_id)
) ENGINE=InnoDB;
