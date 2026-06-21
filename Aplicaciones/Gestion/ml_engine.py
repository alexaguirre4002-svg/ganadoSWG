# Aplicaciones/Gestion/ml_engine.py
# Motor de Machine Learning para ganadoSWG
# AD-1: Arbol de Decision Regresion -> Prediccion de Litros de Leche
# AD-2: Arbol de Decision Clasificacion -> Preñada/No Preñada
# RL-4: Regresion Logistica -> Calidad de Leche (Apto/No Apto)

import os
import random
from datetime import datetime, date
import joblib
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, accuracy_score, r2_score
from django.conf import settings

# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def obtener_ruta_modelo(codigo_mm):
    base = os.path.join(settings.BASE_DIR, 'media', 'ml')
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f'{codigo_mm}.pkl')

# ---------------------------------------------------------------------------
# DATOS DE EJEMPLO
# Solo se usan cuando NO hay suficientes datos reales en la BD (menos de 10)
# NO se guardan en la base de datos, son solo numeros temporales en memoria
# ---------------------------------------------------------------------------

def generar_datos_ejemplo_ad1(n=100):
    """
    Genera datos de ejemplo para AD-1 cuando no hay suficientes ordeños reales.
    Simula: temperatura_ambiental, cantidad_concentrado_kg, temperatura_leche -> litros
    """
    datos = []
    for _ in range(n):
        temp_amb = round(random.uniform(18.0, 35.0), 2)
        conc_kg = round(random.uniform(2.0, 8.0), 2)
        temp_leche = round(random.uniform(32.0, 39.0), 2)
        litros = (conc_kg * 2.5) - (abs(temp_amb - 25) * 0.3) + random.uniform(-1.5, 1.5)
        litros = round(max(0.5, litros), 2)
        datos.append({
            'temperatura_ambiental': temp_amb,
            'cantidad_concentrado_kg': conc_kg,
            'temperatura_leche': temp_leche,
            'litros': litros
        })
    return pd.DataFrame(datos)


def generar_datos_ejemplo_ad2(n=100):
    """
    Genera datos de ejemplo para AD-2 cuando no hay suficientes inseminaciones reales.
    Simula: dias_desde_inseminacion, condicion_corporal, dia_ciclo -> preñada (1/0)

    NOTA: Estos datos NO tienen claves foraneas, son solo numeros para entrenar
    el modelo matematico. El modelo aprende patrones, no identidades de animales.
    """
    datos = []
    for _ in range(n):
        dias = random.randint(20, 90)
        condicion = round(random.uniform(1.0, 5.0), 1)
        dia_ciclo = random.randint(1, 21)
        prob = 0.4
        if dias > 45:
            prob += 0.25
        if condicion >= 3.0:
            prob += 0.20
        if 10 <= dia_ciclo <= 18:
            prob += 0.15
        prenada = 1 if random.random() < prob else 0
        datos.append({
            'dias_desde_inseminacion': dias,
            'condicion_corporal': condicion,
            'dia_ciclo': dia_ciclo,
            'prenada': prenada
        })
    return pd.DataFrame(datos)


def generar_datos_ejemplo_rl4(n=100):
    """
    Genera datos de ejemplo para RL-4 cuando no hay suficientes registros de calidad reales.
    Simula: grasa_pct, proteina_pct, ccs -> apto (1/0)
    """
    datos = []
    for _ in range(n):
        grasa = round(random.uniform(2.5, 5.0), 2)
        proteina = round(random.uniform(2.8, 4.0), 2)
        cel_som = random.randint(100000, 800000)
        apto = 1
        if grasa < 3.0:
            apto = 0
        if cel_som > 500000:
            apto = 0
        if random.random() < 0.1:
            apto = 1 - apto
        datos.append({
            'grasa': grasa,
            'proteina': proteina,
            'celulas_somaticas': cel_som,
            'apto': apto
        })
    return pd.DataFrame(datos)

# ---------------------------------------------------------------------------
# ENTRENAMIENTO
# ---------------------------------------------------------------------------

