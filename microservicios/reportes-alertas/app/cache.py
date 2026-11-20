"""Cache en memoria con tiempo de vida corto: reutiliza los datos pedidos a otros servicios unos segundos."""
import time


class Cache:
    def __init__(self, ttl, reloj=time.monotonic):
        self.ttl, self.reloj, self.datos = ttl, reloj, {}

    def obtener(self, clave, producir):
        if self.ttl <= 0:
            return producir()
        ahora = self.reloj()
        hit = self.datos.get(clave)
        if hit and ahora - hit[0] < self.ttl:
            return hit[1]
        valor = producir()
        self.datos[clave] = (ahora, valor)
        return valor
