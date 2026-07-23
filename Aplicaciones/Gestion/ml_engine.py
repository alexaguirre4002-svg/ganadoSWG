# ============================================================
# ml_engine.py - VERSIÓN COMPLETA CON PREDICCIONES FUTURAS
# ============================================================
import os
import joblib
import numpy as np
import pandas as pd

from datetime import datetime, date, timedelta

from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, mean_squared_error, r2_score

from django.conf import settings
from django.db.models import Avg, Q, Sum, Count


# ============================================================
# CONSTANTES
# ============================================================

MESES_ESPANOL = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

RAZAS_MAP = {
    'Holstein': 0,
    'Brown Swiss': 1,
    'Jersey': 2,
    'Criollo Ecuatoriano': 3,
    'Mestiza': 4,
    'Normando': 5,
    'desconocida': 6
}

TEMPORADA_MAP = {
    12: 0, 1: 0, 2: 0,   # invierno
    3: 2, 4: 2, 5: 2,   # primavera
    6: 3, 7: 3, 8: 3,   # verano
    9: 1, 10: 1, 11: 1  # otoño
}

NOMBRE_TEMPORADA = {
    0: 'Invierno', 1: 'Otoño', 2: 'Primavera', 3: 'Verano'
}


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def codificar_raza(raza):
    return RAZAS_MAP.get(raza, 6)

def codificar_temporada(mes):
    return TEMPORADA_MAP.get(mes, 0)

def obtener_nombre_temporada(mes):
    return NOMBRE_TEMPORADA.get(codificar_temporada(mes), 'Invierno')

def obtener_ruta_modelo(codigo_mm):
    base = os.path.join(settings.BASE_DIR, 'media', 'ml')
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f'{codigo_mm}.pkl')

def modelo_esta_entrenado(codigo_mm):
    return os.path.exists(obtener_ruta_modelo(codigo_mm))


# ============================================================
# ============================================================
# PREDICCIÓN AD-1: LITROS DE LECHE (FUTURO)
# ============================================================
# ============================================================

def predecir_mes_futuro_ad1(animal_id, mes, anio):
    """
    Predice los litros de leche para un mes FUTURO.
    Usa promedios históricos del animal para ese mes.
    """
    from Aplicaciones.Gestion.models import Animal, Ordeno, Parto
    
    try:
        animal = Animal.objects.select_related('fk_ra').get(id_an=animal_id)
    except Animal.DoesNotExist:
        return {'exito': False, 'mensaje': 'Animal no encontrado'}
    
    # 1. OBTENER PROMEDIOS HISTÓRICOS DEL ANIMAL PARA ESE MES
    promedios = Ordeno.objects.filter(
        fk_an=animal,
        fecha_or__month=mes,
        fecha_or__year__lt=anio
    ).aggregate(
        temp_amb_prom=Avg('temperatura_ambiental_or'),
        temp_leche_prom=Avg('temperatura_leche_or'),
        concentrado_prom=Avg('cantidad_concentrado_kg_or'),
        litros_prom=Avg('litros_or')
    )
    
    # Si no hay datos para ese mes, usar promedios generales
    if promedios['temp_amb_prom'] is None:
        promedios = Ordeno.objects.filter(
            fk_an=animal
        ).aggregate(
            temp_amb_prom=Avg('temperatura_ambiental_or'),
            temp_leche_prom=Avg('temperatura_leche_or'),
            concentrado_prom=Avg('cantidad_concentrado_kg_or'),
            litros_prom=Avg('litros_or')
        )
    
    # 2. DATOS DEL ANIMAL
    fecha_prediccion = date(anio, mes, 1)
    edad_dias = 0
    if animal.fecha_nacimiento_an:
        edad_dias = (fecha_prediccion - animal.fecha_nacimiento_an).days
    
    num_partos = Parto.objects.filter(fk_madre_pa=animal).count()
    raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
    raza_cod = codificar_raza(raza)
    temporada_cod = codificar_temporada(mes)
    
    # 3. CONSTRUIR CARACTERÍSTICAS (14)
    caracteristicas = [
        float(edad_dias),
        float(edad_dias / 365),
        float(raza_cod),
        float(animal.peso_actual_kg_an or 0),
        float(animal.condicion_corporal_an or 0),
        float(num_partos),
        float(promedios.get('litros_prom') or 0),
        0.0,
        0.0,
        float(mes),
        float(temporada_cod),
        float(promedios.get('temp_amb_prom') or 22.0),
        float(promedios.get('temp_leche_prom') or 38.0),
        float(promedios.get('concentrado_prom') or 3.0)
    ]
    
    # 4. CARGAR MODELO Y PREDECIR
    ruta = obtener_ruta_modelo('AD-1')
    if not os.path.exists(ruta):
        return {'exito': False, 'mensaje': 'Modelo AD-1 no encontrado'}
    
    modelo_data = joblib.load(ruta)
    modelo = modelo_data['modelo']
    scaler = modelo_data.get('scaler')
    
    X = np.array([caracteristicas])
    if scaler:
        X_scaled = scaler.transform(X)
        prediccion = modelo.predict(X_scaled)[0]
    else:
        prediccion = modelo.predict(X)[0]
    
    return {
        'exito': True,
        'prediccion': round(float(prediccion), 2),
        'mes': mes,
        'anio': anio,
        'datos_usados': {
            'temperatura_ambiental': round(float(promedios.get('temp_amb_prom') or 22.0), 1),
            'temperatura_leche': round(float(promedios.get('temp_leche_prom') or 38.0), 1),
            'concentrado_kg': round(float(promedios.get('concentrado_prom') or 3.0), 2),
            'edad_dias': edad_dias,
            'raza': raza,
            'num_partos': num_partos,
            'peso': float(animal.peso_actual_kg_an or 0),
            'temporada': obtener_nombre_temporada(mes)
        }
    }