def entrenar_modelo(codigo_mm, usar_datos_ejemplo=False, guardar_db=True):
    from .models import ModeloML

    # -----------------------------------------------------------------------
    # AD-1: Prediccion de Litros de Leche
    # Fuente real: tabla ordenos
    # Campos: temperatura_ambiental_or, cantidad_concentrado_kg_or,
    #         temperatura_leche_or -> litros_or
    # -----------------------------------------------------------------------
    if codigo_mm == 'AD-1':
        from .models import Ordeno
        queryset = Ordeno.objects.filter(
            temperatura_ambiental_or__isnull=False,
            cantidad_concentrado_kg_or__isnull=False,
            temperatura_leche_or__isnull=False,
            litros_or__isnull=False
        ).values(
            'temperatura_ambiental_or',
            'cantidad_concentrado_kg_or',
            'temperatura_leche_or',
            'litros_or'
        )
        df = pd.DataFrame(list(queryset))

        if df.empty or len(df) < 10:
            if usar_datos_ejemplo:
                df = generar_datos_ejemplo_ad1(n=100)
                df.rename(columns={
                    'temperatura_ambiental': 'temperatura_ambiental_or',
                    'cantidad_concentrado_kg': 'cantidad_concentrado_kg_or',
                    'temperatura_leche': 'temperatura_leche_or',
                    'litros': 'litros_or'
                }, inplace=True)
            else:
                return {
                    'exito': False,
                    'mensaje': f'No hay datos reales suficientes para {codigo_mm}. '
                               f'Encontrados: {len(df)}. Use usar_datos_ejemplo=True o ingrese mas ordenos.'
                }

        X = df[['temperatura_ambiental_or', 'cantidad_concentrado_kg_or', 'temperatura_leche_or']].values
        y = df['litros_or'].values
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        modelo = DecisionTreeRegressor(max_depth=5, random_state=42)
        modelo.fit(X_train, y_train)
        y_pred = modelo.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        rmse = np.sqrt(mse)
        ruta_modelo = obtener_ruta_modelo(codigo_mm)
        joblib.dump(modelo, ruta_modelo)
        metricas = {
            'exito': True,
            'codigo': codigo_mm,
            'ruta_modelo': ruta_modelo,
            'mse': round(mse, 4),
            'rmse': round(rmse, 4),
            'r2': round(r2, 4),
            'registros': len(df),
            'entrenamiento': len(X_train),
            'prueba': len(X_test),
            'fuente': 'datos_reales' if len(df) >= 10 else 'datos_ejemplo'
        }

    # -----------------------------------------------------------------------
    # AD-2: Clasificacion Preñada / No Preñada
    # Fuente real: tabla inseminaciones
    # Campos usados:
    #   - dias desde la inseminacion hasta hoy (calculado)
    #   - condicion_corporal_in (condicion corporal al momento de inseminar)
    #   - dia_ciclo_in (dia del ciclo en que se insemino)
    # Resultado: resultado_in ('prenada' = 1, 'no_prenada' = 0)
    #
    # IMPORTANTE: Solo se usan inseminaciones con resultado definido
    # ('prenada' o 'no_prenada'), no las 'pendiente'
    # -----------------------------------------------------------------------
    elif codigo_mm == 'AD-2':
        from .models import Inseminacion
        queryset = Inseminacion.objects.filter(
            resultado_in__in=['preñada', 'no_preñada'],   # solo con resultado conocido
            condicion_corporal_in__isnull=False,           # que tengan condicion corporal
            fecha_in__isnull=False                         # que tengan fecha
        ).values(
            'fecha_in',
            'condicion_corporal_in',
            'dia_ciclo_in',
            'resultado_in'
        )
        df = pd.DataFrame(list(queryset))

        if df.empty or len(df) < 10:
            if usar_datos_ejemplo:
                df = generar_datos_ejemplo_ad2(n=100)
                # Renombrar para que coincida con el resto del flujo
                df.rename(columns={
                    'dias_desde_inseminacion': 'dias',
                    'condicion_corporal': 'condicion_corporal_in',
                    'dia_ciclo': 'dia_ciclo_in',
                    'prenada': 'resultado_num'
                }, inplace=True)
                # ya tiene resultado_num, saltar conversion
                X = df[['dias', 'condicion_corporal_in', 'dia_ciclo_in']].values
                y = df['resultado_num'].values
            else:
                return {
                    'exito': False,
                    'mensaje': f'No hay datos reales suficientes para {codigo_mm}. '
                               f'Encontrados: {len(df)} inseminaciones con resultado definido. '
                               f'Necesita al menos 10. Use usar_datos_ejemplo=True o ingrese mas inseminaciones.'
                }
        else:
            # Calcular dias transcurridos desde la inseminacion hasta hoy
            hoy = date.today()
            df['dias'] = df['fecha_in'].apply(
                lambda f: (hoy - f).days if isinstance(f, date) else 0
            )
            # Convertir resultado a numero: prenada=1, no_prenada=0
            df['resultado_num'] = df['resultado_in'].apply(
                lambda x: 1 if str(x).lower() in ['preñada', 'prenada', '1'] else 0
            )
            # Rellenar dia_ciclo si es nulo con la mediana
            df['dia_ciclo_in'] = df['dia_ciclo_in'].fillna(df['dia_ciclo_in'].median()).fillna(14)

            X = df[['dias', 'condicion_corporal_in', 'dia_ciclo_in']].values
            y = df['resultado_num'].values

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        modelo = DecisionTreeClassifier(max_depth=5, random_state=42)
        modelo.fit(X_train, y_train)
        y_pred = modelo.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        ruta_modelo = obtener_ruta_modelo(codigo_mm)
        joblib.dump(modelo, ruta_modelo)
        metricas = {
            'exito': True,
            'codigo': codigo_mm,
            'ruta_modelo': ruta_modelo,
            'accuracy': round(acc, 4),
            'registros': len(df),
            'entrenamiento': len(X_train),
            'prueba': len(X_test),
            'fuente': 'datos_reales' if not df.empty and 'resultado_in' in df.columns else 'datos_ejemplo'
        }

    # -----------------------------------------------------------------------
    # RL-4: Calidad de Leche (Apto / No Apto)
    # Fuente real: tabla calidad_leche
    # Campos: grasa_pct_cl, proteina_pct_cl, ccs_cl -> resultado_cl
    # -----------------------------------------------------------------------
    elif codigo_mm == 'RL-4':
        from .models import CalidadLeche
        queryset = CalidadLeche.objects.filter(
            grasa_pct_cl__isnull=False,
            proteina_pct_cl__isnull=False,
            ccs_cl__isnull=False,
            resultado_cl__isnull=False
        ).exclude(
            resultado_cl='pendiente'   # solo registros con resultado definitivo
        ).values(
            'grasa_pct_cl',
            'proteina_pct_cl',
            'ccs_cl',
            'resultado_cl'
        )
        df = pd.DataFrame(list(queryset))

        if df.empty or len(df) < 10:
            if usar_datos_ejemplo:
                df = generar_datos_ejemplo_rl4(n=100)
                df.rename(columns={
                    'grasa': 'grasa_pct_cl',
                    'proteina': 'proteina_pct_cl',
                    'celulas_somaticas': 'ccs_cl',
                    'apto': 'resultado_num'
                }, inplace=True)
                X = df[['grasa_pct_cl', 'proteina_pct_cl', 'ccs_cl']].values
                y = df['resultado_num'].values
            else:
                return {
                    'exito': False,
                    'mensaje': f'No hay datos reales suficientes para {codigo_mm}. '
                               f'Encontrados: {len(df)}. Use usar_datos_ejemplo=True o ingrese mas registros de calidad.'
                }
        else:
            df['resultado_num'] = df['resultado_cl'].apply(
                lambda x: 1 if str(x).lower() in ['apto', '1', 'si', 'yes', 'true'] else 0
            )
            X = df[['grasa_pct_cl', 'proteina_pct_cl', 'ccs_cl']].values
            y = df['resultado_num'].values

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        modelo = LogisticRegression(max_iter=1000, random_state=42)
        modelo.fit(X_train, y_train)
        y_pred = modelo.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        ruta_modelo = obtener_ruta_modelo(codigo_mm)
        joblib.dump(modelo, ruta_modelo)
        metricas = {
            'exito': True,
            'codigo': codigo_mm,
            'ruta_modelo': ruta_modelo,
            'accuracy': round(acc, 4),
            'registros': len(df),
            'entrenamiento': len(X_train),
            'prueba': len(X_test),
            'fuente': 'datos_reales' if 'resultado_cl' in df.columns else 'datos_ejemplo'
        }

    else:
        return {
            'exito': False,
            'mensaje': f'Codigo {codigo_mm} aun no implementado. Implementados: AD-1, AD-2, RL-4.'
        }

    # -----------------------------------------------------------------------
    # Guardar resultado en tabla ModeloML
    # -----------------------------------------------------------------------
    if guardar_db:
        try:
            modelo_db, creado = ModeloML.objects.get_or_create(
                codigo_mm=codigo_mm,
                defaults={
                    'nombre_mm': {
                        'AD-1': 'Prediccion Litros de Leche',
                        'AD-2': 'Clasificacion Estado de Prenez',
                        'RL-4': 'Clasificacion Calidad de Leche'
                    }.get(codigo_mm, codigo_mm),
                    'tipo_modelo_mm': 'decision_tree_regressor' if codigo_mm == 'AD-1'
                                      else 'decision_tree_classifier' if codigo_mm == 'AD-2'
                                      else 'logistic_regression',
                    'modulo_aplicacion_mm': 'produccion_lactea' if codigo_mm == 'AD-1'
                                            else 'reproduccion' if codigo_mm == 'AD-2'
                                            else 'calidad_leche',
                    'activo_mm': True
                }
            )
            modelo_db.archivo_modelo_mm = metricas['ruta_modelo']
            modelo_db.fecha_entrenamiento_mm = datetime.now()
            modelo_db.valor_metrica_mm = metricas.get('r2', metricas.get('accuracy', 0))
            modelo_db.save()
            metricas['guardado_db'] = True
            metricas['id_modelo_db'] = modelo_db.id_mm
        except Exception as e:
            metricas['guardado_db'] = False
            metricas['error_db'] = str(e)

    return metricas

