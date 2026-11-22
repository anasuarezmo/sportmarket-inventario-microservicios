"""Pruebas de rendimiento individuales de Ana (Entrega 3, SportMarket).

Cinco rutas de solo lectura x tres perfiles = 15 ejecuciones independientes.
Todas las solicitudes se realizan exclusivamente a traves del Gateway.
"""
import os
from locust import HttpUser, task, constant_pacing

ESCENARIOS = {
    "bodegas_lista": "/api/bodegas",
    "bodegas_detalle": "/api/bodegas/1",
    "usuarios_lista": "/api/usuarios",
    "devoluciones_lista": "/api/devoluciones",
    "compras_lista": "/api/compras",
}

class SportMarketUser(HttpUser):
    # Cada usuario virtual hace como maximo ~1 peticion por segundo.
    wait_time = constant_pacing(1)

    def on_start(self):
        self.escenario = os.environ.get("ESCENARIO", "")
        self.token = os.environ.get("LOCUST_TOKEN", "")
        if self.escenario not in ESCENARIOS:
            raise RuntimeError(f"ESCENARIO debe ser uno de: {', '.join(ESCENARIOS)}")
        if not self.token:
            raise RuntimeError("Falta LOCUST_TOKEN. Usa ejecutar_15.sh para obtenerlo por login.")

    @task
    def consultar(self):
        ruta = ESCENARIOS[self.escenario]
        with self.client.get(
            ruta,
            name=self.escenario,
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
            timeout=10,
        ) as respuesta:
            if respuesta.status_code != 200:
                respuesta.failure(f"Esperado HTTP 200; recibido HTTP {respuesta.status_code}")
            else:
                try:
                    resultado = respuesta.json()
                except ValueError:
                    respuesta.failure("La respuesta no es JSON")
                    return
                if not isinstance(resultado, (dict, list)):
                    respuesta.failure("Formato JSON no esperado")