def predecir_anio_completo_ad1(animal_id, anio):
    """Predice los 12 meses del año para AD-1"""
    resultados = {}
    for mes in range(1, 13):
        resultado = predecir_mes_futuro_ad1(animal_id, mes, anio)
        if resultado['exito']:
            resultados[mes] = resultado
    return resultados


def predecir_anios_ad1(animal_id):
    """Predice año actual y siguiente para AD-1"""
    anio_actual = date.today().year
    resultados = {}
    
    # Año actual
    resultados[anio_actual] = predecir_anio_completo_ad1(animal_id, anio_actual)
    
    # Año siguiente
    resultados[anio_actual + 1] = predecir_anio_completo_ad1(animal_id, anio_actual + 1)
    
    return resultados


# ============================================================
# ============================================================
# PREDICCIÓN AD-2: PREÑEZ (FUTURO)
# ============================================================
# ============================================================

def predecir_mes_futuro_ad2(animal_id, mes, anio):
    """
    Predice si una vaca estará preñada en un mes FUTURO.
    Basado en su historial reproductivo.
    """
    from Aplicaciones.Gestion.models import Animal, Inseminacion, Aborto, Parto, Ordeno
    
    try:
        animal = Animal.objects.select_related('fk_ra').get(id_an=animal_id)
    except Animal.DoesNotExist:
        return {'exito': False, 'mensaje': 'Animal no encontrado'}
    
    # 1. DATOS HISTÓRICOS DEL ANIMAL
    num_partos = Parto.objects.filter(fk_madre_pa=animal).count()
    historial_abortos = Aborto.objects.filter(fk_an=animal).count()
    raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
    raza_cod = codificar_raza(raza)
    
    # 2. PROMEDIO DE PRODUCCIÓN DE LECHE
    produccion = Ordeno.objects.filter(fk_an=animal).aggregate(
        prom=Avg('litros_or')
    )['prom'] or 0
    
    # 3. ÚLTIMA INSEMINACIÓN (para calcular días)
    ultima_ins = Inseminacion.objects.filter(
        fk_an=animal
    ).order_by('-fecha_in').first()
    
    if ultima_ins:
        dias_desde = (date(anio, mes, 1) - ultima_ins.fecha_in).days
    else:
        dias_desde = 60
    
    # 4. CONDICIÓN CORPORAL PROMEDIO
    condicion = Inseminacion.objects.filter(
        fk_an=animal,
        condicion_corporal_in__isnull=False
    ).aggregate(prom=Avg('condicion_corporal_in'))['prom'] or 3
    
    # 5. CONSTRUIR CARACTERÍSTICAS (11)
    caracteristicas = [
        float(dias_desde),
        float(num_partos),
        float(raza_cod),
        float(condicion),
        float(produccion),
        1.0,  # intensidad_cod (media)
        12.0,  # duracion_celo_horas
        0.0,  # tipo_cod (artificial)
        0.0,  # toro_cod
        float(historial_abortos),
        14.0  # dia_ciclo
    ]
    
    # 6. CARGAR MODELO Y PREDECIR
    ruta = obtener_ruta_modelo('AD-2')
    if not os.path.exists(ruta):
        return {'exito': False, 'mensaje': 'Modelo AD-2 no encontrado'}
    
    modelo_data = joblib.load(ruta)
    modelo = modelo_data['modelo']
    
    X = np.array([caracteristicas])
    prediccion = modelo.predict(X)[0]
    probabilidad = modelo.predict_proba(X)[0]
    
    return {
        'exito': True,
        'prediccion': 'Preñada' if prediccion == 1 else 'No Preñada',
        'probabilidad': round(float(max(probabilidad)) * 100, 1),
        'mes': mes,
        'anio': anio,
        'datos_usados': {
            'dias_desde_inseminacion': dias_desde,
            'num_partos': num_partos,
            'raza': raza,
            'condicion_corporal': round(float(condicion), 1),
            'produccion_leche': round(float(produccion), 2),
            'historial_abortos': historial_abortos
        }
    }


