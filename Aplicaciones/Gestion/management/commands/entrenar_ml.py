# Gestion/management/commands/entrenar_ml.py

from django.core.management.base import BaseCommand
from Aplicaciones.Gestion.ml_engine import entrenar_modelo

class Command(BaseCommand):
    help = 'Entrena modelos de Machine Learning SOLO CON DATOS REALES'

    def add_arguments(self, parser):
        parser.add_argument(
            'codigo', 
            nargs='?', 
            type=str, 
            help='Código del modelo (AD-1, AD-2, RL-4)'
        )
        parser.add_argument(
            '--todos', 
            action='store_true', 
            help='Entrenar todos los modelos'
        )

    def handle(self, *args, **options):
        if options['todos']:
            modelos = ['AD-1', 'AD-2', 'RL-4']
        elif options['codigo']:
            modelos = [options['codigo']]
        else:
            self.stdout.write(self.style.ERROR('❌ Especifique --todos o un código de modelo'))
            self.stdout.write('')
            self.stdout.write('Ejemplos:')
            self.stdout.write('  python manage.py entrenar_ml AD-1')
            self.stdout.write('  python manage.py entrenar_ml --todos')
            return

        for codigo in modelos:
            self.stdout.write(f'🔍 Entrenando modelo {codigo} con datos reales...')
            resultado = entrenar_modelo(codigo)
            
            if resultado['exito']:
                self.stdout.write(self.style.SUCCESS(
                    f'✅ {codigo} entrenado exitosamente!'
                ))
                self.stdout.write(f'   📊 Registros usados: {resultado["registros"]}')
                self.stdout.write(f'   📈 R²: {resultado.get("r2", resultado.get("accuracy", 0))}')
                self.stdout.write(f'   📁 Guardado en: {resultado["ruta_modelo"]}')
                self.stdout.write(f'   📂 Fuente: {resultado["fuente"]}')
            else:
                self.stdout.write(self.style.ERROR(f'❌ {resultado["mensaje"]}'))