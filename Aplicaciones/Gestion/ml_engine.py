# ============================================================
# ml_engine.py - Motor de Machine Learning para GanadoSWG
# VERSIÓN 2.0 - SOLO DATOS REALES
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
from sklearn.preprocessing import LabelEncoder
from django.conf import settings
from django.db.models import Avg, Q, Count, Sum

# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def obtener_ruta_modelo(codigo_mm):
    """Obtiene la ruta donde se guarda el archivo .pkl del modelo"""
    base = os.path.join(settings.BASE_DIR, 'media', 'ml')
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f'{codigo_mm}.pkl')


# ---------------------------------------------------------------------------
# OBTENCIÓN DE DATOS REALES
# ---------------------------------------------------------------------------

def obtener_datos_reales_ad1():
    """
    Obtiene datos reales de la base de datos para AD-1.
    """
    from .models import Ordeno, Animal, Racion, EventoSanitario, Parto
    
    print(f"[ML] Obteniendo datos reales para AD-1 de tu BDD...")
    
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
    
    if not ordenos:
        print(f"[ML] ERROR: No hay datos en la tabla Ordeno para entrenar AD-1")
        return None
    
    datos = []
    for o in ordenos:
        animal = o.fk_an
        if not animal:
            continue
            
        try:
            # 1. Edad en días
            edad = 0
            if animal.fecha_nacimiento_an:
                edad = (o.fecha_or - animal.fecha_nacimiento_an).days
            
            # 2. Número de partos previos
            num_partos = Parto.objects.filter(
                fk_madre_pa=animal,
                fecha_pa__lt=o.fecha_or
            ).count()
            
            # 3. Producción promedio últimos 7 días
            fecha_inicio = o.fecha_or - timedelta(days=7)
            prom_7dias = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__gte=fecha_inicio,
                fecha_or__lt=o.fecha_or
            ).aggregate(prom=Avg('litros_or'))['prom'] or 0
            
            # 4. Ración del día
            racion = Racion.objects.filter(
                fk_an=animal,
                fecha_inicio_ra__lte=o.fecha_or
            ).filter(
                Q(fecha_fin_ra__gte=o.fecha_or) | Q(fecha_fin_ra__isnull=True)
            ).first()
            
            cantidad_consumida = float(racion.cantidad_consumida_kg_ra or 0) if racion else 0
            cantidad_ofrecida = float(racion.cantidad_ofrecida_kg_ra or 0) if racion else 0
            
            # 5. Evento sanitario reciente (últimos 15 días)
            tiene_evt_san = EventoSanitario.objects.filter(
                fk_an=animal,
                fecha_ejecutada_es__gte=o.fecha_or - timedelta(days=15)
            ).exists()
            
            # 6. Raza
            raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
            
            # 7. Peso
            peso = float(animal.peso_actual_kg_an or 0)
            
            # 8. Condición corporal
            condicion = float(animal.condicion_corporal_an or 0)
            
            datos.append({
                'edad_dias': edad,
                'raza': raza,
                'peso_kg': peso,
                'condicion_corporal': condicion,
                'cantidad_consumida': cantidad_consumida,
                'cantidad_ofrecida': cantidad_ofrecida,
                'promedio_7dias': float(prom_7dias),
                'temp_ambiental': float(o.temperatura_ambiental_or or 0),
                'temp_leche': float(o.temperatura_leche_or or 0),
                'num_partos': num_partos,
                'estado_sanitario': 1 if tiene_evt_san else 0,
                'litros': float(o.litros_or)
            })
        except Exception as e:
            print(f"[ML] Error en ordeño {o.id_or}: {e}")
            continue
    
    df = pd.DataFrame(datos)
    print(f"[ML] Datos reales AD-1 obtenidos: {len(df)} registros")
    
    if len(df) < 10:
        print(f"[ML] ERROR: Solo {len(df)} registros. Necesitas al menos 10 para entrenar.")
        return None
    
    return df


