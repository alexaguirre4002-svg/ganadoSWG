# ============================================================
# ml_engine.py - Motor de Machine Learning para GanadoSWG
# VERSIÓN 3.0 - CON MÁS VARIABLES PARA AD-1
# ============================================================

import os
from datetime import datetime, date, timedelta
import joblib
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, accuracy_score, r2_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from django.conf import settings
from django.db.models import Avg, Q, Count, Sum, Max, Min

# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def obtener_ruta_modelo(codigo_mm):
    """Obtiene la ruta donde se guarda el archivo .pkl del modelo"""
    base = os.path.join(settings.BASE_DIR, 'media', 'ml')
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f'{codigo_mm}.pkl')


# ---------------------------------------------------------------------------
# OBTENCIÓN DE DATOS REALES - AD-1 MEJORADO
# ---------------------------------------------------------------------------

def obtener_datos_reales_ad1():
    """
    Obtiene datos reales de la base de datos para AD-1.
    VERSIÓN MEJORADA CON MÁS VARIABLES:
    - Edad
    - Raza
    - Peso
    - Condición corporal
    - Cantidad consumida
    - Cantidad ofrecida
    - Promedio 7 días
    - Temp ambiental
    - Temp leche
    - Número de partos
    - Estado sanitario
    - Días en lactancia (NUEVO)
    - Producción acumulada (NUEVO)
    - Eficiencia alimenticia (NUEVO)
    - Mes del año (NUEVO)
    - Hora del ordeño (NUEVO)
    - Días desde último parto (NUEVO)
    - Número de ordeños totales (NUEVO)
    """
    from Aplicaciones.Gestion.models import Ordeno, Animal, Racion, EventoSanitario, Parto, Secado
    
    print(f"[ML] Obteniendo datos reales mejorados para AD-1 de tu BDD...")
    
    ordenos = Ordeno.objects.filter(
        litros_or__isnull=False,
        fk_an__isnull=False,
        fecha_or__isnull=False,
        temperatura_ambiental_or__isnull=False,
        temperatura_leche_or__isnull=False,
        cantidad_concentrado_kg_or__isnull=False
    ).select_related(
        'fk_an',
        'fk_an__fk_ra'
    ).order_by('-fecha_or')
    
    print(f"[ML] Ordeños encontrados: {ordenos.count()}")
    
    if not ordenos:
        print(f"[ML] ERROR: No hay datos en la tabla Ordeno para entrenar AD-1")
        return None
    
    datos = []
    for o in ordenos:
        animal = o.fk_an
        if not animal:
            continue
            
        try:
            # ==========================================
            # 1. DATOS DEL ANIMAL
            # ==========================================
            
            # Edad en días
            edad = 0
            if animal.fecha_nacimiento_an:
                edad = (o.fecha_or - animal.fecha_nacimiento_an).days
            
            # Edad en años (para mejor interpretación)
            edad_anios = round(edad / 365, 1)
            
            # Raza
            raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
            
            # Peso
            peso = float(animal.peso_actual_kg_an or 0)
            
            # Condición corporal
            condicion = float(animal.condicion_corporal_an or 0)
            
            # ==========================================
            # 2. DATOS DE PRODUCCIÓN
            # ==========================================
            
            # Número de partos previos
            num_partos = Parto.objects.filter(
                fk_madre_pa=animal,
                fecha_pa__lt=o.fecha_or
            ).count()
            
            # Fecha del último parto (para calcular días en lactancia)
            ultimo_parto = Parto.objects.filter(
                fk_madre_pa=animal,
                fecha_pa__lt=o.fecha_or
            ).order_by('-fecha_pa').first()
            
            dias_desde_ultimo_parto = 0
            if ultimo_parto:
                dias_desde_ultimo_parto = (o.fecha_or - ultimo_parto.fecha_pa).days
            
            # Días en lactancia (si tiene secado, se reinicia)
            secado = Secado.objects.filter(
                fk_an=animal,
                fecha_ultimo_ordeno_se__lt=o.fecha_or
            ).order_by('-fecha_ultimo_ordeno_se').first()
            
            dias_en_lactancia = dias_desde_ultimo_parto
            if secado and dias_desde_ultimo_parto > 0:
                # Si hubo secado, los días en lactancia son desde el secado
                dias_en_lactancia = (o.fecha_or - secado.fecha_ultimo_ordeno_se).days
            
            # ==========================================
            # 3. HISTORIAL DE PRODUCCIÓN
            # ==========================================
            
            # Producción promedio últimos 7 días
            fecha_inicio = o.fecha_or - timedelta(days=7)
            prom_7dias = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__gte=fecha_inicio,
                fecha_or__lt=o.fecha_or
            ).aggregate(prom=Avg('litros_or'))['prom'] or 0
            
            # Producción promedio últimos 30 días
            fecha_inicio_30 = o.fecha_or - timedelta(days=30)
            prom_30dias = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__gte=fecha_inicio_30,
                fecha_or__lt=o.fecha_or
            ).aggregate(prom=Avg('litros_or'))['prom'] or 0
            
            # Producción acumulada total (histórica)
            produccion_acumulada = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__lt=o.fecha_or
            ).aggregate(total=Sum('litros_or'))['total'] or 0
            
            # Número total de ordeños del animal
            total_ordenos = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__lt=o.fecha_or
            ).count()
            
            # Máxima producción registrada
            max_produccion = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__lt=o.fecha_or
            ).aggregate(max=Max('litros_or'))['max'] or 0
            
            # ==========================================
            # 4. DATOS DE ALIMENTACIÓN
            # ==========================================
            
            # Ración del día
            racion = Racion.objects.filter(
                fk_an=animal,
                fecha_inicio_ra__lte=o.fecha_or
            ).filter(
                Q(fecha_fin_ra__gte=o.fecha_or) | Q(fecha_fin_ra__isnull=True)
            ).first()
            
            cantidad_consumida = float(racion.cantidad_consumida_kg_ra or 0) if racion else 0
            cantidad_ofrecida = float(racion.cantidad_ofrecida_kg_ra or 0) if racion else 0
            
            # Eficiencia alimenticia (litros por kg de consumo)
            eficiencia = 0
            if cantidad_consumida > 0 and o.litros_or > 0:
                eficiencia = float(float(o.litros_or) / float(cantidad_consumida))
            
            # ==========================================
            # 5. ESTADO SANITARIO
            # ==========================================
            
            # Evento sanitario reciente (últimos 15 días)
            tiene_evt_san = EventoSanitario.objects.filter(
                fk_an=animal,
                fecha_ejecutada_es__gte=o.fecha_or - timedelta(days=15)
            ).exists()
            
            # Número de eventos sanitarios en los últimos 30 días
            num_evt_san_30 = EventoSanitario.objects.filter(
                fk_an=animal,
                fecha_ejecutada_es__gte=o.fecha_or - timedelta(days=30)
            ).count()
            
            # ==========================================
            # 6. VARIABLES DE TIEMPO
            # ==========================================
            
            # Mes del año (1-12)
            mes = o.fecha_or.month
            
            # Día de la semana (1=Lunes, 7=Domingo)
            dia_semana = o.fecha_or.isoweekday()
            
            # Temporada
            if mes in [12, 1, 2]:
                temporada = 'invierno'
            elif mes in [3, 4, 5]:
                temporada = 'primavera'
            elif mes in [6, 7, 8]:
                temporada = 'verano'
            else:
                temporada = 'otoño'
            
            # ==========================================
            # 7. DATOS DEL ORDEÑO ACTUAL
            # ==========================================
            
            temp_ambiental = float(o.temperatura_ambiental_or or 0)
            temp_leche = float(o.temperatura_leche_or or 0)
            concentrado = float(o.cantidad_concentrado_kg_or or 0)
            
            # Diferencia de temperatura (ambiental - leche)
            diff_temp = temp_ambiental - temp_leche if temp_ambiental and temp_leche else 0
            
            # ==========================================
            # 8. DATOS DEL POTRERO
            # ==========================================
            
            potrero = animal.fk_potrero_an
            potrero_nombre = potrero.nombre_po if potrero else 'sin_potrero'
            hectareas_potrero = float(potrero.hectareas_po or 0) if potrero else 0
            
            # ==========================================
            # CONSTRUIR DICCIONARIO DE DATOS
            # ==========================================
            
            datos.append({
                # Datos del animal
                'edad_dias': edad,
                'edad_anios': edad_anios,
                'raza': raza,
                'peso_kg': peso,
                'condicion_corporal': condicion,
                'num_partos': num_partos,
                'dias_desde_ultimo_parto': dias_desde_ultimo_parto,
                'dias_en_lactancia': dias_en_lactancia,
                
                # Historial de producción
                'promedio_7dias': float(prom_7dias),
                'promedio_30dias': float(prom_30dias),
                'produccion_acumulada': float(produccion_acumulada),
                'total_ordenos': total_ordenos,
                'max_produccion': float(max_produccion),
                
                # Alimentación
                'cantidad_consumida': cantidad_consumida,
                'cantidad_ofrecida': cantidad_ofrecida,
                'eficiencia_alimenticia': eficiencia,
                
                # Estado sanitario
                'estado_sanitario': 1 if tiene_evt_san else 0,
                'num_eventos_sanitarios_30': num_evt_san_30,
                
                # Variables de tiempo
                'mes': mes,
                'dia_semana': dia_semana,
                'temporada': temporada,
                
                # Datos del ordeño
                'temp_ambiental': temp_ambiental,
                'temp_leche': temp_leche,
                'concentrado_kg': concentrado,
                'diff_temp': diff_temp,
                
                # Datos del potrero
                'potrero': potrero_nombre,
                'hectareas_potrero': hectareas_potrero,
                
                # Variable objetivo
                'litros': float(o.litros_or)
            })
            
        except Exception as e:
            print(f"[ML] Error en ordeño {o.id_or}: {e}")
            continue
    
    df = pd.DataFrame(datos)
    print(f"[ML] Datos reales mejorados AD-1 obtenidos: {len(df)} registros")
    print(f"[ML] Columnas disponibles: {list(df.columns)}")
    
    if len(df) < 10:
        print(f"[ML] ERROR: Solo {len(df)} registros. Necesitas al menos 10 para entrenar.")
        return None
    
    return df