# ---------------------------------------------------------------------------
# PREDICCION
# ---------------------------------------------------------------------------

def predecir(codigo_mm, datos_entrada):
    ruta_modelo = obtener_ruta_modelo(codigo_mm)
    if not os.path.exists(ruta_modelo):
        return {
            'exito': False,
            'mensaje': f'Modelo {codigo_mm} no encontrado. Entrenelo primero: python manage.py entrenar_ml {codigo_mm}'
        }
    modelo = joblib.load(ruta_modelo)

    # -----------------------------------------------------------------------
    # AD-1: Predice litros de leche
    # Entrada: temperatura_ambiental, cantidad_concentrado_kg, temperatura_leche
    # -----------------------------------------------------------------------
    if codigo_mm == 'AD-1':
        X = np.array([[
            float(datos_entrada.get('temperatura_ambiental', 0)),
            float(datos_entrada.get('cantidad_concentrado_kg', 0)),
            float(datos_entrada.get('temperatura_leche', 0))
        ]])
        pred = modelo.predict(X)[0]
        return {
            'exito': True,
            'codigo': codigo_mm,
            'prediccion': round(float(pred), 2),
            'unidad': 'litros',
            'interpretacion': f'Produccion estimada: {round(float(pred), 2)} litros de leche.'
        }

    # -----------------------------------------------------------------------
    # AD-2: Predice si la vaca quedo prenada
    # Entrada: dias_desde_inseminacion, condicion_corporal, dia_ciclo
    #
    # NOTA: dias_desde_inseminacion es la diferencia entre hoy y la fecha
    # de inseminacion. condicion_corporal va de 1 a 5. dia_ciclo va de 1 a 21.
    # -----------------------------------------------------------------------
    elif codigo_mm == 'AD-2':
        X = np.array([[
            int(datos_entrada.get('dias_desde_inseminacion', 0)),
            float(datos_entrada.get('condicion_corporal', 3)),
            int(datos_entrada.get('dia_ciclo', 14))
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

    # -----------------------------------------------------------------------
    # RL-4: Predice si la leche es apta
    # Entrada: grasa_pct, proteina_pct, ccs
    # -----------------------------------------------------------------------
    elif codigo_mm == 'RL-4':
        X = np.array([[
            float(datos_entrada.get('grasa_pct', 0)),
            float(datos_entrada.get('proteina_pct', 0)),
            float(datos_entrada.get('ccs', 0))
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

    else:
        return {
            'exito': False,
            'mensaje': f'Prediccion para {codigo_mm} aun no implementada.'
        }

# ---------------------------------------------------------------------------
# AUXILIAR
# ---------------------------------------------------------------------------

def modelo_esta_entrenado(codigo_mm):
    """Retorna True si el archivo .pkl del modelo existe en disco."""
    return os.path.exists(obtener_ruta_modelo(codigo_mm))