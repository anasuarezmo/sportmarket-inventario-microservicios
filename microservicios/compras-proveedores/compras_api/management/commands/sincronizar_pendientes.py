import uuid
from django.core.management.base import BaseCommand
from compras_api import repositorio, servicio
class Command(BaseCommand):
    help = 'Reintenta recepciones pendientes manteniendo los mismos operacion_id.'
    def handle(self, *args, **kwargs):
        pendientes = repositorio.filas("SELECT id FROM recepcion WHERE estado='PENDIENTE_DE_SINCRONIZAR' ORDER BY id")
        for rec in pendientes:
            resultado = servicio.sincronizar_recepcion(rec['id'], str(uuid.uuid4()))
            self.stdout.write(f"Recepcion {rec['id']}: {resultado['estado']}")