def obtener_datos_reales_ad2():
    """
    Obtiene datos reales de la base de datos para AD-2.
    """
    from .models import Inseminacion, Animal, Celo, Parto, Aborto, Ordeno
    
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
            # 1. Edad en días
            edad = 0
            if animal.fecha_nacimiento_an:
                edad = (ins.fecha_in - animal.fecha_nacimiento_an).days
            
            # 2. Número de partos previos
            num_partos = Parto.objects.filter(fk_madre_pa=animal).count()
            
            # 3. Abortos previos
            abortos = Aborto.objects.filter(fk_an=animal).count()
            
            # 4. Producción promedio (últimos 7 días antes de inseminación)
            fecha_inicio = ins.fecha_in - timedelta(days=7)
            produccion = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__gte=fecha_inicio,
                fecha_or__lt=ins.fecha_in
            ).aggregate(prom=Avg('litros_or'))['prom'] or 0
            
            # 5. Celo más cercano
            celo = Celo.objects.filter(
                fk_an=animal,
                fecha_observacion_ce__lte=ins.fecha_in
            ).order_by('-fecha_observacion_ce').first()
            
            # 6. Raza
            raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
            
            # 7. Toro
            toro = ins.fk_toro_in.codigo_an if ins.fk_toro_in else 'desconocido'
            
            # 8. Tipo de inseminación
            tipo = ins.tipo_inseminacion_in or 'artificial'
            
            # 9. Días desde inseminación
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
    """
    Obtiene datos reales de la base de datos para RL-4.
    """
    from .models import CalidadLeche
    
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
            # Si el campo ufc_cl existe, úsalo, si no, usa 0
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


# ---------------------------------------------------------------------------
# PREPROCESAMIENTO DE DATOS
# ---------------------------------------------------------------------------

def preprocesar_datos_ad1(df):
    """Preprocesa datos para AD-1"""
    if df is None or df.empty:
        return None, None, None
    
    df = df.copy()
    
    # Codificar raza
    if 'raza' in df.columns:
        le = LabelEncoder()
        df['raza_cod'] = le.fit_transform(df['raza'].fillna('desconocida'))
    else:
        df['raza_cod'] = 0
    
    # Características para el modelo
    features = [
        'edad_dias',
        'raza_cod',
        'peso_kg',
        'condicion_corporal',
        'cantidad_consumida',
        'cantidad_ofrecida',
        'promedio_7dias',
        'temp_ambiental',
        'temp_leche',
        'num_partos',
        'estado_sanitario'
    ]
    
    for col in features:
        if col not in df.columns:
            df[col] = 0
    
    X = df[features].fillna(0).values
    y = df['litros'].values
    
    return X, y, le if 'raza' in df.columns else None


