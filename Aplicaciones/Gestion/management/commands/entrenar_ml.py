# Aplicaciones/management/commands/entrenar_ml.py

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
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar información detallada'
        )

    def handle(self, *args, **options):
        if options['todos']:
            modelos = ['AD-1', 'AD-2', 'RL-4']
        elif options['codigo']:
            modelos = [options['codigo']]
        else:
            self.mostrar_ayuda()
            return

        for codigo in modelos:
            self.entrenar_modelo(codigo, options)

    def mostrar_ayuda(self):
        """Muestra ayuda si no se especifica modelo"""
        self.stdout.write(self.style.ERROR('❌ Especifique --todos o un código de modelo'))
        self.stdout.write('')
        self.stdout.write('📚 Ejemplos:')
        self.stdout.write('  python manage.py entrenar_ml AD-1')
        self.stdout.write('  python manage.py entrenar_ml AD-2')
        self.stdout.write('  python manage.py entrenar_ml RL-4')
        self.stdout.write('  python manage.py entrenar_ml --todos')
        self.stdout.write('  python manage.py entrenar_ml AD-1 --force')
        self.stdout.write('  python manage.py entrenar_ml AD-1 --verbose')
        self.stdout.write('')
        self.stdout.write('📊 Modelos disponibles:')
        self.stdout.write('  AD-1  → Predicción de Litros de Leche')
        self.stdout.write('  AD-2  → Predicción de Estado de Preñez')
        self.stdout.write('  RL-4  → Predicción de Calidad de Leche')

    def verificar_datos_reales(self, codigo):
        """
        Verifica cuántos datos reales hay disponibles.
        Retorna: (cantidad, mensaje_adicional)
        """
        self.stdout.write('')
        self.stdout.write(f'🔍 Verificando datos reales para {codigo}...')
        
        try:
            if codigo == 'AD-1':
                from Aplicaciones.Gestion.models import Ordeno
                
                # Contar ordeños con todos los campos necesarios
                cantidad = Ordeno.objects.filter(
                    litros_or__isnull=False,
                    temperatura_ambiental_or__isnull=False,
                    temperatura_leche_or__isnull=False,
                    cantidad_concentrado_kg_or__isnull=False
                ).count()
                
                self.stdout.write(f'   🐄 Ordeños disponibles: {cantidad}')
                
                # Mostrar rango de fechas
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
                
                # Distribución por año (con manejo de errores)
                try:
                    from django.db.models import Count
                    from django.db.models.functions import ExtractYear
                    
                    por_anio = Ordeno.objects.filter(
                        litros_or__isnull=False,
                        temperatura_ambiental_or__isnull=False,
                        temperatura_leche_or__isnull=False,
                        cantidad_concentrado_kg_or__isnull=False
                    ).annotate(
                        anio=ExtractYear('fecha_or')
                    ).values('anio').annotate(
                        total=Count('id_or')
                    ).order_by('anio')
                    
                    if por_anio:
                        self.stdout.write('   📊 Distribución por año:')
                        for item in por_anio:
                            barra = '█' * min(int(item['total'] / 10), 50)
                            self.stdout.write(f'      {item["anio"]}: {item["total"]} registros {barra}')
                except Exception as e:
                    # Si falla la agrupación, no es crítico
                    self.stdout.write(f'   ℹ️ Distribución por año: no disponible')
                
                return cantidad
                
            elif codigo == 'AD-2':
                from Aplicaciones.Gestion.models import Inseminacion
                
                cantidad = Inseminacion.objects.filter(
                    resultado_in__in=['preñada', 'no_preñada'],
                    condicion_corporal_in__isnull=False
                ).count()
                
                self.stdout.write(f'   🐄 Inseminaciones con resultado: {cantidad}')
                
                # Mostrar distribución de resultados
                preñadas = Inseminacion.objects.filter(
                    resultado_in='preñada',
                    condicion_corporal_in__isnull=False
                ).count()
                no_preñadas = Inseminacion.objects.filter(
                    resultado_in='no_preñada',
                    condicion_corporal_in__isnull=False
                ).count()
                
                self.stdout.write(f'      ✅ Preñadas: {preñadas}')
                self.stdout.write(f'      ❌ No preñadas: {no_preñadas}')
                
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
                
                # Mostrar distribución de resultados
                aptos = CalidadLeche.objects.filter(
                    resultado_cl='apto',
                    grasa_pct_cl__isnull=False,
                    proteina_pct_cl__isnull=False,
                    ccs_cl__isnull=False
                ).count()
                no_aptos = CalidadLeche.objects.filter(
                    resultado_cl='no_apto',
                    grasa_pct_cl__isnull=False,
                    proteina_pct_cl__isnull=False,
                    ccs_cl__isnull=False
                ).count()
                
                self.stdout.write(f'      ✅ Aptos: {aptos}')
                self.stdout.write(f'      ❌ No aptos: {no_aptos}')
                
                return cantidad
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error al verificar: {str(e)}'))
            return 0
        
        return 0

    def entrenar_modelo(self, codigo, options):
        """Entrena un modelo específico con validación de datos reales"""
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
            self.stdout.write('')
            self.stdout.write('💡 Sugerencias:')
            self.stdout.write('   1. Ingresa más datos en el sistema')
            self.stdout.write('   2. Verifica que los datos tengan todos los campos requeridos')
            self.stdout.write('   3. Usa el panel de administración para ingresar datos')
            return
        
        # 3. VERIFICAR SI YA ESTÁ ENTRENADO
        if modelo_esta_entrenado(codigo) and not options.get('force', False):
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f'⚠️ El modelo {codigo} ya está entrenado.'))
            self.stdout.write('   Usa --force para reentrenar.')
            return
        
        # 4. MOSTRAR INICIO DEL ENTRENAMIENTO
        self.stdout.write('')
        self.stdout.write(f'⏳ Entrenando con {cantidad_datos} registros reales...')
        inicio = time.time()
        
        # 5. EJECUTAR ENTRENAMIENTO
        try:
            resultado = entrenar_modelo(codigo)
            
            # Calcular tiempo
            tiempo = time.time() - inicio
            
            # 6. MOSTRAR RESULTADOS
            self.stdout.write('')
            self.stdout.write('📊 RESULTADOS DEL ENTRENAMIENTO:')
            self.stdout.write('-' * 40)
            
            if resultado.get('exito'):
                self.stdout.write(self.style.SUCCESS('✅ Entrenamiento exitoso!'))
                self.stdout.write(f'   ⏱️ Tiempo: {tiempo:.2f} segundos')
                self.stdout.write(f'   📁 Archivo: {resultado.get("ruta_modelo", "N/A")}')
                self.stdout.write(f'   📂 Fuente: {resultado.get("fuente", "N/A")}')
                
                # Métricas específicas por modelo
                if 'r2' in resultado:
                    r2 = resultado['r2']
                    if r2 > 0.8:
                        calidad = '🌟 Excelente'
                    elif r2 > 0.6:
                        calidad = '👍 Bueno'
                    elif r2 > 0.4:
                        calidad = '📊 Aceptable'
                    else:
                        calidad = '⚠️ Bajo'
                    self.stdout.write(f'   📈 R²: {r2:.4f} ({calidad})')
                
                if 'rmse' in resultado:
                    self.stdout.write(f'   📉 RMSE: {resultado["rmse"]:.4f}')
                
                if 'accuracy' in resultado:
                    acc = resultado['accuracy']
                    if acc > 0.8:
                        calidad = '🌟 Excelente'
                    elif acc > 0.6:
                        calidad = '👍 Bueno'
                    elif acc > 0.4:
                        calidad = '📊 Aceptable'
                    else:
                        calidad = '⚠️ Bajo'
                    self.stdout.write(f'   📈 Accuracy: {acc:.4f} ({calidad})')
                
                if 'mejor_modelo' in resultado:
                    self.stdout.write(f'   🤖 Mejor modelo: {resultado["mejor_modelo"]}')
                
                if 'cv_mean' in resultado:
                    self.stdout.write(f'   🔄 Cross-Validation: {resultado["cv_mean"]:.4f} (±{resultado.get("cv_std", 0):.4f})')
                
                if 'registros' in resultado:
                    self.stdout.write(f'   📊 Registros totales: {resultado["registros"]}')
                
                if 'variables' in resultado and options.get('verbose', False):
                    self.stdout.write(f'   📋 Variables usadas ({len(resultado["variables"])}):')
                    for i, var in enumerate(resultado['variables']):
                        self.stdout.write(f'      {i+1}. {var}')
                
                if 'guardado_db' in resultado:
                    if resultado['guardado_db']:
                        self.stdout.write(self.style.SUCCESS('   💾 Guardado en base de datos: ✅'))
                    else:
                        self.stdout.write(self.style.WARNING(f'   💾 Guardado en base de datos: ❌ {resultado.get("error_db", "Error desconocido")}'))
                
            else:
                self.stdout.write(self.style.ERROR(f'❌ Error: {resultado.get("mensaje", "Error desconocido")}'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Excepción: {str(e)}'))
            import traceback
            self.stdout.write(traceback.format_exc())
        
        self.stdout.write('=' * 60)