def predecir_anio_completo_ad2(animal_id, anio):
    """Predice los 12 meses del año para AD-2"""
    resultados = {}
    for mes in range(1, 13):
        resultado = predecir_mes_futuro_ad2(animal_id, mes, anio)
        if resultado['exito']:
            resultados[mes] = resultado
    return resultados


def predecir_anios_ad2(animal_id):
    """Predice año actual y siguiente para AD-2"""
    anio_actual = date.today().year
    resultados = {}
    
    resultados[anio_actual] = predecir_anio_completo_ad2(animal_id, anio_actual)
    resultados[anio_actual + 1] = predecir_anio_completo_ad2(animal_id, anio_actual + 1)
    
    return resultados


# ============================================================
# ============================================================
# PREDICCIÓN RL-4: CALIDAD DE LECHE (FUTURO)
# ============================================================
# ============================================================

def predecir_mes_futuro_rl4(animal_id, mes, anio):
    """
    Predice la calidad de leche para un mes FUTURO.
    Basado en el historial de análisis del animal.
    """
    from Aplicaciones.Gestion.models import Animal, CalidadLeche
    
    try:
        animal = Animal.objects.get(id_an=animal_id)
    except Animal.DoesNotExist:
        return {'exito': False, 'mensaje': 'Animal no encontrado'}
    
    # 1. PROMEDIOS HISTÓRICOS PARA ESE MES
    promedios = CalidadLeche.objects.filter(
        fk_an=animal,
        fecha_muestreo_cl__month=mes,
        fecha_muestreo_cl__year__lt=anio
    ).aggregate(
        grasa_prom=Avg('grasa_pct_cl'),
        proteina_prom=Avg('proteina_pct_cl'),
        ccs_prom=Avg('ccs_cl'),
        ufc_prom=Avg('ufc_cl')
    )
    
    # Si no hay datos para ese mes, usar promedios generales
    if promedios['grasa_prom'] is None:
        promedios = CalidadLeche.objects.filter(
            fk_an=animal
        ).aggregate(
            grasa_prom=Avg('grasa_pct_cl'),
            proteina_prom=Avg('proteina_pct_cl'),
            ccs_prom=Avg('ccs_cl'),
            ufc_prom=Avg('ufc_cl')
        )
    
    # 2. CONSTRUIR CARACTERÍSTICAS (4)
    caracteristicas = [
        float(promedios.get('grasa_prom') or 3.5),
        float(promedios.get('proteina_prom') or 3.2),
        float(promedios.get('ccs_prom') or 200000),
        float(promedios.get('ufc_prom') or 0)
    ]
    
    # 3. CARGAR MODELO Y PREDECIR
    ruta = obtener_ruta_modelo('RL-4')
    if not os.path.exists(ruta):
        return {'exito': False, 'mensaje': 'Modelo RL-4 no encontrado'}
    
    modelo_data = joblib.load(ruta)
    modelo = modelo_data['modelo']
    
    X = np.array([caracteristicas])
    prediccion = modelo.predict(X)[0]
    probabilidad = modelo.predict_proba(X)[0]
    
    return {
        'exito': True,
        'prediccion': 'Apto' if prediccion == 1 else 'No Apto',
        'probabilidad': round(float(max(probabilidad)) * 100, 1),
        'mes': mes,
        'anio': anio,
        'datos_usados': {
            'grasa_pct': round(float(promedios.get('grasa_prom') or 3.5), 2),
            'proteina_pct': round(float(promedios.get('proteina_prom') or 3.2), 2),
            'ccs': round(float(promedios.get('ccs_prom') or 200000), 0),
            'ufc': round(float(promedios.get('ufc_prom') or 0), 0)
        }
    }


