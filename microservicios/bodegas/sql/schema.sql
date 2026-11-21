-- Tablas de la base bodegas_db (previamente creada por Edwin).
CREATE TABLE IF NOT EXISTS bodega (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(20) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    direccion VARCHAR(150) NOT NULL,
    ciudad VARCHAR(60) NOT NULL,
    bodega_activa BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ubicacion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bodega_id INT NOT NULL,
    codigo VARCHAR(30) NOT NULL,
    descripcion VARCHAR(255),
    ubicacion_activa BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_ubicacion_bodega FOREIGN KEY (bodega_id) REFERENCES bodega(id),
    CONSTRAINT uq_ubicacion_bodega_codigo UNIQUE (bodega_id, codigo)
) ENGINE=InnoDB;
