from django.core.management.base import BaseCommand
from Aplicaciones.Gestion.ml_engine import entrenar_modelo


class Command(BaseCommand):
    help = 'Entrena modelos de Machine Learning. Codigos: AD-1, AD-2, RL-4'

    def add_arguments(self, parser):
        parser.add_argument('codigo', type=str, help='Codigo del modelo: AD-1, AD-2, RL-4')
        parser.add_argument(
            '--ejemplo',
            action='store_true',
            help='Usar datos de ejemplo si no hay datos reales',
        )
        parser.add_argument(
            '--no-db',
            action='store_true',
            help='No guardar en la tabla ModeloML de la base de datos',
        )

    def handle(self, *args, **options):
        codigo = options['codigo'].upper()
        usar_ejemplo = options['ejemplo']
        guardar_db = not options['no_db']

        self.stdout.write(self.style.NOTICE(f'Entrenando modelo {codigo}...'))
        if usar_ejemplo:
            self.stdout.write(self.style.WARNING('USANDO DATOS DE EJEMPLO (modo demo)'))

        resultado = entrenar_modelo(codigo_mm=codigo, usar_datos_ejemplo=usar_ejemplo, guardar_db=guardar_db)

        if resultado['exito']:
            self.stdout.write(self.style.SUCCESS(f'Modelo {codigo} entrenado exitosamente!'))
            self.stdout.write(f'  Ruta: {resultado["ruta_modelo"]}')
            self.stdout.write(f'  Registros usados: {resultado["registros"]}')
            self.stdout.write(f'  Entrenamiento: {resultado["entrenamiento"]} | Prueba: {resultado["prueba"]}')
            if 'r2' in resultado:
                self.stdout.write(f'  R2: {resultado["r2"]}')
            if 'accuracy' in resultado:
                self.stdout.write(f'  Accuracy: {resultado["accuracy"]}')
            if 'guardado_db' in resultado:
                self.stdout.write(f'  Guardado en DB: {resultado["guardado_db"]}')
        else:
            self.stdout.write(self.style.ERROR(f'Error: {resultado["mensaje"]}'))
            self.stdout.write(self.style.NOTICE('Sugerencia: agrega --ejemplo para usar datos sinteticos'))