def predecir_anio_completo_rl4(animal_id, anio):
    """Predice los 12 meses del año para RL-4"""
    resultados = {}
    for mes in range(1, 13):
        resultado = predecir_mes_futuro_rl4(animal_id, mes, anio)
        if resultado['exito']:
            resultados[mes] = resultado
    return resultados


def predecir_anios_rl4(animal_id):
    """Predice año actual y siguiente para RL-4"""
    anio_actual = date.today().year
    resultados = {}
    
    resultados[anio_actual] = predecir_anio_completo_rl4(animal_id, anio_actual)
    resultados[anio_actual + 1] = predecir_anio_completo_rl4(animal_id, anio_actual + 1)
    
    return resultados


# ============================================================
# FUNCIÓN PREDECIR PRINCIPAL (MANTENER COMPATIBILIDAD)
# ============================================================

def predecir(codigo_mm, datos_entrada):
    """
    Función principal para compatibilidad con código existente.
    Para predicciones futuras usar las funciones específicas.
    """
    # Esta función se mantiene para compatibilidad
    # Las nuevas funciones son: predecir_anios_ad1, predecir_anios_ad2, predecir_anios_rl4
    
    if codigo_mm == 'AD-1':
        # Intentar obtener animal_id de datos_entrada
        animal_id = datos_entrada.get('animal_id')
        if animal_id:
            mes = datos_entrada.get('mes', date.today().month)
            anio = datos_entrada.get('anio', date.today().year)
            return predecir_mes_futuro_ad1(animal_id, mes, anio)
        else:
            return {'exito': False, 'mensaje': 'Se requiere animal_id para AD-1'}
    
    elif codigo_mm == 'AD-2':
        animal_id = datos_entrada.get('animal_id')
        if animal_id:
            mes = datos_entrada.get('mes', date.today().month)
            anio = datos_entrada.get('anio', date.today().year)
            return predecir_mes_futuro_ad2(animal_id, mes, anio)
        else:
            return {'exito': False, 'mensaje': 'Se requiere animal_id para AD-2'}
    
    elif codigo_mm == 'RL-4':
        animal_id = datos_entrada.get('animal_id')
        if animal_id:
            mes = datos_entrada.get('mes', date.today().month)
            anio = datos_entrada.get('anio', date.today().year)
            return predecir_mes_futuro_rl4(animal_id, mes, anio)
        else:
            return {'exito': False, 'mensaje': 'Se requiere animal_id para RL-4'}
    
    else:
        return {'exito': False, 'mensaje': f'Código {codigo_mm} no implementado'}


# ============================================================
# FUNCIONES DE ENTRENAMIENTO (ORIGINALES - SIN CAMBIOS)
# ============================================================

def entrenar_modelo(codigo_mm, guardar_db=True):
    """Entrena un modelo de Machine Learning SOLO CON DATOS REALES."""
    from Aplicaciones.Gestion.models import ModeloML
    
    print(f"[ML] Iniciando entrenamiento de {codigo_mm} con datos reales...")
    
    if codigo_mm == 'AD-1':
        df = obtener_datos_reales_ad1()
        if df is None or len(df) < 10:
            return {
                'exito': False,
                'mensaje': f'❌ ERROR: No hay suficientes datos reales para AD-1. '
                           f'Encontrados: {len(df) if df is not None else 0} registros.'
            }
        resultado = entrenar_ad1_con_datos_reales(df)
        
    elif codigo_mm == 'AD-2':
        df = obtener_datos_reales_ad2()
        if df is None or len(df) < 10:
            return {
                'exito': False,
                'mensaje': f'❌ ERROR: No hay suficientes datos reales para AD-2. '
                           f'Encontrados: {len(df) if df is not None else 0} registros.'
            }
        resultado = entrenar_ad2_con_datos_reales(df)
    
    elif codigo_mm == 'RL-4':
        df = obtener_datos_reales_rl4()
        if df is None or len(df) < 10:
            return {
                'exito': False,
                'mensaje': f'❌ ERROR: No hay suficientes datos reales para RL-4. '
                           f'Encontrados: {len(df) if df is not None else 0} registros.'
            }
        resultado = entrenar_rl4_con_datos_reales(df)
    
    else:
        return {
            'exito': False,
            'mensaje': f'❌ Código {codigo_mm} no implementado.'
        }
    
    if guardar_db and resultado.get('exito'):
        guardar_modelo_en_db(codigo_mm, resultado)
    
    return resultado


