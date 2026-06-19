from django.core.management.base import BaseCommand
import random
from datetime import datetime, timedelta
from Aplicaciones.Gestion.models import Ordeno, CalidadLeche, Animal, Usuario

class Command(BaseCommand):
    help = 'Genera 500 registros de ejemplo en la base de datos y luego entrena los modelos ML'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cantidad',
            type=int,
            default=500,
            help='Cantidad de registros a generar (default: 500)',
        )
        parser.add_argument(
            '--limpiar',
            action='store_true',
            help='Borrar datos existentes antes de generar nuevos',
        )

    def handle(self, *args, **options):
        cantidad = options['cantidad']
        
        self.stdout.write(self.style.NOTICE(f'Generando {cantidad} registros de ejemplo...'))
        
        # Obtener un usuario para asignar
        usuario = self.obtener_usuario()
        if not usuario:
            self.stdout.write(self.style.ERROR('No hay usuarios en la base de datos. Crea uno primero.'))
            return
        
        # Obtener animales
        animales = self.obtener_animales()
        if not animales:
            self.stdout.write(self.style.ERROR('No hay animales. Crea animales primero.'))
            return
        
        # Generar Ordeños (para AD-1)
        self.generar_ordenos(cantidad, animales, usuario)
        
        # Generar Calidad de Leche (para RL-4)
        self.generar_calidad_leche(cantidad, animales, usuario)
        
        self.stdout.write(self.style.SUCCESS(f'✅ {cantidad} registros generados en la base de datos!'))
        self.stdout.write(self.style.NOTICE(''))
        self.stdout.write(self.style.NOTICE('Ahora entrena los modelos con:'))
        self.stdout.write(self.style.NOTICE('  python manage.py entrenar_ml AD-1'))
        self.stdout.write(self.style.NOTICE('  python manage.py entrenar_ml AD-2 --ejemplo'))
        self.stdout.write(self.style.NOTICE('  python manage.py entrenar_ml RL-4'))
    
    def obtener_usuario(self):
        usuarios = list(Usuario.objects.all()[:1])
        if usuarios:
            return usuarios[0]
        return None
    
    def obtener_animales(self):
        animales = list(Animal.objects.all()[:10])
        if not animales:
            self.stdout.write(self.style.WARNING('No hay animales. Creando 5 animales ficticios...'))
            try:
                from Aplicaciones.Gestion.models import Raza
                raza = Raza.objects.first()
                if not raza:
                    raza = Raza.objects.create(nombre_ra='Holstein', activo_ra=True)
                from datetime import date
                animales_creados = []
                for i in range(1, 6):
                    animal = Animal.objects.create(
                        codigo_an=f'VAC-00{i}',
                        nombre_an=f'Vaca Ficticia {i}',
                        fk_ra=raza,
                        sexo_an='H',
                        fecha_nacimiento_an=date(2020, 1, 1),
                        categoria_an='vaca_leche',
                        fecha_ingreso_an=date(2020, 1, 1),
                    )
                    animales_creados.append(animal)
                return animales_creados
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error creando animal: {e}'))
                return []
        return animales

    def generar_ordenos(self, n, animales, usuario):
        self.stdout.write('Generando registros de Ordeños...')
        
        turnos = ['manana', 'tarde', 'unico']
        registros_creados = 0
        combinaciones_usadas = set()  # Para evitar duplicados
        
        for i in range(n):
            animal = random.choice(animales)
            
            # Intentar encontrar una combinación única
            intentos = 0
            while intentos < 50:
                dias_atras = random.randint(0, 1000)
                fecha = datetime.now() - timedelta(days=dias_atras)
                turno = random.choice(turnos)
                combo = (animal.id_an, fecha.date(), turno)
                if combo not in combinaciones_usadas:
                    combinaciones_usadas.add(combo)
                    break
                intentos += 1
            else:
                continue  # Si no encontró combo único, saltar este registro
            
            temp_amb = round(random.uniform(18.0, 35.0), 1)
            conc_kg = round(random.uniform(2.0, 8.0), 2)
            temp_leche = round(random.uniform(32.0, 39.0), 1)
            
            litros_base = (conc_kg * 2.5) - (abs(temp_amb - 25) * 0.3)
            litros = round(max(0.5, litros_base + random.uniform(-1.5, 1.5)), 2)
            
            try:
                Ordeno.objects.create(
                    fk_an=animal,
                    fk_us_or=usuario,
                    fecha_or=fecha.date(),
                    turno_or=turno,
                    litros_or=litros,
                    temperatura_leche_or=temp_leche,
                    cantidad_concentrado_kg_or=conc_kg,
                    temperatura_ambiental_or=temp_amb,
                )
                registros_creados += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Error creando ordeno: {e}'))
                break
        
        self.stdout.write(self.style.SUCCESS(f'  {registros_creados} registros de Ordeños creados'))

    def generar_calidad_leche(self, n, animales, usuario):
        self.stdout.write('Generando registros de Calidad de Leche...')
        
        registros_creados = 0
        combinaciones_usadas = set()
        
        for i in range(n):
            animal = random.choice(animales)
            
            # Encontrar fecha única
            intentos = 0
            while intentos < 50:
                dias_atras = random.randint(0, 1000)
                fecha = datetime.now() - timedelta(days=dias_atras)
                combo = (animal.id_an, fecha.date())
                if combo not in combinaciones_usadas:
                    combinaciones_usadas.add(combo)
                    break
                intentos += 1
            else:
                continue
            
            grasa = round(random.uniform(2.5, 5.0), 2)
            proteina = round(random.uniform(2.8, 4.0), 2)
            ccs = random.randint(100000, 800000)
            ufc = random.randint(1000, 500000)
            
            resultado = 'apto'
            if grasa < 3.0: resultado = 'no_apto'
            if ccs > 500000: resultado = 'no_apto'
            if random.random() < 0.1: resultado = 'no_apto' if resultado == 'apto' else 'apto'
            
            try:
                CalidadLeche.objects.create(
                    fk_an=animal,
                    fk_us_cl=usuario,
                    fecha_muestreo_cl=fecha.date(),
                    grasa_pct_cl=grasa,
                    proteina_pct_cl=proteina,
                    ccs_cl=ccs,
                    ufc_cl=ufc,
                    resultado_cl=resultado,
                    laboratorio_cl='Lab Ganaderia SG',
                )
                registros_creados += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Error creando calidad: {e}'))
                break
        
        self.stdout.write(self.style.SUCCESS(f'  {registros_creados} registros de Calidad de Leche creados'))
