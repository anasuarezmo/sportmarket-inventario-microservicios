-- Ejecutar solo en usuarios_db. No altera bases de datos de otros servicios.
CREATE TABLE IF NOT EXISTS rol (
    id INT PRIMARY KEY,
    nombre VARCHAR(45) NOT NULL UNIQUE,
    descripcion VARCHAR(200) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS usuario (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol_id INT NOT NULL,
    usuario_activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_registro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_ultimo_acceso DATETIME NULL,
    CONSTRAINT fk_usuario_rol FOREIGN KEY (rol_id) REFERENCES rol(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS token_recuperacion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    fecha_expiracion DATETIME NOT NULL,
    token_utilizado BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_token_usuario FOREIGN KEY (usuario_id) REFERENCES usuario(id),
    INDEX idx_token_usuario (usuario_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- IDs fijos para mapear al valor `rol` del JWT que espera el Gateway.
INSERT IGNORE INTO rol (id, nombre, descripcion) VALUES
(1, 'Administrador', 'Gestión y administración de usuarios y roles'),
(2, 'Inventario', 'Responsable de inventario'),
(3, 'Compras', 'Responsable de compras'),
(4, 'Bodega', 'Operador de bodega'),
(5, 'Consulta', 'Usuario de consulta');
