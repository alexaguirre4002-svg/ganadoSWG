from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models.functions import ExtractYear  # ← CORREGIDO
from Aplicaciones.Gestion.ml_engine import entrenar_modelo, modelo_esta_entrenado
import time


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
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar reentrenamiento aunque ya esté entrenado'
        )

    def handle(self, *args, **options):
        if options['todos']:
            modelos = ['AD-1', 'AD-2', 'RL-4']
        elif options['codigo']:
            modelos = [options['codigo']]
        else:
            self.stdout.write(self.style.ERROR('❌ Especifique --todos o un código de modelo'))
            self.stdout.write('')
            self.stdout.write('📚 Ejemplos:')
            self.stdout.write('  python manage.py entrenar_ml AD-1')
            self.stdout.write('  python manage.py entrenar_ml AD-2')
            self.stdout.write('  python manage.py entrenar_ml RL-4')
            self.stdout.write('  python manage.py entrenar_ml --todos')
            self.stdout.write('  python manage.py entrenar_ml AD-1 --force')
            return

        for codigo in modelos:
            self.entrenar_modelo(codigo, options)

    def verificar_datos_reales(self, codigo):
        """Verifica cuántos datos reales hay disponibles"""
        self.stdout.write('')
        self.stdout.write(f'🔍 Verificando datos reales para {codigo}...')
        
        try:
            if codigo == 'AD-1':
                from Aplicaciones.Gestion.models import Ordeno
                
                cantidad = Ordeno.objects.filter(
                    litros_or__isnull=False,
                    temperatura_ambiental_or__isnull=False,
                    temperatura_leche_or__isnull=False,
                    cantidad_concentrado_kg_or__isnull=False
                ).count()
                
                self.stdout.write(f'   🐄 Ordeños disponibles: {cantidad}')
                
                # Mostrar rango de fechas (sin ExtractYear para evitar errores)
                fechas = Ordeno.objects.filter(
                    litros_or__isnull=False,
                    temperatura_ambiental_or__isnull=False,
                    temperatura_leche_or__isnull=False,
                    cantidad_concentrado_kg_or__isnull=False
                ).values_list('fecha_or', flat=True).order_by('fecha_or')
                
                if fechas:
                    primera = fechas[0]
                    ultima = fechas[len(fechas)-1] if len(fechas) > 1 else primera
                    self.stdout.write(f'   📅 Rango: {primera} → {ultima}')
                
                return cantidad
                
            elif codigo == 'AD-2':
                from Aplicaciones.Gestion.models import Inseminacion
                
                cantidad = Inseminacion.objects.filter(
                    resultado_in__in=['preñada', 'no_preñada'],
                    condicion_corporal_in__isnull=False
                ).count()
                
                self.stdout.write(f'   🐄 Inseminaciones con resultado: {cantidad}')
                return cantidad
                
            elif codigo == 'RL-4':
                from Aplicaciones.Gestion.models import CalidadLeche
                
                cantidad = CalidadLeche.objects.filter(
                    grasa_pct_cl__isnull=False,
                    proteina_pct_cl__isnull=False,
                    ccs_cl__isnull=False,
                    resultado_cl__isnull=False
                ).exclude(
                    resultado_cl='pendiente'
                ).count()
                
                self.stdout.write(f'   🧪 Análisis de calidad disponibles: {cantidad}')
                return cantidad
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error al verificar: {str(e)}'))
            return 0
        
        return 0

    def entrenar_modelo(self, codigo, options):
        """Entrena un modelo específico"""
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write(f'🚀 Entrenando modelo {codigo}...')
        self.stdout.write('=' * 60)
        
        # 1. VERIFICAR DATOS REALES
        cantidad_datos = self.verificar_datos_reales(codigo)
        
        # 2. VALIDAR QUE HAYA SUFICIENTES DATOS
        if cantidad_datos < 10:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(f'❌ ERROR: No hay suficientes datos reales para {codigo}'))
            self.stdout.write(self.style.ERROR(f'   Encontrados: {cantidad_datos} registros'))
            self.stdout.write(self.style.ERROR(f'   Se necesitan al menos 10 registros para entrenar'))
            return
        
        # 3. VERIFICAR SI YA ESTÁ ENTRENADO
        if modelo_esta_entrenado(codigo) and not options.get('force', False):
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f'⚠️ El modelo {codigo} ya está entrenado.'))
            self.stdout.write('   Usa --force para reentrenar.')
            return
        
        # 4. EJECUTAR ENTRENAMIENTO
        self.stdout.write('')
        self.stdout.write(f'⏳ Entrenando con {cantidad_datos} registros reales...')
        inicio = time.time()
        
        try:
            resultado = entrenar_modelo(codigo)
            tiempo = time.time() - inicio
            
            self.stdout.write('')
            self.stdout.write('📊 RESULTADOS:')
            self.stdout.write('-' * 40)
            
            if resultado.get('exito'):
                self.stdout.write(self.style.SUCCESS('✅ Entrenamiento exitoso!'))
                self.stdout.write(f'   ⏱️ Tiempo: {tiempo:.2f} segundos')
                
                if 'r2' in resultado:
                    self.stdout.write(f'   📈 R²: {resultado["r2"]:.4f}')
                if 'accuracy' in resultado:
                    self.stdout.write(f'   📈 Accuracy: {resultado["accuracy"]:.4f}')
                if 'registros' in resultado:
                    self.stdout.write(f'   📊 Registros usados: {resultado["registros"]}')
                if 'fuente' in resultado:
                    self.stdout.write(f'   📂 Fuente: {resultado["fuente"]}')
            else:
                self.stdout.write(self.style.ERROR(f'❌ Error: {resultado.get("mensaje", "Error desconocido")}'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Excepción: {str(e)}'))
        
        self.stdout.write('=' * 60)