def guardar_modelo_en_db(codigo_mm, resultado):
    """Guarda el modelo entrenado en la base de datos."""
    from Aplicaciones.Gestion.models import ModeloML
    
    try:
        config = {
            'AD-1': {
                'nombre': 'Predicción de Litros de Leche',
                'tipo': 'gradient_boosting_regressor',
                'modulo': 'produccion_lactea',
                'metrica': 'r2_score',
                'valor': resultado.get('r2', 0)
            },
            'AD-2': {
                'nombre': 'Clasificación de Estado de Preñez',
                'tipo': 'decision_tree_classifier',
                'modulo': 'reproduccion',
                'metrica': 'accuracy',
                'valor': resultado.get('accuracy', 0)
            },
            'RL-4': {
                'nombre': 'Clasificación de Calidad de Leche',
                'tipo': 'logistic_regression',
                'modulo': 'calidad_leche',
                'metrica': 'accuracy',
                'valor': resultado.get('accuracy', 0)
            }
        }
        
        cfg = config.get(codigo_mm)
        if not cfg:
            return
        
        modelo_db, creado = ModeloML.objects.get_or_create(
            codigo_mm=codigo_mm,
            defaults={
                'nombre_mm': cfg['nombre'],
                'tipo_modelo_mm': cfg['tipo'],
                'modulo_aplicacion_mm': cfg['modulo'],
                'activo_mm': True,
                'metrica_principal_mm': cfg['metrica']
            }
        )
        
        modelo_db.archivo_modelo_mm = resultado.get('ruta_modelo')
        modelo_db.fecha_entrenamiento_mm = datetime.now()
        modelo_db.valor_metrica_mm = cfg['valor']
        modelo_db.save()
        
        resultado['guardado_db'] = True
        resultado['id_modelo_db'] = modelo_db.id_mm
        resultado['mensaje_db'] = f"✅ Modelo {codigo_mm} guardado en BD"
        
    except Exception as e:
        resultado['guardado_db'] = False
        resultado['error_db'] = str(e)


# ============================================================
# FUNCIONES DE OBTENCIÓN DE DATOS (ORIGINALES)
# ============================================================