# ---------------------------------------------------------------------------
# PREPROCESAMIENTO MEJORADO PARA AD-1
# ---------------------------------------------------------------------------

def preprocesar_datos_ad1_mejorado(df):
    """
    Preprocesa datos para AD-1 con TODAS las variables mejoradas.
    """
    if df is None or df.empty:
        return None, None, None
    
    df = df.copy()
    
    # ==========================================
    # 1. CODIFICAR VARIABLES CATEGÓRICAS
    # ==========================================
    
    le_raza = LabelEncoder()
    le_temporada = LabelEncoder()
    le_potrero = LabelEncoder()
    
    # Raza
    if 'raza' in df.columns:
        df['raza_cod'] = le_raza.fit_transform(df['raza'].fillna('desconocida'))
    else:
        df['raza_cod'] = 0
    
    # Temporada
    if 'temporada' in df.columns:
        df['temporada_cod'] = le_temporada.fit_transform(df['temporada'].fillna('invierno'))
    else:
        df['temporada_cod'] = 0
    
    # Potrero
    if 'potrero' in df.columns:
        df['potrero_cod'] = le_potrero.fit_transform(df['potrero'].fillna('sin_potrero'))
    else:
        df['potrero_cod'] = 0
    
    # ==========================================
    # 2. CREAR NUEVAS CARACTERÍSTICAS (FEATURE ENGINEERING)
    # ==========================================
    
    # Relación consumo/producción
    df['ratio_consumo_produccion'] = df.apply(
        lambda row: row['cantidad_consumida'] / row['litros'] if row['litros'] > 0 and row['cantidad_consumida'] > 0 else 0,
        axis=1
    )
    
    # Porcentaje de consumo vs ofrecido
    df['pct_consumo'] = df.apply(
        lambda row: (row['cantidad_consumida'] / row['cantidad_ofrecida'] * 100) if row['cantidad_ofrecida'] > 0 else 0,
        axis=1
    )
    
    # Edad en años (redondeado)
    df['edad_anios_redondeado'] = df['edad_anios'].round(0)
    
    # ==========================================
    # 3. SELECCIONAR CARACTERÍSTICAS (TODAS LAS MEJORADAS)
    # ==========================================
    
    features = [
        # Datos del animal
        'edad_dias',
        'edad_anios',
        'raza_cod',
        'peso_kg',
        'condicion_corporal',
        'num_partos',
        'dias_desde_ultimo_parto',
        'dias_en_lactancia',
        
        # Historial de producción
        'promedio_7dias',
        'promedio_30dias',
        'produccion_acumulada',
        'total_ordenos',
        'max_produccion',
        
        # Alimentación
        'cantidad_consumida',
        'cantidad_ofrecida',
        'eficiencia_alimenticia',
        'ratio_consumo_produccion',
        'pct_consumo',
        
        # Estado sanitario
        'estado_sanitario',
        'num_eventos_sanitarios_30',
        
        # Variables de tiempo
        'mes',
        'dia_semana',
        'temporada_cod',
        'potrero_cod',
        'hectareas_potrero',
        
        # Datos del ordeño
        'temp_ambiental',
        'temp_leche',
        'concentrado_kg',
        'diff_temp',
    ]
    
    # Asegurar que todas las columnas existan
    for col in features:
        if col not in df.columns:
            df[col] = 0
    
    X = df[features].fillna(0).values
    y = df['litros'].values
    
    # ==========================================
    # 4. ESCALAR DATOS (OPCIONAL - MEJORA RENDIMIENTO)
    # ==========================================
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    return X_scaled, y, {
        'scaler': scaler,
        'raza_encoder': le_raza,
        'temporada_encoder': le_temporada,
        'potrero_encoder': le_potrero,
        'features': features,
        'feature_names': features  # Para referencia
    }