def preprocesar_datos_ad2(df):
    """Preprocesa datos para AD-2"""
    if df is None or df.empty:
        return None, None, None
    
    df = df.copy()
    
    # Codificar variables categóricas
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
    
    # Características para el modelo
    features = [
        'edad_dias',
        'num_partos',
        'raza_cod',
        'condicion_corporal',
        'produccion_leche',
        'intensidad_cod',
        'duracion_celo_horas',
        'tipo_cod',
        'toro_cod',
        'historial_abortos',
        'dias_desde_inseminacion'
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
    """Preprocesa datos para RL-4"""
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
# ENTRENAMIENTO DE MODELOS
# ---------------------------------------------------------------------------

def entrenar_modelo(codigo_mm, guardar_db=True):
    """
    Entrena un modelo de Machine Learning SOLO CON DATOS REALES.
    """
    from .models import ModeloML
    
    print(f"[ML] Iniciando entrenamiento de {codigo_mm} con datos reales...")
    
    # -----------------------------------------------------------------------
    # AD-1: Predicción de Litros de Leche
    # -----------------------------------------------------------------------
    if codigo_mm == 'AD-1':
        df = obtener_datos_reales_ad1()
        
        if df is None or len(df) < 10:
            return {
                'exito': False,
                'mensaje': f'❌ No hay suficientes datos reales para {codigo_mm}. '
                           f'Encontrados: {len(df) if df is not None else 0} registros. '
                           f'Necesitas al menos 10 registros en la tabla Ordeno.'
            }
        
        X, y, _ = preprocesar_datos_ad1(df)
        if X is None or len(X) < 10:
            return {'exito': False, 'mensaje': f'❌ Error en preprocesamiento de {codigo_mm}'}
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        modelo = DecisionTreeRegressor(
            max_depth=8,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42
        )
        modelo.fit(X_train, y_train)
        
        y_pred = modelo.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        rmse = np.sqrt(mse)
        
        ruta = obtener_ruta_modelo(codigo_mm)
        joblib.dump(modelo, ruta)
        
        metricas = {
            'exito': True,
            'codigo': codigo_mm,
            'ruta_modelo': ruta,
            'mse': round(mse, 4),
            'rmse': round(rmse, 4),
            'r2': round(r2, 4),
            'registros': len(df),
            'entrenamiento': len(X_train),
            'prueba': len(X_test),
            'fuente': 'datos_reales',
            'variables': ['edad_dias', 'raza', 'peso_kg', 'condicion_corporal', 
                         'cantidad_consumida', 'cantidad_ofrecida', 'promedio_7dias',
                         'temp_ambiental', 'temp_leche', 'num_partos', 'estado_sanitario']
        }
    
    # -----------------------------------------------------------------------
    # AD-2: Clasificación de Preñez
    # -----------------------------------------------------------------------
    elif codigo_mm == 'AD-2':
        df = obtener_datos_reales_ad2()
        
        if df is None or len(df) < 10:
            return {
                'exito': False,
                'mensaje': f'❌ No hay suficientes datos reales para {codigo_mm}. '
                           f'Encontrados: {len(df) if df is not None else 0} registros. '
                           f'Necesitas al menos 10 inseminaciones con resultado definido.'
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
                           f'Encontrados: {len(df) if df is not None else 0} registros. '
                           f'Necesitas al menos 10 registros en CalidadLeche.'
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
                tipo_modelo = 'decision_tree_regressor'
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
                        'AD-1': 'Predicción de Litros de Leche (v2 - Datos Reales)',
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


# ---------------------------------------------------------------------------
# PREDICCIÓN CON MODELOS
# ---------------------------------------------------------------------------

def predecir(codigo_mm, datos_entrada):
    """
    Realiza una predicción con un modelo entrenado.
    """
    from django.db.models import Q, Avg
    from datetime import timedelta
    
    ruta = obtener_ruta_modelo(codigo_mm)
    
    if not os.path.exists(ruta):
        return {
            'exito': False,
            'mensaje': f'❌ Modelo {codigo_mm} no encontrado. Entrénelo primero.'
        }
    
    try:
        modelo = joblib.load(ruta)
    except Exception as e:
        return {
            'exito': False,
            'mensaje': f'❌ Error cargando modelo: {str(e)}'
        }
    
    # ============================================================
    # AD-1: Predicción de Litros de Leche
    # ============================================================
    if codigo_mm == 'AD-1':
        try:
            # Si viene animal_id, obtener datos de la BDD
            if 'animal_id' in datos_entrada:
                from .models import Animal, Racion, EventoSanitario, Parto, Ordeno
                
                animal = Animal.objects.get(id_an=datos_entrada['animal_id'])
                fecha = datos_entrada.get('fecha', date.today())
                
                # Edad en días
                edad = (fecha - animal.fecha_nacimiento_an).days if animal.fecha_nacimiento_an else 0
                
                # Número de partos previos
                num_partos = Parto.objects.filter(fk_madre_pa=animal).count()
                
                # Promedio últimos 7 días
                fecha_inicio = fecha - timedelta(days=7)
                prom_7dias = Ordeno.objects.filter(
                    fk_an=animal,
                    fecha_or__gte=fecha_inicio,
                    fecha_or__lt=fecha
                ).aggregate(prom=Avg('litros_or'))['prom'] or 0
                
                # Ración del día
                racion = Racion.objects.filter(
                    fk_an=animal,
                    fecha_inicio_ra__lte=fecha
                ).filter(
                    Q(fecha_fin_ra__gte=fecha) | Q(fecha_fin_ra__isnull=True)
                ).first()
                
                # Estado sanitario (eventos en últimos 15 días)
                tiene_evt = EventoSanitario.objects.filter(
                    fk_an=animal,
                    fecha_ejecutada_es__gte=fecha - timedelta(days=15)
                ).exists()
                
                # Raza
                raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
                
                # Construir array de entrada
                X = np.array([[
                    edad,
                    hash(raza) % 100,
                    float(animal.peso_actual_kg_an or 0),
                    float(animal.condicion_corporal_an or 0),
                    float(racion.cantidad_consumida_kg_ra or 0) if racion else 0,
                    float(racion.cantidad_ofrecida_kg_ra or 0) if racion else 0,
                    float(prom_7dias),
                    float(datos_entrada.get('temp_ambiental', 0)),
                    float(datos_entrada.get('temp_leche', 0)),
                    num_partos,
                    1 if tiene_evt else 0
                ]])
            else:
                # Datos directos del formulario
                X = np.array([[
                    float(datos_entrada.get('edad_dias', 0)),
                    hash(datos_entrada.get('raza', 'desconocida')) % 100,
                    float(datos_entrada.get('peso_kg', 0)),
                    float(datos_entrada.get('condicion_corporal', 0)),
                    float(datos_entrada.get('cantidad_consumida', 0)),
                    float(datos_entrada.get('cantidad_ofrecida', 0)),
                    float(datos_entrada.get('promedio_7dias', 0)),
                    float(datos_entrada.get('temp_ambiental', 0)),
                    float(datos_entrada.get('temp_leche', 0)),
                    float(datos_entrada.get('num_partos', 0)),
                    float(datos_entrada.get('estado_sanitario', 0))
                ]])
            
            pred = modelo.predict(X)[0]
            return {
                'exito': True,
                'codigo': codigo_mm,
                'prediccion': round(float(pred), 2),
                'unidad': 'litros',
                'interpretacion': f'Producción estimada: {round(float(pred), 2)} litros de leche'
            }
        except Exception as e:
            return {'exito': False, 'mensaje': f'❌ Error en predicción AD-1: {str(e)}'}
    
    # ============================================================
    # AD-2: Predicción de Preñez
    # ============================================================
    elif codigo_mm == 'AD-2':
        try:
            if 'animal_id' in datos_entrada:
                from .models import Animal, Celo, Parto, Aborto, Ordeno
                
                animal = Animal.objects.get(id_an=datos_entrada['animal_id'])
                fecha = datos_entrada.get('fecha_inseminacion', date.today())
                
                # Edad en días
                edad = (fecha - animal.fecha_nacimiento_an).days if animal.fecha_nacimiento_an else 0
                
                # Número de partos previos
                num_partos = Parto.objects.filter(fk_madre_pa=animal).count()
                
                # Abortos previos
                abortos = Aborto.objects.filter(fk_an=animal).count()
                
                # Producción promedio (últimos 7 días)
                prom_prod = Ordeno.objects.filter(
                    fk_an=animal,
                    fecha_or__gte=fecha - timedelta(days=7)
                ).aggregate(prom=Avg('litros_or'))['prom'] or 0
                
                # Celo más reciente
                celo = Celo.objects.filter(
                    fk_an=animal,
                    fecha_observacion_ce__lte=fecha
                ).order_by('-fecha_observacion_ce').first()
                
                # Raza
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


# ---------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------------------------

def modelo_esta_entrenado(codigo_mm):
    """Verifica si un modelo está entrenado (archivo .pkl existe)"""
    return os.path.exists(obtener_ruta_modelo(codigo_mm))


def obtener_metricas_modelo(codigo_mm):
    """Obtiene las métricas de un modelo desde la base de datos"""
    from .models import ModeloML
    
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