def obtener_datos_reales_ad1():
    """Obtiene datos reales de la base de datos para AD-1."""
    from Aplicaciones.Gestion.models import Ordeno, Animal, Racion, Parto
    
    print(f"[ML] Obteniendo datos reales para AD-1...")
    
    ordenos = Ordeno.objects.filter(
        litros_or__isnull=False,
        fk_an__isnull=False,
        fecha_or__isnull=False,
        temperatura_ambiental_or__isnull=False,
        temperatura_leche_or__isnull=False,
        cantidad_concentrado_kg_or__isnull=False
    ).select_related('fk_an', 'fk_an__fk_ra').order_by('-fecha_or')
    
    print(f"[ML] Ordeños encontrados: {ordenos.count()}")
    
    if not ordenos:
        return None
    
    datos = []
    for o in ordenos:
        animal = o.fk_an
        if not animal:
            continue
        
        try:
            edad = 0
            if animal.fecha_nacimiento_an:
                edad = (o.fecha_or - animal.fecha_nacimiento_an).days
            
            raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
            num_partos = Parto.objects.filter(fk_madre_pa=animal, fecha_pa__lt=o.fecha_or).count()
            
            fecha_inicio = o.fecha_or - timedelta(days=7)
            prom_7dias = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__gte=fecha_inicio,
                fecha_or__lt=o.fecha_or
            ).aggregate(prom=Avg('litros_or'))['prom'] or 0
            
            racion = Racion.objects.filter(
                fk_an=animal,
                fecha_inicio_ra__lte=o.fecha_or
            ).filter(Q(fecha_fin_ra__gte=o.fecha_or) | Q(fecha_fin_ra__isnull=True)).first()
            
            cantidad_consumida = float(racion.cantidad_consumida_kg_ra or 0) if racion else 0
            cantidad_ofrecida = float(racion.cantidad_ofrecida_kg_ra or 0) if racion else 0
            
            mes = o.fecha_or.month
            if mes in [12, 1, 2]:
                temporada = 'invierno'
            elif mes in [3, 4, 5]:
                temporada = 'primavera'
            elif mes in [6, 7, 8]:
                temporada = 'verano'
            else:
                temporada = 'otoño'
            
            datos.append({
                'edad_dias': edad,
                'edad_anios': round(edad / 365, 1),
                'raza': raza,
                'peso_kg': float(animal.peso_actual_kg_an or 0),
                'condicion_corporal': float(animal.condicion_corporal_an or 0),
                'num_partos': num_partos,
                'promedio_7dias': float(prom_7dias),
                'cantidad_consumida': cantidad_consumida,
                'cantidad_ofrecida': cantidad_ofrecida,
                'mes': mes,
                'temporada': temporada,
                'temp_ambiental': float(o.temperatura_ambiental_or or 0),
                'temp_leche': float(o.temperatura_leche_or or 0),
                'concentrado_kg': float(o.cantidad_concentrado_kg_or or 0),
                'litros': float(o.litros_or)
            })
            
        except Exception as e:
            print(f"[ML] Error en ordeño {o.id_or}: {e}")
            continue
    
    df = pd.DataFrame(datos)
    print(f"[ML] Datos AD-1 obtenidos: {len(df)} registros")
    
    if len(df) < 10:
        return None
    
    return df


def obtener_datos_reales_ad2():
    """Obtiene datos reales para AD-2."""
    from Aplicaciones.Gestion.models import Inseminacion, Animal, Celo, Parto, Aborto, Ordeno
    
    print(f"[ML] Obteniendo datos reales para AD-2...")
    
    inseminaciones = Inseminacion.objects.filter(
        resultado_in__in=['preñada', 'no_preñada'],
        fk_an__isnull=False,
        fecha_in__isnull=False,
        condicion_corporal_in__isnull=False
    ).select_related('fk_an', 'fk_an__fk_ra', 'fk_toro_in').order_by('-fecha_in')
    
    print(f"[ML] Inseminaciones encontradas: {inseminaciones.count()}")
    
    if not inseminaciones:
        return None
    
    datos = []
    for ins in inseminaciones:
        animal = ins.fk_an
        if not animal:
            continue
        
        try:
            edad = 0
            if animal.fecha_nacimiento_an:
                edad = (ins.fecha_in - animal.fecha_nacimiento_an).days
            
            num_partos = Parto.objects.filter(fk_madre_pa=animal).count()
            abortos = Aborto.objects.filter(fk_an=animal).count()
            
            fecha_inicio = ins.fecha_in - timedelta(days=7)
            produccion = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__gte=fecha_inicio,
                fecha_or__lt=ins.fecha_in
            ).aggregate(prom=Avg('litros_or'))['prom'] or 0
            
            celo = Celo.objects.filter(
                fk_an=animal,
                fecha_observacion_ce__lte=ins.fecha_in
            ).order_by('-fecha_observacion_ce').first()
            
            raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
            toro = ins.fk_toro_in.codigo_an if ins.fk_toro_in else 'desconocido'
            tipo = ins.tipo_inseminacion_in or 'artificial'
            dias = (date.today() - ins.fecha_in).days
            
            datos.append({
                'edad_dias': edad,
                'num_partos': num_partos,
                'raza': raza,
                'condicion_corporal': float(ins.condicion_corporal_in or 0),
                'produccion_leche': float(produccion),
                'intensidad_celo': celo.intensidad_ce if celo else 'media',
                'duracion_celo_horas': celo.duracion_aproximada_horas_ce if celo else 12,
                'tipo_inseminacion': tipo,
                'toro': toro,
                'historial_abortos': abortos,
                'dias_desde_inseminacion': dias,
                'preñada': 1 if ins.resultado_in == 'preñada' else 0
            })
        except Exception as e:
            print(f"[ML] Error en inseminación {ins.id_in}: {e}")
            continue
    
    df = pd.DataFrame(datos)
    print(f"[ML] Datos AD-2 obtenidos: {len(df)} registros")
    
    if len(df) < 10:
        return None
    
    return df