# ---------------------------------------------------------------------------
# ENTRENAMIENTO MEJORADO PARA AD-1
# ---------------------------------------------------------------------------

def entrenar_modelo_ad1_mejorado():
    """
    Entrena AD-1 con el modelo mejorado (Random Forest o Gradient Boosting)
    """
    from Aplicaciones.Gestion.models import ModeloML
    
    print(f"[ML] Iniciando entrenamiento mejorado de AD-1...")
    
    # Obtener datos
    df = obtener_datos_reales_ad1()
    
    if df is None or len(df) < 10:
        return {
            'exito': False,
            'mensaje': f'❌ No hay suficientes datos reales para AD-1. '
                       f'Encontrados: {len(df) if df is not None else 0} registros.'
        }
    
    # Preprocesar
    X, y, encoders = preprocesar_datos_ad1_mejorado(df)
    if X is None or len(X) < 10:
        return {'exito': False, 'mensaje': f'❌ Error en preprocesamiento de AD-1'}
    
    # Dividir datos
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # ==========================================
    # PROBAR MÚLTIPLES MODELOS
    # ==========================================
    
    modelos = {
        'RandomForest': RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1
        ),
        'GradientBoosting': GradientBoostingRegressor(
            n_estimators=100,
            max_depth=6,
            min_samples_split=10,
            min_samples_leaf=5,
            learning_rate=0.1,
            random_state=42
        ),
        'DecisionTree': DecisionTreeRegressor(
            max_depth=8,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42
        )
    }
    
    mejores_metricas = {
        'modelo': None,
        'r2': -1,
        'rmse': float('inf'),
        'nombre': None
    }
    
    for nombre, modelo in modelos.items():
        print(f"[ML] Probando {nombre}...")
        modelo.fit(X_train, y_train)
        y_pred = modelo.predict(X_test)
        r2 = r2_score(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        
        print(f"[ML]   {nombre} - R²: {r2:.4f}, RMSE: {rmse:.4f}")
        
        if r2 > mejores_metricas['r2']:
            mejores_metricas['r2'] = r2
            mejores_metricas['rmse'] = rmse
            mejores_metricas['modelo'] = modelo
            mejores_metricas['nombre'] = nombre
    
    # ==========================================
    # GUARDAR EL MEJOR MODELO
    # ==========================================
    
    ruta = obtener_ruta_modelo('AD-1')
    joblib.dump({
        'modelo': mejores_metricas['modelo'],
        'scaler': encoders['scaler'],
        'features': encoders['features'],
        'raza_encoder': encoders['raza_encoder'],
        'temporada_encoder': encoders['temporada_encoder'],
        'potrero_encoder': encoders['potrero_encoder']
    }, ruta)
    
    # ==========================================
    # GUARDAR EN BASE DE DATOS
    # ==========================================
    
    try:
        modelo_db, creado = ModeloML.objects.get_or_create(
            codigo_mm='AD-1',
            defaults={
                'nombre_mm': 'Predicción de Litros de Leche (v3 - Mejorado)',
                'tipo_modelo_mm': mejores_metricas['nombre'].lower(),
                'modulo_aplicacion_mm': 'produccion_lactea',
                'activo_mm': True,
                'metrica_principal_mm': 'r2_score'
            }
        )
        
        modelo_db.archivo_modelo_mm = ruta
        modelo_db.fecha_entrenamiento_mm = datetime.now()
        modelo_db.valor_metrica_mm = mejores_metricas['r2']
        modelo_db.save()
        
        guardado_db = True
        id_modelo_db = modelo_db.id_mm
        
    except Exception as e:
        guardado_db = False
        id_modelo_db = None
        print(f"[ML] Error guardando en BD: {e}")
    
    # ==========================================
    # RESULTADOS
    # ==========================================
    
    metricas = {
        'exito': True,
        'codigo': 'AD-1',
        'ruta_modelo': ruta,
        'r2': round(mejores_metricas['r2'], 4),
        'rmse': round(mejores_metricas['rmse'], 4),
        'mejor_modelo': mejores_metricas['nombre'],
        'registros': len(df),
        'entrenamiento': len(X_train),
        'prueba': len(X_test),
        'fuente': 'datos_reales',
        'variables': encoders['features'],
        'guardado_db': guardado_db,
        'id_modelo_db': id_modelo_db
    }
    
    print(f"[ML] ✅ AD-1 mejorado entrenado con {mejores_metricas['nombre']}")
    print(f"[ML]    R²: {mejores_metricas['r2']:.4f}")
    print(f"[ML]    RMSE: {mejores_metricas['rmse']:.4f}")
    
    return metricas


# ---------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL DE ENTRENAMIENTO (MODIFICADA)
# ---------------------------------------------------------------------------

def entrenar_modelo(codigo_mm, guardar_db=True):
    """
    Entrena un modelo de Machine Learning SOLO CON DATOS REALES.
    """
    from Aplicaciones.Gestion.models import ModeloML
    
    print(f"[ML] Iniciando entrenamiento de {codigo_mm} con datos reales...")
    
    # -----------------------------------------------------------------------
    # AD-1: USAR VERSIÓN MEJORADA
    # -----------------------------------------------------------------------
    if codigo_mm == 'AD-1':
        return entrenar_modelo_ad1_mejorado()
    
    # -----------------------------------------------------------------------
    # AD-2: Clasificación de Preñez
    # -----------------------------------------------------------------------
    elif codigo_mm == 'AD-2':
        df = obtener_datos_reales_ad2()
        
        if df is None or len(df) < 10:
            return {
                'exito': False,
                'mensaje': f'❌ No hay suficientes datos reales para {codigo_mm}. '
                           f'Encontrados: {len(df) if df is not None else 0} registros.'
            }
        
        X, y, _ = preprocesar_datos_ad2(df)
        if X is None or len(X) < 10:
            return {'exito': False, 'mensaje': f'❌ Error en preprocesamiento de {codigo_mm}'}
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        modelo = DecisionTreeClassifier(
            max_depth=6,
            min_samples_split=15,
            min_samples_leaf=5,
            random_state=42
        )
        modelo.fit(X_train, y_train)
        
        y_pred = modelo.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        
        cv_scores = cross_val_score(modelo, X, y, cv=5)
        
        ruta = obtener_ruta_modelo(codigo_mm)
        joblib.dump(modelo, ruta)
        
        metricas = {
            'exito': True,
            'codigo': codigo_mm,
            'ruta_modelo': ruta,
            'accuracy': round(acc, 4),
            'cv_mean': round(cv_scores.mean(), 4),
            'cv_std': round(cv_scores.std(), 4),
            'registros': len(df),
            'entrenamiento': len(X_train),
            'prueba': len(X_test),
            'fuente': 'datos_reales',
            'variables': ['edad_dias', 'num_partos', 'raza', 'condicion_corporal',
                         'produccion_leche', 'intensidad_celo', 'duracion_celo_horas',
                         'tipo_inseminacion', 'toro', 'historial_abortos', 'dias_desde_inseminacion']
        }
    
    # -----------------------------------------------------------------------
    # RL-4: Clasificación de Calidad de Leche
    # -----------------------------------------------------------------------
    elif codigo_mm == 'RL-4':
        df = obtener_datos_reales_rl4()
        
        if df is None or len(df) < 10:
            return {
                'exito': False,
                'mensaje': f'❌ No hay suficientes datos reales para {codigo_mm}. '
                           f'Encontrados: {len(df) if df is not None else 0} registros.'
            }
        
        X, y, _ = preprocesar_datos_rl4(df)
        if X is None or len(X) < 10:
            return {'exito': False, 'mensaje': f'❌ Error en preprocesamiento de {codigo_mm}'}
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        modelo = LogisticRegression(
            max_iter=1000,
            random_state=42,
            class_weight='balanced'
        )
        modelo.fit(X_train, y_train)
        
        y_pred = modelo.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        
        cv_scores = cross_val_score(modelo, X, y, cv=5)
        
        ruta = obtener_ruta_modelo(codigo_mm)
        joblib.dump(modelo, ruta)
        
        metricas = {
            'exito': True,
            'codigo': codigo_mm,
            'ruta_modelo': ruta,
            'accuracy': round(acc, 4),
            'cv_mean': round(cv_scores.mean(), 4),
            'cv_std': round(cv_scores.std(), 4),
            'registros': len(df),
            'entrenamiento': len(X_train),
            'prueba': len(X_test),
            'fuente': 'datos_reales',
            'variables': ['grasa_pct', 'proteina_pct', 'ccs', 'ufc']
        }
    
    else:
        return {
            'exito': False,
            'mensaje': f'❌ Código {codigo_mm} no implementado. Implementados: AD-1, AD-2, RL-4'
        }
    
    # -----------------------------------------------------------------------
    # Guardar en base de datos
    # -----------------------------------------------------------------------
    if guardar_db and metricas.get('exito'):
        try:
            if codigo_mm == 'AD-1':
                valor_metrica = metricas.get('r2', 0)
                metrica_nombre = 'r2_score'
                tipo_modelo = 'random_forest_regressor'  # Cambiado a RandomForest
                modulo = 'produccion_lactea'
            elif codigo_mm == 'AD-2':
                valor_metrica = metricas.get('accuracy', 0)
                metrica_nombre = 'accuracy'
                tipo_modelo = 'decision_tree_classifier'
                modulo = 'reproduccion'
            else:  # RL-4
                valor_metrica = metricas.get('accuracy', 0)
                metrica_nombre = 'accuracy'
                tipo_modelo = 'logistic_regression'
                modulo = 'calidad_leche'
            
            modelo_db, creado = ModeloML.objects.get_or_create(
                codigo_mm=codigo_mm,
                defaults={
                    'nombre_mm': {
                        'AD-1': 'Predicción de Litros de Leche (v3 - Mejorado)',
                        'AD-2': 'Clasificación de Estado de Preñez (v2 - Datos Reales)',
                        'RL-4': 'Clasificación de Calidad de Leche (v2 - Datos Reales)'
                    }.get(codigo_mm, codigo_mm),
                    'tipo_modelo_mm': tipo_modelo,
                    'modulo_aplicacion_mm': modulo,
                    'activo_mm': True,
                    'metrica_principal_mm': metrica_nombre
                }
            )
            
            modelo_db.archivo_modelo_mm = metricas['ruta_modelo']
            modelo_db.fecha_entrenamiento_mm = datetime.now()
            modelo_db.valor_metrica_mm = valor_metrica
            modelo_db.save()
            
            metricas['guardado_db'] = True
            metricas['id_modelo_db'] = modelo_db.id_mm
            
        except Exception as e:
            metricas['guardado_db'] = False
            metricas['error_db'] = str(e)
    
    return metricas


# ============================================================
# FUNCIONES EXISTENTES (SE MANTIENEN IGUAL)
# ============================================================

def obtener_datos_reales_ad2():
    """Obtiene datos reales para AD-2 (sin cambios)"""
    from Aplicaciones.Gestion.models import Inseminacion, Animal, Celo, Parto, Aborto, Ordeno
    
    print(f"[ML] Obteniendo datos reales para AD-2 de tu BDD...")
    
    inseminaciones = Inseminacion.objects.filter(
        resultado_in__in=['preñada', 'no_preñada'],
        fk_an__isnull=False,
        fecha_in__isnull=False,
        condicion_corporal_in__isnull=False
    ).select_related(
        'fk_an',
        'fk_an__fk_ra',
        'fk_toro_in'
    ).order_by('-fecha_in')
    
    if not inseminaciones:
        print(f"[ML] ERROR: No hay datos en la tabla Inseminacion para entrenar AD-2")
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
    print(f"[ML] Datos reales AD-2 obtenidos: {len(df)} registros")
    
    if len(df) < 10:
        print(f"[ML] ERROR: Solo {len(df)} registros. Necesitas al menos 10 para entrenar.")
        return None
    
    return df


def obtener_datos_reales_rl4():
    """Obtiene datos reales para RL-4 (sin cambios)"""
    from Aplicaciones.Gestion.models import CalidadLeche
    
    print(f"[ML] Obteniendo datos reales para RL-4 de tu BDD...")
    
    calidades = CalidadLeche.objects.filter(
        grasa_pct_cl__isnull=False,
        proteina_pct_cl__isnull=False,
        ccs_cl__isnull=False,
        resultado_cl__isnull=False
    ).exclude(
        resultado_cl='pendiente'
    ).order_by('-fecha_muestreo_cl')
    
    if not calidades:
        print(f"[ML] ERROR: No hay datos en la tabla CalidadLeche para entrenar RL-4")
        return None
    
    datos = []
    for c in calidades:
        try:
            try:
                ufc = float(c.ufc_cl) if hasattr(c, 'ufc_cl') and c.ufc_cl is not None else 0
            except:
                ufc = 0
            
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
    print(f"[ML] Datos reales RL-4 obtenidos: {len(df)} registros")
    
    if len(df) < 10:
        print(f"[ML] ERROR: Solo {len(df)} registros. Necesitas al menos 10 para entrenar.")
        return None
    
    return df


def preprocesar_datos_ad2(df):
    """Preprocesa datos para AD-2 (sin cambios)"""
    if df is None or df.empty:
        return None, None, None
    
    df = df.copy()
    
    le_raza = LabelEncoder()
    le_intensidad = LabelEncoder()
    le_tipo = LabelEncoder()
    le_toro = LabelEncoder()
    
    if 'raza' in df.columns:
        df['raza_cod'] = le_raza.fit_transform(df['raza'].fillna('desconocida'))
    else:
        df['raza_cod'] = 0
        
    if 'intensidad_celo' in df.columns:
        df['intensidad_cod'] = le_intensidad.fit_transform(df['intensidad_celo'].fillna('media'))
    else:
        df['intensidad_cod'] = 0
        
    if 'tipo_inseminacion' in df.columns:
        df['tipo_cod'] = le_tipo.fit_transform(df['tipo_inseminacion'].fillna('artificial'))
    else:
        df['tipo_cod'] = 0
        
    if 'toro' in df.columns:
        df['toro_cod'] = le_toro.fit_transform(df['toro'].fillna('desconocido'))
    else:
        df['toro_cod'] = 0
    
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
    """Preprocesa datos para RL-4 (sin cambios)"""
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


# ---------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------------------------

def modelo_esta_entrenado(codigo_mm):
    """Verifica si un modelo está entrenado (archivo .pkl existe)"""
    return os.path.exists(obtener_ruta_modelo(codigo_mm))


def obtener_metricas_modelo(codigo_mm):
    """Obtiene las métricas de un modelo desde la base de datos"""
    from Aplicaciones.Gestion.models import ModeloML
    
    try:
        modelo = ModeloML.objects.get(codigo_mm=codigo_mm)
        return {
            'exito': True,
            'nombre': modelo.nombre_mm,
            'tipo': modelo.tipo_modelo_mm,
            'modulo': modelo.modulo_aplicacion_mm,
            'metrica': modelo.metrica_principal_mm,
            'valor': float(modelo.valor_metrica_mm) if modelo.valor_metrica_mm else None,
            'fecha_entrenamiento': modelo.fecha_entrenamiento_mm,
            'activo': modelo.activo_mm,
            'archivo': modelo.archivo_modelo_mm
        }
    except ModeloML.DoesNotExist:
        return {
            'exito': False,
            'mensaje': f'Modelo {codigo_mm} no encontrado en la base de datos'
        }


def reentrenar_modelo(codigo_mm):
    """Reentrena un modelo usando los datos más recientes"""
    return entrenar_modelo(codigo_mm, guardar_db=True)


# ============================================================
# PREDICCIÓN CON MODELOS (ACTUALIZADO PARA AD-1 MEJORADO)
# ============================================================

def predecir(codigo_mm, datos_entrada):
    """
    Realiza una predicción con un modelo entrenado.
    """
    from django.db.models import Q, Avg
    from datetime import timedelta
    from Aplicaciones.Gestion.models import Animal, Racion, EventoSanitario, Parto, Ordeno, Secado, Celo, Aborto
    
    ruta = obtener_ruta_modelo(codigo_mm)
    
    if not os.path.exists(ruta):
        return {
            'exito': False,
            'mensaje': f'❌ Modelo {codigo_mm} no encontrado. Entrénelo primero.'
        }
    
    try:
        modelo_data = joblib.load(ruta)
        
        # Si es AD-1, el archivo contiene un diccionario con modelo + scaler
        if codigo_mm == 'AD-1' and isinstance(modelo_data, dict):
            modelo = modelo_data['modelo']
            scaler = modelo_data.get('scaler')
            features = modelo_data.get('features', [])
        else:
            modelo = modelo_data
            scaler = None
            features = []
            
    except Exception as e:
        return {
            'exito': False,
            'mensaje': f'❌ Error cargando modelo: {str(e)}'
        }
    
    # ============================================================
    # AD-1: Predicción de Litros de Leche (VERSIÓN MEJORADA)
    # ============================================================
    if codigo_mm == 'AD-1':
        try:
            if 'animal_id' in datos_entrada:
                animal = Animal.objects.get(id_an=datos_entrada['animal_id'])
                fecha = datos_entrada.get('fecha', date.today())
                
                # ==========================================
                # CALCULAR TODAS LAS VARIABLES
                # ==========================================
                
                # Edad
                edad = (fecha - animal.fecha_nacimiento_an).days if animal.fecha_nacimiento_an else 0
                edad_anios = round(edad / 365, 1)
                
                # Raza
                raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
                
                # Partos
                num_partos = Parto.objects.filter(fk_madre_pa=animal).count()
                ultimo_parto = Parto.objects.filter(
                    fk_madre_pa=animal,
                    fecha_pa__lt=fecha
                ).order_by('-fecha_pa').first()
                dias_desde_ultimo_parto = 0
                if ultimo_parto:
                    dias_desde_ultimo_parto = (fecha - ultimo_parto.fecha_pa).days
                
                # Días en lactancia
                secado = Secado.objects.filter(
                    fk_an=animal,
                    fecha_ultimo_ordeno_se__lt=fecha
                ).order_by('-fecha_ultimo_ordeno_se').first()
                dias_en_lactancia = dias_desde_ultimo_parto
                if secado and dias_desde_ultimo_parto > 0:
                    dias_en_lactancia = (fecha - secado.fecha_ultimo_ordeno_se).days
                
                # Historial de producción
                prom_7dias = Ordeno.objects.filter(
                    fk_an=animal,
                    fecha_or__gte=fecha - timedelta(days=7),
                    fecha_or__lt=fecha
                ).aggregate(prom=Avg('litros_or'))['prom'] or 0
                
                prom_30dias = Ordeno.objects.filter(
                    fk_an=animal,
                    fecha_or__gte=fecha - timedelta(days=30),
                    fecha_or__lt=fecha
                ).aggregate(prom=Avg('litros_or'))['prom'] or 0
                
                produccion_acumulada = Ordeno.objects.filter(
                    fk_an=animal,
                    fecha_or__lt=fecha
                ).aggregate(total=Sum('litros_or'))['total'] or 0
                
                total_ordenos = Ordeno.objects.filter(
                    fk_an=animal,
                    fecha_or__lt=fecha
                ).count()
                
                max_produccion = Ordeno.objects.filter(
                    fk_an=animal,
                    fecha_or__lt=fecha
                ).aggregate(max=Max('litros_or'))['max'] or 0
                
                # Alimentación
                racion = Racion.objects.filter(
                    fk_an=animal,
                    fecha_inicio_ra__lte=fecha
                ).filter(
                    Q(fecha_fin_ra__gte=fecha) | Q(fecha_fin_ra__isnull=True)
                ).first()
                
                cantidad_consumida = float(racion.cantidad_consumida_kg_ra or 0) if racion else 0
                cantidad_ofrecida = float(racion.cantidad_ofrecida_kg_ra or 0) if racion else 0
                
                eficiencia = 0
                if cantidad_consumida > 0:
                    # Usar el promedio_7dias como estimación de producción actual
                    produccion_estimada = prom_7dias if prom_7dias > 0 else 20
                    eficiencia = float(float(produccion_estimada) / float(cantidad_consumida)) if cantidad_consumida > 0 else 0
                
                # Estado sanitario
                tiene_evt = EventoSanitario.objects.filter(
                    fk_an=animal,
                    fecha_ejecutada_es__gte=fecha - timedelta(days=15)
                ).exists()
                
                num_evt_san_30 = EventoSanitario.objects.filter(
                    fk_an=animal,
                    fecha_ejecutada_es__gte=fecha - timedelta(days=30)
                ).count()
                
                # Variables de tiempo
                mes = fecha.month
                dia_semana = fecha.isoweekday()
                
                if mes in [12, 1, 2]:
                    temporada = 'invierno'
                elif mes in [3, 4, 5]:
                    temporada = 'primavera'
                elif mes in [6, 7, 8]:
                    temporada = 'verano'
                else:
                    temporada = 'otoño'
                
                # Datos del ordeño
                temp_ambiental = float(datos_entrada.get('temp_ambiental', 0))
                temp_leche = float(datos_entrada.get('temp_leche', 0))
                concentrado_kg = float(datos_entrada.get('concentrado_kg', 0))
                diff_temp = temp_ambiental - temp_leche if temp_ambiental and temp_leche else 0
                
                # Datos del potrero
                potrero = animal.fk_potrero_an
                potrero_nombre = potrero.nombre_po if potrero else 'sin_potrero'
                hectareas_potrero = float(potrero.hectareas_po or 0) if potrero else 0
                
                # ==========================================
                # CODIFICAR CATEGÓRICAS
                # ==========================================
                
                # Usar los encoders guardados
                if 'raza_encoder' in modelo_data:
                    try:
                        raza_cod = modelo_data['raza_encoder'].transform([raza])[0]
                    except:
                        raza_cod = 0
                else:
                    raza_cod = hash(raza) % 100
                
                if 'temporada_encoder' in modelo_data:
                    try:
                        temporada_cod = modelo_data['temporada_encoder'].transform([temporada])[0]
                    except:
                        temporada_cod = 0
                else:
                    temporada_cod = hash(temporada) % 100
                
                if 'potrero_encoder' in modelo_data:
                    try:
                        potrero_cod = modelo_data['potrero_encoder'].transform([potrero_nombre])[0]
                    except:
                        potrero_cod = 0
                else:
                    potrero_cod = hash(potrero_nombre) % 100
                
                # ==========================================
                # CONSTRUIR ARRAY DE ENTRADA
                # ==========================================
                
                X = np.array([[
                    edad,
                    edad_anios,
                    raza_cod,
                    float(animal.peso_actual_kg_an or 0),
                    float(animal.condicion_corporal_an or 0),
                    num_partos,
                    dias_desde_ultimo_parto,
                    dias_en_lactancia,
                    float(prom_7dias),
                    float(prom_30dias),
                    float(produccion_acumulada),
                    total_ordenos,
                    float(max_produccion),
                    cantidad_consumida,
                    cantidad_ofrecida,
                    eficiencia,
                    # ratio_consumo_produccion
                    float(float(cantidad_consumida) / float(prom_7dias if prom_7dias > 0 else 1)),
                    # pct_consumo
                    (float(float(cantidad_consumida) / float(cantidad_ofrecida)) * 100) if cantidad_ofrecida > 0 else 0,
                    1 if tiene_evt else 0,
                    num_evt_san_30,
                    mes,
                    dia_semana,
                    temporada_cod,
                    potrero_cod,
                    hectareas_potrero,
                    temp_ambiental,
                    temp_leche,
                    concentrado_kg,
                    diff_temp
                ]])
                
                # Escalar si hay scaler
                if scaler is not None:
                    X = scaler.transform(X)
                
                pred = modelo.predict(X)[0]
                return {
                    'exito': True,
                    'codigo': codigo_mm,
                    'prediccion': round(float(pred), 2),
                    'unidad': 'litros',
                    'interpretacion': f'Producción estimada: {round(float(pred), 2)} litros de leche'
                }
            else:
                return {
                    'exito': False,
                    'mensaje': '❌ Para AD-1 mejorado se requiere animal_id'
                }
                
        except Exception as e:
            return {'exito': False, 'mensaje': f'❌ Error en predicción AD-1: {str(e)}'}
    
    # ============================================================
    # AD-2: Predicción de Preñez
    # ============================================================
    elif codigo_mm == 'AD-2':
        try:
            if 'animal_id' in datos_entrada:
                animal = Animal.objects.get(id_an=datos_entrada['animal_id'])
                fecha = datos_entrada.get('fecha_inseminacion', date.today())
                
                edad = (fecha - animal.fecha_nacimiento_an).days if animal.fecha_nacimiento_an else 0
                num_partos = Parto.objects.filter(fk_madre_pa=animal).count()
                abortos = Aborto.objects.filter(fk_an=animal).count()
                
                prom_prod = Ordeno.objects.filter(
                    fk_an=animal,
                    fecha_or__gte=fecha - timedelta(days=7)
                ).aggregate(prom=Avg('litros_or'))['prom'] or 0
                
                celo = Celo.objects.filter(
                    fk_an=animal,
                    fecha_observacion_ce__lte=fecha
                ).order_by('-fecha_observacion_ce').first()
                
                raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
                
                X = np.array([[
                    edad,
                    num_partos,
                    hash(raza) % 100,
                    float(datos_entrada.get('condicion_corporal', animal.condicion_corporal_an or 0)),
                    float(prom_prod),
                    hash(datos_entrada.get('intensidad_celo', celo.intensidad_ce if celo else 'media')) % 100,
                    float(datos_entrada.get('duracion_celo_horas', celo.duracion_aproximada_horas_ce if celo else 12)),
                    hash(datos_entrada.get('tipo_inseminacion', 'artificial')) % 100,
                    hash(datos_entrada.get('toro', 'desconocido')) % 100,
                    abortos,
                    float(datos_entrada.get('dias_desde_inseminacion', 0))
                ]])
            else:
                X = np.array([[
                    float(datos_entrada.get('edad_dias', 0)),
                    float(datos_entrada.get('num_partos', 0)),
                    hash(datos_entrada.get('raza', 'desconocida')) % 100,
                    float(datos_entrada.get('condicion_corporal', 0)),
                    float(datos_entrada.get('produccion_leche', 0)),
                    hash(datos_entrada.get('intensidad_celo', 'media')) % 100,
                    float(datos_entrada.get('duracion_celo_horas', 12)),
                    hash(datos_entrada.get('tipo_inseminacion', 'artificial')) % 100,
                    hash(datos_entrada.get('toro', 'desconocido')) % 100,
                    float(datos_entrada.get('historial_abortos', 0)),
                    float(datos_entrada.get('dias_desde_inseminacion', 0))
                ]])
            
            pred = modelo.predict(X)[0]
            prob = modelo.predict_proba(X)[0] if hasattr(modelo, 'predict_proba') else [0.5, 0.5]
            resultado = 'PREÑADA' if pred == 1 else 'NO PREÑADA'
            
            return {
                'exito': True,
                'codigo': codigo_mm,
                'prediccion': resultado,
                'probabilidad': round(float(max(prob)), 4),
                'unidad': 'clase',
                'interpretacion': f'{resultado} (confianza: {round(float(max(prob)) * 100, 1)}%)'
            }
        except Exception as e:
            return {'exito': False, 'mensaje': f'❌ Error en predicción AD-2: {str(e)}'}
    
    # ============================================================
    # RL-4: Predicción de Calidad de Leche
    # ============================================================
    elif codigo_mm == 'RL-4':
        try:
            X = np.array([[
                float(datos_entrada.get('grasa_pct', 0)),
                float(datos_entrada.get('proteina_pct', 0)),
                float(datos_entrada.get('ccs', 0)),
                float(datos_entrada.get('ufc', 0))
            ]])
            
            pred = modelo.predict(X)[0]
            prob = modelo.predict_proba(X)[0] if hasattr(modelo, 'predict_proba') else [0.5, 0.5]
            resultado = 'APTO' if pred == 1 else 'NO APTO'
            
            return {
                'exito': True,
                'codigo': codigo_mm,
                'prediccion': resultado,
                'probabilidad': round(float(max(prob)), 4),
                'unidad': 'clase',
                'interpretacion': f'Calidad: {resultado} (confianza: {round(float(max(prob)) * 100, 1)}%)'
            }
        except Exception as e:
            return {'exito': False, 'mensaje': f'❌ Error en predicción RL-4: {str(e)}'}
    
    else:
        return {
            'exito': False,
            'mensaje': f'❌ Predicción para {codigo_mm} no implementada'
        }