def obtener_datos_reales_rl4():
    """Obtiene datos reales para RL-4."""
    from Aplicaciones.Gestion.models import CalidadLeche
    
    print(f"[ML] Obteniendo datos reales para RL-4...")
    
    calidades = CalidadLeche.objects.filter(
        grasa_pct_cl__isnull=False,
        proteina_pct_cl__isnull=False,
        ccs_cl__isnull=False,
        resultado_cl__isnull=False
    ).exclude(resultado_cl='pendiente').order_by('-fecha_muestreo_cl')
    
    print(f"[ML] Calidades encontradas: {calidades.count()}")
    
    if not calidades:
        return None
    
    datos = []
    for c in calidades:
        try:
            ufc = float(c.ufc_cl) if hasattr(c, 'ufc_cl') and c.ufc_cl is not None else 0
            
            datos.append({
                'grasa_pct': float(c.grasa_pct_cl or 0),
                'proteina_pct': float(c.proteina_pct_cl or 0),
                'ccs': float(c.ccs_cl or 0),
                'ufc': ufc,
                'apto': 1 if str(c.resultado_cl).lower() == 'apto' else 0
            })
        except Exception as e:
            print(f"[ML] Error en calidad {c.id_cl}: {e}")
            continue
    
    df = pd.DataFrame(datos)
    print(f"[ML] Datos RL-4 obtenidos: {len(df)} registros")
    
    if len(df) < 10:
        return None
    
    return df


# ============================================================
# FUNCIONES DE ENTRENAMIENTO (ORIGINALES)
# ============================================================

def entrenar_ad1_con_datos_reales(df):
    """Entrena AD-1 con datos reales."""
    X, y, encoders = preprocesar_datos_ad1(df)
    if X is None or len(X) < 10:
        return {'exito': False, 'mensaje': 'Error en preprocesamiento de AD-1'}
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    modelo = GradientBoostingRegressor(
        n_estimators=100, max_depth=6, min_samples_split=10,
        min_samples_leaf=5, learning_rate=0.1, random_state=42
    )
    modelo.fit(X_train, y_train)
    y_pred = modelo.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    
    ruta = obtener_ruta_modelo('AD-1')
    joblib.dump({
        'modelo': modelo,
        'scaler': encoders['scaler'],
        'features': encoders['features'],
        'raza_encoder': encoders['raza_encoder'],
        'temporada_encoder': encoders['temporada_encoder']
    }, ruta)
    
    return {
        'exito': True, 'codigo': 'AD-1', 'ruta_modelo': ruta,
        'r2': round(r2, 4), 'rmse': round(rmse, 4),
        'registros': len(df), 'entrenamiento': len(X_train),
        'prueba': len(X_test), 'fuente': 'datos_reales',
        'variables': encoders['features']
    }


def entrenar_ad2_con_datos_reales(df):
    """Entrena AD-2 con datos reales."""
    X, y, encoders = preprocesar_datos_ad2(df)
    if X is None or len(X) < 10:
        return {'exito': False, 'mensaje': 'Error en preprocesamiento de AD-2'}
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    modelo = DecisionTreeClassifier(max_depth=6, min_samples_split=15, min_samples_leaf=5, random_state=42)
    modelo.fit(X_train, y_train)
    y_pred = modelo.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    cv_scores = cross_val_score(modelo, X, y, cv=5)
    
    ruta = obtener_ruta_modelo('AD-2')
    joblib.dump({
        'modelo': modelo,
        'features': ['edad_dias', 'num_partos', 'raza_cod', 'condicion_corporal',
                    'produccion_leche', 'intensidad_cod', 'duracion_celo_horas',
                    'tipo_cod', 'toro_cod', 'historial_abortos', 'dias_desde_inseminacion']
    }, ruta)
    
    return {
        'exito': True, 'codigo': 'AD-2', 'ruta_modelo': ruta,
        'accuracy': round(acc, 4), 'cv_mean': round(cv_scores.mean(), 4),
        'cv_std': round(cv_scores.std(), 4), 'registros': len(df),
        'entrenamiento': len(X_train), 'prueba': len(X_test),
        'fuente': 'datos_reales'
    }


def entrenar_rl4_con_datos_reales(df):
    """Entrena RL-4 con datos reales."""
    X, y, _ = preprocesar_datos_rl4(df)
    if X is None or len(X) < 10:
        return {'exito': False, 'mensaje': 'Error en preprocesamiento de RL-4'}
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    modelo = LogisticRegression(max_iter=1000, random_state=42, class_weight='balanced')
    modelo.fit(X_train, y_train)
    y_pred = modelo.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    cv_scores = cross_val_score(modelo, X, y, cv=5)
    
    ruta = obtener_ruta_modelo('RL-4')
    joblib.dump({
        'modelo': modelo,
        'features': ['grasa_pct', 'proteina_pct', 'ccs', 'ufc']
    }, ruta)
    
    return {
        'exito': True, 'codigo': 'RL-4', 'ruta_modelo': ruta,
        'accuracy': round(acc, 4), 'cv_mean': round(cv_scores.mean(), 4),
        'cv_std': round(cv_scores.std(), 4), 'registros': len(df),
        'entrenamiento': len(X_train), 'prueba': len(X_test),
        'fuente': 'datos_reales'
    }


# ============================================================
# FUNCIONES DE PREPROCESAMIENTO (ORIGINALES)
# ============================================================

def preprocesar_datos_ad1(df):
    """Preprocesa datos para AD-1."""
    if df is None or df.empty:
        return None, None, None
    
    df = df.copy()
    le_raza = LabelEncoder()
    le_temporada = LabelEncoder()
    
    df['raza_cod'] = le_raza.fit_transform(df['raza'].fillna('desconocida'))
    df['temporada_cod'] = le_temporada.fit_transform(df['temporada'].fillna('invierno'))
    
    features = [
        'edad_dias', 'edad_anios', 'raza_cod', 'peso_kg',
        'condicion_corporal', 'num_partos', 'promedio_7dias',
        'cantidad_consumida', 'cantidad_ofrecida',
        'mes', 'temporada_cod',
        'temp_ambiental', 'temp_leche', 'concentrado_kg'
    ]
    
    for col in features:
        if col not in df.columns:
            df[col] = 0
    
    X = df[features].fillna(0).values
    y = df['litros'].values
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    return X_scaled, y, {
        'scaler': scaler,
        'raza_encoder': le_raza,
        'temporada_encoder': le_temporada,
        'features': features
    }


def preprocesar_datos_ad2(df):
    """Preprocesa datos para AD-2."""
    if df is None or df.empty:
        return None, None, None
    
    df = df.copy()
    le_raza = LabelEncoder()
    le_intensidad = LabelEncoder()
    le_tipo = LabelEncoder()
    le_toro = LabelEncoder()
    
    df['raza_cod'] = le_raza.fit_transform(df['raza'].fillna('desconocida'))
    df['intensidad_cod'] = le_intensidad.fit_transform(df['intensidad_celo'].fillna('media'))
    df['tipo_cod'] = le_tipo.fit_transform(df['tipo_inseminacion'].fillna('artificial'))
    df['toro_cod'] = le_toro.fit_transform(df['toro'].fillna('desconocido'))
    
    features = [
        'edad_dias', 'num_partos', 'raza_cod', 'condicion_corporal',
        'produccion_leche', 'intensidad_cod', 'duracion_celo_horas',
        'tipo_cod', 'toro_cod', 'historial_abortos', 'dias_desde_inseminacion'
    ]
    
    for col in features:
        if col not in df.columns:
            df[col] = 0
    
    X = df[features].fillna(0).values
    y = df['preñada'].values
    
    return X, y, {
        'raza': le_raza,
        'intensidad': le_intensidad,
        'tipo': le_tipo,
        'toro': le_toro
    }


def preprocesar_datos_rl4(df):
    """Preprocesa datos para RL-4."""
    if df is None or df.empty:
        return None, None, None
    
    df = df.copy()
    features = ['grasa_pct', 'proteina_pct', 'ccs', 'ufc']
    
    for col in features:
        if col not in df.columns:
            df[col] = 0
    
    X = df[features].fillna(0).values
    y = df['apto'].values
    
    return X, y, None