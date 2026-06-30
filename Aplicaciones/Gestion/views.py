import base64
from decimal import Decimal,InvalidOperation
from django.db import transaction
import os
from django.contrib import messages
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from .models import Aborto, Animal, AsignacionPotrero, CalidadLeche, Celo, Costo, EntregaLeche, EventoSanitario, Ingreso, Inseminacion, InsumoAlimenticio, LogAuditoria, ModeloML, MovimientoAnimal, Ordeno, Parto, Pesaje, PrediccionML, Prenez, Racion, Raza, Potrero,ProductoVeterinario,Dieta, RegistroClinico, Secado, Usuario  
from django.db import IntegrityError
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from datetime import timedelta,date, datetime
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.hashers import make_password
import random,string
from django.core.files.storage import FileSystemStorage
from django.db.models import F, Count, Q, Sum, Avg, Max, Min
# ====== NUEVO: IMPORTS PARA CLOUDINARY ======
import cloudinary
import cloudinary.uploader
import cloudinary.api

def inicio(request):
    return render(request,'inicio.html')

# ==========================================
# Raza
# ==========================================
def listaraza(request):
    """
    Muestra el listado completo de razas con estadísticas.
    Incluye conteos por estado, tipo de producción y animales asociados.
    """
    raza_list = Raza.objects.all().annotate(
        total_animales=Count('animal')
    ).order_by('nombre_ra')
    
    # Estadísticas generales
    total_razas = raza_list.count()
    total_activas = raza_list.filter(activo_ra=True).count()
    total_inactivas = raza_list.filter(activo_ra=False).count()
    
    contexto = {
        'raza_list': raza_list,
        'total_razas': total_razas,
        'total_activas': total_activas,
        'total_inactivas': total_inactivas,
    }
    
    return render(request, 'catalogos/razas/lista_raza.html', contexto)


# ==========================================
# VISTA: NUEVA RAZA (formulario)
# ==========================================
def nuevaraza(request):
    """
    Muestra el formulario para registrar una nueva raza.
    """
    return render(request, 'catalogos/razas/nueva_raza.html')


# ==========================================
# VISTA: GUARDAR RAZA (procesar creación)
# ==========================================
def guardarraza(request):
    """
    Procesa el formulario de creación de una nueva raza.
    Valida UNIQUE en nombre_ra, CHECK constraint en tipo_produccion_ra,
    y registra auditoría.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevaraza/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Nombre (obligatorio, UNIQUE)
        nombre_ra = request.POST.get('txt_nombre_ra', '').strip()
        if not nombre_ra:
            messages.error(request, "El nombre de la raza es obligatorio")
            return redirect('/nuevaraza/')
        
        if len(nombre_ra) < 2:
            messages.error(request, "El nombre debe tener al menos 2 caracteres")
            return redirect('/nuevaraza/')
        
        if len(nombre_ra) > 100:
            messages.error(request, "El nombre no puede exceder 100 caracteres")
            return redirect('/nuevaraza/')
        
        # Validar UNIQUE
        if Raza.objects.filter(nombre_ra__iexact=nombre_ra).exists():
            messages.error(request, f"Ya existe una raza con el nombre '{nombre_ra}'")
            return redirect('/nuevaraza/')
        
        # Origen (opcional)
        origen_ra = request.POST.get('txt_origen_ra', '').strip()
        if origen_ra and len(origen_ra) > 100:
            messages.error(request, "El origen no puede exceder 100 caracteres")
            return redirect('/nuevaraza/')
        
        # Descripción (opcional)
        descripcion_ra = request.POST.get('txt_descripcion_ra', '').strip()
        if descripcion_ra and len(descripcion_ra) > 1000:
            messages.error(request, "La descripción no puede exceder 1000 caracteres")
            return redirect('/nuevaraza/')
        
        # Estado (default True)
        activo_ra = request.POST.get('chk_activo_ra') == '1'
        
        # ==========================================
        # CREAR RAZA
        # ==========================================
        nueva_raza = Raza.objects.create(
            nombre_ra=nombre_ra,
            origen_ra=origen_ra if origen_ra else None,
            descripcion_ra=descripcion_ra if descripcion_ra else None,
            activo_ra=activo_ra
        )
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'Raza',
            nueva_raza.id_ra,
            f'Se creó raza: {nombre_ra}'
        )
        
        messages.success(request, f"Raza '{nombre_ra}' registrada exitosamente")
        return redirect('/listaraza/')
        
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevaraza/')


# ==========================================
# VISTA: EDITAR RAZA (formulario)
# ==========================================
def editarraza(request, id_ra):
    """
    Muestra el formulario de edición con los datos precargados.
    Calcula animales asociados para control de integridad.
    """
    raza = get_object_or_404(Raza, id_ra=id_ra)
    
    # Contar animales asociados (integridad referencial)
    total_animales = Animal.objects.filter(fk_ra=raza).count()
    
    contexto = {
        'raza': raza,
        'total_animales': total_animales,
    }
    
    return render(request, 'catalogos/razas/editar_raza.html', contexto)


# ==========================================
# VISTA: PROCESAR EDICION RAZA
# ==========================================
def procesareditarraza(request):
    """
    Procesa el formulario de edición de una raza existente.
    Valida UNIQUE en nombre_ra (excluyendo la actual), CHECK constraint.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listaraza/')
    
    try:
        # Obtener raza existente
        id_ra = request.POST.get('id_ra')
        if not id_ra:
            messages.error(request, "ID de raza no proporcionado")
            return redirect('/listaraza/')
        
        raza = Raza.objects.get(id_ra=id_ra)
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Nombre (obligatorio, UNIQUE excluyendo actual)
        nombre_ra = request.POST.get('txt_nombre_ra', '').strip()
        if not nombre_ra:
            messages.error(request, "El nombre de la raza es obligatorio")
            return redirect(f'/editarraza/{id_ra}')
        
        if len(nombre_ra) < 2:
            messages.error(request, "El nombre debe tener al menos 2 caracteres")
            return redirect(f'/editarraza/{id_ra}')
        
        if len(nombre_ra) > 100:
            messages.error(request, "El nombre no puede exceder 100 caracteres")
            return redirect(f'/editarraza/{id_ra}')
        
        # Validar UNIQUE (excluyendo la raza actual)
        if Raza.objects.filter(nombre_ra__iexact=nombre_ra).exclude(id_ra=id_ra).exists():
            messages.error(request, f"Ya existe otra raza con el nombre '{nombre_ra}'")
            return redirect(f'/editarraza/{id_ra}')
              
        # Origen (opcional)
        origen_ra = request.POST.get('txt_origen_ra', '').strip()
        if origen_ra and len(origen_ra) > 100:
            messages.error(request, "El origen no puede exceder 100 caracteres")
            return redirect(f'/editarraza/{id_ra}')
        
        # Descripción (opcional)
        descripcion_ra = request.POST.get('txt_descripcion_ra', '').strip()
        if descripcion_ra and len(descripcion_ra) > 1000:
            messages.error(request, "La descripción no puede exceder 1000 caracteres")
            return redirect(f'/editarraza/{id_ra}')
        
        # Estado - AHORA LIBRE, sin restricción de animales asociados
        activo_ra = request.POST.get('chk_activo_ra') == '1'
        
        # ==========================================
        # ACTUALIZAR RAZA
        # ==========================================
        nombre_anterior = raza.nombre_ra 
        raza.nombre_ra = nombre_ra
        raza.origen_ra = origen_ra if origen_ra else None
        raza.descripcion_ra = descripcion_ra if descripcion_ra else None
        raza.activo_ra = activo_ra
        
        raza.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        cambios = []
        if nombre_anterior != nombre_ra:
            cambios.append(f"nombre: {nombre_anterior} → {nombre_ra}")
        
        descripcion_auditoria = f'Se editó raza #{id_ra}'
        if cambios:
            descripcion_auditoria += ': ' + ', '.join(cambios)
        
        guardar_auditoria(
            request,
            'editar',
            'Raza',
            raza.id_ra,
            descripcion_auditoria
        )
        
        messages.success(request, f"Raza '{nombre_ra}' actualizada exitosamente")
        return redirect('/listaraza/')
        
    except Raza.DoesNotExist:
        messages.error(request, "Raza no encontrada")
        return redirect('/listaraza/')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarraza/{id_ra}')


# ==========================================
# VISTA: ELIMINAR RAZA
# ==========================================
def eliminaraza(request, id_ra):
    """
    Elimina una raza del sistema.
    NO permite eliminar si tiene animales asociados (integridad referencial).
    Revierte el estado de animales si aplica (no aplica, bloqueo total).
    """
    raza = get_object_or_404(Raza, id_ra=id_ra)
    
    # Guardar datos antes de eliminar para auditoría
    id_raza = raza.id_ra
    nombre_raza = raza.nombre_ra
    
    # Verificar integridad referencial
    total_animales = Animal.objects.filter(fk_ra=raza).count()
    
    if total_animales > 0:
        messages.error(
            request, 
            f"No se puede eliminar la raza '{nombre_raza}' porque tiene {total_animales} animal(es) asociado(s). "
            f"Debe reasignar o eliminar los animales primero."
        )
        return redirect('/listaraza/')
    
    try:
        # ==========================================
        # ELIMINAR RAZA
        # ==========================================
        raza.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'Raza',
            id_raza,
            f'Se eliminó raza #{id_raza}: {nombre_raza}'
        )
        
        messages.success(request, f"Raza '{nombre_raza}' eliminada exitosamente")
        
    except Exception as e:
        messages.error(request, f"Error al eliminar: {str(e)}")
    
    return redirect('/listaraza/')


# ============================================================
# POTREROS
# ============================================================
def listapotrero(request):
    """
    Muestra el listado completo de potreros con estadísticas de ocupación.
    Incluye conteo de animales activos asignados a cada potrero.
    """
    potreros = Potrero.objects.annotate(
        num_animales=Count(
            'animal',
            filter=Q(animal__estado_an='activo')
        )
    ).order_by('codigo_po')

    # Estadísticas generales
    total_potreros = potreros.count()
    potreros_disponibles = potreros.filter(estado_po='disponible').count()
    potreros_ocupados = potreros.filter(estado_po='ocupado').count()
    potreros_descanso = potreros.filter(estado_po='en_descanso').count()

    contexto = {
        'potreros': potreros,
        'total_potreros': total_potreros,
        'potreros_disponibles': potreros_disponibles,
        'potreros_ocupados': potreros_ocupados,
        'potreros_descanso': potreros_descanso,
    }

    return render(request, 'catalogos/potreros/lista_potrero.html', contexto)

# VISTA: NUEVO POTRERO (formulario)
def nuevopotrero(request):
    """
    Muestra el formulario para registrar un nuevo potrero.
    """
    return render(request, 'catalogos/potreros/nuevo_potrero.html')

# VISTA: GUARDAR POTRERO (procesar creación)
def guardarpotrero(request):
    """
    Procesa el formulario de creación de un nuevo potrero.
    Valida datos, verifica código único, y registra auditoría.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevopotrero/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        codigo_po = request.POST.get('txt_codigo_po', '').strip().upper()
        nombre_po = request.POST.get('txt_nombre_po', '').strip()
        
        # Validaciones básicas de campos obligatorios
        if not codigo_po:
            messages.error(request, "El código del potrero es obligatorio")
            return redirect('/nuevopotrero/')
        
        if not nombre_po:
            messages.error(request, "El nombre del potrero es obligatorio")
            return redirect('/nuevopotrero/')
        
        # Hectáreas (obligatoria, > 0)
        hectareas_str = request.POST.get('txt_hectareas_po', '').strip()
        if not hectareas_str:
            messages.error(request, "Las hectáreas son obligatorias")
            return redirect('/nuevopotrero/')
        
        try:
            hectareas_po = float(hectareas_str)
            if hectareas_po <= 0:
                messages.error(request, "Las hectáreas deben ser mayores a 0")
                return redirect('/nuevopotrero/')
            if hectareas_po > 9999.99:
                messages.error(request, "Las hectáreas no pueden exceder 9999.99")
                return redirect('/nuevopotrero/')
        except ValueError:
            messages.error(request, "Las hectáreas deben ser un número válido")
            return redirect('/nuevopotrero/')
        
        # Capacidad máxima (obligatoria, >= 1)
        capacidad_str = request.POST.get('txt_capacidad_maxima_po', '').strip()
        if not capacidad_str:
            messages.error(request, "La capacidad máxima es obligatoria")
            return redirect('/nuevopotrero/')
        
        try:
            capacidad_maxima_po = int(capacidad_str)
            if capacidad_maxima_po < 1:
                messages.error(request, "La capacidad mínima es 1 animal")
                return redirect('/nuevopotrero/')
        except ValueError:
            messages.error(request, "La capacidad máxima debe ser un número entero")
            return redirect('/nuevopotrero/')
        
        # Estado (con validación contra choices)
        estado_po = request.POST.get('sel_estado_po', 'disponible')
        estados_validos = ['disponible', 'ocupado', 'en_descanso', 'inactivo']
        if estado_po not in estados_validos:
            messages.error(request, "Estado no válido")
            return redirect('/nuevopotrero/')
        
        # Coordenadas GPS (opcionales)
        latitud_po = None
        longitud_po = None
        
        latitud_str = request.POST.get('txt_latitud_po', '').strip()
        if latitud_str:
            try:
                latitud_po = float(latitud_str)
                if latitud_po < -90 or latitud_po > 90:
                    messages.error(request, "La latitud debe estar entre -90 y 90")
                    return redirect('/nuevopotrero/')
            except ValueError:
                messages.error(request, "La latitud debe ser un número válido")
                return redirect('/nuevopotrero/')
        
        longitud_str = request.POST.get('txt_longitud_po', '').strip()
        if longitud_str:
            try:
                longitud_po = float(longitud_str)
                if longitud_po < -180 or longitud_po > 180:
                    messages.error(request, "La longitud debe estar entre -180 y 180")
                    return redirect('/nuevopotrero/')
            except ValueError:
                messages.error(request, "La longitud debe ser un número válido")
                return redirect('/nuevopotrero/')
        
        # Observaciones (opcional)
        observaciones_po = request.POST.get('txt_observaciones_po', '').strip()
        
        # ==========================================
        # VALIDAR CÓDIGO ÚNICO
        # ==========================================
        if Potrero.objects.filter(codigo_po=codigo_po).exists():
            messages.error(request, f"Ya existe un potrero con el código '{codigo_po}'")
            return redirect('/nuevopotrero/')
        
        # ==========================================
        # CREAR POTRERO
        # ==========================================
        nuevo_potrero = Potrero.objects.create(
            codigo_po=codigo_po,
            nombre_po=nombre_po,
            hectareas_po=hectareas_po,
            capacidad_maxima_po=capacidad_maxima_po,
            estado_po=estado_po,
            latitud_po=latitud_po,
            longitud_po=longitud_po,
            observaciones_po=observaciones_po if observaciones_po else None
        )
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'Potrero',
            nuevo_potrero.id_po,
            f'Se creó el potrero: {nuevo_potrero.codigo_po} - {nuevo_potrero.nombre_po}'
        )
        
        messages.success(request, f"Potrero '{nuevo_potrero.codigo_po}' guardado exitosamente")
        return redirect('/listapotrero/')
        
    except IntegrityError:
        messages.error(request, f"Error de integridad: posiblemente el código '{codigo_po}' ya existe")
        return redirect('/nuevopotrero/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevopotrero/')

# VISTA: EDITAR POTRERO (formulario)
def editarpotrero(request, id_po):
    """
    Muestra el formulario de edición con los datos precargados.
    """
    potrero = get_object_or_404(Potrero, id_po=id_po)
    
    # Contar animales activos en este potrero (para validaciones de estado)
    animales_activos = Animal.objects.filter(
        fk_potrero_an=potrero, 
        estado_an='activo'
    ).count()
    
    contexto = {
        'potrero': potrero,
        'animales_activos': animales_activos,
    }
    
    return render(request, 'catalogos/potreros/editar_potrero.html', contexto)


# VISTA: PROCESAR EDICIÓN POTRERO
def procesareditarpotrero(request):
    """
    Procesa el formulario de edición de un potrero existente.
    Maneja restricciones de estado según animales asignados.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listapotrero/')
    
    try:
        # Obtener potrero existente
        id_po = request.POST.get('id_po')
        if not id_po:
            messages.error(request, "ID de potrero no proporcionado")
            return redirect('/listapotrero/')
        
        potrero = Potrero.objects.get(id_po=id_po)
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        codigo_po = request.POST.get('txt_codigo_po', '').strip().upper()
        nombre_po = request.POST.get('txt_nombre_po', '').strip()
        
        if not codigo_po:
            messages.error(request, "El código del potrero es obligatorio")
            return redirect(f'/editarpotrero/{id_po}')
        
        if not nombre_po:
            messages.error(request, "El nombre del potrero es obligatorio")
            return redirect(f'/editarpotrero/{id_po}')
        
        # Hectáreas
        hectareas_str = request.POST.get('txt_hectareas_po', '').strip()
        if not hectareas_str:
            messages.error(request, "Las hectáreas son obligatorias")
            return redirect(f'/editarpotrero/{id_po}')
        
        try:
            hectareas_po = float(hectareas_str)
            if hectareas_po <= 0:
                messages.error(request, "Las hectáreas deben ser mayores a 0")
                return redirect(f'/editarpotrero/{id_po}')
            if hectareas_po > 9999.99:
                messages.error(request, "Las hectáreas no pueden exceder 9999.99")
                return redirect(f'/editarpotrero/{id_po}')
        except ValueError:
            messages.error(request, "Las hectáreas deben ser un número válido")
            return redirect(f'/editarpotrero/{id_po}')
        
        # Capacidad máxima
        capacidad_str = request.POST.get('txt_capacidad_maxima_po', '').strip()
        if not capacidad_str:
            messages.error(request, "La capacidad máxima es obligatoria")
            return redirect(f'/editarpotrero/{id_po}')
        
        try:
            capacidad_maxima_po = int(capacidad_str)
            if capacidad_maxima_po < 1:
                messages.error(request, "La capacidad mínima es 1 animal")
                return redirect(f'/editarpotrero/{id_po}')
        except ValueError:
            messages.error(request, "La capacidad máxima debe ser un número entero")
            return redirect(f'/editarpotrero/{id_po}')
        
        # Validar que la capacidad no sea menor a los animales activos actuales
        animales_activos = Animal.objects.filter(
            fk_potrero_an=potrero, 
            estado_an='activo'
        ).count()
        
        if capacidad_maxima_po < animales_activos:
            messages.error(
                request, 
                f"No puede reducir la capacidad a {capacidad_maxima_po} porque hay {animales_activos} animales activos asignados"
            )
            return redirect(f'/editarpotrero/{id_po}')
        
        # Estado (con validación de restricciones de negocio)
        estado_po = request.POST.get('sel_estado_po', potrero.estado_po)
        estados_validos = ['disponible', 'ocupado', 'en_descanso', 'inactivo']
        if estado_po not in estados_validos:
            messages.error(request, "Estado no válido")
            return redirect(f'/editarpotrero/{id_po}')
        
        # RESTRICCIÓN DE NEGOCIO: No puede ponerse 'disponible' si tiene animales activos
        if estado_po == 'disponible' and animales_activos > 0:
            messages.error(
                request,
                f"No puede cambiar el estado a 'Disponible' porque tiene {animales_activos} animales activos asignados. "
                f"Trasfiera los animales primero."
            )
            return redirect(f'/editarpotrero/{id_po}')
        
        # RESTRICCIÓN DE NEGOCIO: No puede ponerse 'inactivo' si tiene animales activos
        if estado_po == 'inactivo' and animales_activos > 0:
            messages.error(
                request,
                f"No puede inactivar el potrero porque tiene {animales_activos} animales activos asignados"
            )
            return redirect(f'/editarpotrero/{id_po}')
        
        # Coordenadas GPS
        latitud_po = None
        longitud_po = None
        
        latitud_str = request.POST.get('txt_latitud_po', '').strip()
        if latitud_str:
            try:
                latitud_po = float(latitud_str)
                if latitud_po < -90 or latitud_po > 90:
                    messages.error(request, "La latitud debe estar entre -90 y 90")
                    return redirect(f'/editarpotrero/{id_po}')
            except ValueError:
                messages.error(request, "La latitud debe ser un número válido")
                return redirect(f'/editarpotrero/{id_po}')
        
        longitud_str = request.POST.get('txt_longitud_po', '').strip()
        if longitud_str:
            try:
                longitud_po = float(longitud_str)
                if longitud_po < -180 or longitud_po > 180:
                    messages.error(request, "La longitud debe estar entre -180 y 180")
                    return redirect(f'/editarpotrero/{id_po}')
            except ValueError:
                messages.error(request, "La longitud debe ser un número válido")
                return redirect(f'/editarpotrero/{id_po}')
        
        observaciones_po = request.POST.get('txt_observaciones_po', '').strip()
        
        # ==========================================
        # VALIDAR CÓDIGO ÚNICO (excluyendo el actual)
        # ==========================================
        if Potrero.objects.filter(codigo_po=codigo_po).exclude(id_po=id_po).exists():
            messages.error(request, f"Ya existe otro potrero con el código '{codigo_po}'")
            return redirect(f'/editarpotrero/{id_po}')
        
        # ==========================================
        # ACTUALIZAR POTRERO
        # ==========================================
        potrero.codigo_po = codigo_po
        potrero.nombre_po = nombre_po
        potrero.hectareas_po = hectareas_po
        potrero.capacidad_maxima_po = capacidad_maxima_po
        potrero.estado_po = estado_po
        potrero.latitud_po = latitud_po
        potrero.longitud_po = longitud_po
        potrero.observaciones_po = observaciones_po if observaciones_po else None
        
        potrero.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'Potrero',
            potrero.id_po,
            f'Se editó el potrero: {potrero.codigo_po} - {potrero.nombre_po}'
        )
        
        messages.success(request, f"Potrero '{potrero.codigo_po}' actualizado exitosamente")
        return redirect('/listapotrero/')
        
    except Potrero.DoesNotExist:
        messages.error(request, "Potrero no encontrado")
        return redirect('/listapotrero/')
    except IntegrityError:
        messages.error(request, f"Error de integridad: posiblemente el código '{codigo_po}' ya existe")
        return redirect(f'/editarpotrero/{id_po}')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarpotrero/{id_po}')

# VISTA: ELIMINAR POTRERO
def eliminarpotrero(request, id_po):
    """
    Elimina un potrero del sistema.
    Maneja restricciones de integridad referencial.
    """
    potrero = get_object_or_404(Potrero, id_po=id_po)
    
    # Guardar datos antes de eliminar para auditoría
    codigo_potrero = potrero.codigo_po
    nombre_potrero = potrero.nombre_po
    id_potrero = potrero.id_po
    
    # Verificar si tiene animales asignados (activos o inactivos)
    animales_asignados = Animal.objects.filter(fk_potrero_an=potrero).count()
    
    if animales_asignados > 0:
        messages.error(
            request,
            f"No se puede eliminar el potrero '{codigo_potrero}': "
            f"tiene {animales_asignados} animal(es) asignado(s). "
            f"Reasigne los animales a otro potrero primero."
        )
        return redirect('/listapotrero/')
    
    try:
        potrero.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'Potrero',
            id_potrero,
            f'Se eliminó el potrero: {codigo_potrero} - {nombre_potrero}'
        )
        
        messages.success(request, f"Potrero '{codigo_potrero}' eliminado exitosamente")
        
    except IntegrityError:
        messages.error(
            request,
            f"No se puede eliminar el potrero '{codigo_potrero}': "
            f"tiene registros asociados (movimientos, asignaciones, etc.)"
        )
    
    return redirect('/listapotrero/')
# ============================================================
# PRODUCTOS VETERINARIOS
# ============================================================

def nuevoprodvet(request):
    return render(request, 'catalogos/salud/prodvet/nuevo_prodvet.html')

def listadoprodvet(request):
    prodvetBdd = ProductoVeterinario.objects.all()
    
    # ==========================================
    # TARJETAS ESTADÍSTICAS
    # ==========================================
    total_prodvet = prodvetBdd.count()
    total_activos = prodvetBdd.filter(activo_pv=True).count()
    total_vacunas = prodvetBdd.filter(tipo_pv='vacuna').count()
    total_antibioticos = prodvetBdd.filter(tipo_pv='antibiotico').count()
    total_vitaminas = prodvetBdd.filter(tipo_pv='vitamina').count()
    total_stock_bajo = prodvetBdd.filter(stock_pv__lte=F('stock_minimo_pv')).count()
    
    return render(request, 'catalogos/salud/prodvet/lista_prodvet.html', {
        'prodvet': prodvetBdd,
        'total_prodvet': total_prodvet,
        'total_activos': total_activos,
        'total_vacunas': total_vacunas,
        'total_antibioticos': total_antibioticos,
        'total_vitaminas': total_vitaminas,
        'total_stock_bajo': total_stock_bajo,
    })

def guardarprodvet(request):
    codigo_pv = request.POST['txt_codigo_pv']
    nombre_pv = request.POST['txt_nombre_pv']
    tipo_pv = request.POST['txt_tipo_pv']
    presentacion_pv = request.POST.get('txt_presentacion_pv', '')
    stock_pv = request.POST['txt_stock_pv']
    stock_minimo_pv = request.POST.get('txt_stock_minimo_pv', 10)
    unidad_medida_pv = request.POST['txt_unidad_medida_pv']
    fecha_vencimiento_pv = request.POST.get('txt_fecha_vencimiento_pv') or None
    proveedor_pv = request.POST.get('txt_proveedor_pv', '')
    costo_unitario_pv = request.POST.get('txt_costo_unitario_pv') or None
    activo_pv = request.POST.get('chk_activo_pv') == '1'

    nuevoprodvet = ProductoVeterinario.objects.create(
        codigo_pv=codigo_pv,
        nombre_pv=nombre_pv,
        tipo_pv=tipo_pv,
        presentacion_pv=presentacion_pv,
        stock_pv=stock_pv,
        stock_minimo_pv=stock_minimo_pv,
        unidad_medida_pv=unidad_medida_pv,
        fecha_vencimiento_pv=fecha_vencimiento_pv,
        proveedor_pv=proveedor_pv,
        costo_unitario_pv=costo_unitario_pv,
        activo_pv=activo_pv
    )

    # ==========================================
    # AUDITORÍA
    # ==========================================
    guardar_auditoria(
        request,
        'crear',
        'ProductoVeterinario',
        nuevoprodvet.id_pv,
        f'Se creó el producto veterinario: {nuevoprodvet.nombre_pv}'
    )

    messages.success(request, "Producto veterinario guardado exitosamente")
    return redirect('/listadoprodvet')


def eliminarprodvet(request, id_pv):
    prodvetBdd = get_object_or_404(ProductoVeterinario, id_pv=id_pv)

    try:
        # GUARDAR DATOS ANTES DE ELIMINAR
        nombre_prodvet = prodvetBdd.nombre_pv
        id_prodvet = prodvetBdd.id_pv

        prodvetBdd.delete()

        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'ProductoVeterinario',
            id_prodvet,
            f'Se eliminó el producto veterinario: {nombre_prodvet}'
        )

        messages.success(request, "Producto veterinario eliminado exitosamente")

    except IntegrityError:
        messages.error(request, "No se puede eliminar: tiene registros asociados")

    return redirect('/listadoprodvet')


def editarprodvet(request, id_pv):
    prodvetBdd = ProductoVeterinario.objects.get(id_pv=id_pv)
    return render(request, 'catalogos/salud/prodvet/editar_prodvet.html', {'prodvet': prodvetBdd})

def procesareditarprodvet(request):
    cam = ProductoVeterinario.objects.get(id_pv=request.POST['id_pv'])

    cam.codigo_pv = request.POST['txt_codigo_pv']
    cam.nombre_pv = request.POST['txt_nombre_pv']
    cam.tipo_pv = request.POST['txt_tipo_pv']
    cam.presentacion_pv = request.POST.get('txt_presentacion_pv', '')
    cam.stock_pv = request.POST['txt_stock_pv']
    cam.stock_minimo_pv = request.POST.get('txt_stock_minimo_pv', 10)
    cam.unidad_medida_pv = request.POST['txt_unidad_medida_pv']
    cam.fecha_vencimiento_pv = request.POST.get('txt_fecha_vencimiento_pv') or None
    cam.proveedor_pv = request.POST.get('txt_proveedor_pv', '')
    cam.costo_unitario_pv = request.POST.get('txt_costo_unitario_pv') or None
    cam.activo_pv = request.POST.get('chk_activo_pv') == '1'

    cam.save()

    # ==========================================
    # AUDITORÍA
    # ==========================================
    guardar_auditoria(
        request,
        'editar',
        'ProductoVeterinario',
        cam.id_pv,
        f'Se editó el producto veterinario: {cam.nombre_pv}'
    )

    messages.success(request, "Producto veterinario editado exitosamente")
    return redirect('/listadoprodvet')
# ==========================================
# INSUMOS ALIMENTICIOS
# ==========================================

def nuevoinsumo(request):
    return render(request, 'catalogos/insualim/nuevo_insumo.html')

def listadoinsumos(request):
    insumosBdd = InsumoAlimenticio.objects.all()
    
    # ── ESTADÍSTICAS ──
    total_insumos = insumosBdd.count()
    total_activos = insumosBdd.filter(activo_ia=True).count()
    total_bajo_stock = insumosBdd.filter(
        stock_kg_ia__lte=models.F('stock_minimo_kg_ia')
    ).count()
    
    # ── SUBTOTAL POR INSUMO ──
    insumos_con_subtotal = []
    valor_total = 0
    
    for insumo in insumosBdd:
        stock = float(insumo.stock_kg_ia or 0)
        costo = float(insumo.costo_kg_ia or 0)
        subtotal = round(stock * costo, 2)
        valor_total += subtotal
        
        insumos_con_subtotal.append({
            'insumo': insumo,
            'subtotal': subtotal,
            'formula': f"{stock} kg × ${costo}"
        })
    
    return render(request, 'catalogos/insualim/lista_insumo.html', {
        'insumos_con_subtotal': insumos_con_subtotal,
        'total_insumos': total_insumos,
        'total_activos': total_activos,
        'total_bajo_stock': total_bajo_stock,
        'valor_total_inventario': round(valor_total, 2),
    })

def guardarinsumo(request):
    codigo_ia = request.POST['txt_codigo_ia'].strip().upper()
    nombre_ia = request.POST['txt_nombre_ia'].strip()
    tipo_ia = request.POST['sel_tipo_ia']
    marca_ia = request.POST.get('txt_marca_ia', '').strip()
    stock_kg_ia = request.POST.get('txt_stock_kg_ia', '0').replace(',', '.')
    stock_minimo_kg_ia = request.POST.get('txt_stock_minimo_kg_ia', '100').replace(',', '.')
    costo_kg_ia = request.POST.get('txt_costo_kg_ia', '0').replace(',', '.')
    proveedor_ia = request.POST.get('txt_proveedor_ia', '').strip()
    fecha_compra_ia = request.POST.get('dt_fecha_compra_ia') or None
    activo_ia = request.POST.get('chk_activo_ia') == '1'

    try:
        stock_kg_ia = Decimal(stock_kg_ia) if stock_kg_ia else Decimal('0')
        stock_minimo_kg_ia = Decimal(stock_minimo_kg_ia) if stock_minimo_kg_ia else Decimal('100')
        costo_kg_ia = Decimal(costo_kg_ia) if costo_kg_ia else Decimal('0')
    except:
        messages.error(request, "Error en valores numéricos")
        return redirect('/nuevoinsumo/')

    nuevo_insumo = InsumoAlimenticio.objects.create(
        codigo_ia=codigo_ia,
        nombre_ia=nombre_ia,
        tipo_ia=tipo_ia,
        marca_ia=marca_ia,
        stock_kg_ia=stock_kg_ia,
        stock_minimo_kg_ia=stock_minimo_kg_ia,
        costo_kg_ia=costo_kg_ia,
        proveedor_ia=proveedor_ia,
        fecha_compra_ia=fecha_compra_ia,
        activo_ia=activo_ia
    )

    # ==========================================
    # AUDITORÍA
    # ==========================================
    guardar_auditoria(
        request,
        'crear',
        'InsumoAlimenticio',
        nuevo_insumo.id_ia,
        f'Se creó el insumo alimenticio: {nuevo_insumo.nombre_ia}'
    )

    messages.success(request, "Insumo alimenticio guardado exitosamente")
    return redirect('/listadoinsumos/')

def eliminarinsumo(request, id_ia):
    insumoBdd = get_object_or_404(InsumoAlimenticio, id_ia=id_ia)

    try:
        # GUARDAR DATOS ANTES DE ELIMINAR
        nombre_insumo = insumoBdd.nombre_ia
        id_insumo = insumoBdd.id_ia

        insumoBdd.delete()

        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'InsumoAlimenticio',
            id_insumo,
            f'Se eliminó el insumo alimenticio: {nombre_insumo}'
        )

        messages.success(request, "Insumo eliminado exitosamente")

    except IntegrityError:
        messages.error(request, "No se puede eliminar: tiene registros asociados")

    return redirect('/listadoinsumos/')

def editarinsumo(request, id_ia):
    insumoBdd = InsumoAlimenticio.objects.get(id_ia=id_ia)
    return render(request, 'catalogos/insualim/editar_insumo.html', {'insumo': insumoBdd})

def procesareditarinsumo(request):
    cam = InsumoAlimenticio.objects.get(id_ia=request.POST['id_ia'])

    cam.codigo_ia = request.POST['txt_codigo_ia'].strip().upper()
    cam.nombre_ia = request.POST['txt_nombre_ia'].strip()
    cam.tipo_ia = request.POST['sel_tipo_ia']
    cam.marca_ia = request.POST.get('txt_marca_ia', '').strip()

    stock_kg = request.POST.get('txt_stock_kg_ia', '0').replace(',', '.')
    stock_min = request.POST.get('txt_stock_minimo_kg_ia', '100').replace(',', '.')
    costo = request.POST.get('txt_costo_kg_ia', '0').replace(',', '.')

    try:
        cam.stock_kg_ia = Decimal(stock_kg) if stock_kg else Decimal('0')
        cam.stock_minimo_kg_ia = Decimal(stock_min) if stock_min else Decimal('100')
        cam.costo_kg_ia = Decimal(costo) if costo else Decimal('0')
    except:
        messages.error(request, "Error en valores numéricos")
        return redirect('/editarinsumo/' + request.POST['id_ia'])

    cam.proveedor_ia = request.POST.get('txt_proveedor_ia', '').strip()
    cam.fecha_compra_ia = request.POST.get('dt_fecha_compra_ia') or None
    cam.activo_ia = request.POST.get('chk_activo_ia') == '1'

    cam.save()

    # ==========================================
    # AUDITORÍA
    # ==========================================
    guardar_auditoria(
        request,
        'editar',
        'InsumoAlimenticio',
        cam.id_ia,
        f'Se editó el insumo alimenticio: {cam.nombre_ia}'
    )

    messages.success(request, "Insumo editado exitosamente")
    return redirect('/listadoinsumos/')

# ==========================================
# DIETAS
# ==========================================

def nuevadieta(request):
    return render(request, 'catalogos/dieta/nueva_dieta.html')

def listadodietas(request):
    dietasBdd = Dieta.objects.all()
    
    # ── ESTADÍSTICAS ──
    total_dietas = dietasBdd.count()
    total_activas = dietasBdd.filter(activa_di=True).count()
    total_inactivas = dietasBdd.filter(activa_di=False).count()
    
    # Costo promedio diario
    costos = [float(d.costo_diario_estimado_di or 0) for d in dietasBdd if d.costo_diario_estimado_di]
    costo_promedio_diario = sum(costos) / len(costos) if costos else 0
    
    # Costo total diario
    costo_total_diario = sum(costos)
    
    # ── PREPARAR DATOS PARA EL TEMPLATE ──
    dietas_con_datos = []
    for dieta in dietasBdd:
        dietas_con_datos.append({
            'dieta': dieta,
        })
    
    return render(request, 'catalogos/dieta/lista_dieta.html', {
        'dietas_con_datos': dietas_con_datos,
        'total_dietas': total_dietas,
        'total_activas': total_activas,
        'total_inactivas': total_inactivas,
        'costo_promedio_diario': round(costo_promedio_diario, 2),
        'costo_total_diario': round(costo_total_diario, 2),
    })

def guardardieta(request):
    codigo_di = request.POST['txt_codigo_di'].strip().upper()
    nombre_di = request.POST['txt_nombre_di'].strip()
    categoria_objetivo_di = request.POST['sel_categoria_objetivo_di']

    materia_seca_kg_di = request.POST.get('txt_materia_seca_kg_di', '').replace(',', '.') or None
    energia_mcal_di = request.POST.get('txt_energia_mcal_di', '').replace(',', '.') or None
    proteina_cruda_pct_di = request.POST.get('txt_proteina_cruda_pct_di', '').replace(',', '.') or None
    fibra_cruda_pct_di = request.POST.get('txt_fibra_cruda_pct_di', '').replace(',', '.') or None
    calcio_pct_di = request.POST.get('txt_calcio_pct_di', '').replace(',', '.') or None
    fosforo_pct_di = request.POST.get('txt_fosforo_pct_di', '').replace(',', '.') or None
    costo_diario_estimado_di = request.POST.get('txt_costo_diario_estimado_di', '').replace(',', '.') or None

    activa_di = request.POST.get('chk_activa_di') == '1'

    def to_decimal(val, max_digits=10):
        if val is None or val == '':
            return None
        try:
            d = Decimal(val)
            if d >= Decimal('10') ** (max_digits - 2):
                return None
            return d
        except:
            return None

    nueva_dieta = Dieta.objects.create(
        codigo_di=codigo_di,
        nombre_di=nombre_di,
        categoria_objetivo_di=categoria_objetivo_di,
        materia_seca_kg_di=to_decimal(materia_seca_kg_di, 6),
        energia_mcal_di=to_decimal(energia_mcal_di, 6),
        proteina_cruda_pct_di=to_decimal(proteina_cruda_pct_di, 5),
        fibra_cruda_pct_di=to_decimal(fibra_cruda_pct_di, 5),
        calcio_pct_di=to_decimal(calcio_pct_di, 5),
        fosforo_pct_di=to_decimal(fosforo_pct_di, 5),
        costo_diario_estimado_di=to_decimal(costo_diario_estimado_di, 8),
        activa_di=activa_di
    )

    # ==========================================
    # AUDITORÍA
    # ==========================================
    guardar_auditoria(
        request,
        'crear',
        'Dieta',
        nueva_dieta.id_di,
        f'Se creó la dieta: {nueva_dieta.nombre_di}'
    )

    messages.success(request, "Dieta guardada exitosamente")
    return redirect('/listadodietas/')

def eliminardieta(request, id_di):
    dietaBdd = get_object_or_404(Dieta, id_di=id_di)

    try:
        # GUARDAR DATOS ANTES DE ELIMINAR
        nombre_dieta = dietaBdd.nombre_di
        id_dieta = dietaBdd.id_di

        dietaBdd.delete()

        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'Dieta',
            id_dieta,
            f'Se eliminó la dieta: {nombre_dieta}'
        )

        messages.success(request, "Dieta eliminada exitosamente")

    except IntegrityError:
        messages.error(request, "No se puede eliminar: tiene registros asociados")

    return redirect('/listadodietas/')

def editardieta(request, id_di):
    dietaBdd = Dieta.objects.get(id_di=id_di)
    return render(request, 'catalogos/dieta/editar_dieta.html', {'dieta': dietaBdd})

def procesareditardieta(request):
    cam = Dieta.objects.get(id_di=request.POST['id_di'])

    cam.codigo_di = request.POST['txt_codigo_di'].strip().upper()
    cam.nombre_di = request.POST['txt_nombre_di'].strip()
    cam.categoria_objetivo_di = request.POST['sel_categoria_objetivo_di']

    def to_decimal(val, max_digits=10):
        if val is None or val == '':
            return None
        try:
            d = Decimal(val)
            if d >= Decimal('10') ** (max_digits - 2):
                return None
            return d
        except:
            return None

    materia_seca = request.POST.get('txt_materia_seca_kg_di', '').replace(',', '.') or None
    energia = request.POST.get('txt_energia_mcal_di', '').replace(',', '.') or None
    proteina = request.POST.get('txt_proteina_cruda_pct_di', '').replace(',', '.') or None
    fibra = request.POST.get('txt_fibra_cruda_pct_di', '').replace(',', '.') or None
    calcio = request.POST.get('txt_calcio_pct_di', '').replace(',', '.') or None
    fosforo = request.POST.get('txt_fosforo_pct_di', '').replace(',', '.') or None
    costo = request.POST.get('txt_costo_diario_estimado_di', '').replace(',', '.') or None

    cam.materia_seca_kg_di = to_decimal(materia_seca, 6)
    cam.energia_mcal_di = to_decimal(energia, 6)
    cam.proteina_cruda_pct_di = to_decimal(proteina, 5)
    cam.fibra_cruda_pct_di = to_decimal(fibra, 5)
    cam.calcio_pct_di = to_decimal(calcio, 5)
    cam.fosforo_pct_di = to_decimal(fosforo, 5)
    cam.costo_diario_estimado_di = to_decimal(costo, 8)

    cam.activa_di = request.POST.get('chk_activa_di') == '1'

    cam.save()

    # ==========================================
    # AUDITORÍA
    # ==========================================
    guardar_auditoria(
        request,
        'editar',
        'Dieta',
        cam.id_di,
        f'Se editó la dieta: {cam.nombre_di}'
    )

    messages.success(request, "Dieta editada exitosamente")
    return redirect('/listadodietas/')
# ==========================================
# LOGIN
# ==========================================
def loginusuario(request):

    # Leer cookies de "Recordarme"
    cookie_username = request.COOKIES.get('recordar_usuario', '')
    cookie_password_enc = request.COOKIES.get('recordar_password', '')

    # Precargar contraseña si existe cookie
    cookie_password = ''

    if cookie_password_enc:
        try:
            cookie_password = base64.b64decode(
                cookie_password_enc.encode()
            ).decode()
        except:
            cookie_password = ''

    if request.method == 'POST':

        username = request.POST.get('txt_username', '').strip()
        password = request.POST.get('txt_password', '')
        recordar = request.POST.get('chk_recordar') == '1'

        try:
            user = Usuario.objects.get(username_us=username)

            # ==========================================
            # VERIFICAR BLOQUEO
            # ==========================================
            if user.bloqueado_hasta_us and user.bloqueado_hasta_us > timezone.now():

                tiempo_restante = int(
                    (
                        user.bloqueado_hasta_us - timezone.now()
                    ).total_seconds() / 60
                )

                messages.error(
                    request,
                    f"Cuenta bloqueada. Intente nuevamente en {tiempo_restante} minutos."
                )

                return render(
                    request,
                    'catalogos/usuario/login/login_usuario.html',
                    {
                        'cookie_username': cookie_username,
                        'cookie_password': cookie_password
                    }
                )

            # ==========================================
            # LOGIN CORRECTO
            # ==========================================
            if check_password(password, user.password_us):

                # Resetear intentos
                user.intentos_fallidos_us = 0
                user.bloqueado_hasta_us = None
                user.ultimo_acceso_us = timezone.now()

                user.save()

                # ==========================================
                # CREAR SESIÓN
                # ==========================================
                request.session['usuario_id'] = user.id_us
                request.session['usuario_username'] = user.username_us
                request.session['usuario_rol'] = user.rol_us
                request.session['usuario_nombre'] = f"{user.nombre_us} {user.apellido_us}"

                # ==========================================
                # AUDITORÍA LOGIN
                # ==========================================
                guardar_auditoria(
                    request,
                    'login',
                    'Usuario',
                    user.id_us,
                    f'Inicio de sesión del usuario: {user.username_us}'
                )

                messages.success(
                    request,
                    f"Bienvenido, {user.nombre_us}!"
                )

                response = redirect('/inicio/')

                # ==========================================
                # RECORDARME
                # ==========================================
                if recordar:

                    response.set_cookie(
                        'recordar_usuario',
                        username,
                        max_age=30*24*60*60,
                        httponly=True,
                        secure=False,
                        samesite='Lax'
                    )

                    password_ofuscada = base64.b64encode(
                        password.encode()
                    ).decode()

                    response.set_cookie(
                        'recordar_password',
                        password_ofuscada,
                        max_age=30*24*60*60,
                        httponly=True,
                        secure=False,
                        samesite='Lax'
                    )

                else:

                    response.delete_cookie('recordar_usuario')
                    response.delete_cookie('recordar_password')

                return response

            # ==========================================
            # CONTRASEÑA INCORRECTA
            # ==========================================
            else:

                user.intentos_fallidos_us += 1

                # ==========================================
                # BLOQUEAR CUENTA
                # ==========================================
                if user.intentos_fallidos_us >= 5:

                    user.bloqueado_hasta_us = timezone.now() + timedelta(minutes=30)

                    user.save()

                    # AUDITORÍA BLOQUEO
                    guardar_auditoria(
                        request,
                        'bloqueo',
                        'Usuario',
                        user.id_us,
                        f'Cuenta bloqueada: {user.username_us}'
                    )

                    messages.error(
                        request,
                        "Cuenta bloqueada por 30 minutos por seguridad."
                    )

                else:

                    intentos_restantes = 5 - user.intentos_fallidos_us

                    user.save()

                    # AUDITORÍA LOGIN FALLIDO
                    guardar_auditoria(
                        request,
                        'login_fallido',
                        'Usuario',
                        user.id_us,
                        f'Intento fallido de login: {user.username_us}'
                    )

                    messages.warning(
                        request,
                        f"Contraseña incorrecta. Le quedan {intentos_restantes} intentos."
                    )

                return render(
                    request,
                    'catalogos/usuario/login/login_usuario.html',
                    {
                        'cookie_username': cookie_username,
                        'cookie_password': cookie_password
                    }
                )

        except Usuario.DoesNotExist:

            messages.error(
                request,
                "Usuario o contraseña incorrectos."
            )

            return render(
                request,
                'catalogos/usuario/login/login_usuario.html',
                {
                    'cookie_username': cookie_username,
                    'cookie_password': cookie_password
                }
            )

    return render(
        request,
        'catalogos/usuario/login/login_usuario.html',
        {
            'cookie_username': cookie_username,
            'cookie_password': cookie_password
        }
    )

def logoutusuario(request):

    # ==========================================
    # AUDITORÍA LOGOUT
    # ==========================================
    guardar_auditoria(
        request,
        'logout',
        'Usuario',
        request.session.get('usuario_id'),
        f'Cierre de sesión del usuario: {request.session.get("usuario_username")}'
    )

    request.session.flush()

    response = redirect('/login/')

    response.delete_cookie('recordar_usuario')
    response.delete_cookie('recordar_password')

    messages.success(
        request,
        "Sesión cerrada exitosamente."
    )

    return response
# ==========================================
# RECUPERAR CONTRASEÑA - PASO 1: SOLICITAR
# ==========================================
def recuperarcontrasena(request):
    if request.method == 'POST':
        email = request.POST.get('txt_email', '').strip().lower()
        
        try:
            usuario = Usuario.objects.get(email_us=email)
            
            # Generar código de 6 dígitos
            codigo = ''.join(random.choices(string.digits, k=6))
            
            # Guardar código en sesión (temporal)
            request.session['codigo_recuperacion'] = codigo
            request.session['email_recuperacion'] = email
            request.session['codigo_expira'] = (timezone.now() + timedelta(minutes=15)).isoformat()
            
            # Enviar correo
            try:
                send_mail(
                    subject='🔐 Recuperación de Contraseña - Hacienda El Roble',
                    message=f'''
                    Hola {usuario.nombre_us},

                    Has solicitado recuperar tu contraseña en el Sistema de Gestión Ganadera Hacienda El Roble.

                    Tu código de verificación es: {codigo}

                    Este código expira en 15 minutos.

                    Si no solicitaste este cambio, ignora este correo.
                                        ''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                messages.success(request, "Código enviado a su correo electrónico. Tiene 15 minutos para usarlo.")
                return redirect('/verificarcodigo/')
                
            except Exception as e:
                messages.error(request, "Error al enviar el correo. Por favor contacte al administrador.")
                return render(request, 'catalogos/usuario/contrasena/recont_usuario.html')
                
        except Usuario.DoesNotExist:
            # Por seguridad, no revelar si el correo existe o no
            messages.success(request, "Si el correo está registrado, recibirá un código de verificación.")
            return render(request, 'catalogos/usuario/contrasena/recont_usuario.html')
    
    return render(request, 'catalogos/usuario/contrasena/recont_usuario.html')

# ==========================================
# RECUPERAR CONTRASEÑA - PASO 2: VERIFICAR CÓDIGO
# ==========================================
def verificarcodigo(request):
    # Verificar que venga del flujo correcto
    if 'codigo_recuperacion' not in request.session:
        messages.error(request, "Sesión expirada. Solicite un nuevo código.")
        return redirect('/recuperarcontrasena/')
    
    # Verificar expiración
    expira = timezone.datetime.fromisoformat(request.session.get('codigo_expira', '2000-01-01'))
    if timezone.now() > expira:
        # Limpiar sesión
        del request.session['codigo_recuperacion']
        del request.session['email_recuperacion']
        del request.session['codigo_expira']
        messages.error(request, "Código expirado. Solicite uno nuevo.")
        return redirect('/recuperarcontrasena/')
    
    if request.method == 'POST':
        codigo_ingresado = request.POST.get('txt_codigo', '').strip()
        codigo_guardado = request.session.get('codigo_recuperacion', '')
        
        if codigo_ingresado == codigo_guardado:
            # Código correcto, redirigir a reestablecer
            request.session['codigo_verificado'] = True
            messages.success(request, "Código verificado. Ingrese su nueva contraseña.")
            return redirect('/reestablecercontrasena/')
        else:
            messages.error(request, "Código incorrecto. Intente nuevamente.")
            return render(request, 'usuarios/recont_usuario.html', {'paso': 'verificar'})
    
    return render(request, 'catalogos/usuario/contrasena/recont_usuario.html', {'paso': 'verificar'})

# ==========================================
# RECUPERAR CONTRASEÑA - PASO 3: REESTABLECER
# ==========================================
def reestablecercontrasena(request):
    # Verificar flujo
    if 'codigo_verificado' not in request.session or not request.session['codigo_verificado']:
        messages.error(request, "Acceso no autorizado.")
        return redirect('/recuperarcontrasena/')
    
    if request.method == 'POST':
        nueva_password = request.POST.get('txt_nueva_password', '')
        confirmar_password = request.POST.get('txt_confirmar_password', '')
        
        # Validaciones
        if nueva_password != confirmar_password:
            messages.error(request, "Las contraseñas no coinciden.")
            return render(request, 'catalogos/usuario/contrasena/recont_usuario.html', {'paso': 'reestablecer'})
        
        if len(nueva_password) < 8:
            messages.error(request, "La contraseña debe tener al menos 8 caracteres.")
            return render(request, 'catalogos/usuario/contrasena/recont_usuario.html', {'paso': 'reestablecer'})
        
        if not any(c.isupper() for c in nueva_password) or \
           not any(c.islower() for c in nueva_password) or \
           not any(c.isdigit() for c in nueva_password):
            messages.error(request, "Debe incluir mayúscula, minúscula y número.")
            return render(request, 'catalogos/usuario/contrasena/recont_usuario.html', {'paso': 'reestablecer'})
        
        # Actualizar contraseña
        try:
            email = request.session.get('email_recuperacion')
            usuario = Usuario.objects.get(email_us=email)
            usuario.password_us = make_password(nueva_password)
            usuario.intentos_fallidos_us = 0
            usuario.bloqueado_hasta_us = None
            usuario.save()
            
            # Limpiar sesión
            del request.session['codigo_recuperacion']
            del request.session['email_recuperacion']
            del request.session['codigo_expira']
            del request.session['codigo_verificado']
            
            messages.success(request, "Contraseña actualizada exitosamente. Inicie sesión.")
            return redirect('/login/')
            
        except Usuario.DoesNotExist:
            messages.error(request, "Error al actualizar. Contacte al administrador.")
            return redirect('/recuperarcontrasena/')
    
    return render(request, 'catalogos/usuario/contrasena/recont_usuario.html', {'paso': 'reestablecer'})

# ==========================================
# CRUD USUARIOS
# ==========================================
def nuevousuario(request):
    return render(request, 'catalogos/usuario/nuevo_usuario.html')

def listadousuarios(request):
    usuariosBdd = Usuario.objects.all()
    return render(request, 'catalogos/usuario/lista_usuario.html', {'usuarios': usuariosBdd})

def guardarusuario(request):
    username_us = request.POST['txt_username_us'].strip().lower()
    password_us = request.POST['txt_password_us']
    confirm_password = request.POST['txt_confirm_password']
    email_us = request.POST['txt_email_us'].strip().lower()
    nombre_us = request.POST['txt_nombre_us'].strip()
    apellido_us = request.POST['txt_apellido_us'].strip()
    telefono_us = request.POST.get('txt_telefono_us', '').strip()
    cedula_us = request.POST.get('txt_cedula_us', '').strip() or None
    rol_us = request.POST['sel_rol_us']
    activo_us = request.POST.get('chk_activo_us') == '1'

    # VALIDACIONES
    if password_us != confirm_password:
        messages.error(request, "Las contraseñas no coinciden.")
        return redirect('/nuevousuario/')

    if len(password_us) < 8:
        messages.error(request, "La contraseña debe tener al menos 8 caracteres.")
        return redirect('/nuevousuario/')

    if Usuario.objects.filter(username_us=username_us).exists():
        messages.error(request, "El nombre de usuario ya existe.")
        return redirect('/nuevousuario/')

    if Usuario.objects.filter(email_us=email_us).exists():
        messages.error(request, "El correo electrónico ya está registrado.")
        return redirect('/nuevousuario/')

    if cedula_us and Usuario.objects.filter(cedula_us=cedula_us).exists():
        messages.error(request, "La cédula ya está registrada.")
        return redirect('/nuevousuario/')

    nuevo_usuario = Usuario.objects.create(
        username_us=username_us,
        password_us=make_password(password_us),
        email_us=email_us,
        nombre_us=nombre_us,
        apellido_us=apellido_us,
        telefono_us=telefono_us,
        cedula_us=cedula_us,
        rol_us=rol_us,
        activo_us=activo_us
    )

    # ==========================================
    # AUDITORÍA
    # ==========================================
    guardar_auditoria(
        request,
        'crear',
        'Usuario',
        nuevo_usuario.id_us,
        f'Se creó el usuario: {nuevo_usuario.username_us}'
    )

    messages.success(request, "Usuario creado exitosamente")
    return redirect('/listadousuarios/')

def eliminarusuario(request, id_us):
    usuarioBdd = get_object_or_404(Usuario, id_us=id_us)

    # No permitir eliminar el último administrador
    if usuarioBdd.rol_us == 'administrador' and Usuario.objects.filter(rol_us='administrador').count() <= 1:
        messages.error(request, "No se puede eliminar el único administrador del sistema.")
        return redirect('/listadousuarios/')

    try:
        # GUARDAR DATOS ANTES DE ELIMINAR
        username_usuario = usuarioBdd.username_us
        id_usuario = usuarioBdd.id_us

        usuarioBdd.delete()

        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'Usuario',
            id_usuario,
            f'Se eliminó el usuario: {username_usuario}'
        )

        messages.success(request, "Usuario eliminado exitosamente")

    except IntegrityError:
        messages.error(request, "No se puede eliminar: tiene registros asociados")

    return redirect('/listadousuarios/')

def editarusuario(request, id_us):
    usuarioBdd = Usuario.objects.get(id_us=id_us)
    return render(request, 'catalogos/usuario/editar_usuario.html', {'usuario': usuarioBdd})

def procesareditarusuario(request):
    cam = Usuario.objects.get(id_us=request.POST['id_us'])

    cam.username_us = request.POST['txt_username_us'].strip().lower()
    cam.email_us = request.POST['txt_email_us'].strip().lower()
    cam.nombre_us = request.POST['txt_nombre_us'].strip()
    cam.apellido_us = request.POST['txt_apellido_us'].strip()
    cam.telefono_us = request.POST.get('txt_telefono_us', '').strip()
    cam.cedula_us = request.POST.get('txt_cedula_us', '').strip() or None
    cam.rol_us = request.POST['sel_rol_us']
    cam.activo_us = request.POST.get('chk_activo_us') == '1'
    # ACTUALIZAR CONTRASEÑA SOLO SI SE INGRESA UNA NUEVA
    nueva_password = request.POST.get('txt_password_us', '')
    if nueva_password:
        if len(nueva_password) < 8:
            messages.error(request, "La contraseña debe tener al menos 8 caracteres.")
            return redirect('/editarusuario/' + request.POST['id_us'])

        cam.password_us = make_password(nueva_password)
    cam.save()
    # ==========================================
    # AUDITORÍA
    # ==========================================
    guardar_auditoria(
        request,
        'editar',
        'Usuario',
        cam.id_us,
        f'Se editó el usuario: {cam.username_us}'
    )
    messages.success(request, "Usuario editado exitosamente")
    return redirect('/listadousuarios/')


# ==========================================
# AUDITORÍA - HISTORIAL
# ==========================================
def historialauditoria(request):
    # Solo administradores pueden ver
    if request.session.get('usuario_rol') != 'administrador':
        messages.error(request, "No tienes permisos.")
        return redirect('/inicio/')
    
    # Trae todos los logs con info del usuario
    logs = LogAuditoria.objects.select_related('fk_us_la').all()
    return render(request, 'catalogos/usuario/historial/historial_auditoria.html', {'logs': logs})


# ==========================================
# AUDITORÍA - VER DETALLE
# ==========================================
def verdetallelog(request, id_la):
    if request.session.get('usuario_rol') != 'administrador':
        messages.error(request, "No tienes permisos.")
        return redirect('/inicio/')
    
    log = LogAuditoria.objects.select_related('fk_us_la').get(id_la=id_la)
    return render(request, 'catalogos/usuario/historial/detalle_auditoria.html', {'log': log})


# ==========================================
# AUDITORÍA - ELIMINAR LOG
# ==========================================
def eliminarlog(request, id_la):
    if request.session.get('usuario_rol') != 'administrador':
        messages.error(request, "No tienes permisos.")
        return redirect('/inicio/')
    
    log = LogAuditoria.objects.get(id_la=id_la)
    log.delete()
    
    messages.success(request, "Registro eliminado.")
    return redirect('/historialauditoria/')


# ==========================================
# FUNCIÓN PARA GUARDAR AUDITORÍA AUTOMÁTICO
# ==========================================
def guardar_auditoria(request, accion, modelo, objeto_id=None, descripcion=''):
    """
    Usa esta función después de crear/editar/eliminar cualquier cosa.
    
    Ejemplo:
        guardar_auditoria(request, 'crear', 'Usuario', nuevo.id_us)
    """
    try:
        LogAuditoria.objects.create(
            fk_us_la_id=request.session.get('usuario_id'),
            accion_la=accion,           # 'crear', 'editar', 'eliminar', etc.
            modelo_afectado_la=modelo,   # 'Usuario', 'Animal', etc.
            objeto_id_la=objeto_id,
            descripcion_la=descripcion,
            ip_address_la=request.META.get('REMOTE_ADDR')
        )
    except:
        pass  

# ==========================================
# ANIMALES
# ==========================================
#SE HIZO MODIFICACION AQUI PARA CLAUDINARY
# SE HIZO MODIFICACION AQUI PARA CLAUDINARY
def guardar_foto(request, campo_file, carpeta='animales'):
    if campo_file in request.FILES:
        foto = request.FILES[campo_file]  # ← SIN COMILLAS
        # ... validaciones ...
        try:
            resultado = cloudinary.uploader.upload(
                foto,
                upload_preset='animal_fotos_preset'  # ← CON EL PRESET
            )
            return resultado['secure_url'], None
        except Exception as e:
            # Fallback local
            fs = FileSystemStorage(location=f'media/{carpeta}/')
            filename = fs.save(foto.name, foto)
            return f'media/{carpeta}/{filename}', None
    return None, None
# VISTA: NUEVO ANIMAL (formulario)
def nuevoanimal(request):
    """
    Muestra el formulario para registrar un nuevo animal.
    Carga las listas de razas, potreros, hembras y machos para los selects.
    """
    # Obtener listas para selects
    razas = Raza.objects.filter(activo_ra=True).order_by('nombre_ra')
    potreros = Potrero.objects.filter(estado_po__in=['disponible', 'ocupado']).order_by('nombre_po')
    
    # Hembras disponibles como madres (excluir el animal actual si estuviera editando)
    hembras = Animal.objects.filter(sexo_an='H').order_by('codigo_an')
    
    # Machos disponibles como padres
    machos = Animal.objects.filter(sexo_an='M').order_by('codigo_an')
    
    contexto = {
        'razas': razas,
        'potreros': potreros,
        'hembras': hembras,
        'machos': machos
    }
    
    return render(request, 'catalogos/animal/nuevo_animal.html', contexto)


# VISTA: LISTA ANIMALES
def listaanimal(request):
    """
    Muestra el listado completo de animales con sus relaciones.
    """
    # Prefetch_related para optimizar consultas de FK
    animalesBdd = Animal.objects.all().select_related(
        'fk_ra', 'fk_potrero_an', 'fk_madre_an', 'fk_padre_an'
    ).order_by('-created_at_an')
    
    # ==========================================
    # TARJETAS ESTADÍSTICAS
    # ==========================================
    total_animales = animalesBdd.count()
    total_activos = animalesBdd.filter(estado_an='activo').count()
    total_terneros = animalesBdd.filter(categoria_an='ternero').count()
    total_vacas_leche = animalesBdd.filter(categoria_an='vaca_leche').count()
    total_toros = animalesBdd.filter(categoria_an='toro').count()
    total_retirados = animalesBdd.filter(estado_an='retirado').count()
    
    return render(request, 'catalogos/animal/lista_animal.html', {
        'animales': animalesBdd,
        'total_animales': total_animales,
        'total_activos': total_activos,
        'total_terneros': total_terneros,
        'total_vacas_leche': total_vacas_leche,
        'total_toros': total_toros,
        'total_retirados': total_retirados,
    })
# VISTA: GUARDAR ANIMAL (procesar creación)
def guardaranimal(request):
    """
    Procesa el formulario de creación de un nuevo animal.
    Valida datos, guarda foto si existe, y registra auditoría.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevoanimal/')
    
    try:
        # ==========================================
        # OBTENER DATOS DEL FORMULARIO
        # ==========================================
        codigo_an = request.POST.get('txt_codigo_an', '').strip().upper()
        nombre_an = request.POST.get('txt_nombre_an', '').strip()
        
        # FK Raza (obligatoria)
        fk_ra_id = request.POST.get('sel_raza_an')
        if not fk_ra_id:
            messages.error(request, "Debe seleccionar una raza")
            return redirect('/nuevoanimal/')
        
        # Sexo (obligatorio)
        sexo_an = request.POST.get('sel_sexo_an')
        if not sexo_an:
            messages.error(request, "Debe seleccionar el sexo")
            return redirect('/nuevoanimal/')
        
        # Fecha nacimiento (obligatoria)
        fecha_nacimiento_an = request.POST.get('txt_fecha_nacimiento_an')
        if not fecha_nacimiento_an:
            messages.error(request, "La fecha de nacimiento es obligatoria")
            return redirect('/nuevoanimal/')
        
        # Pesos (opcionales, decimales) - CORREGIDO PARA DECIMALES
        peso_nacimiento = request.POST.get('txt_peso_nacimiento_an', '').strip()
        peso_nacimiento_kg_an = None
        if peso_nacimiento:
            try:
                peso_nacimiento_kg_an = float(peso_nacimiento)
                if peso_nacimiento_kg_an < 0:
                    messages.error(request, "El peso al nacimiento no puede ser negativo")
                    return redirect('/nuevoanimal/')
            except ValueError:
                messages.error(request, "El peso al nacimiento debe ser un número válido")
                return redirect('/nuevoanimal/')
        
        peso_actual = request.POST.get('txt_peso_actual_an', '').strip()
        peso_actual_kg_an = None
        if peso_actual:
            try:
                peso_actual_kg_an = float(peso_actual)
                if peso_actual_kg_an < 0:
                    messages.error(request, "El peso actual no puede ser negativo")
                    return redirect('/nuevoanimal/')
            except ValueError:
                messages.error(request, "El peso actual debe ser un número válido")
                return redirect('/nuevoanimal/')
        
        # Color (opcional)
        color_an = request.POST.get('txt_color_an', '').strip()
        
        # Señas particulares (opcional)
        senas_particulares_an = request.POST.get('txt_senas_particulares_an', '').strip()
        
        # FK Madre (opcional)
        fk_madre_id = request.POST.get('sel_madre_an')
        fk_madre_an = Animal.objects.get(id_an=fk_madre_id) if fk_madre_id else None
        
        # FK Padre (opcional)
        fk_padre_id = request.POST.get('sel_padre_an')
        fk_padre_an = Animal.objects.get(id_an=fk_padre_id) if fk_padre_id else None
        
        # FK Potrero (opcional)
        fk_potrero_id = request.POST.get('sel_potrero_an')
        fk_potrero_an = Potrero.objects.get(id_po=fk_potrero_id) if fk_potrero_id else None
        
        # Estado (default 'activo')
        estado_an = request.POST.get('sel_estado_an', 'activo')
        
        # Categoría (obligatoria)
        categoria_an = request.POST.get('sel_categoria_an')
        if not categoria_an:
            messages.error(request, "Debe seleccionar una categoría")
            return redirect('/nuevoanimal/')
        
        # Condición corporal (opcional, 1-5)
        condicion = request.POST.get('sel_condicion_corporal_an', '').strip()
        condicion_corporal_an = None
        if condicion:
            try:
                condicion_corporal_an = int(condicion)
                if condicion_corporal_an < 1 or condicion_corporal_an > 5:
                    messages.error(request, "La condición corporal debe estar entre 1 y 5")
                    return redirect('/nuevoanimal/')
            except ValueError:
                messages.error(request, "La condición corporal debe ser un número entero")
                return redirect('/nuevoanimal/')
        
        # Fecha ingreso (obligatoria, default hoy en frontend)
        fecha_ingreso_an = request.POST.get('txt_fecha_ingreso_an')
        if not fecha_ingreso_an:
            messages.error(request, "La fecha de ingreso es obligatoria")
            return redirect('/nuevoanimal/')
        
        # Fecha salida (opcional)
        fecha_salida = request.POST.get('txt_fecha_salida_an', '').strip()
        fecha_salida_an = fecha_salida if fecha_salida else None
        
        # Motivo salida (opcional)
        motivo_salida_an = request.POST.get('txt_motivo_salida_an', '').strip()
        
        # ==========================================
        # VALIDAR CÓDIGO ÚNICO
        # ==========================================
        if Animal.objects.filter(codigo_an=codigo_an).exists():
            messages.error(request, f"Ya existe un animal con el código '{codigo_an}'")
            return redirect('/nuevoanimal/')
        
        # ==========================================
        # GUARDAR FOTO SI EXISTE
        # ==========================================
        foto_path, error_foto = guardar_foto(request, 'file_foto_an')
        if error_foto:
            messages.error(request, error_foto)
            return redirect('/nuevoanimal/')
        
        # ==========================================
        # CREAR ANIMAL
        # ==========================================
        nuevo_animal = Animal.objects.create(
            codigo_an=codigo_an,
            nombre_an=nombre_an if nombre_an else None,
            fk_ra_id=fk_ra_id,
            sexo_an=sexo_an,
            fecha_nacimiento_an=fecha_nacimiento_an,
            peso_nacimiento_kg_an=peso_nacimiento_kg_an,
            peso_actual_kg_an=peso_actual_kg_an,
            color_an=color_an if color_an else None,
            senas_particulares_an=senas_particulares_an if senas_particulares_an else None,
            fk_madre_an=fk_madre_an,
            fk_padre_an=fk_padre_an,
            fk_potrero_an=fk_potrero_an,
            estado_an=estado_an,
            categoria_an=categoria_an,
            condicion_corporal_an=condicion_corporal_an,
            foto_an=foto_path,
            fecha_ingreso_an=fecha_ingreso_an,
            fecha_salida_an=fecha_salida_an,
            motivo_salida_an=motivo_salida_an if motivo_salida_an else None
        )
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'Animal',
            nuevo_animal.id_an,
            f'Se creó el animal: {nuevo_animal.codigo_an} - {nuevo_animal.nombre_an or "Sin nombre"}'
        )
        
        messages.success(request, f"Animal '{nuevo_animal.codigo_an}' guardado exitosamente")
        return redirect('/listaanimal/')
        
    except ValueError as e:
        messages.error(request, f"Error en los datos numéricos: {str(e)}")
        return redirect('/nuevoanimal/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevoanimal/')


# VISTA: ELIMINAR ANIMAL
def eliminaranimal(request, id_an):
    """
    Elimina un animal del sistema.
    Maneja IntegrityError si tiene registros asociados.
    """
    animalBdd = get_object_or_404(Animal, id_an=id_an)
    
    # Guardar datos antes de eliminar para auditoría
    codigo_animal = animalBdd.codigo_an
    nombre_animal = animalBdd.nombre_an
    id_animal = animalBdd.id_an
    
    try:
        # Eliminar foto si existe
        # Eliminar foto de Cloudinary si existe
        if animalBdd.foto_an and 'cloudinary' in animalBdd.foto_an:
            try:
                # Extraer public_id de la URL
                # Ejemplo: https://res.cloudinary.com/dnf7nccg/image/upload/v123/ganado/animales/foto.jpg
                public_id = animalBdd.foto_an.split('/upload/')[-1].split('/')[-1].split('.')[0]
                cloudinary.uploader.destroy(f'ganado/animales/{public_id}')
            except Exception:
                pass  # Si falla, no importa, la foto queda en Cloudinary
        
        animalBdd.delete()
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'Animal',
            id_animal,
            f'Se eliminó el animal: {codigo_animal} - {nombre_animal or "Sin nombre"}'
        )
        
        messages.success(request, f"Animal '{codigo_animal}' eliminado exitosamente")
        
    except IntegrityError:
        messages.error(request, f"No se puede eliminar el animal '{codigo_animal}': tiene registros asociados (movimientos, eventos sanitarios, ordeños, etc.)")
    
    return redirect('/listaanimal/')


# VISTA: EDITAR ANIMAL (formulario)
def editaranimal(request, id_an):
    """
    Muestra el formulario de edición con los datos precargados.
    Resuelve el problema de decimales usando |default:'' en el template.
    """
    animalBdd = get_object_or_404(Animal, id_an=id_an)
    
    # Obtener listas para selects
    razas = Raza.objects.filter(activo_ra=True).order_by('nombre_ra')
    potreros = Potrero.objects.filter(estado_po__in=['disponible', 'ocupado']).order_by('nombre_po')
    
    # Hembras disponibles como madres (excluir el animal actual para evitar auto-padre)
    hembras = Animal.objects.filter(sexo_an='H').exclude(id_an=id_an).order_by('codigo_an')
    
    # Machos disponibles como padres (excluir el animal actual)
    machos = Animal.objects.filter(sexo_an='M').exclude(id_an=id_an).order_by('codigo_an')
    
    contexto = {
        'animal': animalBdd,
        'razas': razas,
        'potreros': potreros,
        'hembras': hembras,
        'machos': machos
    }
    
    return render(request, 'catalogos/animal/editar_animal.html', contexto)


# VISTA: PROCESAR EDICION ANIMAL
def procesareditanimal(request):
    """
    Procesa el formulario de edición de un animal existente.
    Maneja la foto nueva y conserva la actual si no se cambia.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listaanimal/')
    
    try:
        # Obtener animal existente
        id_an = request.POST.get('id_an')
        if not id_an:
            messages.error(request, "ID de animal no proporcionado")
            return redirect('/listaanimal/')
        
        animal = Animal.objects.get(id_an=id_an)
        
        # ==========================================
        # OBTENER DATOS DEL FORMULARIO
        # ==========================================
        codigo_an = request.POST.get('txt_codigo_an', '').strip().upper()
        nombre_an = request.POST.get('txt_nombre_an', '').strip()
        
        # FK Raza (obligatoria)
        fk_ra_id = request.POST.get('sel_raza_an')
        if not fk_ra_id:
            messages.error(request, "Debe seleccionar una raza")
            return redirect(f'/editaranimal/{id_an}')
        
        # Sexo (obligatorio)
        sexo_an = request.POST.get('sel_sexo_an')
        if not sexo_an:
            messages.error(request, "Debe seleccionar el sexo")
            return redirect(f'/editaranimal/{id_an}')
        
        # Fecha nacimiento (obligatoria)
        fecha_nacimiento_an = request.POST.get('txt_fecha_nacimiento_an')
        if not fecha_nacimiento_an:
            messages.error(request, "La fecha de nacimiento es obligatoria")
            return redirect(f'/editaranimal/{id_an}')
        
        # Pesos (opcionales, decimales) - CORREGIDO PARA DECIMALES
        peso_nacimiento = request.POST.get('txt_peso_nacimiento_an', '').strip()
        peso_nacimiento_kg_an = None
        if peso_nacimiento:
            try:
                peso_nacimiento_kg_an = float(peso_nacimiento)
                if peso_nacimiento_kg_an < 0:
                    messages.error(request, "El peso al nacimiento no puede ser negativo")
                    return redirect(f'/editaranimal/{id_an}')
            except ValueError:
                messages.error(request, "El peso al nacimiento debe ser un número válido")
                return redirect(f'/editaranimal/{id_an}')
        
        peso_actual = request.POST.get('txt_peso_actual_an', '').strip()
        peso_actual_kg_an = None
        if peso_actual:
            try:
                peso_actual_kg_an = float(peso_actual)
                if peso_actual_kg_an < 0:
                    messages.error(request, "El peso actual no puede ser negativo")
                    return redirect(f'/editaranimal/{id_an}')
            except ValueError:
                messages.error(request, "El peso actual debe ser un número válido")
                return redirect(f'/editaranimal/{id_an}')
        
        # Color (opcional)
        color_an = request.POST.get('txt_color_an', '').strip()
        
        # Señas particulares (opcional)
        senas_particulares_an = request.POST.get('txt_senas_particulares_an', '').strip()
        
        # FK Madre (opcional)
        fk_madre_id = request.POST.get('sel_madre_an')
        fk_madre_an = Animal.objects.get(id_an=fk_madre_id) if fk_madre_id else None
        
        # FK Padre (opcional)
        fk_padre_id = request.POST.get('sel_padre_an')
        fk_padre_an = Animal.objects.get(id_an=fk_padre_id) if fk_padre_id else None
        
        # FK Potrero (opcional)
        fk_potrero_id = request.POST.get('sel_potrero_an')
        fk_potrero_an = Potrero.objects.get(id_po=fk_potrero_id) if fk_potrero_id else None
        
        # Estado
        estado_an = request.POST.get('sel_estado_an', 'activo')
        
        # Categoría (obligatoria)
        categoria_an = request.POST.get('sel_categoria_an')
        if not categoria_an:
            messages.error(request, "Debe seleccionar una categoría")
            return redirect(f'/editaranimal/{id_an}')
        
        # Condición corporal (opcional, 1-5)
        condicion = request.POST.get('sel_condicion_corporal_an', '').strip()
        condicion_corporal_an = None
        if condicion:
            try:
                condicion_corporal_an = int(condicion)
                if condicion_corporal_an < 1 or condicion_corporal_an > 5:
                    messages.error(request, "La condición corporal debe estar entre 1 y 5")
                    return redirect(f'/editaranimal/{id_an}')
            except ValueError:
                messages.error(request, "La condición corporal debe ser un número entero")
                return redirect(f'/editaranimal/{id_an}')
        
        # Fecha ingreso (obligatoria)
        fecha_ingreso_an = request.POST.get('txt_fecha_ingreso_an')
        if not fecha_ingreso_an:
            messages.error(request, "La fecha de ingreso es obligatoria")
            return redirect(f'/editaranimal/{id_an}')
        
        # Fecha salida (opcional)
        fecha_salida = request.POST.get('txt_fecha_salida_an', '').strip()
        fecha_salida_an = fecha_salida if fecha_salida else None
        
        # Motivo salida (opcional)
        motivo_salida_an = request.POST.get('txt_motivo_salida_an', '').strip()
        
        # ==========================================
        # VALIDAR CÓDIGO ÚNICO (excluyendo el actual)
        # ==========================================
        if Animal.objects.filter(codigo_an=codigo_an).exclude(id_an=id_an).exists():
            messages.error(request, f"Ya existe otro animal con el código '{codigo_an}'")
            return redirect(f'/editaranimal/{id_an}')
        
        # ==========================================
        # MANEJO DE FOTO (CLOUDINARY)
        # ==========================================
        foto_path = animal.foto_an  # Conservar foto actual por defecto

        if 'file_foto_an' in request.FILES:
            # Guardar nueva foto (Cloudinary sobrescribe automáticamente si usas mismo public_id)
            nueva_foto, error_foto = guardar_foto(request, 'file_foto_an')
            if error_foto:
                messages.error(request, error_foto)
                return redirect(f'/editaranimal/{id_an}')
            foto_path = nueva_foto
            # No necesitas eliminar la anterior, Cloudinary maneja el almacenamiento
        
        # Si se envió foto_actual vacía y no hay nueva foto, mantener la actual
        # (el campo hidden foto_actual se usa para referencia)
        
        # ==========================================
        # ACTUALIZAR ANIMAL
        # ==========================================
        animal.codigo_an = codigo_an
        animal.nombre_an = nombre_an if nombre_an else None
        animal.fk_ra_id = fk_ra_id
        animal.sexo_an = sexo_an
        animal.fecha_nacimiento_an = fecha_nacimiento_an
        animal.peso_nacimiento_kg_an = peso_nacimiento_kg_an
        animal.peso_actual_kg_an = peso_actual_kg_an
        animal.color_an = color_an if color_an else None
        animal.senas_particulares_an = senas_particulares_an if senas_particulares_an else None
        animal.fk_madre_an = fk_madre_an
        animal.fk_padre_an = fk_padre_an
        animal.fk_potrero_an = fk_potrero_an
        animal.estado_an = estado_an
        animal.categoria_an = categoria_an
        animal.condicion_corporal_an = condicion_corporal_an
        animal.foto_an = foto_path
        animal.fecha_ingreso_an = fecha_ingreso_an
        animal.fecha_salida_an = fecha_salida_an
        animal.motivo_salida_an = motivo_salida_an if motivo_salida_an else None
        
        animal.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'Animal',
            animal.id_an,
            f'Se editó el animal: {animal.codigo_an} - {animal.nombre_an or "Sin nombre"}'
        )
        
        messages.success(request, f"Animal '{animal.codigo_an}' actualizado exitosamente")
        return redirect('/listaanimal/')
        
    except Animal.DoesNotExist:
        messages.error(request, "Animal no encontrado")
        return redirect('/listaanimal/')
    except ValueError as e:
        messages.error(request, f"Error en los datos numéricos: {str(e)}")
        return redirect(f'/editaranimal/{id_an}')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editaranimal/{id_an}')


# VISTA: DETALLE ANIMAL (opcional, para el botón de ojo)
def detalleanimal(request, id_an):
    """
    Muestra el detalle completo de un animal con todas sus relaciones.
    """
    animal = get_object_or_404(
        Animal.objects.select_related(
            'fk_ra', 'fk_potrero_an', 'fk_madre_an', 'fk_padre_an'
        ),
        id_an=id_an
    )
    
    # Obtener registros relacionados (ajusta según tus modelos)
    # movimientos = MovimientoAnimal.objects.filter(fk_an=animal).order_by('-fecha_ma')
    # eventos_sanitarios = EventoSanitario.objects.filter(fk_an=animal).order_by('-fecha_programada_es')
    # pesajes = Pesaje.objects.filter(fk_an=animal).order_by('-fecha_pe')
    # ordeños = Ordeno.objects.filter(fk_an=animal).order_by('-fecha_or')
    
    contexto = {
        'animal': animal,
        # 'movimientos': movimientos,
        # 'eventos_sanitarios': eventos_sanitarios,
        # 'pesajes': pesajes,
        # 'ordeños': ordeños,
    }
    
    return render(request, 'catalogos/animales/detalle_animal.html', contexto)



# ==========================================
# MOVIMIENTOS DE ANIMALES
# ==========================================

def listamovimiento(request):
    """
    Muestra el listado completo de movimientos con estadísticas por tipo.
    Incluye conteos agregados para el dashboard superior.
    """
    movimientos = MovimientoAnimal.objects.all().select_related(
        'fk_an', 'fk_potrero_origen_ma', 'fk_potrero_destino_ma', 'fk_us_ma'
    ).order_by('-fecha_ma', '-created_at_ma')
    
    # Estadísticas generales
    total_movimientos = movimientos.count()
    total_compras = movimientos.filter(tipo_movimiento_ma='compra').count()
    total_ventas = movimientos.filter(tipo_movimiento_ma='venta').count()
    total_traslados = movimientos.filter(tipo_movimiento_ma='traslado').count()
    total_nacimientos = movimientos.filter(tipo_movimiento_ma='nacimiento').count()
    total_muertes = movimientos.filter(tipo_movimiento_ma='muerte').count()
    
    contexto = {
        'movimientos': movimientos,
        'total_movimientos': total_movimientos,
        'total_compras': total_compras,
        'total_ventas': total_ventas,
        'total_traslados': total_traslados,
        'total_nacimientos': total_nacimientos,
        'total_muertes': total_muertes,
    }
    
    return render(request, 'catalogos/animal/movimientos/lista_movimiento.html', contexto)

# VISTA: NUEVO MOVIMIENTO (formulario)
def nuevomovimiento(request):
    """
    Muestra el formulario para registrar un nuevo movimiento.
    Carga listas de animales activos y potreros disponibles.
    """
    # Animales activos para el select (excluir muertos, vendidos, faenados)
    animales = Animal.objects.filter(
        estado_an='activo'
    ).select_related('fk_ra').order_by('codigo_an')
    
    # Potreros disponibles u ocupados para origen/destino
    potreros = Potrero.objects.filter(
        estado_po__in=['disponible', 'ocupado']
    ).order_by('codigo_po')
    
    contexto = {
        'animales': animales,
        'potreros': potreros,
    }
    
    return render(request, 'catalogos/animal/movimientos/nuevo_movimiento.html', contexto)


# VISTA: GUARDAR MOVIMIENTO (procesar creación)
def guardarmovimiento(request):
    """
    Procesa el formulario de creación de un nuevo movimiento.
    Valida datos, verifica reglas de negocio según tipo, y registra auditoría.
    Actualiza estado del animal y potrero según corresponda.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevomovimiento/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Tipo de movimiento (obligatorio)
        tipo_movimiento_ma = request.POST.get('sel_tipo_movimiento_ma')
        tipos_validos = ['compra', 'venta', 'traslado', 'nacimiento', 'muerte', 'faena']
        if not tipo_movimiento_ma or tipo_movimiento_ma not in tipos_validos:
            messages.error(request, "Seleccione un tipo de movimiento válido")
            return redirect('/nuevomovimiento/')
        
        # Fecha (obligatoria)
        fecha_ma = request.POST.get('txt_fecha_ma')
        if not fecha_ma:
            messages.error(request, "La fecha del movimiento es obligatoria")
            return redirect('/nuevomovimiento/')
        
        # Animal (obligatorio)
        fk_an_id = request.POST.get('sel_animal_ma')
        if not fk_an_id:
            messages.error(request, "Debe seleccionar un animal")
            return redirect('/nuevomovimiento/')
        
        animal = get_object_or_404(Animal, id_an=fk_an_id)
        
        # Validar que el animal esté activo (excepto para compra/nacimiento)
        if tipo_movimiento_ma not in ['compra', 'nacimiento'] and animal.estado_an != 'activo':
            messages.error(request, f"El animal {animal.codigo_an} no está activo. Solo se pueden mover animales activos.")
            return redirect('/nuevomovimiento/')
        
        # Potreros (condicionales según tipo)
        fk_potrero_origen_ma = None
        fk_potrero_destino_ma = None
        
        potrero_origen_id = request.POST.get('sel_potrero_origen_ma')
        potrero_destino_id = request.POST.get('sel_potrero_destino_ma')
        
        # Validaciones específicas por tipo
        if tipo_movimiento_ma == 'traslado':
            if not potrero_origen_id or not potrero_destino_id:
                messages.error(request, "Para traslados se requiere potrero origen y destino")
                return redirect('/nuevomovimiento/')
            if potrero_origen_id == potrero_destino_id:
                messages.error(request, "El potrero origen y destino no pueden ser el mismo")
                return redirect('/nuevomovimiento/')
            fk_potrero_origen_ma = Potrero.objects.get(id_po=potrero_origen_id)
            fk_potrero_destino_ma = Potrero.objects.get(id_po=potrero_destino_id)
            
        elif tipo_movimiento_ma in ['compra', 'nacimiento']:
            if not potrero_destino_id:
                messages.error(request, f"Para {tipo_movimiento_ma} se requiere potrero destino")
                return redirect('/nuevomovimiento/')
            fk_potrero_destino_ma = Potrero.objects.get(id_po=potrero_destino_id)
            
        elif tipo_movimiento_ma in ['venta', 'muerte', 'faena']:
            if not potrero_origen_id:
                messages.error(request, f"Para {tipo_movimiento_ma} se requiere potrero origen")
                return redirect('/nuevomovimiento/')
            fk_potrero_origen_ma = Potrero.objects.get(id_po=potrero_origen_id)
        
        # Precio (obligatorio para compra/venta)
        precio_ma = None
        if tipo_movimiento_ma in ['compra', 'venta']:
            precio_str = request.POST.get('txt_precio_ma', '').strip()
            if not precio_str:
                messages.error(request, "El precio es obligatorio para compras y ventas")
                return redirect('/nuevomovimiento/')
            try:
                precio_ma = float(precio_str)
                if precio_ma < 0:
                    messages.error(request, "El precio no puede ser negativo")
                    return redirect('/nuevomovimiento/')
                if precio_ma > 99999999.99:
                    messages.error(request, "El precio excede el máximo permitido")
                    return redirect('/nuevomovimiento/')
            except ValueError:
                messages.error(request, "El precio debe ser un número válido")
                return redirect('/nuevomovimiento/')
        
        # Comprador/vendedor (opcional)
        comprador_vendedor_ma = request.POST.get('txt_comprador_vendedor_ma', '').strip()
        if comprador_vendedor_ma and len(comprador_vendedor_ma) > 200:
            messages.error(request, "El nombre del comprador/vendedor excede 200 caracteres")
            return redirect('/nuevomovimiento/')
        
        # Documento soporte (opcional)
        documento_soporte_ma = request.POST.get('txt_documento_soporte_ma', '').strip()
        if documento_soporte_ma and len(documento_soporte_ma) > 255:
            messages.error(request, "El documento soporte excede 255 caracteres")
            return redirect('/nuevomovimiento/')
        
        # Motivo (opcional)
        motivo_ma = request.POST.get('txt_motivo_ma', '').strip()
        if motivo_ma and len(motivo_ma) > 1000:
            messages.error(request, "El motivo excede 1000 caracteres")
            return redirect('/nuevomovimiento/')
        
        # Usuario actual (obligatorio - del request)
        # fk_us_ma = request.user.usuario  # Ajusta según tu modelo de usuario
        # Por ahora, obtener el primer usuario administrador o el de la sesión
        try:
            fk_us_ma = Usuario.objects.get(id_us=request.session.get('id_us', 1))
        except Usuario.DoesNotExist:
            messages.error(request, "Error de autenticación de usuario")
            return redirect('/nuevomovimiento/')
        
        # ==========================================
        # CREAR MOVIMIENTO
        # ==========================================
        nuevo_movimiento = MovimientoAnimal.objects.create(
            fk_an=animal,
            tipo_movimiento_ma=tipo_movimiento_ma,
            fecha_ma=fecha_ma,
            motivo_ma=motivo_ma if motivo_ma else None,
            fk_potrero_origen_ma=fk_potrero_origen_ma,
            fk_potrero_destino_ma=fk_potrero_destino_ma,
            precio_ma=precio_ma,
            comprador_vendedor_ma=comprador_vendedor_ma if comprador_vendedor_ma else None,
            documento_soporte_ma=documento_soporte_ma if documento_soporte_ma else None,
            fk_us_ma=fk_us_ma
        )
        
        # ==========================================
        # ACTUALIZAR ESTADO DEL ANIMAL SEGUN TIPO
        # ==========================================
        if tipo_movimiento_ma == 'venta':
            animal.estado_an = 'vendido'
            animal.fecha_salida_an = fecha_ma
            animal.motivo_salida_an = f"Venta - {comprador_vendedor_ma or 'Sin comprador'}"
            animal.save()
        elif tipo_movimiento_ma == 'muerte':
            animal.estado_an = 'muerto'
            animal.fecha_salida_an = fecha_ma
            animal.motivo_salida_an = f"Muerte - {motivo_ma or 'Sin observaciones'}"
            animal.save()
        elif tipo_movimiento_ma == 'faena':
            animal.estado_an = 'faenado'
            animal.fecha_salida_an = fecha_ma
            animal.motivo_salida_an = f"Faena - {motivo_ma or 'Sin observaciones'}"
            animal.save()
        elif tipo_movimiento_ma == 'traslado':
            # Actualizar potrero del animal al destino
            animal.fk_potrero_an = fk_potrero_destino_ma
            animal.save()
        elif tipo_movimiento_ma == 'compra' or tipo_movimiento_ma == 'nacimiento':
            # Asignar potrero destino al animal
            animal.fk_potrero_an = fk_potrero_destino_ma
            animal.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'MovimientoAnimal',
            nuevo_movimiento.id_ma,
            f'Se creó movimiento de {tipo_movimiento_ma}: {animal.codigo_an} - Fecha: {fecha_ma}'
        )
        
        messages.success(request, f"Movimiento de {tipo_movimiento_ma.upper()} para '{animal.codigo_an}' guardado exitosamente")
        return redirect('/listamovimiento/')
        
    except Potrero.DoesNotExist:
        messages.error(request, "Potrero no encontrado")
        return redirect('/nuevomovimiento/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect('/nuevomovimiento/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevomovimiento/')

# VISTA: EDITAR MOVIMIENTO (formulario)
def editarmovimiento(request, id_ma):
    """
    Muestra el formulario de edición con los datos precargados.
    El tipo de movimiento no se puede cambiar.
    """
    movimiento = get_object_or_404(
        MovimientoAnimal.objects.select_related('fk_an', 'fk_potrero_origen_ma', 'fk_potrero_destino_ma', 'fk_us_ma'),
        id_ma=id_ma
    )
    
    # Animales disponibles (incluir el actual aunque no esté activo)
    animales = Animal.objects.filter(
        Q(estado_an='activo') | Q(id_an=movimiento.fk_an_id)
    ).select_related('fk_ra').order_by('codigo_an')
    
    # Potreros disponibles
    potreros = Potrero.objects.filter(
        estado_po__in=['disponible', 'ocupado']
    ).order_by('codigo_po')
    
    contexto = {
        'movimiento': movimiento,
        'animales': animales,
        'potreros': potreros,
    }
    
    return render(request, 'catalogos/animal/movimientos/editar_movimiento.html', contexto)

# VISTA: PROCESAR EDICION MOVIMIENTO
def procesareditarmovimiento(request):
    """
    Procesa el formulario de edición de un movimiento existente.
    El tipo de movimiento no se puede modificar.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listamovimiento/')
    
    try:
        # Obtener movimiento existente
        id_ma = request.POST.get('id_ma')
        if not id_ma:
            messages.error(request, "ID de movimiento no proporcionado")
            return redirect('/listamovimiento/')
        
        movimiento = MovimientoAnimal.objects.get(id_ma=id_ma)
        tipo_original = movimiento.tipo_movimiento_ma
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha (obligatoria)
        fecha_ma = request.POST.get('txt_fecha_ma')
        if not fecha_ma:
            messages.error(request, "La fecha del movimiento es obligatoria")
            return redirect(f'/editarmovimiento/{id_ma}')
        
        # Animal (obligatorio)
        fk_an_id = request.POST.get('sel_animal_ma')
        if not fk_an_id:
            messages.error(request, "Debe seleccionar un animal")
            return redirect(f'/editarmovimiento/{id_ma}')
        
        animal = get_object_or_404(Animal, id_an=fk_an_id)
        
        # Potreros (condicionales según tipo original)
        fk_potrero_origen_ma = None
        fk_potrero_destino_ma = None
        
        potrero_origen_id = request.POST.get('sel_potrero_origen_ma')
        potrero_destino_id = request.POST.get('sel_potrero_destino_ma')
        
        if tipo_original == 'traslado':
            if not potrero_origen_id or not potrero_destino_id:
                messages.error(request, "Para traslados se requiere potrero origen y destino")
                return redirect(f'/editarmovimiento/{id_ma}')
            if potrero_origen_id == potrero_destino_id:
                messages.error(request, "El potrero origen y destino no pueden ser el mismo")
                return redirect(f'/editarmovimiento/{id_ma}')
            fk_potrero_origen_ma = Potrero.objects.get(id_po=potrero_origen_id)
            fk_potrero_destino_ma = Potrero.objects.get(id_po=potrero_destino_id)
            
        elif tipo_original in ['compra', 'nacimiento']:
            if not potrero_destino_id:
                messages.error(request, f"Para {tipo_original} se requiere potrero destino")
                return redirect(f'/editarmovimiento/{id_ma}')
            fk_potrero_destino_ma = Potrero.objects.get(id_po=potrero_destino_id)
            
        elif tipo_original in ['venta', 'muerte', 'faena']:
            if not potrero_origen_id:
                messages.error(request, f"Para {tipo_original} se requiere potrero origen")
                return redirect(f'/editarmovimiento/{id_ma}')
            fk_potrero_origen_ma = Potrero.objects.get(id_po=potrero_origen_id)
        
        # Precio (obligatorio para compra/venta)
        precio_ma = None
        if tipo_original in ['compra', 'venta']:
            precio_str = request.POST.get('txt_precio_ma', '').strip()
            if not precio_str:
                messages.error(request, "El precio es obligatorio para compras y ventas")
                return redirect(f'/editarmovimiento/{id_ma}')
            try:
                precio_ma = float(precio_str)
                if precio_ma < 0:
                    messages.error(request, "El precio no puede ser negativo")
                    return redirect(f'/editarmovimiento/{id_ma}')
                if precio_ma > 99999999.99:
                    messages.error(request, "El precio excede el máximo permitido")
                    return redirect(f'/editarmovimiento/{id_ma}')
            except ValueError:
                messages.error(request, "El precio debe ser un número válido")
                return redirect(f'/editarmovimiento/{id_ma}')
        
        # Comprador/vendedor
        comprador_vendedor_ma = request.POST.get('txt_comprador_vendedor_ma', '').strip()
        if comprador_vendedor_ma and len(comprador_vendedor_ma) > 200:
            messages.error(request, "El nombre excede 200 caracteres")
            return redirect(f'/editarmovimiento/{id_ma}')
        
        # Documento soporte
        documento_soporte_ma = request.POST.get('txt_documento_soporte_ma', '').strip()
        if documento_soporte_ma and len(documento_soporte_ma) > 255:
            messages.error(request, "El documento excede 255 caracteres")
            return redirect(f'/editarmovimiento/{id_ma}')
        
        # Motivo
        motivo_ma = request.POST.get('txt_motivo_ma', '').strip()
        if motivo_ma and len(motivo_ma) > 1000:
            messages.error(request, "El motivo excede 1000 caracteres")
            return redirect(f'/editarmovimiento/{id_ma}')
        
        # ==========================================
        # ACTUALIZAR MOVIMIENTO
        # ==========================================
        movimiento.fecha_ma = fecha_ma
        movimiento.fk_an = animal
        movimiento.motivo_ma = motivo_ma if motivo_ma else None
        movimiento.fk_potrero_origen_ma = fk_potrero_origen_ma
        movimiento.fk_potrero_destino_ma = fk_potrero_destino_ma
        movimiento.precio_ma = precio_ma
        movimiento.comprador_vendedor_ma = comprador_vendedor_ma if comprador_vendedor_ma else None
        movimiento.documento_soporte_ma = documento_soporte_ma if documento_soporte_ma else None
        
        movimiento.save()
        
        # ==========================================
        # ACTUALIZAR ANIMAL SI CAMBIÓ
        # ==========================================
        if tipo_original in ['traslado', 'compra', 'nacimiento']:
            animal.fk_potrero_an = fk_potrero_destino_ma
            animal.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'MovimientoAnimal',
            movimiento.id_ma,
            f'Se editó movimiento de {tipo_original}: {animal.codigo_an}'
        )
        
        messages.success(request, f"Movimiento de {tipo_original.upper()} actualizado exitosamente")
        return redirect('/listamovimiento/')
        
    except MovimientoAnimal.DoesNotExist:
        messages.error(request, "Movimiento no encontrado")
        return redirect('/listamovimiento/')
    except Potrero.DoesNotExist:
        messages.error(request, "Potrero no encontrado")
        return redirect(f'/editarmovimiento/{id_ma}')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect(f'/editarmovimiento/{id_ma}')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarmovimiento/{id_ma}')


# VISTA: ELIMINAR MOVIMIENTO
def eliminarmovimiento(request, id_ma):
    """
    Elimina un movimiento del sistema.
    REVIERTE el estado del animal si es compra/venta/muerte/faena.
    """
    movimiento = get_object_or_404(
        MovimientoAnimal.objects.select_related('fk_an'),
        id_ma=id_ma
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_movimiento = movimiento.id_ma
    tipo_mov = movimiento.tipo_movimiento_ma
    codigo_animal = movimiento.fk_an.codigo_an
    animal = movimiento.fk_an
    
    try:
        # ==========================================
        # REVERTIR ESTADO DEL ANIMAL SI APLICA
        # ==========================================
        if tipo_mov in ['venta', 'muerte', 'faena']:
            # Revertir a activo (asumiendo que volvió a la hacienda)
            animal.estado_an = 'activo'
            animal.fecha_salida_an = None
            animal.motivo_salida_an = None
            animal.save()
            messages.info(request, f"El animal {codigo_animal} ha sido revertido a estado ACTIVO")
        
        # ==========================================
        # ELIMINAR MOVIMIENTO
        # ==========================================
        movimiento.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'MovimientoAnimal',
            id_movimiento,
            f'Se eliminó movimiento de {tipo_mov}: {codigo_animal}'
        )
        
        messages.success(request, f"Movimiento de {tipo_mov.upper()} eliminado exitosamente")
        
    except IntegrityError:
        messages.error(request, f"No se puede eliminar el movimiento: tiene registros asociados")
    
    return redirect('/listamovimiento/')

# ==========================================
# EVENTOS SANITARIOS
# ==========================================
def listaeventosanitario(request):
    """
    Muestra el listado completo de eventos sanitarios con estadísticas.
    Incluye conteos por estado y costo total.
    """
    eventos = EventoSanitario.objects.all().select_related(
        'fk_an', 'fk_pv', 'fk_us_es'
    ).order_by('-fecha_programada_es', '-created_at_es')
    
    # Estadísticas generales
    total_eventos = eventos.count()
    total_pendientes = eventos.filter(estado_es='pendiente').count()
    total_ejecutados = eventos.filter(estado_es='ejecutado').count()
    total_cancelados = eventos.filter(estado_es='cancelado').count()
    total_pospuestos = eventos.filter(estado_es='pospuesto').count()
    
    # Costo total de eventos ejecutados
    costo_total = eventos.filter(
        estado_es='ejecutado'
    ).aggregate(total=Sum('costo_es'))['total'] or 0
    
    contexto = {
        'eventos': eventos,
        'total_eventos': total_eventos,
        'total_pendientes': total_pendientes,
        'total_ejecutados': total_ejecutados,
        'total_cancelados': total_cancelados,
        'total_pospuestos': total_pospuestos,
        'costo_total': costo_total,
    }
    
    return render(request, 'catalogos/animal/eventosS/lista_evento.html', contexto)


# ==========================================
# VISTA: NUEVO EVENTO SANITARIO (formulario)
# ==========================================
def nuevoeventosanitario(request):
    """
    Muestra el formulario para registrar un nuevo evento sanitario.
    Carga listas de animales activos y productos veterinarios disponibles.
    """
    # Animales activos para el select
    animales = Animal.objects.filter(
        estado_an='activo'
    ).select_related('fk_ra').order_by('codigo_an')
    
    # Productos veterinarios activos con stock
    productos = ProductoVeterinario.objects.filter(
        activo_pv=True,
        stock_pv__gt=0
    ).order_by('nombre_pv')
    
    contexto = {
        'animales': animales,
        'productos': productos,
    }
    
    return render(request, 'catalogos/animal/eventosS/nuevo_evento.html', contexto)


# ==========================================
# VISTA: GUARDAR EVENTO SANITARIO (procesar creación)
# ==========================================
def guardareventosanitario(request):
    """
    Procesa el formulario de creación de un nuevo evento sanitario.
    Valida datos, verifica reglas de negocio, y registra auditoría.
    Actualiza stock de producto veterinario si aplica.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevoeventosanitario/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Tipo de evento (obligatorio)
        tipo_evento_es = request.POST.get('sel_tipo_evento_es')
        tipos_validos = ['vacunacion', 'desparasitacion', 'vitaminacion', 
                        'prueba_tuberculosis', 'prueba_brucelosis', 'otro']
        if not tipo_evento_es or tipo_evento_es not in tipos_validos:
            messages.error(request, "Seleccione un tipo de evento válido")
            return redirect('/nuevoeventosanitario/')
        
        # Fecha programada (obligatoria)
        fecha_programada_es = request.POST.get('txt_fecha_programada_es')
        if not fecha_programada_es:
            messages.error(request, "La fecha programada es obligatoria")
            return redirect('/nuevoeventosanitario/')
        
        # Animal (obligatorio)
        fk_an_id = request.POST.get('sel_animal_es')
        if not fk_an_id:
            messages.error(request, "Debe seleccionar un animal")
            return redirect('/nuevoeventosanitario/')
        
        animal = get_object_or_404(Animal, id_an=fk_an_id)
        
        # Validar que el animal esté activo
        if animal.estado_an != 'activo':
            messages.error(request, f"El animal {animal.codigo_an} no está activo. Solo se pueden programar eventos para animales activos.")
            return redirect('/nuevoeventosanitario/')
        
        # Estado (obligatorio)
        estado_es = request.POST.get('sel_estado_es')
        estados_validos = ['pendiente', 'ejecutado', 'cancelado', 'pospuesto']
        if not estado_es or estado_es not in estados_validos:
            messages.error(request, "Seleccione un estado válido")
            return redirect('/nuevoeventosanitario/')
        
        # Fecha ejecutada (condicional)
        fecha_ejecutada_es = None
        if estado_es == 'ejecutado':
            fecha_ejecutada_str = request.POST.get('txt_fecha_ejecutada_es', '').strip()
            if not fecha_ejecutada_str:
                messages.error(request, "La fecha ejecutada es obligatoria cuando el estado es 'Ejecutado'")
                return redirect('/nuevoeventosanitario/')
            fecha_ejecutada_es = fecha_ejecutada_str
            # Validar que fecha ejecutada >= fecha programada
            if fecha_ejecutada_es < fecha_programada_es:
                messages.error(request, "La fecha ejecutada no puede ser anterior a la fecha programada")
                return redirect('/nuevoeventosanitario/')
        
        # Producto veterinario (condicional según tipo)
        fk_pv = None
        producto_id = request.POST.get('sel_producto_es', '').strip()
        
        if tipo_evento_es in ['vacunacion', 'desparasitacion', 'vitaminacion']:
            if not producto_id:
                messages.error(request, f"El producto veterinario es obligatorio para {tipo_evento_es}")
                return redirect('/nuevoeventosanitario/')
            fk_pv = get_object_or_404(ProductoVeterinario, id_pv=producto_id)
            # Validar que tenga stock
            if fk_pv.stock_pv <= 0:
                messages.error(request, f"El producto {fk_pv.nombre_pv} no tiene stock disponible")
                return redirect('/nuevoeventosanitario/')
        
        elif producto_id:
            fk_pv = ProductoVeterinario.objects.filter(id_pv=producto_id).first()
        
        # Dosis (opcional, pero validar formato)
        dosis_es = None
        dosis_str = request.POST.get('txt_dosis_es', '').strip()

        if dosis_str:
            try:
                dosis_es = Decimal(dosis_str)

                if dosis_es < 0:
                    messages.error(request, "La dosis no puede ser negativa")
                    return redirect('/nuevoeventosanitario/')

                if dosis_es > 999999.99:
                    messages.error(request, "La dosis excede el máximo permitido")
                    return redirect('/nuevoeventosanitario/')

                # Validar que hay suficiente stock si hay producto y dosis
                if fk_pv and dosis_es > fk_pv.stock_pv:
                    messages.error(request, f"Dosis ({dosis_es}) excede el stock disponible ({fk_pv.stock_pv})")
                    return redirect('/nuevoeventosanitario/')

            except ValueError:
                messages.error(request, "La dosis debe ser un número válido")
                return redirect('/nuevoeventosanitario/')
        
        # Vía de administración (opcional)
        via_administracion_es = request.POST.get('sel_via_administracion_es', '').strip()
        vias_validas = ['oral', 'subcutanea', 'intramuscular', 'intravenosa', 'topica']
        if via_administracion_es and via_administracion_es not in vias_validas:
            messages.error(request, "Vía de administración no válida")
            return redirect('/nuevoeventosanitario/')
        
        # Veterinario responsable (opcional)
        veterinario_responsable_es = request.POST.get('txt_veterinario_responsable_es', '').strip()
        if veterinario_responsable_es and len(veterinario_responsable_es) > 100:
            messages.error(request, "El nombre del veterinario excede 100 caracteres")
            return redirect('/nuevoeventosanitario/')
        
        # Resultado (opcional)
        resultado_es = request.POST.get('txt_resultado_es', '').strip()
        if resultado_es and len(resultado_es) > 1000:
            messages.error(request, "El resultado excede 1000 caracteres")
            return redirect('/nuevoeventosanitario/')
        
        # Costo (opcional)
        costo_es = None
        costo_str = request.POST.get('txt_costo_es', '').strip()

        if costo_str:
            try:
                costo_es = Decimal(costo_str)

                if costo_es < 0:
                    messages.error(request, "El costo no puede ser negativo")
                    return redirect('/nuevoeventosanitario/')

                if costo_es > Decimal('999999.99'):
                    messages.error(request, "El costo excede el máximo permitido")
                    return redirect('/nuevoeventosanitario/')

            except InvalidOperation:
                messages.error(request, "El costo debe ser un número válido")
                return redirect('/nuevoeventosanitario/')
        
        # Usuario actual (obligatorio)
        try:
            fk_us_es = Usuario.objects.get(id_us=request.session.get('id_us', 1))
        except Usuario.DoesNotExist:
            messages.error(request, "Error de autenticación de usuario")
            return redirect('/nuevoeventosanitario/')
        
        # ==========================================
        # CREAR EVENTO SANITARIO
        # ==========================================
        nuevo_evento = EventoSanitario.objects.create(
            fk_an=animal,
            tipo_evento_es=tipo_evento_es,
            fecha_programada_es=fecha_programada_es,
            fecha_ejecutada_es=fecha_ejecutada_es,
            estado_es=estado_es,
            fk_pv=fk_pv,
            dosis_es=dosis_es,
            via_administracion_es=via_administracion_es if via_administracion_es else None,
            veterinario_responsable_es=veterinario_responsable_es if veterinario_responsable_es else None,
            resultado_es=resultado_es if resultado_es else None,
            costo_es=costo_es,
            fk_us_es=fk_us_es
        )
        
        # ==========================================
        # ACTUALIZAR STOCK DE PRODUCTO SI APLICA
        # ==========================================
        if fk_pv and dosis_es and estado_es == 'ejecutado':
            fk_pv.stock_pv = max(0, fk_pv.stock_pv - dosis_es)
            fk_pv.save()
            messages.info(request, f"Stock de {fk_pv.nombre_pv} actualizado: {fk_pv.stock_pv} {fk_pv.unidad_medida_pv} restantes")
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'EventoSanitario',
            nuevo_evento.id_es,
            f'Se creó evento de {tipo_evento_es}: {animal.codigo_an} - Fecha: {fecha_programada_es}'
        )
        
        messages.success(request, f"Evento de {tipo_evento_es.upper()} para '{animal.codigo_an}' guardado exitosamente")
        return redirect('/listaeventosanitario/')
        
    except ProductoVeterinario.DoesNotExist:
        messages.error(request, "Producto veterinario no encontrado")
        return redirect('/nuevoeventosanitario/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect('/nuevoeventosanitario/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevoeventosanitario/')


# ==========================================
# VISTA: EDITAR EVENTO SANITARIO (formulario)
# ==========================================
def editareventosanitario(request, id_es):
    """
    Muestra el formulario de edición con los datos precargados.
    El tipo de evento no se puede cambiar.
    """
    evento = get_object_or_404(
        EventoSanitario.objects.select_related('fk_an', 'fk_pv', 'fk_us_es'),
        id_es=id_es
    )
    
    # Animales disponibles (incluir el actual aunque no esté activo)
    animales = Animal.objects.filter(
        Q(estado_an='activo') | Q(id_an=evento.fk_an_id)
    ).select_related('fk_ra').order_by('codigo_an')
    
    # Productos veterinarios activos con stock (incluir el actual si ya no tiene stock)
    productos = ProductoVeterinario.objects.filter(
        Q(activo_pv=True, stock_pv__gt=0) | Q(id_pv=evento.fk_pv_id)
    ).order_by('nombre_pv')
    
    contexto = {
        'evento': evento,
        'animales': animales,
        'productos': productos,
    }
    
    return render(request, 'catalogos/animal/eventosS/editar_evento.html', contexto)


# ==========================================
# VISTA: PROCESAR EDICION EVENTO SANITARIO
# ==========================================
def procesareditareventosanitario(request):
    """
    Procesa el formulario de edición de un evento sanitario existente.
    El tipo de evento no se puede modificar.
    Maneja cambio de stock de producto si cambia la dosis o estado.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listaeventosanitario/')
    
    try:
        # Obtener evento existente
        id_es = request.POST.get('id_es')
        if not id_es:
            messages.error(request, "ID de evento no proporcionado")
            return redirect('/listaeventosanitario/')
        
        evento = EventoSanitario.objects.select_related('fk_pv').get(id_es=id_es)
        tipo_original = evento.tipo_evento_es
        estado_anterior = evento.estado_es
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha programada (obligatoria)
        fecha_programada_es = request.POST.get('txt_fecha_programada_es')
        if not fecha_programada_es:
            messages.error(request, "La fecha programada es obligatoria")
            return redirect(f'/editareventosanitario/{id_es}')
        
        # Animal (obligatorio)
        fk_an_id = request.POST.get('sel_animal_es')
        if not fk_an_id:
            messages.error(request, "Debe seleccionar un animal")
            return redirect(f'/editareventosanitario/{id_es}')
        
        animal = get_object_or_404(Animal, id_an=fk_an_id)
        
        # Estado (obligatorio)
        estado_es = request.POST.get('sel_estado_es')
        estados_validos = ['pendiente', 'ejecutado', 'cancelado', 'pospuesto']
        if not estado_es or estado_es not in estados_validos:
            messages.error(request, "Seleccione un estado válido")
            return redirect(f'/editareventosanitario/{id_es}')
        
        # Fecha ejecutada (condicional)
        fecha_ejecutada_es = None
        if estado_es == 'ejecutado':
            fecha_ejecutada_str = request.POST.get('txt_fecha_ejecutada_es', '').strip()
            if not fecha_ejecutada_str:
                messages.error(request, "La fecha ejecutada es obligatoria cuando el estado es 'Ejecutado'")
                return redirect(f'/editareventosanitario/{id_es}')
            fecha_ejecutada_es = fecha_ejecutada_str
            if fecha_ejecutada_es < fecha_programada_es:
                messages.error(request, "La fecha ejecutada no puede ser anterior a la fecha programada")
                return redirect(f'/editareventosanitario/{id_es}')
        
        # Producto veterinario (condicional según tipo original)
        fk_pv = None
        producto_id = request.POST.get('sel_producto_es', '').strip()
        
        if tipo_original in ['vacunacion', 'desparasitacion', 'vitaminacion']:
            if not producto_id:
                messages.error(request, f"El producto veterinario es obligatorio para {tipo_original}")
                return redirect(f'/editareventosanitario/{id_es}')
            fk_pv = get_object_or_404(ProductoVeterinario, id_pv=producto_id)
            # Validar stock si se va a ejecutar
            if estado_es == 'ejecutado' and fk_pv.stock_pv <= 0:
                messages.error(request, f"El producto {fk_pv.nombre_pv} no tiene stock disponible")
                return redirect(f'/editareventosanitario/{id_es}')
        elif producto_id:
            fk_pv = ProductoVeterinario.objects.filter(id_pv=producto_id).first()
        
        # Dosis (opcional)
        dosis_es = None
        dosis_str = request.POST.get('txt_dosis_es', '').strip()

        if dosis_str:
            try:
                dosis_es = Decimal(dosis_str)

                if dosis_es < 0:
                    messages.error(request, "La dosis no puede ser negativa")
                    return redirect(f'/editareventosanitario/{id_es}')

                if dosis_es > Decimal('999999.99'):
                    messages.error(request, "La dosis excede el máximo permitido")
                    return redirect(f'/editareventosanitario/{id_es}')

                if fk_pv and estado_es == 'ejecutado' and dosis_es > fk_pv.stock_pv:
                    messages.error(
                        request,
                        f"Dosis ({dosis_es}) excede el stock disponible ({fk_pv.stock_pv})"
                    )
                    return redirect(f'/editareventosanitario/{id_es}')

            except InvalidOperation:
                messages.error(request, "La dosis debe ser un número válido")
                return redirect(f'/editareventosanitario/{id_es}')
        
        # Vía de administración
        via_administracion_es = request.POST.get('sel_via_administracion_es', '').strip()
        vias_validas = ['oral', 'subcutanea', 'intramuscular', 'intravenosa', 'topica']
        if via_administracion_es and via_administracion_es not in vias_validas:
            messages.error(request, "Vía de administración no válida")
            return redirect(f'/editareventosanitario/{id_es}')
        
        # Veterinario responsable
        veterinario_responsable_es = request.POST.get('txt_veterinario_responsable_es', '').strip()
        if veterinario_responsable_es and len(veterinario_responsable_es) > 100:
            messages.error(request, "El nombre del veterinario excede 100 caracteres")
            return redirect(f'/editareventosanitario/{id_es}')
        
        # Resultado
        resultado_es = request.POST.get('txt_resultado_es', '').strip()
        if resultado_es and len(resultado_es) > 1000:
            messages.error(request, "El resultado excede 1000 caracteres")
            return redirect(f'/editareventosanitario/{id_es}')
        
        # Costo
        costo_es = None
        costo_str = request.POST.get('txt_costo_es', '').strip()

        if costo_str:
            try:
                costo_es = Decimal(costo_str)

                if costo_es < 0:
                    messages.error(request, "El costo no puede ser negativo")
                    return redirect(f'/editareventosanitario/{id_es}')

                if costo_es > Decimal('999999.99'):
                    messages.error(request, "El costo excede el máximo permitido")
                    return redirect(f'/editareventosanitario/{id_es}')

            except InvalidOperation:
                messages.error(request, "El costo debe ser un número válido")
                return redirect(f'/editareventosanitario/{id_es}')
        
        # ==========================================
        # MANEJO DE STOCK DE PRODUCTO
        # ==========================================
        # Si cambia de no-ejecutado a ejecutado, descontar stock
        # Si cambia de ejecutado a no-ejecutado, reintegrar stock anterior
        # Si cambia la dosis en estado ejecutado, ajustar stock
        
        producto_anterior = evento.fk_pv
        dosis_anterior = evento.dosis_es or 0
        
        # Reintegrar stock anterior si estaba ejecutado y ahora no lo está
        if estado_anterior == 'ejecutado' and estado_es != 'ejecutado' and producto_anterior:
            producto_anterior.stock_pv += dosis_anterior
            producto_anterior.save()
            messages.info(request, f"Stock de {producto_anterior.nombre_pv} reintegrado: +{dosis_anterior}")
        
        # Descontar nuevo stock si pasa a ejecutado
        elif estado_es == 'ejecutado' and fk_pv and dosis_es:
            # Si ya estaba ejecutado con el mismo producto, ajustar diferencia
            if estado_anterior == 'ejecutado' and producto_anterior and producto_anterior.id_pv == fk_pv.id_pv:
                diferencia = dosis_es - dosis_anterior
                if diferencia != 0:
                    fk_pv.stock_pv -= diferencia
                    fk_pv.save()
                    if diferencia > 0:
                        messages.info(request, f"Stock de {fk_pv.nombre_pv} descontado adicional: -{diferencia}")
                    else:
                        messages.info(request, f"Stock de {fk_pv.nombre_pv} reintegrado: +{abs(diferencia)}")
            else:
                # Nuevo descuento completo
                fk_pv.stock_pv = max(0, fk_pv.stock_pv - dosis_es)
                fk_pv.save()
                messages.info(request, f"Stock de {fk_pv.nombre_pv} actualizado: {fk_pv.stock_pv} restantes")
        
        # ==========================================
        # ACTUALIZAR EVENTO
        # ==========================================
        evento.fecha_programada_es = fecha_programada_es
        evento.fecha_ejecutada_es = fecha_ejecutada_es
        evento.fk_an = animal
        evento.estado_es = estado_es
        evento.fk_pv = fk_pv
        evento.dosis_es = dosis_es
        evento.via_administracion_es = via_administracion_es if via_administracion_es else None
        evento.veterinario_responsable_es = veterinario_responsable_es if veterinario_responsable_es else None
        evento.resultado_es = resultado_es if resultado_es else None
        evento.costo_es = costo_es
        
        evento.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'EventoSanitario',
            evento.id_es,
            f'Se editó evento de {tipo_original}: {animal.codigo_an} - Estado: {estado_es}'
        )
        
        messages.success(request, f"Evento de {tipo_original.upper()} actualizado exitosamente")
        return redirect('/listaeventosanitario/')
        
    except EventoSanitario.DoesNotExist:
        messages.error(request, "Evento no encontrado")
        return redirect('/listaeventosanitario/')
    except ProductoVeterinario.DoesNotExist:
        messages.error(request, "Producto veterinario no encontrado")
        return redirect(f'/editareventosanitario/{id_es}')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect(f'/editareventosanitario/{id_es}')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editareventosanitario/{id_es}')


# ==========================================
# VISTA: ELIMINAR EVENTO SANITARIO
# ==========================================
def eliminareventosanitario(request, id_es):
    """
    Elimina un evento sanitario del sistema.
    Reintegra stock de producto si el evento estaba ejecutado.
    """
    evento = get_object_or_404(
        EventoSanitario.objects.select_related('fk_an', 'fk_pv'),
        id_es=id_es
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_evento = evento.id_es
    tipo_evento = evento.tipo_evento_es
    codigo_animal = evento.fk_an.codigo_an
    estado_evento = evento.estado_es
    producto = evento.fk_pv
    dosis = evento.dosis_es or 0
    
    try:
        # ==========================================
        # REINTEGRAR STOCK SI ESTABA EJECUTADO
        # ==========================================
        if estado_evento == 'ejecutado' and producto and dosis > 0:
            producto.stock_pv += dosis
            producto.save()
            messages.info(request, f"Stock de {producto.nombre_pv} reintegrado: +{dosis} {producto.unidad_medida_pv}")
        
        # ==========================================
        # ELIMINAR EVENTO
        # ==========================================
        evento.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'EventoSanitario',
            id_evento,
            f'Se eliminó evento de {tipo_evento}: {codigo_animal}'
        )
        
        messages.success(request, f"Evento de {tipo_evento.upper()} eliminado exitosamente")
        
    except IntegrityError:
        messages.error(request, f"No se puede eliminar el evento: tiene registros asociados")
    
    return redirect('/listaeventosanitario/')
# ==========================================
# REGISTROS CLÍNICOS
# ==========================================

def listaregistroclinico(request):
    """
    Muestra el listado completo de registros clínicos con estadísticas.
    Incluye conteos por resultado y costo total.
    """
    registros = RegistroClinico.objects.all().select_related(
        'fk_an', 'fk_us_rc'
    ).order_by('-fecha_rc', '-created_at_rc')
    
    # Estadísticas generales
    total_registros = registros.count()
    total_curados = registros.filter(resultado_rc='curado').count()
    total_en_tratamiento = registros.filter(resultado_rc='en_tratamiento').count()
    total_cronicos = registros.filter(resultado_rc='cronico').count()
    total_fallecidos = registros.filter(resultado_rc='fallecido').count()
    
    # Costo total de tratamientos
    costo_total = registros.aggregate(
        total=Sum('costo_tratamiento_rc')
    )['total'] or 0
    
    contexto = {
        'registros': registros,
        'total_registros': total_registros,
        'total_curados': total_curados,
        'total_en_tratamiento': total_en_tratamiento,
        'total_cronicos': total_cronicos,
        'total_fallecidos': total_fallecidos,
        'costo_total': costo_total,
    }
    
    return render(request, 'catalogos/salud/registrosC/lista_registroC.html', contexto)


# ==========================================
# VISTA: NUEVO REGISTRO CLÍNICO (formulario)
# ==========================================
def nuevoregistroclinico(request):
    """
    Muestra el formulario para registrar un nuevo registro clínico.
    Carga lista de animales activos.
    """
    # Animales activos para el select
    animales = Animal.objects.filter(
        estado_an='activo'
    ).select_related('fk_ra').order_by('codigo_an')
    
    contexto = {
        'animales': animales,
    }
    
    return render(request, 'catalogos/salud/registrosC/nuevo_registroC.html', contexto)


# ==========================================
# VISTA: GUARDAR REGISTRO CLÍNICO (procesar creación)
# ==========================================
def guardarregistroclinico(request):
    """
    Procesa el formulario de creación de un nuevo registro clínico.
    Valida datos, verifica reglas de negocio, y registra auditoría.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevoregistroclinico/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha de atención (obligatoria)
        fecha_rc = request.POST.get('txt_fecha_rc')
        if not fecha_rc:
            messages.error(request, "La fecha de atención es obligatoria")
            return redirect('/nuevoregistroclinico/')
        
        # Animal (obligatorio)
        fk_an_id = request.POST.get('sel_animal_rc')
        if not fk_an_id:
            messages.error(request, "Debe seleccionar un animal")
            return redirect('/nuevoregistroclinico/')
        
        animal = get_object_or_404(Animal, id_an=fk_an_id)
        
        # Validar que el animal esté activo
        if animal.estado_an != 'activo':
            messages.error(request, f"El animal {animal.codigo_an} no está activo. Solo se pueden registrar atenciones para animales activos.")
            return redirect('/nuevoregistroclinico/')
        
        # Síntomas (obligatorio)
        sintomas_rc = request.POST.get('txt_sintomas_rc', '').strip()
        if not sintomas_rc:
            messages.error(request, "Los síntomas son obligatorios")
            return redirect('/nuevoregistroclinico/')
        if len(sintomas_rc) > 2000:
            messages.error(request, "Los síntomas exceden 2000 caracteres")
            return redirect('/nuevoregistroclinico/')
        
        # Diagnóstico (opcional)
        diagnostico_rc = request.POST.get('txt_diagnostico_rc', '').strip()
        if diagnostico_rc and len(diagnostico_rc) > 2000:
            messages.error(request, "El diagnóstico excede 2000 caracteres")
            return redirect('/nuevoregistroclinico/')
        
        # Tratamiento (opcional)
        tratamiento_rc = request.POST.get('txt_tratamiento_rc', '').strip()
        if tratamiento_rc and len(tratamiento_rc) > 2000:
            messages.error(request, "El tratamiento excede 2000 caracteres")
            return redirect('/nuevoregistroclinico/')
        
        # Días de tratamiento (opcional)
        dias_tratamiento_rc = None
        dias_str = request.POST.get('txt_dias_tratamiento_rc', '').strip()
        if dias_str:
            try:
                dias_tratamiento_rc = int(dias_str)
                if dias_tratamiento_rc < 1 or dias_tratamiento_rc > 365:
                    messages.error(request, "Los días de tratamiento deben estar entre 1 y 365")
                    return redirect('/nuevoregistroclinico/')
            except ValueError:
                messages.error(request, "Los días de tratamiento deben ser un número entero válido")
                return redirect('/nuevoregistroclinico/')
        
        # Resultado (opcional, pero validar contra CHECK de SQL)
        resultado_rc = request.POST.get('sel_resultado_rc', '').strip()
        resultados_validos = ['curado', 'en_tratamiento', 'cronico', 'fallecido']
        if resultado_rc and resultado_rc not in resultados_validos:
            messages.error(request, "Seleccione un resultado válido")
            return redirect('/nuevoregistroclinico/')
        
        # Veterinario responsable (opcional)
        veterinario_rc = request.POST.get('txt_veterinario_rc', '').strip()
        if veterinario_rc and len(veterinario_rc) > 100:
            messages.error(request, "El nombre del veterinario excede 100 caracteres")
            return redirect('/nuevoregistroclinico/')
        
        # Costo del tratamiento (opcional)
        costo_tratamiento_rc = None
        costo_str = request.POST.get('txt_costo_tratamiento_rc', '').strip()
        if costo_str:
            try:
                costo_tratamiento_rc = Decimal(costo_str)
                if costo_tratamiento_rc < 0:
                    messages.error(request, "El costo no puede ser negativo")
                    return redirect('/nuevoregistroclinico/')
                if costo_tratamiento_rc > Decimal('999999.99'):
                    messages.error(request, "El costo excede el máximo permitido")
                    return redirect('/nuevoregistroclinico/')
            except InvalidOperation:
                messages.error(request, "El costo debe ser un número válido")
                return redirect('/nuevoregistroclinico/')
        
        # Usuario actual (obligatorio - FK)
        try:
            fk_us_rc = Usuario.objects.get(id_us=request.session.get('id_us', 1))
        except Usuario.DoesNotExist:
            messages.error(request, "Error de autenticación de usuario")
            return redirect('/nuevoregistroclinico/')
        
        # ==========================================
        # CREAR REGISTRO CLÍNICO
        # ==========================================
        nuevo_registro = RegistroClinico.objects.create(
            fk_an=animal,
            fecha_rc=fecha_rc,
            sintomas_rc=sintomas_rc,
            diagnostico_rc=diagnostico_rc if diagnostico_rc else None,
            tratamiento_rc=tratamiento_rc if tratamiento_rc else None,
            dias_tratamiento_rc=dias_tratamiento_rc,
            resultado_rc=resultado_rc if resultado_rc else None,
            veterinario_rc=veterinario_rc if veterinario_rc else None,
            costo_tratamiento_rc=costo_tratamiento_rc,
            fk_us_rc=fk_us_rc
        )
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'RegistroClinico',
            nuevo_registro.id_rc,
            f'Se creó registro clínico: {animal.codigo_an} - Fecha: {fecha_rc}'
        )
        
        messages.success(request, f"Registro clínico para '{animal.codigo_an}' guardado exitosamente")
        return redirect('/listaregistroclinico/')
        
    except Animal.DoesNotExist:
        messages.error(request, "Animal no encontrado")
        return redirect('/nuevoregistroclinico/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevoregistroclinico/')


# ==========================================
# VISTA: EDITAR REGISTRO CLÍNICO (formulario)
# ==========================================
def editarregistroclinico(request, id_rc):
    """
    Muestra el formulario de edición con los datos precargados.
    El animal no se puede cambiar.
    """
    registro = get_object_or_404(
        RegistroClinico.objects.select_related('fk_an', 'fk_us_rc'),
        id_rc=id_rc
    )
    
    # Animales disponibles (solo para mostrar, no se puede cambiar)
    animales = Animal.objects.filter(
        Q(estado_an='activo') | Q(id_an=registro.fk_an_id)
    ).select_related('fk_ra').order_by('codigo_an')
    
    contexto = {
        'registro': registro,
        'animales': animales,
    }
    
    return render(request, 'catalogos/salud/registrosC/editar_registroC.html', contexto)


# ==========================================
# VISTA: PROCESAR EDICION REGISTRO CLÍNICO
# ==========================================
def procesareditarregistroclinico(request):
    """
    Procesa el formulario de edición de un registro clínico existente.
    El animal no se puede modificar.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listaregistroclinico/')
    
    try:
        # Obtener registro existente
        id_rc = request.POST.get('id_rc')
        if not id_rc:
            messages.error(request, "ID de registro no proporcionado")
            return redirect('/listaregistroclinico/')
        
        registro = RegistroClinico.objects.select_related('fk_an').get(id_rc=id_rc)
        animal = registro.fk_an
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha de atención (obligatoria)
        fecha_rc = request.POST.get('txt_fecha_rc')
        if not fecha_rc:
            messages.error(request, "La fecha de atención es obligatoria")
            return redirect(f'/editarregistroclinico/{id_rc}')
        
        # Síntomas (obligatorio)
        sintomas_rc = request.POST.get('txt_sintomas_rc', '').strip()
        if not sintomas_rc:
            messages.error(request, "Los síntomas son obligatorios")
            return redirect(f'/editarregistroclinico/{id_rc}')
        if len(sintomas_rc) > 2000:
            messages.error(request, "Los síntomas exceden 2000 caracteres")
            return redirect(f'/editarregistroclinico/{id_rc}')
        
        # Diagnóstico (opcional)
        diagnostico_rc = request.POST.get('txt_diagnostico_rc', '').strip()
        if diagnostico_rc and len(diagnostico_rc) > 2000:
            messages.error(request, "El diagnóstico excede 2000 caracteres")
            return redirect(f'/editarregistroclinico/{id_rc}')
        
        # Tratamiento (opcional)
        tratamiento_rc = request.POST.get('txt_tratamiento_rc', '').strip()
        if tratamiento_rc and len(tratamiento_rc) > 2000:
            messages.error(request, "El tratamiento excede 2000 caracteres")
            return redirect(f'/editarregistroclinico/{id_rc}')
        
        # Días de tratamiento (opcional)
        dias_tratamiento_rc = None
        dias_str = request.POST.get('txt_dias_tratamiento_rc', '').strip()
        if dias_str:
            try:
                dias_tratamiento_rc = int(dias_str)
                if dias_tratamiento_rc < 1 or dias_tratamiento_rc > 365:
                    messages.error(request, "Los días de tratamiento deben estar entre 1 y 365")
                    return redirect(f'/editarregistroclinico/{id_rc}')
            except ValueError:
                messages.error(request, "Los días de tratamiento deben ser un número entero válido")
                return redirect(f'/editarregistroclinico/{id_rc}')
        
        # Resultado (opcional, validar contra CHECK)
        resultado_rc = request.POST.get('sel_resultado_rc', '').strip()
        resultados_validos = ['curado', 'en_tratamiento', 'cronico', 'fallecido']
        if resultado_rc and resultado_rc not in resultados_validos:
            messages.error(request, "Seleccione un resultado válido")
            return redirect(f'/editarregistroclinico/{id_rc}')
        
        # Veterinario responsable (opcional)
        veterinario_rc = request.POST.get('txt_veterinario_rc', '').strip()
        if veterinario_rc and len(veterinario_rc) > 100:
            messages.error(request, "El nombre del veterinario excede 100 caracteres")
            return redirect(f'/editarregistroclinico/{id_rc}')
        
        # Costo del tratamiento (opcional)
        costo_tratamiento_rc = None
        costo_str = request.POST.get('txt_costo_tratamiento_rc', '').strip()
        if costo_str:
            try:
                costo_tratamiento_rc = Decimal(costo_str)
                if costo_tratamiento_rc < 0:
                    messages.error(request, "El costo no puede ser negativo")
                    return redirect(f'/editarregistroclinico/{id_rc}')
                if costo_tratamiento_rc > Decimal('999999.99'):
                    messages.error(request, "El costo excede el máximo permitido")
                    return redirect(f'/editarregistroclinico/{id_rc}')
            except InvalidOperation:
                messages.error(request, "El costo debe ser un número válido")
                return redirect(f'/editarregistroclinico/{id_rc}')
        
        # ==========================================
        # ACTUALIZAR REGISTRO CLÍNICO
        # ==========================================
        registro.fecha_rc = fecha_rc
        registro.sintomas_rc = sintomas_rc
        registro.diagnostico_rc = diagnostico_rc if diagnostico_rc else None
        registro.tratamiento_rc = tratamiento_rc if tratamiento_rc else None
        registro.dias_tratamiento_rc = dias_tratamiento_rc
        registro.resultado_rc = resultado_rc if resultado_rc else None
        registro.veterinario_rc = veterinario_rc if veterinario_rc else None
        registro.costo_tratamiento_rc = costo_tratamiento_rc
        
        registro.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'RegistroClinico',
            registro.id_rc,
            f'Se editó registro clínico: {animal.codigo_an} - Fecha: {fecha_rc}'
        )
        
        messages.success(request, f"Registro clínico de '{animal.codigo_an}' actualizado exitosamente")
        return redirect('/listaregistroclinico/')
        
    except RegistroClinico.DoesNotExist:
        messages.error(request, "Registro clínico no encontrado")
        return redirect('/listaregistroclinico/')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarregistroclinico/{id_rc}')


# ==========================================
# VISTA: ELIMINAR REGISTRO CLÍNICO
# ==========================================
def eliminarregistroclinico(request, id_rc):
    """
    Elimina un registro clínico del sistema.
    """
    registro = get_object_or_404(
        RegistroClinico.objects.select_related('fk_an'),
        id_rc=id_rc
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_registro = registro.id_rc
    codigo_animal = registro.fk_an.codigo_an
    fecha_atencion = registro.fecha_rc
    
    try:
        # ==========================================
        # ELIMINAR REGISTRO
        # ==========================================
        registro.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'RegistroClinico',
            id_registro,
            f'Se eliminó registro clínico: {codigo_animal} - Fecha: {fecha_atencion}'
        )
        
        messages.success(request, f"Registro clínico de '{codigo_animal}' eliminado exitosamente")
        
    except Exception as e:
        messages.error(request, f"Error al eliminar: {str(e)}")
    
    return redirect('/listaregistroclinico/')

#==========================================================================================================================================================S
# ==========================================
# CELOS
# ==========================================

def listacelo(request):
    """
    Muestra el listado completo de celos con estadísticas.
    Incluye conteos por intensidad.
    """
    celos = Celo.objects.all().select_related(
        'fk_an', 'fk_us_ce'
    ).order_by('-fecha_observacion_ce', '-created_at_ce')
    
    # Estadísticas generales
    total_celos = celos.count()
    total_alta = celos.filter(intensidad_ce='alta').count()
    total_media = celos.filter(intensidad_ce='media').count()
    total_baja = celos.filter(intensidad_ce='baja').count()
    
    contexto = {
        'celos': celos,
        'total_celos': total_celos,
        'total_alta': total_alta,
        'total_media': total_media,
        'total_baja': total_baja,
    }
    
    return render(request, 'catalogos/reproduccion/celos/lista_celo.html', contexto)


# ==========================================
# VISTA: NUEVO CELO (formulario)
# ==========================================
def nuevocelo(request):
    """
    Muestra el formulario para registrar un nuevo celo.
    Carga lista de hembras activas en categorías reproductivas.
    """
    # Hembras activas en categorías reproductivas
    # Según SQL: vaca_leche, vaca_seca, novilla, ternero (hembra)
    categorias_reproductivas = ['vaca_leche', 'vaca_seca', 'novilla', 'ternero']
    
    animales = Animal.objects.filter(
        estado_an='activo',
        sexo_an='H',
        categoria_an__in=categorias_reproductivas
    ).select_related('fk_ra').order_by('codigo_an')
    
    contexto = {
        'animales': animales,
    }
    
    return render(request, 'catalogos/reproduccion/celos/nuevo_celo.html', contexto)


# ==========================================
# VISTA: GUARDAR CELO (procesar creación)
# ==========================================
def guardarcelo(request):
    """
    Procesa el formulario de creación de un nuevo celo.
    Valida datos, verifica reglas de negocio, y registra auditoría.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevocelo/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha de observación (obligatoria)
        fecha_observacion_ce = request.POST.get('txt_fecha_observacion_ce')
        if not fecha_observacion_ce:
            messages.error(request, "La fecha de observación es obligatoria")
            return redirect('/nuevocelo/')
        
        # Animal (obligatorio)
        fk_an_id = request.POST.get('sel_animal_ce')
        if not fk_an_id:
            messages.error(request, "Debe seleccionar una hembra")
            return redirect('/nuevocelo/')
        
        animal = get_object_or_404(Animal, id_an=fk_an_id)
        
        # Validar que el animal esté activo
        if animal.estado_an != 'activo':
            messages.error(request, f"El animal {animal.codigo_an} no está activo.")
            return redirect('/nuevocelo/')
        
        # Validar que sea hembra
        if animal.sexo_an != 'H':
            messages.error(request, f"El animal {animal.codigo_an} no es hembra. Solo se registran celos en hembras.")
            return redirect('/nuevocelo/')
        
        # Validar categoría reproductiva
        categorias_reproductivas = ['vaca_leche', 'vaca_seca', 'novilla', 'ternero']
        if animal.categoria_an not in categorias_reproductivas:
            messages.error(request, f"El animal {animal.codigo_an} no está en categoría reproductiva.")
            return redirect('/nuevocelo/')
        
        # Intensidad (opcional, validar contra choices del modelo)
        intensidad_ce = request.POST.get('sel_intensidad_ce', '').strip()
        intensidades_validas = ['baja', 'media', 'alta']
        if intensidad_ce and intensidad_ce not in intensidades_validas:
            messages.error(request, "Seleccione una intensidad válida")
            return redirect('/nuevocelo/')
        
        # Duración aproximada en horas (opcional)
        duracion_aproximada_horas_ce = None
        duracion_str = request.POST.get('txt_duracion_horas_ce', '').strip()
        if duracion_str:
            try:
                duracion_aproximada_horas_ce = int(duracion_str)
                if duracion_aproximada_horas_ce < 1 or duracion_aproximada_horas_ce > 72:
                    messages.error(request, "La duración debe estar entre 1 y 72 horas")
                    return redirect('/nuevocelo/')
            except ValueError:
                messages.error(request, "La duración debe ser un número entero válido")
                return redirect('/nuevocelo/')
        
        # Observaciones (opcional)
        observaciones_ce = request.POST.get('txt_observaciones_ce', '').strip()
        if observaciones_ce and len(observaciones_ce) > 1000:
            messages.error(request, "Las observaciones exceden 1000 caracteres")
            return redirect('/nuevocelo/')
        
        # Usuario actual (obligatorio - FK)
        try:
            fk_us_ce = Usuario.objects.get(id_us=request.session.get('id_us', 1))
        except Usuario.DoesNotExist:
            messages.error(request, "Error de autenticación de usuario")
            return redirect('/nuevocelo/')
        
        # ==========================================
        # CREAR CELO
        # ==========================================
        nuevo_celo = Celo.objects.create(
            fk_an=animal,
            fecha_observacion_ce=fecha_observacion_ce,
            intensidad_ce=intensidad_ce if intensidad_ce else None,
            duracion_aproximada_horas_ce=duracion_aproximada_horas_ce,
            observaciones_ce=observaciones_ce if observaciones_ce else None,
            fk_us_ce=fk_us_ce
        )
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'Celo',
            nuevo_celo.id_ce,
            f'Se registró celo: {animal.codigo_an} - Fecha: {fecha_observacion_ce}'
        )
        
        messages.success(request, f"Celo de '{animal.codigo_an}' registrado exitosamente")
        return redirect('/listacelo/')
        
    except Animal.DoesNotExist:
        messages.error(request, "Animal no encontrado")
        return redirect('/nuevocelo/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevocelo/')


# ==========================================
# VISTA: EDITAR CELO (formulario)
# ==========================================
def editarcelo(request, id_ce):
    """
    Muestra el formulario de edición con los datos precargados.
    El animal no se puede cambiar.
    """
    celo = get_object_or_404(
        Celo.objects.select_related('fk_an', 'fk_us_ce'),
        id_ce=id_ce
    )
    
    contexto = {
        'celo': celo,
    }
    
    return render(request, 'catalogos/reproduccion/celos/editar_celo.html', contexto)


# ==========================================
# VISTA: PROCESAR EDICION CELO
# ==========================================
def procesareditarcelo(request):
    """
    Procesa el formulario de edición de un celo existente.
    El animal no se puede modificar.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listacelo/')
    
    try:
        # Obtener celo existente
        id_ce = request.POST.get('id_ce')
        if not id_ce:
            messages.error(request, "ID de celo no proporcionado")
            return redirect('/listacelo/')
        
        celo = Celo.objects.select_related('fk_an').get(id_ce=id_ce)
        animal = celo.fk_an
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha de observación (obligatoria)
        fecha_observacion_ce = request.POST.get('txt_fecha_observacion_ce')
        if not fecha_observacion_ce:
            messages.error(request, "La fecha de observación es obligatoria")
            return redirect(f'/editarcelo/{id_ce}')
        
        # Intensidad (opcional, validar contra choices)
        intensidad_ce = request.POST.get('sel_intensidad_ce', '').strip()
        intensidades_validas = ['baja', 'media', 'alta']
        if intensidad_ce and intensidad_ce not in intensidades_validas:
            messages.error(request, "Seleccione una intensidad válida")
            return redirect(f'/editarcelo/{id_ce}')
        
        # Duración aproximada en horas (opcional)
        duracion_aproximada_horas_ce = None
        duracion_str = request.POST.get('txt_duracion_horas_ce', '').strip()
        if duracion_str:
            try:
                duracion_aproximada_horas_ce = int(duracion_str)
                if duracion_aproximada_horas_ce < 1 or duracion_aproximada_horas_ce > 72:
                    messages.error(request, "La duración debe estar entre 1 y 72 horas")
                    return redirect(f'/editarcelo/{id_ce}')
            except ValueError:
                messages.error(request, "La duración debe ser un número entero válido")
                return redirect(f'/editarcelo/{id_ce}')
        
        # Observaciones (opcional)
        observaciones_ce = request.POST.get('txt_observaciones_ce', '').strip()
        if observaciones_ce and len(observaciones_ce) > 1000:
            messages.error(request, "Las observaciones exceden 1000 caracteres")
            return redirect(f'/editarcelo/{id_ce}')
        
        # ==========================================
        # ACTUALIZAR CELO
        # ==========================================
        celo.fecha_observacion_ce = fecha_observacion_ce
        celo.intensidad_ce = intensidad_ce if intensidad_ce else None
        celo.duracion_aproximada_horas_ce = duracion_aproximada_horas_ce
        celo.observaciones_ce = observaciones_ce if observaciones_ce else None
        
        celo.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'Celo',
            celo.id_ce,
            f'Se editó celo: {animal.codigo_an} - Fecha: {fecha_observacion_ce}'
        )
        
        messages.success(request, f"Celo de '{animal.codigo_an}' actualizado exitosamente")
        return redirect('/listacelo/')
        
    except Celo.DoesNotExist:
        messages.error(request, "Celo no encontrado")
        return redirect('/listacelo/')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarcelo/{id_ce}')


# ==========================================
# VISTA: ELIMINAR CELO
# ==========================================
def eliminarcelo(request, id_ce):
    """
    Elimina un registro de celo del sistema.
    """
    celo = get_object_or_404(
        Celo.objects.select_related('fk_an'),
        id_ce=id_ce
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_celo = celo.id_ce
    codigo_animal = celo.fk_an.codigo_an
    fecha_observacion = celo.fecha_observacion_ce
    
    try:
        # ==========================================
        # ELIMINAR CELO
        # ==========================================
        celo.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'Celo',
            id_celo,
            f'Se eliminó celo: {codigo_animal} - Fecha: {fecha_observacion}'
        )
        
        messages.success(request, f"Celo de '{codigo_animal}' eliminado exitosamente")
        
    except Exception as e:
        messages.error(request, f"Error al eliminar: {str(e)}")
    
    return redirect('/listacelo/')


# ==========================================
# INSEMINACIONES
# ==========================================
def listainseminacion(request):
    """
    Muestra el listado completo de inseminaciones con estadísticas.
    Incluye conteos por resultado y costo total.
    """
    inseminaciones = Inseminacion.objects.all().select_related(
        'fk_an', 'fk_an__fk_ra', 'fk_toro_in', 'fk_toro_in__fk_ra', 'fk_us_in'
    ).order_by('-fecha_in', '-created_at_in')
    
    # Estadísticas generales
    total_inseminaciones = inseminaciones.count()
    total_pendientes = inseminaciones.filter(
        Q(resultado_in='pendiente') | Q(resultado_in__isnull=True) | Q(resultado_in='')
    ).count()
    total_prenadas = inseminaciones.filter(resultado_in='preñada').count()
    total_no_prenadas = inseminaciones.filter(resultado_in='no_preñada').count()
    total_artificiales = inseminaciones.filter(tipo_inseminacion_in='artificial').count()
    
    # Costo total
    costo_total = inseminaciones.aggregate(total=Sum('costo_in'))['total'] or 0
    
    contexto = {
        'inseminaciones': inseminaciones,
        'total_inseminaciones': total_inseminaciones,
        'total_pendientes': total_pendientes,
        'total_prenadas': total_prenadas,
        'total_no_prenadas': total_no_prenadas,
        'total_artificiales': total_artificiales,
        'costo_total': costo_total,
    }
    
    return render(request, 'catalogos/reproduccion/inseminaciones/lista_inseminacion.html', contexto)


# ==========================================
# VISTA: NUEVA INSEMINACIÓN (formulario)
# ==========================================
def nuevainseminacion(request):
    """
    Muestra el formulario para registrar una nueva inseminación.
    Carga listas de hembras activas (hembras reproductivas) y toros activos.
    """
    # Hembras activas y reproductivas (vaca_leche, vaca_seca, novilla)
    hembras = Animal.objects.filter(
        estado_an='activo',
        sexo_an='H',
        categoria_an__in=['vaca_leche', 'vaca_seca', 'novilla']
    ).select_related('fk_ra').order_by('codigo_an')
    
    # Toros activos (machos reproductivos)
    toros = Animal.objects.filter(
        estado_an='activo',
        sexo_an='M',
        categoria_an__in=['toro', 'torito']
    ).select_related('fk_ra').order_by('codigo_an')
    
    contexto = {
        'hembras': hembras,
        'toros': toros,
    }
    
    return render(request, 'catalogos/reproduccion/inseminaciones/nueva_inseminacion.html', contexto)


# ==========================================
# VISTA: GUARDAR INSEMINACIÓN (procesar creación)
# ==========================================
def guardarinseminacion(request):
    """
    Procesa el formulario de creación de una nueva inseminación.
    Valida datos, verifica reglas de negocio, y registra auditoría.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevainseminacion/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Hembra (obligatoria)
        fk_an_id = request.POST.get('sel_hembra_in')
        if not fk_an_id:
            messages.error(request, "Debe seleccionar una hembra")
            return redirect('/nuevainseminacion/')
        
        hembra = get_object_or_404(Animal, id_an=fk_an_id)
        
        # Validar que sea hembra activa y reproductiva
        if hembra.sexo_an != 'H':
            messages.error(request, f"El animal {hembra.codigo_an} no es una hembra")
            return redirect('/nuevainseminacion/')
        
        if hembra.estado_an != 'activo':
            messages.error(request, f"La hembra {hembra.codigo_an} no está activa")
            return redirect('/nuevainseminacion/')
        
        if hembra.categoria_an not in ['vaca_leche', 'vaca_seca', 'novilla']:
            messages.error(request, f"La hembra {hembra.codigo_an} no está en categoría reproductiva")
            return redirect('/nuevainseminacion/')
        
        # Fecha inseminación (obligatoria)
        fecha_in = request.POST.get('txt_fecha_in')
        if not fecha_in:
            messages.error(request, "La fecha de inseminación es obligatoria")
            return redirect('/nuevainseminacion/')
        
        # Tipo de inseminación (obligatorio)
        tipo_inseminacion_in = request.POST.get('sel_tipo_inseminacion_in')
        tipos_validos = ['natural', 'artificial']
        if not tipo_inseminacion_in or tipo_inseminacion_in not in tipos_validos:
            messages.error(request, "Seleccione un tipo de inseminación válido")
            return redirect('/nuevainseminacion/')
        
        # Día del ciclo (opcional, validar rango 1-21)
        dia_ciclo_in = None
        dia_ciclo_str = request.POST.get('txt_dia_ciclo_in', '').strip()
        if dia_ciclo_str:
            try:
                dia_ciclo_in = int(dia_ciclo_str)
                if dia_ciclo_in < 1 or dia_ciclo_in > 21:
                    messages.error(request, "El día del ciclo debe estar entre 1 y 21")
                    return redirect('/nuevainseminacion/')
            except ValueError:
                messages.error(request, "El día del ciclo debe ser un número entero")
                return redirect('/nuevainseminacion/')
        
        # Toro (condicional - solo natural)
        fk_toro_in = None
        if tipo_inseminacion_in == 'natural':
            toro_id = request.POST.get('sel_toro_in', '').strip()
            if not toro_id:
                messages.error(request, "El toro es obligatorio para inseminación natural")
                return redirect('/nuevainseminacion/')
            fk_toro_in = get_object_or_404(Animal, id_an=toro_id)
            # Validar que sea toro activo y macho
            if fk_toro_in.sexo_an != 'M':
                messages.error(request, f"El animal {fk_toro_in.codigo_an} no es un macho")
                return redirect('/nuevainseminacion/')
            if fk_toro_in.estado_an != 'activo':
                messages.error(request, f"El toro {fk_toro_in.codigo_an} no está activo")
                return redirect('/nuevainseminacion/')
            if fk_toro_in.categoria_an not in ['toro', 'torito']:
                messages.error(request, f"El animal {fk_toro_in.codigo_an} no está en categoría reproductiva masculina")
                return redirect('/nuevainseminacion/')
        
        # Lote de semen (condicional - solo artificial)
        lote_semen_in = None
        if tipo_inseminacion_in == 'artificial':
            lote_semen_in = request.POST.get('txt_lote_semen_in', '').strip()
            if not lote_semen_in:
                messages.error(request, "El lote de semen es obligatorio para inseminación artificial")
                return redirect('/nuevainseminacion/')
            if len(lote_semen_in) > 50:
                messages.error(request, "El lote de semen excede 50 caracteres")
                return redirect('/nuevainseminacion/')
        
        # Condición corporal (opcional, rango 1-5)
        condicion_corporal_in = None
        condicion_str = request.POST.get('sel_condicion_corporal_in', '').strip()
        if condicion_str:
            try:
                condicion_corporal_in = int(condicion_str)
                if condicion_corporal_in < 1 or condicion_corporal_in > 5:
                    messages.error(request, "La condición corporal debe estar entre 1 y 5")
                    return redirect('/nuevainseminacion/')
            except ValueError:
                messages.error(request, "La condición corporal debe ser un número entero")
                return redirect('/nuevainseminacion/')
        
        # Resultado (opcional)
        resultado_in = request.POST.get('sel_resultado_in', '').strip()
        resultados_validos = ['preñada', 'no_preñada', '']
        if resultado_in and resultado_in not in resultados_validos:
            messages.error(request, "Resultado no válido")
            return redirect('/nuevainseminacion/')
        
        resultado_in = resultado_in if resultado_in else None
        
        # Fecha resultado (condicional)
        fecha_resultado_in = None
        if resultado_in in ['preñada', 'no_preñada']:
            fecha_resultado_str = request.POST.get('txt_fecha_resultado_in', '').strip()
            if not fecha_resultado_str:
                messages.error(request, "La fecha de resultado es obligatoria cuando hay resultado")
                return redirect('/nuevainseminacion/')
            fecha_resultado_in = fecha_resultado_str
            # Validar que fecha resultado >= fecha inseminación
            if fecha_resultado_in < fecha_in:
                messages.error(request, "La fecha de resultado no puede ser anterior a la inseminación")
                return redirect('/nuevainseminacion/')
        
        # Veterinario (opcional)
        veterinario_in = request.POST.get('txt_veterinario_in', '').strip()
        if veterinario_in and len(veterinario_in) > 100:
            messages.error(request, "El nombre del veterinario excede 100 caracteres")
            return redirect('/nuevainseminacion/')
        
        # Costo (opcional)
        costo_in = None
        costo_str = request.POST.get('txt_costo_in', '').strip()
        if costo_str:
            try:
                costo_in = Decimal(costo_str)
                if costo_in < 0:
                    messages.error(request, "El costo no puede ser negativo")
                    return redirect('/nuevainseminacion/')
                if costo_in > Decimal('999999.99'):
                    messages.error(request, "El costo excede el máximo permitido")
                    return redirect('/nuevainseminacion/')
            except InvalidOperation:
                messages.error(request, "El costo debe ser un número válido")
                return redirect('/nuevainseminacion/')
        
        # Usuario actual (obligatorio)
        try:
            fk_us_in = Usuario.objects.get(id_us=request.session.get('id_us', 1))
        except Usuario.DoesNotExist:
            messages.error(request, "Error de autenticación de usuario")
            return redirect('/nuevainseminacion/')
        
        # ==========================================
        # CREAR INSEMINACIÓN
        # ==========================================
        nueva_inseminacion = Inseminacion.objects.create(
            fk_an=hembra,
            fecha_in=fecha_in,
            tipo_inseminacion_in=tipo_inseminacion_in,
            dia_ciclo_in=dia_ciclo_in,
            fk_toro_in=fk_toro_in,
            lote_semen_in=lote_semen_in,
            condicion_corporal_in=condicion_corporal_in,
            resultado_in=resultado_in,
            fecha_resultado_in=fecha_resultado_in,
            veterinario_in=veterinario_in if veterinario_in else None,
            costo_in=costo_in,
            fk_us_in=fk_us_in
        )
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'Inseminacion',
            nueva_inseminacion.id_in,
            f'Se creó inseminación {tipo_inseminacion_in}: {hembra.codigo_an} - Fecha: {fecha_in}'
        )
        
        messages.success(request, f"Inseminación {tipo_inseminacion_in.upper()} para '{hembra.codigo_an}' guardada exitosamente")
        return redirect('/listainseminacion/')
        
    except Animal.DoesNotExist:
        messages.error(request, "Animal no encontrado")
        return redirect('/nuevainseminacion/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect('/nuevainseminacion/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevainseminacion/')


# ==========================================
# VISTA: EDITAR INSEMINACIÓN (formulario)
# ==========================================
def editarinseminacion(request, id_in):
    """
    Muestra el formulario de edición con los datos precargados.
    El tipo de inseminación no se puede cambiar.
    """
    inseminacion = get_object_or_404(
        Inseminacion.objects.select_related('fk_an', 'fk_an__fk_ra', 'fk_toro_in', 'fk_toro_in__fk_ra', 'fk_us_in'),
        id_in=id_in
    )
    
    # Hembras disponibles (incluir la actual aunque no esté activa o no sea reproductiva)
    hembras = Animal.objects.filter(
        Q(estado_an='activo', sexo_an='H', categoria_an__in=['vaca_leche', 'vaca_seca', 'novilla']) |
        Q(id_an=inseminacion.fk_an_id)
    ).select_related('fk_ra').order_by('codigo_an')
    
    # Toros disponibles (incluir el actual si aplica)
    toros = Animal.objects.filter(
        Q(estado_an='activo', sexo_an='M', categoria_an__in=['toro', 'torito']) |
        Q(id_an=inseminacion.fk_toro_in_id)
    ).select_related('fk_ra').order_by('codigo_an')
    
    contexto = {
        'inseminacion': inseminacion,
        'hembras': hembras,
        'toros': toros,
    }
    
    return render(request, 'catalogos/reproduccion/inseminaciones/editar_inseminacion.html', contexto)


# ==========================================
# VISTA: PROCESAR EDICION INSEMINACIÓN
# ==========================================
def procesareditarinseminacion(request):
    """
    Procesa el formulario de edición de una inseminación existente.
    El tipo de inseminación no se puede modificar.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listainseminacion/')
    
    try:
        # Obtener inseminación existente
        id_in = request.POST.get('id_in')
        if not id_in:
            messages.error(request, "ID de inseminación no proporcionado")
            return redirect('/listainseminacion/')
        
        inseminacion = Inseminacion.objects.select_related('fk_an').get(id_in=id_in)
        tipo_original = inseminacion.tipo_inseminacion_in
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha inseminación (obligatoria)
        fecha_in = request.POST.get('txt_fecha_in')
        if not fecha_in:
            messages.error(request, "La fecha de inseminación es obligatoria")
            return redirect(f'/editarinseminacion/{id_in}')
        
        # Hembra (obligatoria)
        fk_an_id = request.POST.get('sel_hembra_in')
        if not fk_an_id:
            messages.error(request, "Debe seleccionar una hembra")
            return redirect(f'/editarinseminacion/{id_in}')
        
        hembra = get_object_or_404(Animal, id_an=fk_an_id)
        
        # Validar que sea hembra
        if hembra.sexo_an != 'H':
            messages.error(request, f"El animal {hembra.codigo_an} no es una hembra")
            return redirect(f'/editarinseminacion/{id_in}')
        
        # Día del ciclo (opcional)
        dia_ciclo_in = None
        dia_ciclo_str = request.POST.get('txt_dia_ciclo_in', '').strip()
        if dia_ciclo_str:
            try:
                dia_ciclo_in = int(dia_ciclo_str)
                if dia_ciclo_in < 1 or dia_ciclo_in > 21:
                    messages.error(request, "El día del ciclo debe estar entre 1 y 21")
                    return redirect(f'/editarinseminacion/{id_in}')
            except ValueError:
                messages.error(request, "El día del ciclo debe ser un número entero")
                return redirect(f'/editarinseminacion/{id_in}')
        
        # Toro (condicional según tipo original)
        fk_toro_in = None
        if tipo_original == 'natural':
            toro_id = request.POST.get('sel_toro_in', '').strip()
            if not toro_id:
                messages.error(request, "El toro es obligatorio para inseminación natural")
                return redirect(f'/editarinseminacion/{id_in}')
            fk_toro_in = get_object_or_404(Animal, id_an=toro_id)
            if fk_toro_in.sexo_an != 'M':
                messages.error(request, f"El animal {fk_toro_in.codigo_an} no es un macho")
                return redirect(f'/editarinseminacion/{id_in}')
        
        # Lote de semen (condicional según tipo original)
        lote_semen_in = None
        if tipo_original == 'artificial':
            lote_semen_in = request.POST.get('txt_lote_semen_in', '').strip()
            if not lote_semen_in:
                messages.error(request, "El lote de semen es obligatorio para inseminación artificial")
                return redirect(f'/editarinseminacion/{id_in}')
            if len(lote_semen_in) > 50:
                messages.error(request, "El lote de semen excede 50 caracteres")
                return redirect(f'/editarinseminacion/{id_in}')
        
        # Condición corporal (opcional)
        condicion_corporal_in = None
        condicion_str = request.POST.get('sel_condicion_corporal_in', '').strip()
        if condicion_str:
            try:
                condicion_corporal_in = int(condicion_str)
                if condicion_corporal_in < 1 or condicion_corporal_in > 5:
                    messages.error(request, "La condición corporal debe estar entre 1 y 5")
                    return redirect(f'/editarinseminacion/{id_in}')
            except ValueError:
                messages.error(request, "La condición corporal debe ser un número entero")
                return redirect(f'/editarinseminacion/{id_in}')
        
        # Resultado (opcional)
        resultado_in = request.POST.get('sel_resultado_in', '').strip()
        resultados_validos = ['preñada', 'no_preñada', '']
        if resultado_in and resultado_in not in resultados_validos:
            messages.error(request, "Resultado no válido")
            return redirect(f'/editarinseminacion/{id_in}')
        
        resultado_in = resultado_in if resultado_in else None
        
        # Fecha resultado (condicional)
        fecha_resultado_in = None
        if resultado_in in ['preñada', 'no_preñada']:
            fecha_resultado_str = request.POST.get('txt_fecha_resultado_in', '').strip()
            if not fecha_resultado_str:
                messages.error(request, "La fecha de resultado es obligatoria cuando hay resultado")
                return redirect(f'/editarinseminacion/{id_in}')
            fecha_resultado_in = fecha_resultado_str
            if fecha_resultado_in < fecha_in:
                messages.error(request, "La fecha de resultado no puede ser anterior a la inseminación")
                return redirect(f'/editarinseminacion/{id_in}')
        
        # Veterinario (opcional)
        veterinario_in = request.POST.get('txt_veterinario_in', '').strip()
        if veterinario_in and len(veterinario_in) > 100:
            messages.error(request, "El nombre del veterinario excede 100 caracteres")
            return redirect(f'/editarinseminacion/{id_in}')
        
        # Costo (opcional)
        costo_in = None
        costo_str = request.POST.get('txt_costo_in', '').strip()
        if costo_str:
            try:
                costo_in = Decimal(costo_str)
                if costo_in < 0:
                    messages.error(request, "El costo no puede ser negativo")
                    return redirect(f'/editarinseminacion/{id_in}')
                if costo_in > Decimal('999999.99'):
                    messages.error(request, "El costo excede el máximo permitido")
                    return redirect(f'/editarinseminacion/{id_in}')
            except InvalidOperation:
                messages.error(request, "El costo debe ser un número válido")
                return redirect(f'/editarinseminacion/{id_in}')
        
        # ==========================================
        # ACTUALIZAR INSEMINACIÓN
        # ==========================================
        inseminacion.fecha_in = fecha_in
        inseminacion.fk_an = hembra
        inseminacion.dia_ciclo_in = dia_ciclo_in
        inseminacion.fk_toro_in = fk_toro_in
        inseminacion.lote_semen_in = lote_semen_in
        inseminacion.condicion_corporal_in = condicion_corporal_in
        inseminacion.resultado_in = resultado_in
        inseminacion.fecha_resultado_in = fecha_resultado_in
        inseminacion.veterinario_in = veterinario_in if veterinario_in else None
        inseminacion.costo_in = costo_in
        
        inseminacion.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'Inseminacion',
            inseminacion.id_in,
            f'Se editó inseminación {tipo_original}: {hembra.codigo_an} - Resultado: {resultado_in or "pendiente"}'
        )
        
        messages.success(request, f"Inseminación {tipo_original.upper()} actualizada exitosamente")
        return redirect('/listainseminacion/')
        
    except Inseminacion.DoesNotExist:
        messages.error(request, "Inseminación no encontrada")
        return redirect('/listainseminacion/')
    except Animal.DoesNotExist:
        messages.error(request, "Animal no encontrado")
        return redirect(f'/editarinseminacion/{id_in}')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect(f'/editarinseminacion/{id_in}')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarinseminacion/{id_in}')


# ==========================================
# VISTA: ELIMINAR INSEMINACIÓN
# ==========================================
def eliminainseminacion(request, id_in):
    """
    Elimina una inseminación del sistema.
    Verifica que no tenga preñeces asociadas antes de eliminar.
    """
    inseminacion = get_object_or_404(
        Inseminacion.objects.select_related('fk_an', 'fk_toro_in'),
        id_in=id_in
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_inseminacion = inseminacion.id_in
    tipo_inseminacion = inseminacion.tipo_inseminacion_in
    codigo_hembra = inseminacion.fk_an.codigo_an
    
    try:
        # ==========================================
        # VERIFICAR DEPENDENCIAS (preñeces asociadas)
        # ==========================================
        # Si hay preñeces vinculadas a esta inseminación, no permitir eliminar
        from .models import Preñez  # Importar modelo de preñeces
        if Preñez.objects.filter(fk_in=inseminacion).exists():
            messages.error(request, f"No se puede eliminar: esta inseminación tiene preñeces asociadas")
            return redirect('/listainseminacion/')
        
        # ==========================================
        # ELIMINAR INSEMINACIÓN
        # ==========================================
        inseminacion.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'Inseminacion',
            id_inseminacion,
            f'Se eliminó inseminación {tipo_inseminacion}: {codigo_hembra}'
        )
        
        messages.success(request, f"Inseminación {tipo_inseminacion.upper()} eliminada exitosamente")
        
    except IntegrityError:
        messages.error(request, f"No se puede eliminar la inseminación: tiene registros asociados")
    
    return redirect('/listainseminacion/')

# ==========================================
# PREÑECES
# ==========================================
def listaprenez(request):
    """
    Muestra el listado completo de preñeces con estadísticas.
    Incluye conteos por método diagnóstico, inseminación vinculada,
    próximas a parto (≤30 días) y fechas vencidas.
    """
    prenez_list = Prenez.objects.all().select_related(
        'fk_an', 'fk_in', 'fk_in__fk_toro_in', 'fk_us_pr'
    ).order_by('-fecha_confirmacion_pr', '-created_at_pr')
    
    # Calcular días restantes para cada preñez
    hoy = date.today()
    for prenez in prenez_list:
        if prenez.fecha_probable_parto_pr:
            prenez.dias_restantes = (prenez.fecha_probable_parto_pr - hoy).days
        else:
            prenez.dias_restantes = None
    
    # Estadísticas generales
    total_prenez = prenez_list.count()
    total_con_inseminacion = prenez_list.filter(fk_in__isnull=False).count()
    total_palpacion = prenez_list.filter(metodo_diagnostico_pr='palpacion').count()
    total_ultrasonido = prenez_list.filter(metodo_diagnostico_pr='ultrasonido').count()
    
    # Próximas a parto (≤30 días y no vencidas)
    proximas_a_parto = sum(
        1 for p in prenez_list 
        if p.dias_restantes is not None and 0 < p.dias_restantes <= 30
    )
    
    # Fechas vencidas (días restantes ≤ 0)
    vencidas = sum(
        1 for p in prenez_list 
        if p.dias_restantes is not None and p.dias_restantes <= 0
    )
    
    contexto = {
        'prenez_list': prenez_list,
        'total_prenez': total_prenez,
        'total_con_inseminacion': total_con_inseminacion,
        'total_palpacion': total_palpacion,
        'total_ultrasonido': total_ultrasonido,
        'proximas_a_parto': proximas_a_parto,
        'vencidas': vencidas,
    }
    
    return render(request, 'catalogos/reproduccion/prenez/lista_prenez.html', contexto)

# ==========================================
# VISTA: NUEVA PREÑEZ (formulario)
# ==========================================
def nuevaprenez(request):
    """
    Muestra el formulario para registrar una nueva preñez.
    Carga lista de animales hembras activas en categoría reproductiva
    e inseminaciones pendientes o con resultado positivo.
    """
    # Animales hembras activas en categorías reproductivas
    animales = Animal.objects.filter(
        sexo_an='H',
        estado_an='activo',
        categoria_an__in=['vaca_leche', 'vaca_seca', 'novilla']
    ).select_related('fk_ra').order_by('codigo_an')
    
    # Inseminaciones disponibles para vincular (resultado pendiente o preñada)
    inseminaciones = Inseminacion.objects.filter(
        Q(resultado_in='pendiente') | Q(resultado_in='preñada'),
        fk_an__sexo_an='H'
    ).select_related('fk_an', 'fk_toro_in').order_by('-fecha_in')
    
    contexto = {
        'animales': animales,
        'inseminaciones': inseminaciones,
    }
    
    return render(request, 'catalogos/reproduccion/prenez/nueva_prenez.html', contexto)

# ==========================================
# VISTA: GUARDAR PREÑEZ (procesar creación)
# ==========================================
def guardarprenez(request):
    """
    Procesa el formulario de creación de una nueva preñez.
    Valida datos, verifica reglas de negocio, vincula inseminación si aplica,
    y registra auditoría.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevaprenez/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Animal (obligatorio)
        fk_an_id = request.POST.get('sel_animal_pr')
        if not fk_an_id:
            messages.error(request, "Debe seleccionar un animal")
            return redirect('/nuevaprenez/')
        
        animal = get_object_or_404(Animal, id_an=fk_an_id)
        
        # Validar que sea hembra
        if animal.sexo_an != 'H':
            messages.error(request, f"El animal {animal.codigo_an} no es hembra. Solo se registran preñeces en hembras.")
            return redirect('/nuevaprenez/')
        
        # Validar categoría reproductiva
        categorias_validas = ['vaca_leche', 'vaca_seca', 'novilla']
        if animal.categoria_an not in categorias_validas:
            messages.error(request, f"El animal {animal.codigo_an} debe ser vaca_leche, vaca_seca o novilla.")
            return redirect('/nuevaprenez/')
        
        # Validar que esté activo
        if animal.estado_an != 'activo':
            messages.error(request, f"El animal {animal.codigo_an} no está activo.")
            return redirect('/nuevaprenez/')
        
        # Fecha confirmación (obligatoria)
        fecha_confirmacion_pr = request.POST.get('txt_fecha_confirmacion_pr')
        if not fecha_confirmacion_pr:
            messages.error(request, "La fecha de confirmación es obligatoria")
            return redirect('/nuevaprenez/')
        
        # Validar que no sea futura
        if fecha_confirmacion_pr > str(date.today()):
            messages.error(request, "La fecha de confirmación no puede ser futura")
            return redirect('/nuevaprenez/')
        
        # Inseminación asociada (opcional)
        fk_in = None
        inseminacion_id = request.POST.get('sel_inseminacion_pr', '').strip()
        if inseminacion_id:
            fk_in = get_object_or_404(Inseminacion, id_in=inseminacion_id)
            # Validar que la inseminación sea del mismo animal
            if fk_in.fk_an_id != animal.id_an:
                messages.error(request, "La inseminación seleccionada no corresponde al animal elegido")
                return redirect('/nuevaprenez/')
        
        # Método diagnóstico (opcional pero validado)
        metodo_diagnostico_pr = request.POST.get('sel_metodo_diagnostico_pr', '').strip()
        metodos_validos = ['palpacion', 'ultrasonido', 'sangre', 'otro']
        if metodo_diagnostico_pr and metodo_diagnostico_pr not in metodos_validos:
            messages.error(request, "Método de diagnóstico no válido")
            return redirect('/nuevaprenez/')
        
        # Fecha probable parto (obligatoria)
        fecha_probable_parto_pr = request.POST.get('txt_fecha_probable_parto_pr')
        if not fecha_probable_parto_pr:
            messages.error(request, "La fecha probable de parto es obligatoria")
            return redirect('/nuevaprenez/')
        
        # Validar que sea posterior a fecha confirmación
        if fecha_probable_parto_pr <= fecha_confirmacion_pr:
            messages.error(request, "La fecha probable de parto debe ser posterior a la fecha de confirmación")
            return redirect('/nuevaprenez/')
        
        # Validar que no exceda 365 días
        fecha_conf = datetime.strptime(fecha_confirmacion_pr, '%Y-%m-%d').date()
        fecha_parto = datetime.strptime(fecha_probable_parto_pr, '%Y-%m-%d').date()
        if (fecha_parto - fecha_conf).days > 365:
            messages.error(request, "La fecha probable de parto no puede exceder 365 días desde la confirmación")
            return redirect('/nuevaprenez/')
        
        # Observaciones (opcional)
        observaciones_pr = request.POST.get('txt_observaciones_pr', '').strip()
        if observaciones_pr and len(observaciones_pr) > 1000:
            messages.error(request, "Las observaciones exceden 1000 caracteres")
            return redirect('/nuevaprenez/')
        
        # Usuario actual (obligatorio)
        try:
            fk_us_pr = Usuario.objects.get(id_us=request.session.get('id_us', 1))
        except Usuario.DoesNotExist:
            messages.error(request, "Error de autenticación de usuario")
            return redirect('/nuevaprenez/')
        
        # ==========================================
        # VERIFICAR PREÑEZ EXISTENTE ACTIVA
        # ==========================================
        prenez_existente = Prenez.objects.filter(
            fk_an=animal,
            fecha_probable_parto_pr__gte=date.today()
        ).exclude(
            id_pr__isnull=True  # Excluir la misma en edición (no aplica en creación)
        ).first()
        
        if prenez_existente:
            messages.warning(
                request, 
                f"ADVERTENCIA: El animal {animal.codigo_an} ya tiene una preñez activa "
                f"(ID: #{prenez_existente.id_pr}, parto estimado: {prenez_existente.fecha_probable_parto_pr}). "
                f"Verifique antes de continuar."
            )
        
        # ==========================================
        # CREAR PREÑEZ
        # ==========================================
        nueva_prenez = Prenez.objects.create(
            fk_an=animal,
            fk_in=fk_in,
            fecha_confirmacion_pr=fecha_confirmacion_pr,
            metodo_diagnostico_pr=metodo_diagnostico_pr if metodo_diagnostico_pr else None,
            fecha_probable_parto_pr=fecha_probable_parto_pr,
            observaciones_pr=observaciones_pr if observaciones_pr else None,
            fk_us_pr=fk_us_pr
        )
        
        # ==========================================
        # ACTUALIZAR RESULTADO DE INSEMINACIÓN SI APLICA
        # ==========================================
        if fk_in and fk_in.resultado_in == 'pendiente':
            fk_in.resultado_in = 'preñada'
            fk_in.fecha_resultado_in = date.today()
            fk_in.save()
            messages.info(request, f"Resultado de inseminación #{fk_in.id_in} actualizado a 'Preñada'")
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'Prenez',
            nueva_prenez.id_pr,
            f'Se creó preñez: {animal.codigo_an} - Confirmación: {fecha_confirmacion_pr} - Parto estimado: {fecha_probable_parto_pr}'
        )
        
        messages.success(request, f"Preñez de '{animal.codigo_an}' registrada exitosamente. Fecha probable de parto: {fecha_probable_parto_pr}")
        return redirect('/listaprenez/')
        
    except Animal.DoesNotExist:
        messages.error(request, "Animal no encontrado")
        return redirect('/nuevaprenez/')
    except Inseminacion.DoesNotExist:
        messages.error(request, "Inseminación no encontrada")
        return redirect('/nuevaprenez/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect('/nuevaprenez/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevaprenez/')

# ==========================================
# VISTA: EDITAR PREÑEZ (formulario)
# ==========================================
def editarprenez(request, id_pr):
    """
    Muestra el formulario de edición con los datos precargados.
    El animal no se puede cambiar. La inseminación sí se puede modificar.
    """
    prenez = get_object_or_404(
        Prenez.objects.select_related('fk_an', 'fk_in', 'fk_in__fk_toro_in', 'fk_us_pr'),
        id_pr=id_pr
    )
    
    # Inseminaciones disponibles para vincular (incluir la actual aunque tenga otro estado)
    inseminaciones = Inseminacion.objects.filter(
        Q(fk_an=prenez.fk_an) | Q(id_in=prenez.fk_in_id)
    ).select_related('fk_an', 'fk_toro_in').order_by('-fecha_in')
    
    # Calcular días restantes
    hoy = date.today()
    if prenez.fecha_probable_parto_pr:
        prenez.dias_restantes = (prenez.fecha_probable_parto_pr - hoy).days
    else:
        prenez.dias_restantes = None
    
    contexto = {
        'prenez': prenez,
        'inseminaciones': inseminaciones,
    }
    
    return render(request, 'catalogos/reproduccion/prenez/editar_prenez.html', contexto)

# ==========================================
# VISTA: PROCESAR EDICION PREÑEZ
# ==========================================
def procesareditarprenez(request):
    """
    Procesa el formulario de edición de una preñez existente.
    El animal no se puede modificar. La inseminación sí.
    Maneja cambio de inseminación vinculada y actualiza resultados.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listaprenez/')
    
    try:
        # Obtener preñez existente
        id_pr = request.POST.get('id_pr')
        if not id_pr:
            messages.error(request, "ID de preñez no proporcionado")
            return redirect('/listaprenez/')
        
        prenez = Prenez.objects.select_related('fk_an', 'fk_in').get(id_pr=id_pr)
        animal = prenez.fk_an
        inseminacion_anterior = prenez.fk_in
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha confirmación (obligatoria)
        fecha_confirmacion_pr = request.POST.get('txt_fecha_confirmacion_pr')
        if not fecha_confirmacion_pr:
            messages.error(request, "La fecha de confirmación es obligatoria")
            return redirect(f'/editarprenez/{id_pr}')
        
        # Validar que no sea futura
        if fecha_confirmacion_pr > str(date.today()):
            messages.error(request, "La fecha de confirmación no puede ser futura")
            return redirect(f'/editarprenez/{id_pr}')
        
        # Inseminación asociada (opcional, puede cambiar)
        fk_in = None
        inseminacion_id = request.POST.get('sel_inseminacion_pr', '').strip()
        if inseminacion_id:
            fk_in = get_object_or_404(Inseminacion, id_in=inseminacion_id)
            # Validar que sea del mismo animal
            if fk_in.fk_an_id != animal.id_an:
                messages.error(request, "La inseminación seleccionada no corresponde al animal de esta preñez")
                return redirect(f'/editarprenez/{id_pr}')
        else:
            # Si desvincula inseminación, verificar que no sea obligatoria
            pass  # Es opcional, se permite desvincular
        
        # Método diagnóstico (opcional)
        metodo_diagnostico_pr = request.POST.get('sel_metodo_diagnostico_pr', '').strip()
        metodos_validos = ['palpacion', 'ultrasonido', 'sangre', 'otro']
        if metodo_diagnostico_pr and metodo_diagnostico_pr not in metodos_validos:
            messages.error(request, "Método de diagnóstico no válido")
            return redirect(f'/editarprenez/{id_pr}')
        
        # Fecha probable parto (obligatoria)
        fecha_probable_parto_pr = request.POST.get('txt_fecha_probable_parto_pr')
        if not fecha_probable_parto_pr:
            messages.error(request, "La fecha probable de parto es obligatoria")
            return redirect(f'/editarprenez/{id_pr}')
        
        # Validar que sea posterior a fecha confirmación
        if fecha_probable_parto_pr <= fecha_confirmacion_pr:
            messages.error(request, "La fecha probable de parto debe ser posterior a la fecha de confirmación")
            return redirect(f'/editarprenez/{id_pr}')
        
        # Validar que no exceda 365 días
        fecha_conf = datetime.strptime(fecha_confirmacion_pr, '%Y-%m-%d').date()
        fecha_parto = datetime.strptime(fecha_probable_parto_pr, '%Y-%m-%d').date()
        if (fecha_parto - fecha_conf).days > 365:
            messages.error(request, "La fecha probable de parto no puede exceder 365 días desde la confirmación")
            return redirect(f'/editarprenez/{id_pr}')
        
        # Observaciones (opcional)
        observaciones_pr = request.POST.get('txt_observaciones_pr', '').strip()
        if observaciones_pr and len(observaciones_pr) > 1000:
            messages.error(request, "Las observaciones exceden 1000 caracteres")
            return redirect(f'/editarprenez/{id_pr}')
        
        # ==========================================
        # MANEJO DE CAMBIO DE INSEMINACIÓN
        # ==========================================
        # Si cambia la inseminación vinculada
        if inseminacion_anterior and (not fk_in or fk_in.id_in != inseminacion_anterior.id_in):
            # Si la inseminación anterior tenía resultado 'preñada', revertir a 'pendiente'
            if inseminacion_anterior.resultado_in == 'preñada':
                inseminacion_anterior.resultado_in = 'pendiente'
                inseminacion_anterior.fecha_resultado_in = None
                inseminacion_anterior.save()
                messages.info(request, f"Resultado de inseminación anterior #{inseminacion_anterior.id_in} revertido a 'Pendiente'")
        
        # Si vincula nueva inseminación
        if fk_in and (not inseminacion_anterior or fk_in.id_in != inseminacion_anterior.id_in):
            if fk_in.resultado_in == 'pendiente':
                fk_in.resultado_in = 'preñada'
                fk_in.fecha_resultado_in = date.today()
                fk_in.save()
                messages.info(request, f"Resultado de inseminación #{fk_in.id_in} actualizado a 'Preñada'")
        
        # ==========================================
        # ACTUALIZAR PREÑEZ
        # ==========================================
        prenez.fk_in = fk_in
        prenez.fecha_confirmacion_pr = fecha_confirmacion_pr
        prenez.metodo_diagnostico_pr = metodo_diagnostico_pr if metodo_diagnostico_pr else None
        prenez.fecha_probable_parto_pr = fecha_probable_parto_pr
        prenez.observaciones_pr = observaciones_pr if observaciones_pr else None
        
        prenez.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'Prenez',
            prenez.id_pr,
            f'Se editó preñez #{id_pr}: {animal.codigo_an} - Parto estimado: {fecha_probable_parto_pr}'
        )
        
        messages.success(request, f"Preñez de '{animal.codigo_an}' actualizada exitosamente")
        return redirect('/listaprenez/')
        
    except Prenez.DoesNotExist:
        messages.error(request, "Preñez no encontrada")
        return redirect('/listaprenez/')
    except Inseminacion.DoesNotExist:
        messages.error(request, "Inseminación no encontrada")
        return redirect(f'/editarprenez/{id_pr}')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect(f'/editarprenez/{id_pr}')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarprenez/{id_pr}')

# ==========================================
# VISTA: ELIMINAR PREÑEZ
# ==========================================
def eliminaprenez(request, id_pr):
    """
    Elimina una preñez del sistema.
    Revierte el resultado de la inseminación vinculada si aplica.
    """
    prenez = get_object_or_404(
        Prenez.objects.select_related('fk_an', 'fk_in'),
        id_pr=id_pr
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_prenez = prenez.id_pr
    codigo_animal = prenez.fk_an.codigo_an
    inseminacion = prenez.fk_in
    
    try:
        # ==========================================
        # REVERTIR RESULTADO DE INSEMINACIÓN SI APLICA
        # ==========================================
        if inseminacion and inseminacion.resultado_in == 'preñada':
            inseminacion.resultado_in = 'pendiente'
            inseminacion.fecha_resultado_in = None
            inseminacion.save()
            messages.info(request, f"Resultado de inseminación #{inseminacion.id_in} revertido a 'Pendiente'")
        
        # ==========================================
        # ELIMINAR PREÑEZ
        # ==========================================
        prenez.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'Prenez',
            id_prenez,
            f'Se eliminó preñez #{id_prenez}: {codigo_animal}'
        )
        
        messages.success(request, f"Preñez de {codigo_animal} eliminada exitosamente")
        
    except Exception as e:
        messages.error(request, f"Error al eliminar: {str(e)}")
    
    return redirect('/listaprenez/')


# ==========================================
# VISTA: LISTAR PARTOS
# ==========================================
def listapartos(request):
    """
    Muestra el listado completo de partos con estadísticas.
    Incluye conteos por tipo de parto, asistencia veterinaria y crías registradas.
    """
    parto_list = Parto.objects.all().select_related(
        'fk_madre_pa', 'fk_pr', 'fk_cria_pa', 'fk_us_pa'
    ).order_by('-fecha_pa', '-created_at_pa')
    
    # Estadísticas generales
    total_partos = parto_list.count()
    total_normales = parto_list.filter(tipo_parto_pa='normal').count()
    total_distocicos = parto_list.filter(tipo_parto_pa='distocico').count()
    total_cesareas = parto_list.filter(tipo_parto_pa='cesarea').count()
    total_con_veterinario = parto_list.filter(asistencia_veterinaria_pa=True).count()
    total_crias_registradas = parto_list.filter(fk_cria_pa__isnull=False).count()
    
    contexto = {
        'parto_list': parto_list,
        'total_partos': total_partos,
        'total_normales': total_normales,
        'total_distocicos': total_distocicos,
        'total_cesareas': total_cesareas,
        'total_con_veterinario': total_con_veterinario,
        'total_crias_registradas': total_crias_registradas,
    }
    
    return render(request, 'catalogos/reproduccion/partos/lista_parto.html', contexto)

# ==========================================
# VISTA: NUEVO PARTO (formulario)
# ==========================================
def nuevoparto(request):
    """
    Muestra el formulario para registrar un nuevo parto.
    Carga lista de madres (hembras activas en categoría reproductiva),
    preñeces activas y crías disponibles para vincular.
    """
    # Madres: hembras activas en categorías reproductivas
    madres = Animal.objects.filter(
        sexo_an='H',
        estado_an='activo',
        categoria_an__in=['vaca_leche', 'vaca_seca', 'novilla']
    ).select_related('fk_ra').order_by('codigo_an')
    
    # Preñeces activas (con fecha probable de parto >= hoy o no vencidas hace mucho)
    preneces = Prenez.objects.filter(
        fecha_probable_parto_pr__gte=date.today() - timedelta(days=60)
    ).select_related('fk_an').order_by('-fecha_confirmacion_pr')
    
    # Crías disponibles para vincular (animales recién nacidos sin parto asociado)
    crias_ids = Parto.objects.exclude(fk_cria_pa__isnull=True).values_list('fk_cria_pa', flat=True)
    crias_disponibles = Animal.objects.filter(
        categoria_an='ternero',
        estado_an='activo'
    ).exclude(id_an__in=crias_ids).select_related('fk_ra').order_by('codigo_an')
    
    contexto = {
        'madres': madres,
        'preneces': preneces,
        'crias_disponibles': crias_disponibles,
    }
    
    return render(request, 'catalogos/reproduccion/partos/nuevo_parto.html', contexto)

# ==========================================
# VISTA: GUARDAR PARTO (procesar creación)
# ==========================================
def guardarparto(request):
    """
    Procesa el formulario de creación de un nuevo parto.
    Valida datos, verifica reglas de negocio, vincula preñez si aplica,
    y registra auditoría.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevoparto/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Madre (obligatoria)
        fk_madre_pa_id = request.POST.get('sel_madre_pa')
        if not fk_madre_pa_id:
            messages.error(request, "Debe seleccionar la madre")
            return redirect('/nuevoparto/')
        
        madre = get_object_or_404(Animal, id_an=fk_madre_pa_id)
        
        # Validar que sea hembra
        if madre.sexo_an != 'H':
            messages.error(request, f"El animal {madre.codigo_an} no es hembra. Solo se registran partos en hembras.")
            return redirect('/nuevoparto/')
        
        # Validar categoría reproductiva
        categorias_validas = ['vaca_leche', 'vaca_seca', 'novilla']
        if madre.categoria_an not in categorias_validas:
            messages.error(request, f"El animal {madre.codigo_an} debe ser vaca_leche, vaca_seca o novilla.")
            return redirect('/nuevoparto/')
        
        # Validar que esté activa
        if madre.estado_an != 'activo':
            messages.error(request, f"El animal {madre.codigo_an} no está activo.")
            return redirect('/nuevoparto/')
        
        # Fecha parto (obligatoria)
        fecha_pa = request.POST.get('txt_fecha_pa')
        if not fecha_pa:
            messages.error(request, "La fecha del parto es obligatoria")
            return redirect('/nuevoparto/')
        
        # Validar que no sea futura
        if fecha_pa > str(date.today()):
            messages.error(request, "La fecha del parto no puede ser futura")
            return redirect('/nuevoparto/')
        
        # Preñez asociada (opcional)
        fk_pr = None
        prenez_id = request.POST.get('sel_prenez_pa', '').strip()
        if prenez_id:
            fk_pr = get_object_or_404(Prenez, id_pr=prenez_id)
            # Validar que la preñez sea de la misma madre
            if fk_pr.fk_an_id != madre.id_an:
                messages.error(request, "La preñez seleccionada no corresponde a la madre elegida")
                return redirect('/nuevoparto/')
        
        # Tipo de parto (opcional pero validado)
        tipo_parto_pa = request.POST.get('sel_tipo_parto_pa', '').strip()
        tipos_validos = ['normal', 'distocico', 'cesarea']
        if tipo_parto_pa and tipo_parto_pa not in tipos_validos:
            messages.error(request, "Tipo de parto no válido")
            return redirect('/nuevoparto/')
        
        # Asistencia veterinaria
        asistencia_veterinaria_pa = request.POST.get('chk_asistencia_veterinaria_pa') == 'on'
        
        # Sexo cría (opcional)
        cria_sexo_pa = request.POST.get('sel_cria_sexo_pa', '').strip()
        if cria_sexo_pa and cria_sexo_pa not in ['M', 'H']:
            messages.error(request, "Sexo de la cría no válido")
            return redirect('/nuevoparto/')
        
        # Peso cría (opcional)
        cria_peso_kg_pa = None
        peso_str = request.POST.get('txt_cria_peso_kg_pa', '').strip()
        if peso_str:
            try:
                cria_peso_kg_pa = float(peso_str)
                if cria_peso_kg_pa < 5 or cria_peso_kg_pa > 70:
                    messages.error(request, "El peso de la cría debe estar entre 5 y 70 kg")
                    return redirect('/nuevoparto/')
            except ValueError:
                messages.error(request, "Peso de la cría inválido")
                return redirect('/nuevoparto/')
        
        # Cría vinculada como animal (opcional)
        fk_cria_pa = None
        cria_id = request.POST.get('sel_cria_pa', '').strip()
        if cria_id:
            fk_cria_pa = get_object_or_404(Animal, id_an=cria_id)
            # Validar consistencia de sexo
            if cria_sexo_pa and fk_cria_pa.sexo_an != cria_sexo_pa:
                messages.error(request, "El sexo de la cría no coincide con el animal vinculado")
                return redirect('/nuevoparto/')
        
        # Observaciones (opcional)
        observaciones_pa = request.POST.get('txt_observaciones_pa', '').strip()
        if observaciones_pa and len(observaciones_pa) > 2000:
            messages.error(request, "Las observaciones exceden 2000 caracteres")
            return redirect('/nuevoparto/')
        
        # Usuario actual (obligatorio)
        try:
            fk_us_pa = Usuario.objects.get(id_us=request.session.get('id_us', 1))
        except Usuario.DoesNotExist:
            messages.error(request, "Error de autenticación de usuario")
            return redirect('/nuevoparto/')
        
        # ==========================================
        # VERIFICAR PARTO EXISTENTE RECIENTE
        # ==========================================
        parto_existente = Parto.objects.filter(
            fk_madre_pa=madre,
            fecha_pa__gte=date.today() - timedelta(days=30)
        ).first()
        
        if parto_existente:
            messages.warning(
                request, 
                f"ADVERTENCIA: La madre {madre.codigo_an} ya tuvo un parto registrado recientemente "
                f"(ID: #{parto_existente.id_pa}, fecha: {parto_existente.fecha_pa}). "
                f"Verifique antes de continuar."
            )
        
        # ==========================================
        # CREAR PARTO
        # ==========================================
        nuevo_parto = Parto.objects.create(
            fk_madre_pa=madre,
            fk_pr=fk_pr,
            fecha_pa=fecha_pa,
            tipo_parto_pa=tipo_parto_pa if tipo_parto_pa else None,
            cria_sexo_pa=cria_sexo_pa if cria_sexo_pa else None,
            cria_peso_kg_pa=cria_peso_kg_pa,
            fk_cria_pa=fk_cria_pa,
            asistencia_veterinaria_pa=asistencia_veterinaria_pa,
            observaciones_pa=observaciones_pa if observaciones_pa else None,
            fk_us_pa=fk_us_pa
        )
        
        # ==========================================
        # ACTUALIZAR ESTADO DE LA PREÑEZ SI APLICA
        # ==========================================
        if fk_pr:
            # La preñez ha culminado en parto - podrías agregar un campo estado si lo tienes
            messages.info(request, f"Preñez #{fk_pr.id_pr} marcada como culminada en parto")
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'Parto',
            nuevo_parto.id_pa,
            f'Se creó parto: {madre.codigo_an} - Fecha: {fecha_pa} - Tipo: {tipo_parto_pa or "No especificado"}'
        )
        
        messages.success(request, f"Parto de '{madre.codigo_an}' registrado exitosamente")
        return redirect('/listapartos/')
        
    except Animal.DoesNotExist:
        messages.error(request, "Madre no encontrada")
        return redirect('/nuevoparto/')
    except Prenez.DoesNotExist:
        messages.error(request, "Preñez no encontrada")
        return redirect('/nuevoparto/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect('/nuevoparto/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevoparto/')

# ==========================================
# VISTA: EDITAR PARTO (formulario)
# ==========================================
def editarparto(request, id_pa):
    """
    Muestra el formulario de edición con los datos precargados.
    La madre no se puede cambiar. La preñez sí se puede modificar.
    """
    parto = get_object_or_404(
        Parto.objects.select_related('fk_madre_pa', 'fk_pr', 'fk_cria_pa', 'fk_us_pa'),
        id_pa=id_pa
    )
    
    # Preñeces disponibles para vincular (incluir la actual aunque tenga otra madre)
    preneces = Prenez.objects.filter(
        Q(fk_an=parto.fk_madre_pa) | Q(id_pr=parto.fk_pr_id)
    ).select_related('fk_an').order_by('-fecha_confirmacion_pr')
    
    # Crías disponibles para vincular (excluir las ya vinculadas a otros partos, incluir la actual)
    crias_ids = Parto.objects.exclude(
        id_pa=parto.id_pa
    ).exclude(
        fk_cria_pa__isnull=True
    ).values_list('fk_cria_pa', flat=True)
    
    crias_disponibles = Animal.objects.filter(
        Q(categoria_an='ternero', estado_an='activo') | Q(id_an=parto.fk_cria_pa_id)
    ).exclude(
        id_an__in=crias_ids
    ).select_related('fk_ra').order_by('codigo_an')
    
    contexto = {
        'parto': parto,
        'preneces': preneces,
        'crias_disponibles': crias_disponibles,
    }
    
    return render(request, 'catalogos/reproduccion/partos/editar_parto.html', contexto)

# ==========================================
# VISTA: PROCESAR EDICION PARTO
# ==========================================
def procesareditarparto(request):
    """
    Procesa el formulario de edición de un parto existente.
    La madre no se puede modificar. La preñez, cría y demás datos sí.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listapartos/')
    
    try:
        # Obtener parto existente
        id_pa = request.POST.get('id_pa')
        if not id_pa:
            messages.error(request, "ID de parto no proporcionado")
            return redirect('/listapartos/')
        
        parto = Parto.objects.select_related('fk_madre_pa', 'fk_pr', 'fk_cria_pa').get(id_pa=id_pa)
        madre = parto.fk_madre_pa
        prenez_anterior = parto.fk_pr
        cria_anterior = parto.fk_cria_pa
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha parto (obligatoria)
        fecha_pa = request.POST.get('txt_fecha_pa')
        if not fecha_pa:
            messages.error(request, "La fecha del parto es obligatoria")
            return redirect(f'/editarparto/{id_pa}')
        
        # Validar que no sea futura
        if fecha_pa > str(date.today()):
            messages.error(request, "La fecha del parto no puede ser futura")
            return redirect(f'/editarparto/{id_pa}')
        
        # Preñez asociada (opcional, puede cambiar)
        fk_pr = None
        prenez_id = request.POST.get('sel_prenez_pa', '').strip()
        if prenez_id:
            fk_pr = get_object_or_404(Prenez, id_pr=prenez_id)
            # Validar que sea de la misma madre
            if fk_pr.fk_an_id != madre.id_an:
                messages.error(request, "La preñez seleccionada no corresponde a la madre de este parto")
                return redirect(f'/editarparto/{id_pa}')
        
        # Tipo de parto (opcional)
        tipo_parto_pa = request.POST.get('sel_tipo_parto_pa', '').strip()
        tipos_validos = ['normal', 'distocico', 'cesarea']
        if tipo_parto_pa and tipo_parto_pa not in tipos_validos:
            messages.error(request, "Tipo de parto no válido")
            return redirect(f'/editarparto/{id_pa}')
        
        # Asistencia veterinaria
        asistencia_veterinaria_pa = request.POST.get('chk_asistencia_veterinaria_pa') == 'on'
        
        # Sexo cría (opcional)
        cria_sexo_pa = request.POST.get('sel_cria_sexo_pa', '').strip()
        if cria_sexo_pa and cria_sexo_pa not in ['M', 'H']:
            messages.error(request, "Sexo de la cría no válido")
            return redirect(f'/editarparto/{id_pa}')
        
        # Peso cría (opcional)
        cria_peso_kg_pa = None
        peso_str = request.POST.get('txt_cria_peso_kg_pa', '').strip()
        if peso_str:
            try:
                cria_peso_kg_pa = float(peso_str)
                if cria_peso_kg_pa < 5 or cria_peso_kg_pa > 70:
                    messages.error(request, "El peso de la cría debe estar entre 5 y 70 kg")
                    return redirect(f'/editarparto/{id_pa}')
            except ValueError:
                messages.error(request, "Peso de la cría inválido")
                return redirect(f'/editarparto/{id_pa}')
        
        # Cría vinculada (opcional, puede cambiar)
        fk_cria_pa = None
        cria_id = request.POST.get('sel_cria_pa', '').strip()
        if cria_id:
            fk_cria_pa = get_object_or_404(Animal, id_an=cria_id)
            # Validar consistencia de sexo
            if cria_sexo_pa and fk_cria_pa.sexo_an != cria_sexo_pa:
                messages.error(request, "El sexo de la cría no coincide con el animal vinculado")
                return redirect(f'/editarparto/{id_pa}')
        
        # Observaciones (opcional)
        observaciones_pa = request.POST.get('txt_observaciones_pa', '').strip()
        if observaciones_pa and len(observaciones_pa) > 2000:
            messages.error(request, "Las observaciones exceden 2000 caracteres")
            return redirect(f'/editarparto/{id_pa}')
        
        # ==========================================
        # ACTUALIZAR PARTO
        # ==========================================
        parto.fk_pr = fk_pr
        parto.fecha_pa = fecha_pa
        parto.tipo_parto_pa = tipo_parto_pa if tipo_parto_pa else None
        parto.asistencia_veterinaria_pa = asistencia_veterinaria_pa
        parto.cria_sexo_pa = cria_sexo_pa if cria_sexo_pa else None
        parto.cria_peso_kg_pa = cria_peso_kg_pa
        parto.fk_cria_pa = fk_cria_pa
        parto.observaciones_pa = observaciones_pa if observaciones_pa else None
        
        parto.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'Parto',
            parto.id_pa,
            f'Se editó parto #{id_pa}: {madre.codigo_an} - Fecha: {fecha_pa}'
        )
        
        messages.success(request, f"Parto de '{madre.codigo_an}' actualizado exitosamente")
        return redirect('/listapartos/')
        
    except Parto.DoesNotExist:
        messages.error(request, "Parto no encontrado")
        return redirect('/listapartos/')
    except Prenez.DoesNotExist:
        messages.error(request, "Preñez no encontrada")
        return redirect(f'/editarparto/{id_pa}')
    except Animal.DoesNotExist:
        messages.error(request, "Animal no encontrado")
        return redirect(f'/editarparto/{id_pa}')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect(f'/editarparto/{id_pa}')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarparto/{id_pa}')

# ==========================================
# VISTA: ELIMINAR PARTO
# ==========================================
def eliminaparto(request, id_pa):
    """
    Elimina un parto del sistema.
    Desvincula la preñez y la cría si aplica.
    """
    parto = get_object_or_404(
        Parto.objects.select_related('fk_madre_pa', 'fk_pr', 'fk_cria_pa'),
        id_pa=id_pa
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_parto = parto.id_pa
    codigo_madre = parto.fk_madre_pa.codigo_an
    
    try:
        # ==========================================
        # ELIMINAR PARTO
        # ==========================================
        parto.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'Parto',
            id_parto,
            f'Se eliminó parto #{id_parto}: {codigo_madre}'
        )
        
        messages.success(request, f"Parto de {codigo_madre} eliminado exitosamente")
        
    except Exception as e:
        messages.error(request, f"Error al eliminar: {str(e)}")
    
    return redirect('/listapartos/')

#=========================================
# VISTA: LISTAR ABORTOS
# ==========================================
def listaabortos(request):
    """
    Muestra el listado completo de abortos con estadísticas.
    Incluye conteos por destino de la madre y abortos del mes actual.
    """
    aborto_list = Aborto.objects.all().select_related(
        'fk_an', 'fk_us_ab'
    ).order_by('-fecha_ab', '-created_at_ab')
    
    # Estadísticas generales
    total_abortos = aborto_list.count()
    total_reproduccion = aborto_list.filter(destino_madre_ab='reproduccion').count()
    total_reengorde = aborto_list.filter(destino_madre_ab='reengorde').count()
    total_venta = aborto_list.filter(destino_madre_ab='venta').count()
    total_baja = aborto_list.filter(destino_madre_ab='baja').count()
    
    # Abortos del mes actual
    hoy = date.today()
    abortos_mes = aborto_list.filter(
        fecha_ab__year=hoy.year,
        fecha_ab__month=hoy.month
    ).count()
    
    contexto = {
        'aborto_list': aborto_list,
        'total_abortos': total_abortos,
        'total_reproduccion': total_reproduccion,
        'total_reengorde': total_reengorde,
        'total_venta': total_venta,
        'total_baja': total_baja,
        'abortos_mes': abortos_mes,
    }
    
    return render(request, 'catalogos/reproduccion/aborto/lista_aborto.html', contexto)

# ==========================================
# VISTA: NUEVO ABORTO (formulario)
# ==========================================
def nuevoaborto(request):
    """
    Muestra el formulario para registrar un nuevo aborto.
    Carga lista de animales hembras activas en categoría reproductiva.
    """
    # Animales hembras activas en categorías reproductivas
    animales = Animal.objects.filter(
        sexo_an='H',
        estado_an='activo',
        categoria_an__in=['vaca_leche', 'vaca_seca', 'novilla']
    ).select_related('fk_ra').order_by('codigo_an')
    
    contexto = {
        'animales': animales,
    }
    
    return render(request, 'catalogos/reproduccion/aborto/nuevo_aborto.html', contexto)

# ==========================================
# VISTA: GUARDAR ABORTO (procesar creación)
# ==========================================
def guardaraborto(request):
    """
    Procesa el formulario de creación de un nuevo aborto.
    Valida datos, verifica reglas de negocio, y registra auditoría.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevoaborto/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Animal (obligatorio)
        fk_an_id = request.POST.get('sel_animal_ab')
        if not fk_an_id:
            messages.error(request, "Debe seleccionar un animal")
            return redirect('/nuevoaborto/')
        
        animal = get_object_or_404(Animal, id_an=fk_an_id)
        
        # Validar que sea hembra
        if animal.sexo_an != 'H':
            messages.error(request, f"El animal {animal.codigo_an} no es hembra. Solo se registran abortos en hembras.")
            return redirect('/nuevoaborto/')
        
        # Validar categoría reproductiva
        categorias_validas = ['vaca_leche', 'vaca_seca', 'novilla']
        if animal.categoria_an not in categorias_validas:
            messages.error(request, f"El animal {animal.codigo_an} debe ser vaca_leche, vaca_seca o novilla.")
            return redirect('/nuevoaborto/')
        
        # Validar que esté activo
        if animal.estado_an != 'activo':
            messages.error(request, f"El animal {animal.codigo_an} no está activo.")
            return redirect('/nuevoaborto/')
        
        # Fecha aborto (obligatoria)
        fecha_ab = request.POST.get('txt_fecha_ab')
        if not fecha_ab:
            messages.error(request, "La fecha del aborto es obligatoria")
            return redirect('/nuevoaborto/')
        
        # Validar que no sea futura
        if fecha_ab > str(date.today()):
            messages.error(request, "La fecha del aborto no puede ser futura")
            return redirect('/nuevoaborto/')
        
        # Causa probable (opcional)
        causa_probable_ab = request.POST.get('txt_causa_probable_ab', '').strip()
        if causa_probable_ab and len(causa_probable_ab) > 1000:
            messages.error(request, "La causa probable excede 1000 caracteres")
            return redirect('/nuevoaborto/')
        
        # Tratamiento (opcional)
        tratamiento_ab = request.POST.get('txt_tratamiento_ab', '').strip()
        if tratamiento_ab and len(tratamiento_ab) > 1000:
            messages.error(request, "El tratamiento excede 1000 caracteres")
            return redirect('/nuevoaborto/')
        
        # Destino de la madre (obligatorio)
        destino_madre_ab = request.POST.get('sel_destino_madre_ab', '').strip()
        destinos_validos = ['reproduccion', 'reengorde', 'venta', 'baja']
        if not destino_madre_ab or destino_madre_ab not in destinos_validos:
            messages.error(request, "Debe seleccionar un destino válido para la madre")
            return redirect('/nuevoaborto/')
        
        # Usuario actual (obligatorio)
        try:
            fk_us_ab = Usuario.objects.get(id_us=request.session.get('id_us', 1))
        except Usuario.DoesNotExist:
            messages.error(request, "Error de autenticación de usuario")
            return redirect('/nuevoaborto/')
        
        # ==========================================
        # VERIFICAR ABORTO EXISTENTE RECIENTE
        # ==========================================
        aborto_existente = Aborto.objects.filter(
            fk_an=animal,
            fecha_ab__gte=date.today() - timedelta(days=30)
        ).first()
        
        if aborto_existente:
            messages.warning(
                request, 
                f"ADVERTENCIA: El animal {animal.codigo_an} ya tuvo un aborto registrado recientemente "
                f"(ID: #{aborto_existente.id_ab}, fecha: {aborto_existente.fecha_ab}). "
                f"Verifique antes de continuar."
            )
        
        # ==========================================
        # CREAR ABORTO
        # ==========================================
        nuevo_aborto = Aborto.objects.create(
            fk_an=animal,
            fecha_ab=fecha_ab,
            causa_probable_ab=causa_probable_ab if causa_probable_ab else None,
            tratamiento_ab=tratamiento_ab if tratamiento_ab else None,
            destino_madre_ab=destino_madre_ab,
            fk_us_ab=fk_us_ab
        )
        
        # ==========================================
        # ACTUALIZAR ESTADO DEL ANIMAL SEGÚN DESTINO
        # ==========================================
        if destino_madre_ab == 'baja':
            animal.estado_an = 'retirado'
            animal.fecha_salida_an = date.today()
            animal.motivo_salida_an = 'Aborto - baja definitiva'
            animal.save()
            messages.info(request, f"Animal {animal.codigo_an} dado de baja automáticamente")
        elif destino_madre_ab == 'venta':
            animal.estado_an = 'vendido'
            animal.fecha_salida_an = date.today()
            animal.motivo_salida_an = 'Aborto - venta'
            animal.save()
            messages.info(request, f"Animal {animal.codigo_an} marcado como vendido")
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'Aborto',
            nuevo_aborto.id_ab,
            f'Se creó aborto: {animal.codigo_an} - Fecha: {fecha_ab} - Destino: {destino_madre_ab}'
        )
        
        messages.success(request, f"Aborto de '{animal.codigo_an}' registrado exitosamente. Destino: {destino_madre_ab}")
        return redirect('/listaabortos/')
        
    except Animal.DoesNotExist:
        messages.error(request, "Animal no encontrado")
        return redirect('/nuevoaborto/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect('/nuevoaborto/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevoaborto/')

# ==========================================
# VISTA: EDITAR ABORTO (formulario)
# ==========================================
def editaraborto(request, id_ab):
    """
    Muestra el formulario de edición con los datos precargados.
    El animal no se puede cambiar. El destino y demás datos sí.
    """
    aborto = get_object_or_404(
        Aborto.objects.select_related('fk_an', 'fk_us_ab'),
        id_ab=id_ab
    )
    
    contexto = {
        'aborto': aborto,
    }
    
    return render(request, 'catalogos/reproduccion/aborto/editar_aborto.html', contexto)

# ==========================================
# VISTA: PROCESAR EDICION ABORTO
# ==========================================
def procesareditaraborto(request):
    """
    Procesa el formulario de edición de un aborto existente.
    El animal no se puede modificar. Fecha, causa, tratamiento y destino sí.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listaabortos/')
    
    try:
        # Obtener aborto existente
        id_ab = request.POST.get('id_ab')
        if not id_ab:
            messages.error(request, "ID de aborto no proporcionado")
            return redirect('/listaabortos/')
        
        aborto = Aborto.objects.select_related('fk_an').get(id_ab=id_ab)
        animal = aborto.fk_an
        destino_anterior = aborto.destino_madre_ab
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha aborto (obligatoria)
        fecha_ab = request.POST.get('txt_fecha_ab')
        if not fecha_ab:
            messages.error(request, "La fecha del aborto es obligatoria")
            return redirect(f'/editaraborto/{id_ab}')
        
        # Validar que no sea futura
        if fecha_ab > str(date.today()):
            messages.error(request, "La fecha del aborto no puede ser futura")
            return redirect(f'/editaraborto/{id_ab}')
        
        # Causa probable (opcional)
        causa_probable_ab = request.POST.get('txt_causa_probable_ab', '').strip()
        if causa_probable_ab and len(causa_probable_ab) > 1000:
            messages.error(request, "La causa probable excede 1000 caracteres")
            return redirect(f'/editaraborto/{id_ab}')
        
        # Tratamiento (opcional)
        tratamiento_ab = request.POST.get('txt_tratamiento_ab', '').strip()
        if tratamiento_ab and len(tratamiento_ab) > 1000:
            messages.error(request, "El tratamiento excede 1000 caracteres")
            return redirect(f'/editaraborto/{id_ab}')
        
        # Destino de la madre (obligatorio)
        destino_madre_ab = request.POST.get('sel_destino_madre_ab', '').strip()
        destinos_validos = ['reproduccion', 'reengorde', 'venta', 'baja']
        if not destino_madre_ab or destino_madre_ab not in destinos_validos:
            messages.error(request, "Debe seleccionar un destino válido para la madre")
            return redirect(f'/editaraborto/{id_ab}')
        
        # ==========================================
        # MANEJO DE CAMBIO DE DESTINO
        # ==========================================
        # Si cambia el destino, revertir estado anterior del animal si era baja o venta
        if destino_anterior != destino_madre_ab:
            if destino_anterior in ['baja', 'venta']:
                # Revertir estado del animal a activo
                animal.estado_an = 'activo'
                animal.fecha_salida_an = None
                animal.motivo_salida_an = None
                animal.save()
                messages.info(request, f"Estado anterior del animal {animal.codigo_an} revertido a activo")
            
            # Aplicar nuevo destino
            if destino_madre_ab == 'baja':
                animal.estado_an = 'retirado'
                animal.fecha_salida_an = date.today()
                animal.motivo_salida_an = 'Aborto - baja definitiva'
                animal.save()
                messages.info(request, f"Animal {animal.codigo_an} dado de baja automáticamente")
            elif destino_madre_ab == 'venta':
                animal.estado_an = 'vendido'
                animal.fecha_salida_an = date.today()
                animal.motivo_salida_an = 'Aborto - venta'
                animal.save()
                messages.info(request, f"Animal {animal.codigo_an} marcado como vendido")
        
        # ==========================================
        # ACTUALIZAR ABORTO
        # ==========================================
        aborto.fecha_ab = fecha_ab
        aborto.causa_probable_ab = causa_probable_ab if causa_probable_ab else None
        aborto.tratamiento_ab = tratamiento_ab if tratamiento_ab else None
        aborto.destino_madre_ab = destino_madre_ab
        
        aborto.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'Aborto',
            aborto.id_ab,
            f'Se editó aborto #{id_ab}: {animal.codigo_an} - Fecha: {fecha_ab} - Destino: {destino_madre_ab}'
        )
        
        messages.success(request, f"Aborto de '{animal.codigo_an}' actualizado exitosamente")
        return redirect('/listaabortos/')
        
    except Aborto.DoesNotExist:
        messages.error(request, "Aborto no encontrado")
        return redirect('/listaabortos/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect(f'/editaraborto/{id_ab}')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editaraborto/{id_ab}')

# ==========================================
# VISTA: ELIMINAR ABORTO
# ==========================================
def eliminaaborto(request, id_ab):
    """
    Elimina un aborto del sistema.
    Revierte el estado del animal si estaba como baja o venta por este aborto.
    """
    aborto = get_object_or_404(
        Aborto.objects.select_related('fk_an'),
        id_ab=id_ab
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_aborto = aborto.id_ab
    codigo_animal = aborto.fk_an.codigo_an
    animal = aborto.fk_an
    destino = aborto.destino_madre_ab
    
    try:
        # ==========================================
        # REVERTIR ESTADO DEL ANIMAL SI APLICA
        # ==========================================
        if destino in ['baja', 'venta']:
            animal.estado_an = 'activo'
            animal.fecha_salida_an = None
            animal.motivo_salida_an = None
            animal.save()
            messages.info(request, f"Estado del animal {codigo_animal} revertido a activo")
        
        # ==========================================
        # ELIMINAR ABORTO
        # ==========================================
        aborto.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'Aborto',
            id_aborto,
            f'Se eliminó aborto #{id_aborto}: {codigo_animal}'
        )
        
        messages.success(request, f"Aborto de {codigo_animal} eliminado exitosamente")
        
    except Exception as e:
        messages.error(request, f"Error al eliminar: {str(e)}")
    
    return redirect('/listaabortos/')


# ==========================================
# VISTA: LISTA ORDEÑOS
# ==========================================
def listaordeno(request):
    """
    Muestra el listado completo de ordeños con estadísticas.
    Incluye conteos por turno, litros del día, promedio y alertas de temperatura.
    """
    ordeno_list = Ordeno.objects.all().select_related(
        'fk_an', 'fk_us_or'
    ).order_by('-fecha_or', '-created_at_or')
    
    hoy = date.today()
    
    # Estadísticas generales
    total_ordenos = ordeno_list.count()
    total_manana = ordeno_list.filter(turno_or='manana').count()
    total_tarde = ordeno_list.filter(turno_or='tarde').count()
    total_unico = ordeno_list.filter(turno_or='unico').count()
    
    # Litros de hoy
    litros_hoy = Ordeno.objects.filter(fecha_or=hoy).aggregate(
        total=Sum('litros_or')
    )['total'] or 0
    
    # Promedio de litros
    promedio_litros = Ordeno.objects.aggregate(
        promedio=Avg('litros_or')
    )['promedio'] or 0
    
    # Alertas de temperatura (fuera de rango 4-7°C)
    alertas_temp = Ordeno.objects.filter(
        temperatura_leche_or__isnull=False
    ).exclude(
        temperatura_leche_or__gte=4,
        temperatura_leche_or__lte=7
    ).count()
    
    contexto = {
        'ordeno_list': ordeno_list,
        'total_ordenos': total_ordenos,
        'total_manana': total_manana,
        'total_tarde': total_tarde,
        'total_unico': total_unico,
        'litros_hoy': round(litros_hoy, 2),
        'promedio_litros': round(promedio_litros, 2),
        'alertas_temp': alertas_temp,
    }
    
    return render(request, 'catalogos/produccion/ordeno/lista_ordeno.html', contexto)


# ==========================================
# VISTA: NUEVO ORDEÑO (formulario)
# ==========================================
def nuevoordeno(request):
    """
    Muestra el formulario para registrar un nuevo ordeño.
    Carga lista de vacas en producción de leche activas.
    """
    # Solo vacas en producción de leche activas
    animales = Animal.objects.filter(
        sexo_an='H',
        estado_an='activo',
        categoria_an='vaca_leche'
    ).select_related('fk_ra').order_by('codigo_an')
    
    contexto = {
        'animales': animales,
    }
    
    return render(request, 'catalogos/produccion/ordeno/nuevo_ordeno.html', contexto)


# ==========================================
# VISTA: GUARDAR ORDEÑO (procesar creación)
# ==========================================
def guardarordeno(request):
    """
    Procesa el formulario de creación de un nuevo ordeño.
    Valida datos, verifica reglas de negocio, evita duplicados (mismo animal, fecha, turno),
    y registra auditoría.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevoordeno/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Animal (obligatorio)
        fk_an_id = request.POST.get('sel_animal_or')
        if not fk_an_id:
            messages.error(request, "Debe seleccionar un animal")
            return redirect('/nuevoordeno/')
        
        animal = get_object_or_404(Animal, id_an=fk_an_id)
        
        # Validar que sea hembra
        if animal.sexo_an != 'H':
            messages.error(request, f"El animal {animal.codigo_an} no es hembra. Solo se registran ordeños en hembras.")
            return redirect('/nuevoordeno/')
        
        # Validar categoría de producción
        if animal.categoria_an != 'vaca_leche':
            messages.error(request, f"El animal {animal.codigo_an} debe ser una vaca en producción de leche (vaca_leche).")
            return redirect('/nuevoordeno/')
        
        # Validar que esté activo
        if animal.estado_an != 'activo':
            messages.error(request, f"El animal {animal.codigo_an} no está activo.")
            return redirect('/nuevoordeno/')
        
        # Fecha (obligatoria)
        fecha_or = request.POST.get('txt_fecha_or')
        if not fecha_or:
            messages.error(request, "La fecha es obligatoria")
            return redirect('/nuevoordeno/')
        
        # Validar que no sea futura
        if fecha_or > str(date.today()):
            messages.error(request, "La fecha no puede ser futura")
            return redirect('/nuevoordeno/')
        
        # Turno (obligatorio)
        turno_or = request.POST.get('sel_turno_or')
        if not turno_or:
            messages.error(request, "El turno es obligatorio")
            return redirect('/nuevoordeno/')
        
        turnos_validos = ['manana', 'tarde', 'unico']
        if turno_or not in turnos_validos:
            messages.error(request, "Turno no válido")
            return redirect('/nuevoordeno/')
        
        # ==========================================
        # VERIFICAR DUPLICADO: MISMO ANIMAL, FECHA, TURNO
        # ==========================================
        existe_duplicado = Ordeno.objects.filter(
            fk_an=animal,
            fecha_or=fecha_or,
            turno_or=turno_or
        ).exists()
        
        if existe_duplicado:
            messages.error(
                request, 
                f"Ya existe un ordeño registrado para {animal.codigo_an} el {fecha_or} en turno {turno_or}. "
                f"No se permite duplicar ordeños."
            )
            return redirect('/nuevoordeno/')
        
        # Litros (obligatorio)
        litros_or = request.POST.get('txt_litros_or')
        if not litros_or:
            messages.error(request, "Los litros son obligatorios")
            return redirect('/nuevoordeno/')
        
        try:
            litros_or = float(litros_or)
            if litros_or <= 0:
                messages.error(request, "Los litros deben ser mayores a 0")
                return redirect('/nuevoordeno/')
            if litros_or > 99.99:
                messages.error(request, "Los litros no pueden exceder 99.99")
                return redirect('/nuevoordeno/')
        except ValueError:
            messages.error(request, "Los litros deben ser un número válido")
            return redirect('/nuevoordeno/')
        
        # Temperatura leche (opcional)
        temperatura_leche_or = request.POST.get('txt_temperatura_leche_or', '').strip()
        if temperatura_leche_or:
            try:
                temperatura_leche_or = float(temperatura_leche_or)
                if temperatura_leche_or < 0 or temperatura_leche_or > 50:
                    messages.error(request, "Temperatura de leche fuera de rango (0-50°C)")
                    return redirect('/nuevoordeno/')
            except ValueError:
                messages.error(request, "Temperatura de leche inválida")
                return redirect('/nuevoordeno/')
        else:
            temperatura_leche_or = None
        
        # Temperatura ambiental (opcional)
        temperatura_ambiental_or = request.POST.get('txt_temperatura_ambiental_or', '').strip()
        if temperatura_ambiental_or:
            try:
                temperatura_ambiental_or = float(temperatura_ambiental_or)
                if temperatura_ambiental_or < -10 or temperatura_ambiental_or > 50:
                    messages.error(request, "Temperatura ambiental fuera de rango (-10 a 50°C)")
                    return redirect('/nuevoordeno/')
            except ValueError:
                messages.error(request, "Temperatura ambiental inválida")
                return redirect('/nuevoordeno/')
        else:
            temperatura_ambiental_or = None
        
        # Concentrado (opcional)
        cantidad_concentrado_kg_or = request.POST.get('txt_cantidad_concentrado_kg_or', '').strip()
        if cantidad_concentrado_kg_or:
            try:
                cantidad_concentrado_kg_or = float(cantidad_concentrado_kg_or)
                if cantidad_concentrado_kg_or < 0 or cantidad_concentrado_kg_or > 99.99:
                    messages.error(request, "Concentrado fuera de rango (0-99.99 kg)")
                    return redirect('/nuevoordeno/')
            except ValueError:
                messages.error(request, "Concentrado inválido")
                return redirect('/nuevoordeno/')
        else:
            cantidad_concentrado_kg_or = None
        
        # Observaciones (opcional)
        observaciones_or = request.POST.get('txt_observaciones_or', '').strip()
        if observaciones_or and len(observaciones_or) > 1000:
            messages.error(request, "Las observaciones exceden 1000 caracteres")
            return redirect('/nuevoordeno/')
        
        # Usuario actual (obligatorio)
        try:
            fk_us_or = Usuario.objects.get(id_us=request.session.get('id_us', 1))
        except Usuario.DoesNotExist:
            messages.error(request, "Error de autenticación de usuario")
            return redirect('/nuevoordeno/')
        
        # ==========================================
        # CREAR ORDEÑO
        # ==========================================
        nuevo_ordeno = Ordeno.objects.create(
            fk_an=animal,
            fecha_or=fecha_or,
            turno_or=turno_or,
            litros_or=litros_or,
            temperatura_leche_or=temperatura_leche_or,
            temperatura_ambiental_or=temperatura_ambiental_or,
            cantidad_concentrado_kg_or=cantidad_concentrado_kg_or,
            observaciones_or=observaciones_or if observaciones_or else None,
            fk_us_or=fk_us_or
        )
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'Ordeno',
            nuevo_ordeno.id_or,
            f'Se creó ordeño: {animal.codigo_an} - {fecha_or} - {turno_or} - {litros_or} L'
        )
        
        messages.success(request, f"Ordeño de '{animal.codigo_an}' registrado exitosamente. Producción: {litros_or} L")
        return redirect('/listaordeno/')
        
    except Animal.DoesNotExist:
        messages.error(request, "Animal no encontrado")
        return redirect('/nuevoordeno/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect('/nuevoordeno/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevoordeno/')


# ==========================================
# VISTA: EDITAR ORDEÑO (formulario)
# ==========================================
def editarordeno(request, id_or):
    """
    Muestra el formulario de edición con los datos precargados.
    El animal no se puede cambiar. La fecha y turno sí, verificando no duplicar.
    """
    ordeno = get_object_or_404(
        Ordeno.objects.select_related('fk_an', 'fk_us_or'),
        id_or=id_or
    )
    
    # Inseminaciones disponibles (no aplica para ordeño, pero mantenemos estructura consistente)
    # Animal ya está definido en el ordeño, no se puede cambiar
    
    contexto = {
        'ordeno': ordeno,
    }
    
    return render(request, 'catalogos/produccion/ordeno/editar_ordeno.html', contexto)


# ==========================================
# VISTA: PROCESAR EDICION ORDEÑO
# ==========================================
def procesareditarordeno(request):
    """
    Procesa el formulario de edición de un ordeño existente.
    El animal no se puede modificar. Fecha y turno sí, verificando no duplicar.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listaordeno/')
    
    try:
        # Obtener ordeño existente
        id_or = request.POST.get('id_or')
        if not id_or:
            messages.error(request, "ID de ordeño no proporcionado")
            return redirect('/listaordeno/')
        
        ordeno = Ordeno.objects.select_related('fk_an').get(id_or=id_or)
        animal = ordeno.fk_an
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha (obligatoria)
        fecha_or = request.POST.get('txt_fecha_or')
        if not fecha_or:
            messages.error(request, "La fecha es obligatoria")
            return redirect(f'/editarordeno/{id_or}')
        
        # Validar que no sea futura
        if fecha_or > str(date.today()):
            messages.error(request, "La fecha no puede ser futura")
            return redirect(f'/editarordeno/{id_or}')
        
        # Turno (obligatorio)
        turno_or = request.POST.get('sel_turno_or')
        if not turno_or:
            messages.error(request, "El turno es obligatorio")
            return redirect(f'/editarordeno/{id_or}')
        
        turnos_validos = ['manana', 'tarde', 'unico']
        if turno_or not in turnos_validos:
            messages.error(request, "Turno no válido")
            return redirect(f'/editarordeno/{id_or}')
        
        # ==========================================
        # VERIFICAR DUPLICADO: MISMO ANIMAL, FECHA, TURNO (excluyendo el actual)
        # ==========================================
        existe_duplicado = Ordeno.objects.filter(
            fk_an=animal,
            fecha_or=fecha_or,
            turno_or=turno_or
        ).exclude(id_or=id_or).exists()
        
        if existe_duplicado:
            messages.error(
                request, 
                f"Ya existe otro ordeño registrado para {animal.codigo_an} el {fecha_or} en turno {turno_or}. "
                f"No se permite duplicar ordeños."
            )
            return redirect(f'/editarordeno/{id_or}')
        
        # Litros (obligatorio)
        litros_or = request.POST.get('txt_litros_or')
        if not litros_or:
            messages.error(request, "Los litros son obligatorios")
            return redirect(f'/editarordeno/{id_or}')
        
        try:
            litros_or = float(litros_or)
            if litros_or <= 0:
                messages.error(request, "Los litros deben ser mayores a 0")
                return redirect(f'/editarordeno/{id_or}')
            if litros_or > 99.99:
                messages.error(request, "Los litros no pueden exceder 99.99")
                return redirect(f'/editarordeno/{id_or}')
        except ValueError:
            messages.error(request, "Los litros deben ser un número válido")
            return redirect(f'/editarordeno/{id_or}')
        
        # Temperatura leche (opcional)
        temperatura_leche_or = request.POST.get('txt_temperatura_leche_or', '').strip()
        if temperatura_leche_or:
            try:
                temperatura_leche_or = float(temperatura_leche_or)
                if temperatura_leche_or < 0 or temperatura_leche_or > 50:
                    messages.error(request, "Temperatura de leche fuera de rango (0-50°C)")
                    return redirect(f'/editarordeno/{id_or}')
            except ValueError:
                messages.error(request, "Temperatura de leche inválida")
                return redirect(f'/editarordeno/{id_or}')
        else:
            temperatura_leche_or = None
        
        # Temperatura ambiental (opcional)
        temperatura_ambiental_or = request.POST.get('txt_temperatura_ambiental_or', '').strip()
        if temperatura_ambiental_or:
            try:
                temperatura_ambiental_or = float(temperatura_ambiental_or)
                if temperatura_ambiental_or < -10 or temperatura_ambiental_or > 50:
                    messages.error(request, "Temperatura ambiental fuera de rango (-10 a 50°C)")
                    return redirect(f'/editarordeno/{id_or}')
            except ValueError:
                messages.error(request, "Temperatura ambiental inválida")
                return redirect(f'/editarordeno/{id_or}')
        else:
            temperatura_ambiental_or = None
        
        # Concentrado (opcional)
        cantidad_concentrado_kg_or = request.POST.get('txt_cantidad_concentrado_kg_or', '').strip()
        if cantidad_concentrado_kg_or:
            try:
                cantidad_concentrado_kg_or = float(cantidad_concentrado_kg_or)
                if cantidad_concentrado_kg_or < 0 or cantidad_concentrado_kg_or > 99.99:
                    messages.error(request, "Concentrado fuera de rango (0-99.99 kg)")
                    return redirect(f'/editarordeno/{id_or}')
            except ValueError:
                messages.error(request, "Concentrado inválido")
                return redirect(f'/editarordeno/{id_or}')
        else:
            cantidad_concentrado_kg_or = None
        
        # Observaciones (opcional)
        observaciones_or = request.POST.get('txt_observaciones_or', '').strip()
        if observaciones_or and len(observaciones_or) > 1000:
            messages.error(request, "Las observaciones exceden 1000 caracteres")
            return redirect(f'/editarordeno/{id_or}')
        
        # ==========================================
        # ACTUALIZAR ORDEÑO
        # ==========================================
        ordeno.fecha_or = fecha_or
        ordeno.turno_or = turno_or
        ordeno.litros_or = litros_or
        ordeno.temperatura_leche_or = temperatura_leche_or
        ordeno.temperatura_ambiental_or = temperatura_ambiental_or
        ordeno.cantidad_concentrado_kg_or = cantidad_concentrado_kg_or
        ordeno.observaciones_or = observaciones_or if observaciones_or else None
        
        ordeno.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'Ordeno',
            ordeno.id_or,
            f'Se editó ordeño #{id_or}: {animal.codigo_an} - {fecha_or} - {turno_or} - {litros_or} L'
        )
        
        messages.success(request, f"Ordeño de '{animal.codigo_an}' actualizado exitosamente")
        return redirect('/listaordeno/')
        
    except Ordeno.DoesNotExist:
        messages.error(request, "Ordeño no encontrado")
        return redirect('/listaordeno/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect(f'/editarordeno/{id_or}')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarordeno/{id_or}')


# ==========================================
# VISTA: ELIMINAR ORDEÑO
# ==========================================
def eliminaordeno(request, id_or):
    """
    Elimina un ordeño del sistema.
    Registra auditoría antes de eliminar.
    """
    ordeno = get_object_or_404(
        Ordeno.objects.select_related('fk_an'),
        id_or=id_or
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_ordeno = ordeno.id_or
    codigo_animal = ordeno.fk_an.codigo_an
    fecha_or = ordeno.fecha_or
    turno_or = ordeno.turno_or
    litros_or = ordeno.litros_or
    
    try:
        # ==========================================
        # ELIMINAR ORDEÑO
        # ==========================================
        ordeno.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'Ordeno',
            id_ordeno,
            f'Se eliminó ordeño #{id_ordeno}: {codigo_animal} - {fecha_or} - {turno_or} - {litros_or} L'
        )
        
        messages.success(request, f"Ordeño de {codigo_animal} eliminado exitosamente")
        
    except Exception as e:
        messages.error(request, f"Error al eliminar: {str(e)}")
    
    return redirect('/listaordeno/')


# ==========================================
# CALIDAD DE LECHE
# ==========================================
def listacalidadl(request):
    """
    Muestra el listado completo de análisis de calidad de leche con estadísticas.
    Incluye promedios de grasa y proteína, conteos por resultado, 
    alertas de calidad (CCS > 200,000 o UFC > 100,000) y total de costos.
    """
    calidad_list = CalidadLeche.objects.all().select_related(
        'fk_an', 'fk_us_cl'
    ).order_by('-fecha_muestreo_cl', '-created_at_cl')
    
    # Calcular indicadores de calidad para cada registro
    for calidad in calidad_list:
        calidad.alerta_ccs = calidad.ccs_cl and calidad.ccs_cl > 200000
        calidad.alerta_ufc = calidad.ufc_cl and calidad.ufc_cl > 100000
        calidad.alerta_grasa_baja = calidad.grasa_pct_cl and calidad.grasa_pct_cl < 3.0
        calidad.alerta_proteina_baja = calidad.proteina_pct_cl and calidad.proteina_pct_cl < 2.8
    
    # Estadísticas generales
    total_analisis = calidad_list.count()
    total_apto = calidad_list.filter(resultado_cl='apto').count()
    total_no_apto = calidad_list.filter(resultado_cl='no_apto').count()
    total_pendiente = calidad_list.filter(resultado_cl='pendiente').count()
    
    # Promedios (solo registros con datos)
    promedio_grasa = calidad_list.filter(
        grasa_pct_cl__isnull=False
    ).aggregate(prom=Avg('grasa_pct_cl'))['prom']
    
    promedio_proteina = calidad_list.filter(
        proteina_pct_cl__isnull=False
    ).aggregate(prom=Avg('proteina_pct_cl'))['prom']
    
    # TOTAL DE COSTOS (nuevo)
    total_costo = calidad_list.filter(
        costo_analisis_cl__isnull=False
    ).aggregate(total=Sum('costo_analisis_cl'))['total']
    
    # Alertas sanitarias
    alertas_sanitarias = sum(
        1 for c in calidad_list 
        if c.ccs_cl and c.ccs_cl > 200000 or c.ufc_cl and c.ufc_cl > 100000
    )
    
    contexto = {
        'calidad_list': calidad_list,
        'total_analisis': total_analisis,
        'total_apto': total_apto,
        'total_no_apto': total_no_apto,
        'total_pendiente': total_pendiente,
        'promedio_grasa': round(promedio_grasa, 2) if promedio_grasa else 0,
        'promedio_proteina': round(promedio_proteina, 2) if promedio_proteina else 0,
        'total_costo': round(total_costo, 2) if total_costo else 0,  # <-- NUEVO
        'alertas_sanitarias': alertas_sanitarias,
    }
    
    return render(request, 'catalogos/produccion/calidadL/lista_calidadl.html', contexto)

# ==========================================
# VISTA: NUEVO ANÁLISIS (formulario)
# ==========================================
def nuevacalidadl(request):
    """
    Muestra el formulario para registrar un nuevo análisis de calidad de leche.
    Carga lista de animales en categoría productora de leche.
    """
    # Animales productores de leche (vacas en producción)
    animales = Animal.objects.filter(
        sexo_an='H',
        estado_an='activo',
        categoria_an__in=['vaca_leche', 'vaca_seca']
    ).select_related('fk_ra').order_by('codigo_an')
    
    contexto = {
        'animales': animales,
    }
    
    return render(request, 'catalogos/produccion/calidadL/nueva_calidadl.html', contexto)


# ==========================================
# VISTA: GUARDAR ANÁLISIS (procesar creación)
# ==========================================
def guardarcalidadl(request):
    """
    Procesa el formulario de creación de análisis de calidad de leche.
    Valida rangos de grasa/proteína, CCS, UFC y determina resultado automático.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevacalidadl/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Animal (obligatorio)
        fk_an_id = request.POST.get('sel_animal_cl')
        if not fk_an_id:
            messages.error(request, "Debe seleccionar un animal")
            return redirect('/nuevacalidadl/')
        
        animal = get_object_or_404(Animal, id_an=fk_an_id)
        
        # Validar que sea hembra
        if animal.sexo_an != 'H':
            messages.error(request, f"El animal {animal.codigo_an} no es hembra. Solo se analiza leche de hembras.")
            return redirect('/nuevacalidadl/')
        
        # Validar categoría productora
        categorias_validas = ['vaca_leche', 'vaca_seca']
        if animal.categoria_an not in categorias_validas:
            messages.error(request, f"El animal {animal.codigo_an} debe ser vaca_leche o vaca_seca.")
            return redirect('/nuevacalidadl/')
        
        # Validar que esté activo
        if animal.estado_an != 'activo':
            messages.error(request, f"El animal {animal.codigo_an} no está activo.")
            return redirect('/nuevacalidadl/')
        
        # Fecha de muestreo (obligatoria)
        fecha_muestreo_cl = request.POST.get('txt_fecha_muestreo_cl')
        if not fecha_muestreo_cl:
            messages.error(request, "La fecha de muestreo es obligatoria")
            return redirect('/nuevacalidadl/')
        
        # Validar que no sea futura
        if fecha_muestreo_cl > str(date.today()):
            messages.error(request, "La fecha de muestreo no puede ser futura")
            return redirect('/nuevacalidadl/')
        
        # Grasa (%) - opcional pero con rango
        grasa_pct_cl = request.POST.get('txt_grasa_pct_cl', '').strip()
        if grasa_pct_cl:
            try:
                grasa = Decimal(grasa_pct_cl)
                if grasa < 0 or grasa > 15:
                    messages.error(request, "El porcentaje de grasa debe estar entre 0 y 15")
                    return redirect('/nuevacalidadl/')
            except InvalidOperation:
                messages.error(request, "El valor de grasa no es válido")
                return redirect('/nuevacalidadl/')
        else:
            grasa = None
        
        # Proteína (%) - opcional pero con rango
        proteina_pct_cl = request.POST.get('txt_proteina_pct_cl', '').strip()
        if proteina_pct_cl:
            try:
                proteina = Decimal(proteina_pct_cl)
                if proteina < 0 or proteina > 10:
                    messages.error(request, "El porcentaje de proteína debe estar entre 0 y 10")
                    return redirect('/nuevacalidadl/')
            except InvalidOperation:
                messages.error(request, "El valor de proteína no es válido")
                return redirect('/nuevacalidadl/')
        else:
            proteina = None
        
        # CCS - opcional
        ccs_cl = request.POST.get('txt_ccs_cl', '').strip()
        if ccs_cl:
            try:
                ccs = int(ccs_cl)
                if ccs < 0:
                    messages.error(request, "El CCS no puede ser negativo")
                    return redirect('/nuevacalidadl/')
            except ValueError:
                messages.error(request, "El valor de CCS no es válido")
                return redirect('/nuevacalidadl/')
        else:
            ccs = None
        
        # UFC - opcional
        ufc_cl = request.POST.get('txt_ufc_cl', '').strip()
        if ufc_cl:
            try:
                ufc = int(ufc_cl)
                if ufc < 0:
                    messages.error(request, "El UFC no puede ser negativo")
                    return redirect('/nuevacalidadl/')
            except ValueError:
                messages.error(request, "El valor de UFC no es válido")
                return redirect('/nuevacalidadl/')
        else:
            ufc = None
        
        # Resultado - determinar automáticamente si no se especifica
        resultado_cl = request.POST.get('sel_resultado_cl', '').strip()
        
        # Si no hay resultado manual, determinar automáticamente
        if not resultado_cl:
            if ccs and ccs > 200000:
                resultado_cl = 'no_apto'
            elif ufc and ufc > 100000:
                resultado_cl = 'no_apto'
            elif grasa and grasa < 2.5:
                resultado_cl = 'no_apto'
            elif proteina and proteina < 2.5:
                resultado_cl = 'no_apto'
            else:
                resultado_cl = 'apto'
        
        # Validar resultado contra choices
        resultados_validos = ['apto', 'no_apto', 'pendiente']
        if resultado_cl not in resultados_validos:
            messages.error(request, "Resultado no válido")
            return redirect('/nuevacalidadl/')
        
        # Laboratorio - opcional
        laboratorio_cl = request.POST.get('txt_laboratorio_cl', '').strip() or None
        
        # Costo - opcional
        costo_analisis_cl = request.POST.get('txt_costo_analisis_cl', '').strip()
        if costo_analisis_cl:
            try:
                costo = Decimal(costo_analisis_cl)
                if costo < 0:
                    messages.error(request, "El costo no puede ser negativo")
                    return redirect('/nuevacalidadl/')
            except InvalidOperation:
                messages.error(request, "El costo no es válido")
                return redirect('/nuevacalidadl/')
        else:
            costo = None
        
        # Usuario actual (obligatorio)
        try:
            fk_us_cl = Usuario.objects.get(id_us=request.session.get('id_us', 1))
        except Usuario.DoesNotExist:
            messages.error(request, "Error de autenticación de usuario")
            return redirect('/nuevacalidadl/')
        
        # ==========================================
        # VERIFICAR ANÁLISIS DUPLICADO EN MISMO DÍA
        # ==========================================
        analisis_existente = CalidadLeche.objects.filter(
            fk_an=animal,
            fecha_muestreo_cl=fecha_muestreo_cl
        ).first()
        
        if analisis_existente:
            messages.warning(
                request,
                f"ADVERTENCIA: El animal {animal.codigo_an} ya tiene un análisis registrado "
                f"para la fecha {fecha_muestreo_cl}. Verifique antes de continuar."
            )
        
        # ==========================================
        # CREAR ANÁLISIS
        # ==========================================
        nuevo_analisis = CalidadLeche.objects.create(
            fk_an=animal,
            fecha_muestreo_cl=fecha_muestreo_cl,
            grasa_pct_cl=grasa,
            proteina_pct_cl=proteina,
            ccs_cl=ccs,
            ufc_cl=ufc,
            resultado_cl=resultado_cl,
            laboratorio_cl=laboratorio_cl,
            costo_analisis_cl=costo,
            fk_us_cl=fk_us_cl
        )
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'CalidadLeche',
            nuevo_analisis.id_cl,
            f'Se creó análisis de calidad: {animal.codigo_an} - Fecha: {fecha_muestreo_cl} - Resultado: {resultado_cl}'
        )
        
        messages.success(request, f"Análisis de calidad de '{animal.codigo_an}' registrado exitosamente. Resultado: {resultado_cl.upper()}")
        return redirect('/listacalidadl/')
        
    except Animal.DoesNotExist:
        messages.error(request, "Animal no encontrado")
        return redirect('/nuevacalidadl/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect('/nuevacalidadl/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevacalidadl/')


# ==========================================
# VISTA: EDITAR ANÁLISIS (formulario)
# ==========================================
def editarcalidadl(request, id_cl):
    """
    Muestra el formulario de edición con los datos precargados.
    El animal no se puede cambiar.
    """
    analisis = get_object_or_404(
        CalidadLeche.objects.select_related('fk_an', 'fk_us_cl'),
        id_cl=id_cl
    )
    
    # Calcular alertas para mostrar en edición
    analisis.alerta_ccs = analisis.ccs_cl and analisis.ccs_cl > 200000
    analisis.alerta_ufc = analisis.ufc_cl and analisis.ufc_cl > 100000
    
    contexto = {
        'analisis': analisis,
    }
    
    return render(request, 'catalogos/produccion/calidadL/editar_calidadl.html', contexto)


# ==========================================
# VISTA: PROCESAR EDICIÓN
# ==========================================
def procesareditarcalidadl(request):
    """
    Procesa el formulario de edición de un análisis existente.
    El animal no se puede modificar.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listacalidadl/')
    
    try:
        # Obtener análisis existente
        id_cl = request.POST.get('id_cl')
        if not id_cl:
            messages.error(request, "ID de análisis no proporcionado")
            return redirect('/listacalidadl/')
        
        analisis = CalidadLeche.objects.select_related('fk_an').get(id_cl=id_cl)
        animal = analisis.fk_an
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha de muestreo (obligatoria)
        fecha_muestreo_cl = request.POST.get('txt_fecha_muestreo_cl')
        if not fecha_muestreo_cl:
            messages.error(request, "La fecha de muestreo es obligatoria")
            return redirect(f'/editarcalidadl/{id_cl}')
        
        # Validar que no sea futura
        if fecha_muestreo_cl > str(date.today()):
            messages.error(request, "La fecha de muestreo no puede ser futura")
            return redirect(f'/editarcalidadl/{id_cl}')
        
        # Grasa (%)
        grasa_pct_cl = request.POST.get('txt_grasa_pct_cl', '').strip()
        if grasa_pct_cl:
            try:
                grasa = Decimal(grasa_pct_cl)
                if grasa < 0 or grasa > 15:
                    messages.error(request, "El porcentaje de grasa debe estar entre 0 y 15")
                    return redirect(f'/editarcalidadl/{id_cl}')
            except InvalidOperation:
                messages.error(request, "El valor de grasa no es válido")
                return redirect(f'/editarcalidadl/{id_cl}')
        else:
            grasa = None
        
        # Proteína (%)
        proteina_pct_cl = request.POST.get('txt_proteina_pct_cl', '').strip()
        if proteina_pct_cl:
            try:
                proteina = Decimal(proteina_pct_cl)
                if proteina < 0 or proteina > 10:
                    messages.error(request, "El porcentaje de proteína debe estar entre 0 y 10")
                    return redirect(f'/editarcalidadl/{id_cl}')
            except InvalidOperation:
                messages.error(request, "El valor de proteína no es válido")
                return redirect(f'/editarcalidadl/{id_cl}')
        else:
            proteina = None
        
        # CCS
        ccs_cl = request.POST.get('txt_ccs_cl', '').strip()
        if ccs_cl:
            try:
                ccs = int(ccs_cl)
                if ccs < 0:
                    messages.error(request, "El CCS no puede ser negativo")
                    return redirect(f'/editarcalidadl/{id_cl}')
            except ValueError:
                messages.error(request, "El valor de CCS no es válido")
                return redirect(f'/editarcalidadl/{id_cl}')
        else:
            ccs = None
        
        # UFC
        ufc_cl = request.POST.get('txt_ufc_cl', '').strip()
        if ufc_cl:
            try:
                ufc = int(ufc_cl)
                if ufc < 0:
                    messages.error(request, "El UFC no puede ser negativo")
                    return redirect(f'/editarcalidadl/{id_cl}')
            except ValueError:
                messages.error(request, "El valor de UFC no es válido")
                return redirect(f'/editarcalidadl/{id_cl}')
        else:
            ufc = None
        
        # Resultado
        resultado_cl = request.POST.get('sel_resultado_cl', '').strip()
        if not resultado_cl:
            # Determinar automáticamente
            if ccs and ccs > 200000:
                resultado_cl = 'no_apto'
            elif ufc and ufc > 100000:
                resultado_cl = 'no_apto'
            elif grasa and grasa < 2.5:
                resultado_cl = 'no_apto'
            elif proteina and proteina < 2.5:
                resultado_cl = 'no_apto'
            else:
                resultado_cl = 'apto'
        
        resultados_validos = ['apto', 'no_apto', 'pendiente']
        if resultado_cl not in resultados_validos:
            messages.error(request, "Resultado no válido")
            return redirect(f'/editarcalidadl/{id_cl}')
        
        # Laboratorio
        laboratorio_cl = request.POST.get('txt_laboratorio_cl', '').strip() or None
        
        # Costo
        costo_analisis_cl = request.POST.get('txt_costo_analisis_cl', '').strip()
        if costo_analisis_cl:
            try:
                costo = Decimal(costo_analisis_cl)
                if costo < 0:
                    messages.error(request, "El costo no puede ser negativo")
                    return redirect(f'/editarcalidadl/{id_cl}')
            except InvalidOperation:
                messages.error(request, "El costo no es válido")
                return redirect(f'/editarcalidadl/{id_cl}')
        else:
            costo = None
        
        # Observaciones
        observaciones_cl = request.POST.get('txt_observaciones_cl', '').strip() or None
        
        # ==========================================
        # ACTUALIZAR ANÁLISIS
        # ==========================================
        analisis.fecha_muestreo_cl = fecha_muestreo_cl
        analisis.grasa_pct_cl = grasa
        analisis.proteina_pct_cl = proteina
        analisis.ccs_cl = ccs
        analisis.ufc_cl = ufc
        analisis.resultado_cl = resultado_cl
        analisis.laboratorio_cl = laboratorio_cl
        analisis.costo_analisis_cl = costo
        
        analisis.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'CalidadLeche',
            analisis.id_cl,
            f'Se editó análisis #{id_cl}: {animal.codigo_an} - Resultado: {resultado_cl}'
        )
        
        messages.success(request, f"Análisis de calidad de '{animal.codigo_an}' actualizado exitosamente")
        return redirect('/listacalidadl/')
        
    except CalidadLeche.DoesNotExist:
        messages.error(request, "Análisis no encontrado")
        return redirect('/listacalidadl/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect(f'/editarcalidadl/{id_cl}')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarcalidadl/{id_cl}')


# ==========================================
# VISTA: ELIMINAR ANÁLISIS
# ==========================================
def eliminacalidadl(request, id_cl):
    """
    Elimina un análisis de calidad de leche del sistema.
    """
    analisis = get_object_or_404(
        CalidadLeche.objects.select_related('fk_an'),
        id_cl=id_cl
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_analisis = analisis.id_cl
    codigo_animal = analisis.fk_an.codigo_an
    
    try:
        # ==========================================
        # ELIMINAR ANÁLISIS
        # ==========================================
        analisis.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'CalidadLeche',
            id_analisis,
            f'Se eliminó análisis #{id_analisis}: {codigo_animal}'
        )
        
        messages.success(request, f"Análisis de calidad de {codigo_animal} eliminado exitosamente")
        
    except Exception as e:
        messages.error(request, f"Error al eliminar: {str(e)}")
    
    return redirect('/listacalidadl/')


# ==========================================
# VISTA: LISTAR SECADOS
# ==========================================
def listasecado(request):
    """
    Muestra el listado completo de secados con estadísticas.
    Incluye conteos por causa y alertas de secados recientes.
    """
    secado_list = Secado.objects.all().select_related(
        'fk_an', 'fk_us_se'
    ).order_by('-fecha_ultimo_ordeno_se', '-created_at_se')
    
    # Calcular días desde el último ordeño para cada registro
    hoy = date.today()
    for secado in secado_list:
        secado.dias_desde_secado = (hoy - secado.fecha_ultimo_ordeno_se).days
    
    # Estadísticas generales
    total_secados = secado_list.count()
    total_preniez = secado_list.filter(causa_se='preñez_avanzada').count()
    total_baja_prod = secado_list.filter(causa_se='baja_produccion').count()
    total_enfermedad = secado_list.filter(causa_se='enfermedad').count()
    total_programado = secado_list.filter(causa_se='programado').count()
    
    # Secados recientes (≤30 días)
    secados_recientes = sum(
        1 for s in secado_list 
        if s.dias_desde_secado <= 30
    )
    
    contexto = {
        'secado_list': secado_list,
        'total_secados': total_secados,
        'total_preniez': total_preniez,
        'total_baja_prod': total_baja_prod,
        'total_enfermedad': total_enfermedad,
        'total_programado': total_programado,
        'secados_recientes': secados_recientes,
    }
    
    return render(request, 'catalogos/produccion/secado/lista_secado.html', contexto)


# ==========================================
# VISTA: NUEVO SECADO (formulario)
# ==========================================
def nuevosecado(request):
    """
    Muestra el formulario para registrar un nuevo secado.
    Carga lista de animales en categoría productora de leche.
    """
    # Animales productores de leche (vacas en producción)
    animales = Animal.objects.filter(
        sexo_an='H',
        estado_an='activo',
        categoria_an__in=['vaca_leche', 'vaca_seca']
    ).select_related('fk_ra').order_by('codigo_an')
    
    contexto = {
        'animales': animales,
    }
    
    return render(request, 'catalogos/produccion/secado/nuevo_secado.html', contexto)


# ==========================================
# VISTA: GUARDAR SECADO (procesar creación)
# ==========================================
def guardarsecado(request):
    """
    Procesa el formulario de creación de un nuevo secado.
    Valida datos y verifica que el animal esté en producción.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevosecado/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Animal (obligatorio)
        fk_an_id = request.POST.get('sel_animal_se')
        if not fk_an_id:
            messages.error(request, "Debe seleccionar un animal")
            return redirect('/nuevosecado/')
        
        animal = get_object_or_404(Animal, id_an=fk_an_id)
        
        # Validar que sea hembra
        if animal.sexo_an != 'H':
            messages.error(request, f"El animal {animal.codigo_an} no es hembra. Solo se registran secados en hembras.")
            return redirect('/nuevosecado/')
        
        # Validar categoría productora
        categorias_validas = ['vaca_leche', 'vaca_seca']
        if animal.categoria_an not in categorias_validas:
            messages.error(request, f"El animal {animal.codigo_an} debe ser vaca_leche o vaca_seca.")
            return redirect('/nuevosecado/')
        
        # Validar que esté activo
        if animal.estado_an != 'activo':
            messages.error(request, f"El animal {animal.codigo_an} no está activo.")
            return redirect('/nuevosecado/')
        
        # Fecha último ordeño (obligatoria)
        fecha_ultimo_ordeno_se = request.POST.get('txt_fecha_ultimo_ordeno_se')
        if not fecha_ultimo_ordeno_se:
            messages.error(request, "La fecha del último ordeño es obligatoria")
            return redirect('/nuevosecado/')
        
        # Validar que no sea futura
        if fecha_ultimo_ordeno_se > str(date.today()):
            messages.error(request, "La fecha del último ordeño no puede ser futura")
            return redirect('/nuevosecado/')
        
        # Causa (opcional pero validada)
        causa_se = request.POST.get('sel_causa_se', '').strip()
        causas_validas = ['preñez_avanzada', 'baja_produccion', 'enfermedad', 'programado', 'otro']
        if causa_se and causa_se not in causas_validas:
            messages.error(request, "Causa del secado no válida")
            return redirect('/nuevosecado/')
        
        # Observaciones (opcional)
        observaciones_se = request.POST.get('txt_observaciones_se', '').strip() or None
        
        # Usuario actual (obligatorio)
        try:
            fk_us_se = Usuario.objects.get(id_us=request.session.get('id_us', 1))
        except Usuario.DoesNotExist:
            messages.error(request, "Error de autenticación de usuario")
            return redirect('/nuevosecado/')
        
        # ==========================================
        # VERIFICAR SECADO EXISTENTE ACTIVO
        # ==========================================
        secado_existente = Secado.objects.filter(
            fk_an=animal,
            fecha_ultimo_ordeno_se__gte=date.today()
        ).first()
        
        if secado_existente:
            messages.warning(
                request, 
                f"ADVERTENCIA: El animal {animal.codigo_an} ya tiene un secado registrado "
                f"recientemente (ID: #{secado_existente.id_se}, fecha: {secado_existente.fecha_ultimo_ordeno_se}). "
                f"Verifique antes de continuar."
            )
        
        # ==========================================
        # CREAR SECADO
        # ==========================================
        nuevo_secado = Secado.objects.create(
            fk_an=animal,
            fecha_ultimo_ordeno_se=fecha_ultimo_ordeno_se,
            causa_se=causa_se if causa_se else None,
            observaciones_se=observaciones_se,
            fk_us_se=fk_us_se
        )
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'Secado',
            nuevo_secado.id_se,
            f'Se creó secado: {animal.codigo_an} - Último ordeño: {fecha_ultimo_ordeno_se} - Causa: {causa_se}'
        )
        
        messages.success(request, f"Secado de '{animal.codigo_an}' registrado exitosamente.")
        return redirect('/listasecado/')
        
    except Animal.DoesNotExist:
        messages.error(request, "Animal no encontrado")
        return redirect('/nuevosecado/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect('/nuevosecado/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevosecado/')


# ==========================================
# VISTA: EDITAR SECADO (formulario)
# ==========================================
def editarsecado(request, id_se):
    """
    Muestra el formulario de edición con los datos precargados.
    El animal no se puede cambiar.
    """
    secado = get_object_or_404(
        Secado.objects.select_related('fk_an', 'fk_us_se'),
        id_se=id_se
    )
    
    # Calcular días desde el secado
    hoy = date.today()
    secado.dias_desde_secado = (hoy - secado.fecha_ultimo_ordeno_se).days
    
    contexto = {
        'secado': secado,
    }
    
    return render(request, 'catalogos/produccion/secado/editar_secado.html', contexto)


# ==========================================
# VISTA: PROCESAR EDICIÓN SECADO
# ==========================================
def procesareditarsecado(request):
    """
    Procesa el formulario de edición de un secado existente.
    El animal no se puede modificar.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listasecado/')
    
    try:
        # Obtener secado existente
        id_se = request.POST.get('id_se')
        if not id_se:
            messages.error(request, "ID de secado no proporcionado")
            return redirect('/listasecado/')
        
        secado = Secado.objects.select_related('fk_an').get(id_se=id_se)
        animal = secado.fk_an
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha último ordeño (obligatoria)
        fecha_ultimo_ordeno_se = request.POST.get('txt_fecha_ultimo_ordeno_se')
        if not fecha_ultimo_ordeno_se:
            messages.error(request, "La fecha del último ordeño es obligatoria")
            return redirect(f'/editarsecado/{id_se}')
        
        # Validar que no sea futura
        if fecha_ultimo_ordeno_se > str(date.today()):
            messages.error(request, "La fecha del último ordeño no puede ser futura")
            return redirect(f'/editarsecado/{id_se}')
        
        # Causa (opcional)
        causa_se = request.POST.get('sel_causa_se', '').strip()
        causas_validas = ['preñez_avanzada', 'baja_produccion', 'enfermedad', 'programado', 'otro']
        if causa_se and causa_se not in causas_validas:
            messages.error(request, "Causa del secado no válida")
            return redirect(f'/editarsecado/{id_se}')
        
        # Observaciones (opcional)
        observaciones_se = request.POST.get('txt_observaciones_se', '').strip() or None
        
        # ==========================================
        # ACTUALIZAR SECADO
        # ==========================================
        secado.fecha_ultimo_ordeno_se = fecha_ultimo_ordeno_se
        secado.causa_se = causa_se if causa_se else None
        secado.observaciones_se = observaciones_se
        
        secado.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'Secado',
            secado.id_se,
            f'Se editó secado #{id_se}: {animal.codigo_an} - Causa: {causa_se}'
        )
        
        messages.success(request, f"Secado de '{animal.codigo_an}' actualizado exitosamente")
        return redirect('/listasecado/')
        
    except Secado.DoesNotExist:
        messages.error(request, "Secado no encontrado")
        return redirect('/listasecado/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect(f'/editarsecado/{id_se}')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarsecado/{id_se}')


# ==========================================
# VISTA: ELIMINAR SECADO
# ==========================================
def eliminasecado(request, id_se):
    """
    Elimina un secado del sistema.
    """
    secado = get_object_or_404(
        Secado.objects.select_related('fk_an'),
        id_se=id_se
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_secado = secado.id_se
    codigo_animal = secado.fk_an.codigo_an
    
    try:
        # ==========================================
        # ELIMINAR SECADO
        # ==========================================
        secado.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'Secado',
            id_secado,
            f'Se eliminó secado #{id_secado}: {codigo_animal}'
        )
        
        messages.success(request, f"Secado de {codigo_animal} eliminado exitosamente")
        
    except Exception as e:
        messages.error(request, f"Error al eliminar: {str(e)}")
    
    return redirect('/listasecado/')



# ==========================================
# ENTREGAS DE LECHE
# ==========================================
def listaentrega(request):
    """
    Muestra el listado completo de entregas de leche con estadísticas.
    Incluye totales de litros, monto, promedio de precio y conteos.
    """
    entrega_list = EntregaLeche.objects.all().select_related(
        'fk_us_el'
    ).order_by('-fecha_el', '-created_at_el')
    
    # Estadísticas generales
    total_entregas = entrega_list.count()
    
    # Total litros entregados
    total_litros = entrega_list.filter(
        litros_totales_el__isnull=False
    ).aggregate(total=Sum('litros_totales_el'))['total']
    
    # Total monto
    total_monto = entrega_list.filter(
        monto_total_el__isnull=False
    ).aggregate(total=Sum('monto_total_el'))['total']
    
    # Promedio precio por litro
    promedio_precio = entrega_list.filter(
        precio_litro_el__isnull=False
    ).aggregate(prom=Avg('precio_litro_el'))['prom']
    
    # Entregas del mes actual
    hoy = date.today()
    entregas_mes = entrega_list.filter(
        fecha_el__year=hoy.year,
        fecha_el__month=hoy.month
    ).count()
    
    contexto = {
        'entrega_list': entrega_list,
        'total_entregas': total_entregas,
        'total_litros': round(total_litros, 2) if total_litros else 0,
        'total_monto': round(total_monto, 2) if total_monto else 0,
        'promedio_precio': round(promedio_precio, 2) if promedio_precio else 0,
        'entregas_mes': entregas_mes,
    }
    
    return render(request, 'catalogos/produccion/entregaL/lista_entrega.html', contexto)


# ==========================================
# VISTA: NUEVA ENTREGA (formulario)
# ==========================================
def nuevaentrega(request):
    """
    Muestra el formulario para registrar una nueva entrega de leche.
    """
    return render(request, 'catalogos/produccion/entregaL/nueva_entrega.html')


# ==========================================
# VISTA: GUARDAR ENTREGA (procesar creación)
# ==========================================
def guardarentrega(request):
    """
    Procesa el formulario de creación de una nueva entrega de leche.
    Valida datos y calcula monto total automáticamente si aplica.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevaentrega/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha de entrega (obligatoria) - CONVERTIR A DATE
        fecha_str = request.POST.get('txt_fecha_el')
        if not fecha_str:
            messages.error(request, "La fecha de entrega es obligatoria")
            return redirect('/nuevaentrega/')
        
        from datetime import datetime
        fecha_el = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
        # Validar que no sea futura
        if fecha_el > date.today():
            messages.error(request, "La fecha de entrega no puede ser futura")
            return redirect('/nuevaentrega/')
        
        # Litros totales (obligatorios)
        litros_totales_el = request.POST.get('txt_litros_totales_el', '').strip()
        if not litros_totales_el:
            messages.error(request, "Los litros totales son obligatorios")
            return redirect('/nuevaentrega/')
        
        try:
            litros = Decimal(litros_totales_el)
            if litros <= 0:
                messages.error(request, "Los litros totales deben ser mayores a 0")
                return redirect('/nuevaentrega/')
        except InvalidOperation:
            messages.error(request, "El valor de litros totales no es válido")
            return redirect('/nuevaentrega/')
        
        # Cliente (opcional)
        cliente_el = request.POST.get('txt_cliente_el', '').strip() or None
        
        # Precio por litro (opcional)
        precio_litro_el = request.POST.get('txt_precio_litro_el', '').strip()
        if precio_litro_el:
            try:
                precio = Decimal(precio_litro_el)
                if precio < 0:
                    messages.error(request, "El precio por litro no puede ser negativo")
                    return redirect('/nuevaentrega/')
            except InvalidOperation:
                messages.error(request, "El precio por litro no es válido")
                return redirect('/nuevaentrega/')
        else:
            precio = None
        
        # Calcular monto total automáticamente
        monto_total_el = None
        if litros and precio:
            monto_total_el = litros * precio
        
        # Guía de remisión (opcional)
        guia_remision_el = request.POST.get('txt_guia_remision_el', '').strip() or None
        
        # Observaciones (opcional)
        observaciones_el = request.POST.get('txt_observaciones_el', '').strip() or None
        
        # Usuario actual (obligatorio)
        try:
            fk_us_el = Usuario.objects.get(id_us=request.session.get('id_us', 1))
        except Usuario.DoesNotExist:
            messages.error(request, "Error de autenticación de usuario")
            return redirect('/nuevaentrega/')
        
        # ==========================================
        # CREAR ENTREGA
        # ==========================================
        nueva_entrega = EntregaLeche.objects.create(
            fecha_el=fecha_el,
            litros_totales_el=litros,
            cliente_el=cliente_el,
            precio_litro_el=precio,
            monto_total_el=monto_total_el,
            guia_remision_el=guia_remision_el,
            observaciones_el=observaciones_el,
            fk_us_el=fk_us_el
        )
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'EntregaLeche',
            nueva_entrega.id_el,
            f'Se creó entrega: {fecha_el} - {litros}L - Cliente: {cliente_el or "Sin cliente"}'
        )
        
        messages.success(request, f"Entrega de {litros}L registrada exitosamente. Monto total: ${monto_total_el if monto_total_el else 'N/A'}")
        return redirect('/listaentrega/')
        
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect('/nuevaentrega/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevaentrega/')


# ==========================================
# VISTA: EDITAR ENTREGA (formulario)
# ==========================================
def editarentrega(request, id_el):
    """
    Muestra el formulario de edición con los datos precargados.
    """
    entrega = get_object_or_404(
        EntregaLeche.objects.select_related('fk_us_el'),
        id_el=id_el
    )
    
    contexto = {
        'entrega': entrega,
    }
    
    return render(request, 'catalogos/produccion/entregaL/editar_entrega.html', contexto)


# ==========================================
# VISTA: PROCESAR EDICIÓN ENTREGA
# ==========================================
def procesareditarentrega(request):
    """
    Procesa el formulario de edición de una entrega existente.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listaentrega/')
    
    try:
        # Obtener entrega existente
        id_el = request.POST.get('id_el')
        if not id_el:
            messages.error(request, "ID de entrega no proporcionado")
            return redirect('/listaentrega/')
        
        entrega = EntregaLeche.objects.get(id_el=id_el)
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha de entrega (obligatoria) - CONVERTIR A DATE
        fecha_str = request.POST.get('txt_fecha_el')
        if not fecha_str:
            messages.error(request, "La fecha de entrega es obligatoria")
            return redirect(f'/editarentrega/{id_el}')
        
        from datetime import datetime
        fecha_el = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
        # Validar que no sea futura
        if fecha_el > date.today():
            messages.error(request, "La fecha de entrega no puede ser futura")
            return redirect(f'/editarentrega/{id_el}')
        
        # Litros totales (obligatorios)
        litros_totales_el = request.POST.get('txt_litros_totales_el', '').strip()
        if not litros_totales_el:
            messages.error(request, "Los litros totales son obligatorios")
            return redirect(f'/editarentrega/{id_el}')
        
        try:
            litros = Decimal(litros_totales_el)
            if litros <= 0:
                messages.error(request, "Los litros totales deben ser mayores a 0")
                return redirect(f'/editarentrega/{id_el}')
        except InvalidOperation:
            messages.error(request, "El valor de litros totales no es válido")
            return redirect(f'/editarentrega/{id_el}')
        
        # Cliente (opcional)
        cliente_el = request.POST.get('txt_cliente_el', '').strip() or None
        
        # Precio por litro (opcional)
        precio_litro_el = request.POST.get('txt_precio_litro_el', '').strip()
        if precio_litro_el:
            try:
                precio = Decimal(precio_litro_el)
                if precio < 0:
                    messages.error(request, "El precio por litro no puede ser negativo")
                    return redirect(f'/editarentrega/{id_el}')
            except InvalidOperation:
                messages.error(request, "El precio por litro no es válido")
                return redirect(f'/editarentrega/{id_el}')
        else:
            precio = None
        
        # Calcular monto total automáticamente
        monto_total_el = None
        if litros and precio:
            monto_total_el = litros * precio
        
        # Guía de remisión (opcional)
        guia_remision_el = request.POST.get('txt_guia_remision_el', '').strip() or None
        
        # Observaciones (opcional)
        observaciones_el = request.POST.get('txt_observaciones_el', '').strip() or None
        
        # ==========================================
        # ACTUALIZAR ENTREGA
        # ==========================================
        entrega.fecha_el = fecha_el
        entrega.litros_totales_el = litros
        entrega.cliente_el = cliente_el
        entrega.precio_litro_el = precio
        entrega.monto_total_el = monto_total_el
        entrega.guia_remision_el = guia_remision_el
        entrega.observaciones_el = observaciones_el
        
        entrega.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'EntregaLeche',
            entrega.id_el,
            f'Se editó entrega #{id_el}: {fecha_el} - {litros}L'
        )
        
        messages.success(request, f"Entrega de {litros}L actualizada exitosamente")
        return redirect('/listaentrega/')
        
    except EntregaLeche.DoesNotExist:
        messages.error(request, "Entrega no encontrada")
        return redirect('/listaentrega/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect(f'/editarentrega/{id_el}')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarentrega/{id_el}')


# ==========================================
# VISTA: ELIMINAR ENTREGA
# ==========================================
def eliminaentrega(request, id_el):
    """
    Elimina una entrega de leche del sistema.
    """
    entrega = get_object_or_404(
        EntregaLeche.objects.select_related('fk_us_el'),
        id_el=id_el
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_entrega = entrega.id_el
    fecha_entrega = entrega.fecha_el
    litros = entrega.litros_totales_el
    
    try:
        # ==========================================
        # ELIMINAR ENTREGA
        # ==========================================
        entrega.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'EntregaLeche',
            id_entrega,
            f'Se eliminó entrega #{id_entrega}: {fecha_entrega} - {litros}L'
        )
        
        messages.success(request, f"Entrega de {fecha_entrega} eliminada exitosamente")
        
    except Exception as e:
        messages.error(request, f"Error al eliminar: {str(e)}")
    
    return redirect('/listaentrega/')
# ==========================================================
# MÓDULO 5: ALIMENTACIÓN Y NUTRICIÓN
# ==========================================================
#Racion
def listaracion(request):
    """
    Muestra el listado completo de raciones con estadísticas.
    Incluye filtros por animal, dieta, insumo y estado (activa/finalizada).
    """
    raciones_list = Racion.objects.all().select_related(
        'fk_an', 'fk_di', 'fk_ia', 'fk_us_ra'
    ).order_by('-fecha_inicio_ra', '-created_at_ra')
    
    # Calcular estado para cada ración
    hoy = date.today()
    for racion in raciones_list:
        if racion.fecha_fin_ra and racion.fecha_fin_ra < hoy:
            racion.estado = 'finalizada'
        else:
            racion.estado = 'activa'
        # Calcular eficiencia si hay datos
        racion.eficiencia = racion.calcular_eficiencia()
        racion.desperdicio_pct = racion.calcular_desperdicio_pct()
    
    # Estadísticas generales
    total_raciones = raciones_list.count()
    raciones_finalizadas = sum(1 for r in raciones_list if r.estado == 'finalizada')
    
    # Estadísticas de consumo
    total_ofrecido = raciones_list.aggregate(
        total=Sum('cantidad_ofrecida_kg_ra')
    )['total'] or 0
    
    total_consumido = raciones_list.aggregate(
        total=Sum('cantidad_consumida_kg_ra')
    )['total'] or 0
    
    total_desperdicio = raciones_list.aggregate(
        total=Sum('desperdicio_kg_ra')
    )['total'] or 0
    
    # Eficiencia promedio
    raciones_con_eficiencia = [r for r in raciones_list if r.eficiencia is not None]
    eficiencia_promedio = round(
        sum(r.eficiencia for r in raciones_con_eficiencia) / len(raciones_con_eficiencia), 2
    ) if raciones_con_eficiencia else 0
    
    contexto = {
        'raciones_list': raciones_list,
        'total_raciones': total_raciones,
        'raciones_finalizadas': raciones_finalizadas,
        'total_ofrecido': total_ofrecido,
        'total_consumido': total_consumido,
        'total_desperdicio': total_desperdicio,
        'eficiencia_promedio': eficiencia_promedio,
    }
    
    return render(request, 'catalogos/alimentacion/racion/lista_racion.html', contexto)


# ==========================================
# VISTA: NUEVA RACIÓN (formulario)
# ==========================================
def nuevaracion(request):
    """
    Muestra el formulario para registrar una nueva ración.
    Carga animales activos, dietas activas e insumos disponibles.
    """
    # Animales activos (solo los que están en categorías que reciben raciones)
    animales = Animal.objects.filter(
        estado_an='activo',
        categoria_an__in=['ternero', 'novilla', 'vaca_leche', 'vaca_seca', 'toro', 'ceba']
    ).select_related('fk_ra').order_by('codigo_an')
    
    # Dietas activas
    dietas = Dieta.objects.filter(
        activa_di=True
    ).order_by('nombre_di')
    
    # Insumos alimenticios activos con stock
    insumos = InsumoAlimenticio.objects.filter(
        activo_ia=True,
        stock_kg_ia__gt=0
    ).order_by('nombre_ia')
    
    contexto = {
        'animales': animales,
        'dietas': dietas,
        'insumos': insumos,
        'hoy': date.today().isoformat(),
    }
    
    return render(request, 'catalogos/alimentacion/racion/nueva_racion.html', contexto)


# ==========================================
# VISTA: GUARDAR RACIÓN (procesar creación)
# ==========================================
def guardarracion(request):
    """
    Procesa el formulario de creación de una nueva ración.
    Valida datos, verifica stock de insumo, calcula eficiencia,
    y registra auditoría.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevaracion/')
    
    try:
        with transaction.atomic():
            # ==========================================
            # OBTENER Y VALIDAR DATOS DEL FORMULARIO
            # ==========================================
            
            # Animal (obligatorio)
            fk_an_id = request.POST.get('sel_animal_ra')
            if not fk_an_id:
                messages.error(request, "Debe seleccionar un animal")
                return redirect('/nuevaracion/')
            
            animal = get_object_or_404(Animal, id_an=fk_an_id)
            
            # Validar que el animal esté activo
            if animal.estado_an != 'activo':
                messages.error(request, f"El animal {animal.codigo_an} no está activo.")
                return redirect('/nuevaracion/')
            
            # Validar categoría válida para ración
            categorias_validas = ['ternero', 'novilla', 'vaca_leche', 'vaca_seca', 'toro', 'ceba']
            if animal.categoria_an not in categorias_validas:
                messages.error(
                    request, 
                    f"El animal {animal.codigo_an} ({animal.categoria_an}) no está en una categoría que reciba raciones."
                )
                return redirect('/nuevaracion/')
            
            # Dieta (obligatoria)
            fk_di_id = request.POST.get('sel_dieta_ra')
            if not fk_di_id:
                messages.error(request, "Debe seleccionar una dieta")
                return redirect('/nuevaracion/')
            
            dieta = get_object_or_404(Dieta, id_di=fk_di_id)
            
            # Validar que la dieta esté activa
            if not dieta.activa_di:
                messages.error(request, f"La dieta '{dieta.nombre_di}' no está activa.")
                return redirect('/nuevaracion/')
            
            # Insumo alimenticio (opcional)
            fk_ia = None
            insumo_id = request.POST.get('sel_insumo_ra', '').strip()
            if insumo_id:
                fk_ia = get_object_or_404(InsumoAlimenticio, id_ia=insumo_id)
                # Validar que el insumo esté activo
                if not fk_ia.activo_ia:
                    messages.error(request, f"El insumo '{fk_ia.nombre_ia}' no está activo.")
                    return redirect('/nuevaracion/')
            
            # Fecha inicio (obligatoria)
            fecha_inicio_ra = request.POST.get('txt_fecha_inicio_ra')
            if not fecha_inicio_ra:
                messages.error(request, "La fecha de inicio es obligatoria")
                return redirect('/nuevaracion/')
            
            # Validar que no sea futura
            if fecha_inicio_ra > str(date.today()):
                messages.error(request, "La fecha de inicio no puede ser futura")
                return redirect('/nuevaracion/')
            
            # Fecha fin (opcional)
            fecha_fin_ra = request.POST.get('txt_fecha_fin_ra', '').strip() or None
            
            # Validar que fecha_fin sea posterior a fecha_inicio
            if fecha_fin_ra:
                if fecha_fin_ra < fecha_inicio_ra:
                    messages.error(request, "La fecha de fin debe ser posterior o igual a la fecha de inicio")
                    return redirect('/nuevaracion/')
            
            # Cantidad ofrecida (obligatoria)
            cantidad_ofrecida = request.POST.get('txt_cantidad_ofrecida_kg_ra', '').strip()
            if not cantidad_ofrecida:
                messages.error(request, "La cantidad ofrecida es obligatoria")
                return redirect('/nuevaracion/')
            
            try:
                cantidad_ofrecida_kg_ra = Decimal(cantidad_ofrecida)
                if cantidad_ofrecida_kg_ra <= 0:
                    messages.error(request, "La cantidad ofrecida debe ser mayor a 0")
                    return redirect('/nuevaracion/')
            except InvalidOperation:
                messages.error(request, "La cantidad ofrecida no es un número válido")
                return redirect('/nuevaracion/')
            
            # Cantidad consumida (opcional)
            cantidad_consumida_kg_ra = None
            cantidad_consumida = request.POST.get('txt_cantidad_consumida_kg_ra', '').strip()
            if cantidad_consumida:
                try:
                    cantidad_consumida_kg_ra = Decimal(cantidad_consumida)
                    if cantidad_consumida_kg_ra < 0:
                        messages.error(request, "La cantidad consumida no puede ser negativa")
                        return redirect('/nuevaracion/')
                    if cantidad_consumida_kg_ra > cantidad_ofrecida_kg_ra:
                        messages.error(
                            request, 
                            f"La cantidad consumida ({cantidad_consumida_kg_ra} kg) no puede superar la ofrecida ({cantidad_ofrecida_kg_ra} kg)"
                        )
                        return redirect('/nuevaracion/')
                except InvalidOperation:
                    messages.error(request, "La cantidad consumida no es un número válido")
                    return redirect('/nuevaracion/')
            
            # Desperdicio (opcional)
            desperdicio_kg_ra = None
            desperdicio = request.POST.get('txt_desperdicio_kg_ra', '').strip()
            if desperdicio:
                try:
                    desperdicio_kg_ra = Decimal(desperdicio)
                    if desperdicio_kg_ra < 0:
                        messages.error(request, "El desperdicio no puede ser negativo")
                        return redirect('/nuevaracion/')
                    # Validar que desperdicio no supere lo no consumido
                    if cantidad_consumida_kg_ra:
                        no_consumido = cantidad_ofrecida_kg_ra - cantidad_consumida_kg_ra
                        if desperdicio_kg_ra > no_consumido:
                            messages.error(
                                request,
                                f"El desperdicio ({desperdicio_kg_ra} kg) no puede superar lo no consumido ({no_consumido} kg)"
                            )
                            return redirect('/nuevaracion/')
                except InvalidOperation:
                    messages.error(request, "El desperdicio no es un número válido")
                    return redirect('/nuevaracion/')
            
            # Días en potrero (opcional)
            dias_en_potrero_ra = None
            dias_potrero = request.POST.get('txt_dias_en_potrero_ra', '').strip()
            if dias_potrero:
                try:
                    dias_en_potrero_ra = int(dias_potrero)
                    if dias_en_potrero_ra < 0:
                        messages.error(request, "Los días en potrero no pueden ser negativos")
                        return redirect('/nuevaracion/')
                except ValueError:
                    messages.error(request, "Los días en potrero deben ser un número entero")
                    return redirect('/nuevaracion/')
            
            # Usuario actual (obligatorio)
            try:
                fk_us_ra = Usuario.objects.get(id_us=request.session.get('id_us', 1))
            except Usuario.DoesNotExist:
                messages.error(request, "Error de autenticación de usuario")
                return redirect('/nuevaracion/')
            
            # ==========================================
            # VERIFICAR RACIÓN ACTIVA EXISTENTE
            # ==========================================
            racion_activa = Racion.objects.filter(
                fk_an=animal,
                fecha_fin_ra__isnull=True
            ).first()
            
            if racion_activa:
                messages.warning(
                    request,
                    f"ADVERTENCIA: El animal {animal.codigo_an} ya tiene una ración activa "
                    f"(ID: #{racion_activa.id_ra}, inicio: {racion_activa.fecha_inicio_ra}). "
                    f"Considere finalizarla antes de crear una nueva."
                )
            
            # ==========================================
            # VERIFICAR STOCK DE INSUMO SI APLICA
            # ==========================================
            if fk_ia:
                if fk_ia.stock_kg_ia < cantidad_ofrecida_kg_ra:
                    messages.error(
                        request,
                        f"Stock insuficiente de '{fk_ia.nombre_ia}'. "
                        f"Disponible: {fk_ia.stock_kg_ia} kg, Requerido: {cantidad_ofrecida_kg_ra} kg"
                    )
                    return redirect('/nuevaracion/')
            
            # ==========================================
            # CREAR RACIÓN
            # ==========================================
            nueva_racion = Racion.objects.create(
                fk_an=animal,
                fk_di=dieta,
                fk_ia=fk_ia,
                fecha_inicio_ra=fecha_inicio_ra,
                fecha_fin_ra=fecha_fin_ra,
                cantidad_ofrecida_kg_ra=cantidad_ofrecida_kg_ra,
                cantidad_consumida_kg_ra=cantidad_consumida_kg_ra,
                desperdicio_kg_ra=desperdicio_kg_ra,
                dias_en_potrero_ra=dias_en_potrero_ra,
                fk_us_ra=fk_us_ra
            )
            
            # ==========================================
            # DESCONTAR STOCK DE INSUMO SI APLICA
            # ==========================================
            if fk_ia:
                fk_ia.stock_kg_ia -= cantidad_ofrecida_kg_ra
                fk_ia.save()
                messages.info(
                    request,
                    f"Stock de '{fk_ia.nombre_ia}' actualizado: {fk_ia.stock_kg_ia} kg restantes"
                )
            
            # ==========================================
            # AUDITORÍA
            # ==========================================
            guardar_auditoria(
                request,
                'crear',
                'Racion',
                nueva_racion.id_ra,
                f'Se creó ración #{nueva_racion.id_ra}: {animal.codigo_an} - '
                f'Dieta: {dieta.nombre_di} - Ofrecido: {cantidad_ofrecida_kg_ra} kg'
            )
            
            messages.success(
                request,
                f"Ración de '{animal.codigo_an}' registrada exitosamente. "
                f"Cantidad ofrecida: {cantidad_ofrecida_kg_ra} kg"
            )
            return redirect('/listaracion/')
            
    except Animal.DoesNotExist:
        messages.error(request, "Animal no encontrado")
        return redirect('/nuevaracion/')
    except Dieta.DoesNotExist:
        messages.error(request, "Dieta no encontrada")
        return redirect('/nuevaracion/')
    except InsumoAlimenticio.DoesNotExist:
        messages.error(request, "Insumo alimenticio no encontrado")
        return redirect('/nuevaracion/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevaracion/')


# ==========================================
# VISTA: EDITAR RACIÓN (formulario)
# ==========================================
def editarracion(request, id_ra):
    """
    Muestra el formulario de edición con los datos precargados.
    El animal y la dieta no se pueden cambiar. El insumo sí.
    """
    racion = get_object_or_404(
        Racion.objects.select_related('fk_an', 'fk_di', 'fk_ia', 'fk_us_ra'),
        id_ra=id_ra
    )
    
    # Insumos disponibles (incluir el actual aunque no tenga stock)
    insumos = InsumoAlimenticio.objects.filter(
        Q(activo_ia=True, stock_kg_ia__gt=0) | Q(id_ia=racion.fk_ia_id)
    ).order_by('nombre_ia')
    
    # Calcular estado
    hoy = date.today()
    if racion.fecha_fin_ra and racion.fecha_fin_ra < hoy:
        racion.estado = 'finalizada'
    else:
        racion.estado = 'activa'
    
    contexto = {
        'racion': racion,
        'insumos': insumos,
    }
    
    return render(request, 'catalogos/alimentacion/racion/editar_racion.html', contexto)


# ==========================================
# VISTA: PROCESAR EDICIÓN RACIÓN
# ==========================================
def procesareditarracion(request):
    """
    Procesa el formulario de edición de una ración existente.
    El animal y la dieta no se modifican. El insumo, cantidades y fechas sí.
    Maneja cambio de insumo y ajuste de stock.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listaracion/')
    
    try:
        with transaction.atomic():
            # Obtener ración existente
            id_ra = request.POST.get('id_ra')
            if not id_ra:
                messages.error(request, "ID de ración no proporcionado")
                return redirect('/listaracion/')
            
            racion = Racion.objects.select_related('fk_an', 'fk_di', 'fk_ia').get(id_ra=id_ra)
            animal = racion.fk_an
            dieta = racion.fk_di
            insumo_anterior = racion.fk_ia
            
            # ==========================================
            # OBTENER Y VALIDAR DATOS DEL FORMULARIO
            # ==========================================
            
            # Fecha inicio (obligatoria)
            fecha_inicio_ra = request.POST.get('txt_fecha_inicio_ra')
            if not fecha_inicio_ra:
                messages.error(request, "La fecha de inicio es obligatoria")
                return redirect(f'/editarracion/{id_ra}')
            
            # Validar que no sea futura
            if fecha_inicio_ra > str(date.today()):
                messages.error(request, "La fecha de inicio no puede ser futura")
                return redirect(f'/editarracion/{id_ra}')
            
            # Fecha fin (opcional)
            fecha_fin_ra = request.POST.get('txt_fecha_fin_ra', '').strip() or None
            if fecha_fin_ra:
                if fecha_fin_ra < fecha_inicio_ra:
                    messages.error(request, "La fecha de fin debe ser posterior o igual a la fecha de inicio")
                    return redirect(f'/editarracion/{id_ra}')
            
            # Insumo (opcional, puede cambiar)
            fk_ia = None
            insumo_id = request.POST.get('sel_insumo_ra', '').strip()
            if insumo_id:
                fk_ia = get_object_or_404(InsumoAlimenticio, id_ia=insumo_id)
                if not fk_ia.activo_ia:
                    messages.error(request, f"El insumo '{fk_ia.nombre_ia}' no está activo.")
                    return redirect(f'/editarracion/{id_ra}')
            else:
                # Si desvincula insumo, verificar que no sea obligatorio
                pass  # Es opcional, se permite desvincular
            
            # Cantidad ofrecida (obligatoria)
            cantidad_ofrecida = request.POST.get('txt_cantidad_ofrecida_kg_ra', '').strip()
            if not cantidad_ofrecida:
                messages.error(request, "La cantidad ofrecida es obligatoria")
                return redirect(f'/editarracion/{id_ra}')
            
            try:
                cantidad_ofrecida_kg_ra = Decimal(cantidad_ofrecida)
                if cantidad_ofrecida_kg_ra <= 0:
                    messages.error(request, "La cantidad ofrecida debe ser mayor a 0")
                    return redirect(f'/editarracion/{id_ra}')
            except InvalidOperation:
                messages.error(request, "La cantidad ofrecida no es un número válido")
                return redirect(f'/editarracion/{id_ra}')
            
            # Cantidad consumida (opcional)
            cantidad_consumida_kg_ra = None
            cantidad_consumida = request.POST.get('txt_cantidad_consumida_kg_ra', '').strip()
            if cantidad_consumida:
                try:
                    cantidad_consumida_kg_ra = Decimal(cantidad_consumida)
                    if cantidad_consumida_kg_ra < 0:
                        messages.error(request, "La cantidad consumida no puede ser negativa")
                        return redirect(f'/editarracion/{id_ra}')
                    if cantidad_consumida_kg_ra > cantidad_ofrecida_kg_ra:
                        messages.error(
                            request,
                            f"La cantidad consumida ({cantidad_consumida_kg_ra} kg) no puede superar la ofrecida ({cantidad_ofrecida_kg_ra} kg)"
                        )
                        return redirect(f'/editarracion/{id_ra}')
                except InvalidOperation:
                    messages.error(request, "La cantidad consumida no es un número válido")
                    return redirect(f'/editarracion/{id_ra}')
            
            # Desperdicio (opcional)
            desperdicio_kg_ra = None
            desperdicio = request.POST.get('txt_desperdicio_kg_ra', '').strip()
            if desperdicio:
                try:
                    desperdicio_kg_ra = Decimal(desperdicio)
                    if desperdicio_kg_ra < 0:
                        messages.error(request, "El desperdicio no puede ser negativo")
                        return redirect(f'/editarracion/{id_ra}')
                    if cantidad_consumida_kg_ra:
                        no_consumido = cantidad_ofrecida_kg_ra - cantidad_consumida_kg_ra
                        if desperdicio_kg_ra > no_consumido:
                            messages.error(
                                request,
                                f"El desperdicio ({desperdicio_kg_ra} kg) no puede superar lo no consumido ({no_consumido} kg)"
                            )
                            return redirect(f'/editarracion/{id_ra}')
                except InvalidOperation:
                    messages.error(request, "El desperdicio no es un número válido")
                    return redirect(f'/editarracion/{id_ra}')
            
            # Días en potrero (opcional)
            dias_en_potrero_ra = None
            dias_potrero = request.POST.get('txt_dias_en_potrero_ra', '').strip()
            if dias_potrero:
                try:
                    dias_en_potrero_ra = int(dias_potrero)
                    if dias_en_potrero_ra < 0:
                        messages.error(request, "Los días en potrero no pueden ser negativos")
                        return redirect(f'/editarracion/{id_ra}')
                except ValueError:
                    messages.error(request, "Los días en potrero deben ser un número entero")
                    return redirect(f'/editarracion/{id_ra}')
            
            # ==========================================
            # MANEJO DE CAMBIO DE INSUMO Y STOCK
            # ==========================================
            
            # Si cambia el insumo o la cantidad
            cantidad_anterior = racion.cantidad_ofrecida_kg_ra or Decimal('0')
            
            # Revertir stock del insumo anterior si aplica
            if insumo_anterior and (not fk_ia or fk_ia.id_ia != insumo_anterior.id_ia):
                insumo_anterior.stock_kg_ia += cantidad_anterior
                insumo_anterior.save()
                messages.info(
                    request,
                    f"Stock de '{insumo_anterior.nombre_ia}' restaurado: +{cantidad_anterior} kg"
                )
            
            # Si mantiene el mismo insumo pero cambia la cantidad
            if fk_ia and insumo_anterior and fk_ia.id_ia == insumo_anterior.id_ia:
                diferencia = cantidad_ofrecida_kg_ra - cantidad_anterior
                if diferencia > 0:
                    # Necesita más stock
                    if fk_ia.stock_kg_ia < diferencia:
                        messages.error(
                            request,
                            f"Stock insuficiente de '{fk_ia.nombre_ia}'. "
                            f"Disponible: {fk_ia.stock_kg_ia} kg, Adicional requerido: {diferencia} kg"
                        )
                        return redirect(f'/editarracion/{id_ra}')
                    fk_ia.stock_kg_ia -= diferencia
                    fk_ia.save()
                    messages.info(
                        request,
                        f"Stock de '{fk_ia.nombre_ia}' descontado: -{diferencia} kg"
                    )
                elif diferencia < 0:
                    # Devuelve stock
                    fk_ia.stock_kg_ia += abs(diferencia)
                    fk_ia.save()
                    messages.info(
                        request,
                        f"Stock de '{fk_ia.nombre_ia}' restaurado: +{abs(diferencia)} kg"
                    )
            
            # Si vincula nuevo insumo
            elif fk_ia and (not insumo_anterior or fk_ia.id_ia != insumo_anterior.id_ia):
                if fk_ia.stock_kg_ia < cantidad_ofrecida_kg_ra:
                    messages.error(
                        request,
                        f"Stock insuficiente de '{fk_ia.nombre_ia}'. "
                        f"Disponible: {fk_ia.stock_kg_ia} kg, Requerido: {cantidad_ofrecida_kg_ra} kg"
                    )
                    return redirect(f'/editarracion/{id_ra}')
                fk_ia.stock_kg_ia -= cantidad_ofrecida_kg_ra
                fk_ia.save()
                messages.info(
                    request,
                    f"Stock de '{fk_ia.nombre_ia}' descontado: -{cantidad_ofrecida_kg_ra} kg"
                )
            
            # ==========================================
            # ACTUALIZAR RACIÓN
            # ==========================================
            racion.fk_ia = fk_ia
            racion.fecha_inicio_ra = fecha_inicio_ra
            racion.fecha_fin_ra = fecha_fin_ra
            racion.cantidad_ofrecida_kg_ra = cantidad_ofrecida_kg_ra
            racion.cantidad_consumida_kg_ra = cantidad_consumida_kg_ra
            racion.desperdicio_kg_ra = desperdicio_kg_ra
            racion.dias_en_potrero_ra = dias_en_potrero_ra
            
            racion.save()
            
            # ==========================================
            # AUDITORÍA
            # ==========================================
            guardar_auditoria(
                request,
                'editar',
                'Racion',
                racion.id_ra,
                f'Se editó ración #{id_ra}: {animal.codigo_an} - '
                f'Ofrecido: {cantidad_ofrecida_kg_ra} kg'
            )
            
            messages.success(
                request,
                f"Ración de '{animal.codigo_an}' actualizada exitosamente"
            )
            return redirect('/listaracion/')
            
    except Racion.DoesNotExist:
        messages.error(request, "Ración no encontrada")
        return redirect('/listaracion/')
    except InsumoAlimenticio.DoesNotExist:
        messages.error(request, "Insumo alimenticio no encontrado")
        return redirect(f'/editarracion/{id_ra}')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarracion/{id_ra}')


# ==========================================
# VISTA: ELIMINAR RACIÓN
# ==========================================
def eliminaracion(request, id_ra):
    """
    Elimina una ración del sistema.
    Restaura el stock del insumo vinculado si aplica.
    """
    racion = get_object_or_404(
        Racion.objects.select_related('fk_an', 'fk_ia'),
        id_ra=id_ra
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_racion = racion.id_ra
    codigo_animal = racion.fk_an.codigo_an
    insumo = racion.fk_ia
    cantidad_ofrecida = racion.cantidad_ofrecida_kg_ra or Decimal('0')
    
    try:
        with transaction.atomic():
            # ==========================================
            # RESTAURAR STOCK DE INSUMO SI APLICA
            # ==========================================
            if insumo:
                insumo.stock_kg_ia += cantidad_ofrecida
                insumo.save()
                messages.info(
                    request,
                    f"Stock de '{insumo.nombre_ia}' restaurado: +{cantidad_ofrecida} kg"
                )
            
            # ==========================================
            # ELIMINAR RACIÓN
            # ==========================================
            racion.delete()
            
            # ==========================================
            # AUDITORÍA
            # ==========================================
            guardar_auditoria(
                request,
                'eliminar',
                'Racion',
                id_racion,
                f'Se eliminó ración #{id_racion}: {codigo_animal}'
            )
            
            messages.success(request, f"Ración de {codigo_animal} eliminada exitosamente")
            
    except Exception as e:
        messages.error(request, f"Error al eliminar: {str(e)}")
    
    return redirect('/listaracion/')
#------------------------------
# Asignacion potrero
#------------------------------
def listaasignacionp(request):
    """
    Muestra el listado completo de asignaciones de potrero con estadísticas.
    Incluye conteos por estado (activa, vencida, finalizada).
    """
    asignaciones_list = AsignacionPotrero.objects.all().select_related(
        'fk_po', 'fk_an', 'fk_us_ap'
    ).order_by('-fecha_ingreso_ap', '-created_at_ap')
    
    hoy = date.today()
    
    # Calcular estado y métricas para cada asignación
    for asignacion in asignaciones_list:
        asignacion.estado_calculado = asignacion.estado
        asignacion.dias_en_potrero_calculado = asignacion.dias_en_potrero
        asignacion.dias_restantes_calculado = asignacion.dias_restantes
    
    # Estadísticas generales
    total_asignaciones = asignaciones_list.count()
    asignaciones_activas = sum(1 for a in asignaciones_list if a.estado_calculado == 'activa')
    asignaciones_vencidas = sum(1 for a in asignaciones_list if a.estado_calculado == 'vencida')
    asignaciones_finalizadas = sum(1 for a in asignaciones_list if a.estado_calculado == 'finalizada')
    
    # Estadísticas de potreros
    potreros_ocupados = asignaciones_list.filter(
        fecha_salida_real_ap__isnull=True
    ).values('fk_po').distinct().count()
    
    # Animales en potrero
    animales_en_potrero = asignaciones_list.filter(
        fecha_salida_real_ap__isnull=True
    ).count()
    
    contexto = {
        'asignaciones_list': asignaciones_list,
        'total_asignaciones': total_asignaciones,
        'asignaciones_activas': asignaciones_activas,
        'asignaciones_vencidas': asignaciones_vencidas,
        'asignaciones_finalizadas': asignaciones_finalizadas,
        'potreros_ocupados': potreros_ocupados,
        'animales_en_potrero': animales_en_potrero,
    }
    
    return render(request, 'catalogos/potreros/asignacion/lista_asignacionp.html', contexto)


# ==========================================
# VISTA: NUEVA ASIGNACIÓN (formulario)
# ==========================================
def nuevaasignacionp(request):
    """
    Muestra el formulario para registrar una nueva asignación de potrero.
    Carga potreros disponibles y animales activos no asignados.
    """
    # Potreros disponibles (estado disponible o en_descanso, capacidad no excedida)
    potreros = Potrero.objects.filter(
        estado_po__in=['disponible', 'en_descanso']
    ).order_by('codigo_po')
    
    # Animales activos no asignados actualmente a un potrero
    animales_asignados = AsignacionPotrero.objects.filter(
        fecha_salida_real_ap__isnull=True
    ).values_list('fk_an_id', flat=True)
    
    animales = Animal.objects.filter(
        estado_an='activo'
    ).exclude(
        id_an__in=animales_asignados
    ).select_related('fk_ra').order_by('codigo_an')
    
    contexto = {
        'potreros': potreros,
        'animales': animales,
        'hoy': date.today().isoformat(),
    }
    
    return render(request, 'catalogos/potreros/asignacion/nueva_asignacionp.html', contexto)


# ==========================================
# VISTA: GUARDAR ASIGNACIÓN (procesar creación)
# ==========================================
def guardarasignacionp(request):
    """
    Procesa el formulario de creación de una nueva asignación de potrero.
    Valida datos, verifica capacidad del potrero, y registra auditoría.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevaasignacionp/')
    
    try:
        with transaction.atomic():
            # ==========================================
            # OBTENER Y VALIDAR DATOS DEL FORMULARIO
            # ==========================================
            
            # Potrero (obligatorio)
            fk_po_id = request.POST.get('sel_potrero_ap')
            if not fk_po_id:
                messages.error(request, "Debe seleccionar un potrero")
                return redirect('/nuevaasignacionp/')
            
            potrero = get_object_or_404(Potrero, id_po=fk_po_id)
            
            # Validar que el potrero esté disponible
            if potrero.estado_po not in ['disponible', 'en_descanso']:
                messages.error(request, f"El potrero {potrero.codigo_po} no está disponible.")
                return redirect('/nuevaasignacionp/')
            
            # Animal (obligatorio)
            fk_an_id = request.POST.get('sel_animal_ap')
            if not fk_an_id:
                messages.error(request, "Debe seleccionar un animal")
                return redirect('/nuevaasignacionp/')
            
            animal = get_object_or_404(Animal, id_an=fk_an_id)
            
            # Validar que el animal esté activo
            if animal.estado_an != 'activo':
                messages.error(request, f"El animal {animal.codigo_an} no está activo.")
                return redirect('/nuevaasignacionp/')
            
            # Validar que el animal no esté asignado a otro potrero
            asignacion_activa = AsignacionPotrero.objects.filter(
                fk_an=animal,
                fecha_salida_real_ap__isnull=True
            ).first()
            
            if asignacion_activa:
                messages.error(
                    request,
                    f"El animal {animal.codigo_an} ya está asignado al potrero {asignacion_activa.fk_po.codigo_po}. "
                    f"Finalice esa asignación antes de crear una nueva."
                )
                return redirect('/nuevaasignacionp/')
            
            # Fecha ingreso (obligatoria)
            fecha_ingreso_ap = request.POST.get('txt_fecha_ingreso_ap')
            if not fecha_ingreso_ap:
                messages.error(request, "La fecha de ingreso es obligatoria")
                return redirect('/nuevaasignacionp/')
            
            # Validar que no sea futura
            if fecha_ingreso_ap > str(date.today()):
                messages.error(request, "La fecha de ingreso no puede ser futura")
                return redirect('/nuevaasignacionp/')
            
            # Fecha salida estimada (opcional)
            fecha_salida_estimada_ap = request.POST.get('txt_fecha_salida_estimada_ap', '').strip() or None
            
            # Validar que sea posterior a fecha ingreso
            if fecha_salida_estimada_ap:
                if fecha_salida_estimada_ap < fecha_ingreso_ap:
                    messages.error(request, "La fecha de salida estimada debe ser posterior a la fecha de ingreso")
                    return redirect('/nuevaasignacionp/')
            
            # Días descanso posterior (opcional, default 30)
            dias_descanso_posterior_ap = 30
            dias_descanso = request.POST.get('txt_dias_descanso_posterior_ap', '').strip()
            if dias_descanso:
                try:
                    dias_descanso_posterior_ap = int(dias_descanso)
                    if dias_descanso_posterior_ap < 0:
                        messages.error(request, "Los días de descanso no pueden ser negativos")
                        return redirect('/nuevaasignacionp/')
                except ValueError:
                    messages.error(request, "Los días de descanso deben ser un número entero")
                    return redirect('/nuevaasignacionp/')
            
            # Observaciones (opcional)
            observaciones_ap = request.POST.get('txt_observaciones_ap', '').strip() or None
            
            # Usuario actual (obligatorio)
            try:
                fk_us_ap = Usuario.objects.get(id_us=request.session.get('id_us', 1))
            except Usuario.DoesNotExist:
                messages.error(request, "Error de autenticación de usuario")
                return redirect('/nuevaasignacionp/')
            
            # ==========================================
            # VERIFICAR CAPACIDAD DEL POTRERO
            # ==========================================
            asignaciones_actuales = AsignacionPotrero.objects.filter(
                fk_po=potrero,
                fecha_salida_real_ap__isnull=True
            ).count()
            
            if asignaciones_actuales >= potrero.capacidad_maxima_po:
                messages.error(
                    request,
                    f"El potrero {potrero.codigo_po} ha alcanzado su capacidad máxima "
                    f"({potrero.capacidad_maxima_po} animales)."
                )
                return redirect('/nuevaasignacionp/')
            
            # ==========================================
            # CREAR ASIGNACIÓN
            # ==========================================
            nueva_asignacion = AsignacionPotrero.objects.create(
                fk_po=potrero,
                fk_an=animal,
                fecha_ingreso_ap=fecha_ingreso_ap,
                fecha_salida_estimada_ap=fecha_salida_estimada_ap,
                fecha_salida_real_ap=None,
                dias_descanso_posterior_ap=dias_descanso_posterior_ap,
                observaciones_ap=observaciones_ap,
                fk_us_ap=fk_us_ap
            )
            
            # Actualizar estado del potrero si se llena
            if asignaciones_actuales + 1 >= potrero.capacidad_maxima_po:
                potrero.estado_po = 'ocupado'
                potrero.save()
                messages.info(request, f"Potrero {potrero.codigo_po} marcado como ocupado.")
            
            # ==========================================
            # AUDITORÍA
            # ==========================================
            guardar_auditoria(
                request,
                'crear',
                'AsignacionPotrero',
                nueva_asignacion.id_ap,
                f'Se creó asignación #{nueva_asignacion.id_ap}: {animal.codigo_an} → {potrero.codigo_po}'
            )
            
            messages.success(
                request,
                f"Asignación creada: '{animal.codigo_an}' asignado a '{potrero.codigo_po}'."
            )
            return redirect('/listaasignacionp/')
            
    except Potrero.DoesNotExist:
        messages.error(request, "Potrero no encontrado")
        return redirect('/nuevaasignacionp/')
    except Animal.DoesNotExist:
        messages.error(request, "Animal no encontrado")
        return redirect('/nuevaasignacionp/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevaasignacionp/')


# ==========================================
# VISTA: EDITAR ASIGNACIÓN (formulario)
# ==========================================
def editarasignacionp(request, id_ap):
    """
    Muestra el formulario de edición con los datos precargados.
    El potrero y animal no se pueden cambiar. Solo fechas y observaciones.
    """
    asignacion = get_object_or_404(
        AsignacionPotrero.objects.select_related('fk_po', 'fk_an', 'fk_us_ap'),
        id_ap=id_ap
    )
    
    contexto = {
        'asignacion': asignacion,
    }
    
    return render(request, 'catalogos/potreros/asignacion/editar_asignacionp.html', contexto)


# ==========================================
# VISTA: PROCESAR EDICIÓN ASIGNACIÓN
# ==========================================
def procesareditarasignacionp(request):
    """
    Procesa el formulario de edición de una asignación existente.
    El potrero y animal no se modifican. Se puede registrar salida real.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listaasignacionp/')
    
    try:
        with transaction.atomic():
            # Obtener asignación existente
            id_ap = request.POST.get('id_ap')
            if not id_ap:
                messages.error(request, "ID de asignación no proporcionado")
                return redirect('/listaasignacionp/')
            
            asignacion = AsignacionPotrero.objects.select_related('fk_po', 'fk_an').get(id_ap=id_ap)
            potrero = asignacion.fk_po
            animal = asignacion.fk_an
            
            # ==========================================
            # OBTENER Y VALIDAR DATOS DEL FORMULARIO
            # ==========================================
            
            # Fecha ingreso (obligatoria)
            fecha_ingreso_ap = request.POST.get('txt_fecha_ingreso_ap')
            if not fecha_ingreso_ap:
                messages.error(request, "La fecha de ingreso es obligatoria")
                return redirect(f'/editarasignacionp/{id_ap}')
            
            # Validar que no sea futura
            if fecha_ingreso_ap > str(date.today()):
                messages.error(request, "La fecha de ingreso no puede ser futura")
                return redirect(f'/editarasignacionp/{id_ap}')
            
            # Fecha salida estimada (opcional)
            fecha_salida_estimada_ap = request.POST.get('txt_fecha_salida_estimada_ap', '').strip() or None
            
            if fecha_salida_estimada_ap:
                if fecha_salida_estimada_ap < fecha_ingreso_ap:
                    messages.error(request, "La fecha de salida estimada debe ser posterior a la fecha de ingreso")
                    return redirect(f'/editarasignacionp/{id_ap}')
            
            # Fecha salida real (opcional - para finalizar asignación)
            fecha_salida_real_ap = request.POST.get('txt_fecha_salida_real_ap', '').strip() or None
            
            if fecha_salida_real_ap:
                if fecha_salida_real_ap < fecha_ingreso_ap:
                    messages.error(request, "La fecha de salida real no puede ser anterior a la fecha de ingreso")
                    return redirect(f'/editarasignacionp/{id_ap}')
                
                if fecha_salida_real_ap > str(date.today()):
                    messages.error(request, "La fecha de salida real no puede ser futura")
                    return redirect(f'/editarasignacionp/{id_ap}')
            
            # Días descanso posterior
            dias_descanso_posterior_ap = 30
            dias_descanso = request.POST.get('txt_dias_descanso_posterior_ap', '').strip()
            if dias_descanso:
                try:
                    dias_descanso_posterior_ap = int(dias_descanso)
                    if dias_descanso_posterior_ap < 0:
                        messages.error(request, "Los días de descanso no pueden ser negativos")
                        return redirect(f'/editarasignacionp/{id_ap}')
                except ValueError:
                    messages.error(request, "Los días de descanso deben ser un número entero")
                    return redirect(f'/editarasignacionp/{id_ap}')
            
            # Observaciones (opcional)
            observaciones_ap = request.POST.get('txt_observaciones_ap', '').strip() or None
            
            # ==========================================
            # ACTUALIZAR ASIGNACIÓN
            # ==========================================
            asignacion.fecha_ingreso_ap = fecha_ingreso_ap
            asignacion.fecha_salida_estimada_ap = fecha_salida_estimada_ap
            asignacion.fecha_salida_real_ap = fecha_salida_real_ap
            asignacion.dias_descanso_posterior_ap = dias_descanso_posterior_ap
            asignacion.observaciones_ap = observaciones_ap
            
            asignacion.save()
            
            # Si se registró salida real, liberar potrero
            if fecha_salida_real_ap:
                # Verificar si quedan animales en el potrero
                animales_restantes = AsignacionPotrero.objects.filter(
                    fk_po=potrero,
                    fecha_salida_real_ap__isnull=True
                ).count()
                
                if animales_restantes == 0:
                    potrero.estado_po = 'en_descanso'
                    potrero.save()
                    messages.info(
                        request,
                        f"Potrero {potrero.codigo_po} liberado. Estado: en descanso."
                    )
                else:
                    potrero.estado_po = 'disponible'
                    potrero.save()
                    messages.info(
                        request,
                        f"Potrero {potrero.codigo_po} liberado. Animales restantes: {animales_restantes}."
                    )
            
            # ==========================================
            # AUDITORÍA
            # ==========================================
            guardar_auditoria(
                request,
                'editar',
                'AsignacionPotrero',
                asignacion.id_ap,
                f'Se editó asignación #{id_ap}: {animal.codigo_an} → {potrero.codigo_po}'
            )
            
            messages.success(
                request,
                f"Asignación de '{animal.codigo_an}' actualizada exitosamente."
            )
            return redirect('/listaasignacionp/')
            
    except AsignacionPotrero.DoesNotExist:
        messages.error(request, "Asignación no encontrada")
        return redirect('/listaasignacionp/')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarasignacionp/{id_ap}')


# ==========================================
# VISTA: ELIMINAR ASIGNACIÓN
# ==========================================
def eliminaasignacionp(request, id_ap):
    """
    Elimina una asignación de potrero del sistema.
    Libera el potrero si queda vacío.
    """
    asignacion = get_object_or_404(
        AsignacionPotrero.objects.select_related('fk_po', 'fk_an'),
        id_ap=id_ap
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_asignacion = asignacion.id_ap
    codigo_animal = asignacion.fk_an.codigo_an
    codigo_potrero = asignacion.fk_po.codigo_po
    potrero = asignacion.fk_po
    
    try:
        with transaction.atomic():
            # ==========================================
            # ELIMINAR ASIGNACIÓN
            # ==========================================
            asignacion.delete()
            
            # Verificar si el potrero quedó vacío
            animales_restantes = AsignacionPotrero.objects.filter(
                fk_po=potrero,
                fecha_salida_real_ap__isnull=True
            ).count()
            
            if animales_restantes == 0:
                potrero.estado_po = 'disponible'
                potrero.save()
                messages.info(request, f"Potrero {codigo_potrero} liberado. Estado: disponible.")
            
            # ==========================================
            # AUDITORÍA
            # ==========================================
            guardar_auditoria(
                request,
                'eliminar',
                'AsignacionPotrero',
                id_asignacion,
                f'Se eliminó asignación #{id_asignacion}: {codigo_animal} → {codigo_potrero}'
            )
            
            messages.success(request, f"Asignación de {codigo_animal} eliminada exitosamente")
            
    except Exception as e:
        messages.error(request, f"Error al eliminar: {str(e)}")
    
    return redirect('/listaasignacionp/')

#Pesajes
def listapesaje(request):
    """
    Muestra el listado completo de pesajes con estadísticas.
    Incluye promedio de peso, peso máximo, mínimo y conteos por método.
    """
    pesaje_list = Pesaje.objects.all().select_related(
        'fk_an', 'fk_an__fk_ra', 'fk_us_pe'
    ).order_by('-fecha_pe', '-created_at_pe')
    
    # Estadísticas generales
    total_pesajes = pesaje_list.count()
    
    # Promedio de peso general
    peso_promedio = pesaje_list.aggregate(promedio=Avg('peso_kg_pe'))['promedio'] or 0
    
    # Peso máximo y mínimo
    peso_maximo = pesaje_list.aggregate(maximo=Max('peso_kg_pe'))['maximo'] or 0
    peso_minimo = pesaje_list.aggregate(minimo=Min('peso_kg_pe'))['minimo'] or 0
    
    # Conteos por método
    total_bascula = pesaje_list.filter(metodo_pe='bascula').count()
    total_cinta = pesaje_list.filter(metodo_pe='cinta_metrica').count()
    total_estimacion = pesaje_list.filter(metodo_pe='estimacion_visual').count()
    
    # Pesajes del mes actual
    hoy = date.today()
    pesajes_mes = pesaje_list.filter(
        fecha_pe__year=hoy.year,
        fecha_pe__month=hoy.month
    ).count()
    
    contexto = {
        'pesaje_list': pesaje_list,
        'total_pesajes': total_pesajes,
        'peso_promedio': round(peso_promedio, 2),
        'peso_maximo': peso_maximo,
        'peso_minimo': peso_minimo,
        'total_bascula': total_bascula,
        'total_cinta': total_cinta,
        'total_estimacion': total_estimacion,
        'pesajes_mes': pesajes_mes,
    }
    
    return render(request, 'catalogos/animal/pesajes/lista_pesaje.html', contexto)


# ==========================================
# VISTA: NUEVO PESAJE (formulario)
# ==========================================
def nuevapesaje(request):
    """
    Muestra el formulario para registrar un nuevo pesaje.
    Carga lista de animales activos.
    """
    # Animales activos ordenados por código
    animales = Animal.objects.filter(
        estado_an='activo'
    ).select_related('fk_ra').order_by('codigo_an')
    
    contexto = {
        'animales': animales,
    }
    
    return render(request, 'catalogos/animal/pesajes/nuevo_pesaje.html', contexto)


# ==========================================
# VISTA: GUARDAR PESAJE (procesar creación)
# ==========================================
def guardarpesaje(request):
    """
    Procesa el formulario de creación de un nuevo pesaje.
    Valida datos, verifica reglas de negocio y registra auditoría.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevapesaje/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Animal (obligatorio)
        fk_an_id = request.POST.get('sel_animal_pe')
        if not fk_an_id:
            messages.error(request, "Debe seleccionar un animal")
            return redirect('/nuevapesaje/')
        
        animal = get_object_or_404(Animal, id_an=fk_an_id)
        
        # Validar que esté activo
        if animal.estado_an != 'activo':
            messages.error(request, f"El animal {animal.codigo_an} no está activo.")
            return redirect('/nuevapesaje/')
        
        # Fecha de pesaje (obligatoria)
        fecha_pe = request.POST.get('txt_fecha_pe')
        if not fecha_pe:
            messages.error(request, "La fecha de pesaje es obligatoria")
            return redirect('/nuevapesaje/')
        
        # Validar que no sea futura
        if fecha_pe > str(date.today()):
            messages.error(request, "La fecha de pesaje no puede ser futura")
            return redirect('/nuevapesaje/')
        
        # Peso en kg (obligatorio)
        peso_kg_pe = request.POST.get('txt_peso_kg_pe', '').strip()
        if not peso_kg_pe:
            messages.error(request, "El peso es obligatorio")
            return redirect('/nuevapesaje/')
        
        try:
            peso_decimal = Decimal(peso_kg_pe)
            if peso_decimal <= 0:
                messages.error(request, "El peso debe ser mayor a 0")
                return redirect('/nuevapesaje/')
            if peso_decimal > 9999.99:
                messages.error(request, "El peso no puede exceder 9999.99 kg")
                return redirect('/nuevapesaje/')
        except InvalidOperation:
            messages.error(request, "El peso ingresado no es válido")
            return redirect('/nuevapesaje/')
        
        # Condición corporal (opcional, 1-5)
        condicion_corporal_pe = request.POST.get('txt_condicion_corporal_pe', '').strip()
        condicion_int = None
        if condicion_corporal_pe:
            try:
                condicion_int = int(condicion_corporal_pe)
                if condicion_int < 1 or condicion_int > 5:
                    messages.error(request, "La condición corporal debe estar entre 1 y 5")
                    return redirect('/nuevapesaje/')
            except ValueError:
                messages.error(request, "La condición corporal debe ser un número entero")
                return redirect('/nuevapesaje/')
        
        # Método de pesaje (opcional)
        metodo_pe = request.POST.get('sel_metodo_pe', '').strip()
        metodos_validos = ['bascula', 'cinta_metrica', 'estimacion_visual']
        if metodo_pe and metodo_pe not in metodos_validos:
            messages.error(request, "Método de pesaje no válido")
            return redirect('/nuevapesaje/')
        
        # Observaciones (opcional)
        observaciones_pe = request.POST.get('txt_observaciones_pe', '').strip()
        if observaciones_pe and len(observaciones_pe) > 2000:
            messages.error(request, "Las observaciones exceden 2000 caracteres")
            return redirect('/nuevapesaje/')
        
        # Usuario actual (obligatorio)
        try:
            fk_us_pe = Usuario.objects.get(id_us=request.session.get('id_us', 1))
        except Usuario.DoesNotExist:
            messages.error(request, "Error de autenticación de usuario")
            return redirect('/nuevapesaje/')
        
        # ==========================================
        # CREAR PESAJE
        # ==========================================
        nuevo_pesaje = Pesaje.objects.create(
            fk_an=animal,
            fecha_pe=fecha_pe,
            peso_kg_pe=peso_decimal,
            condicion_corporal_pe=condicion_int,
            metodo_pe=metodo_pe if metodo_pe else None,
            observaciones_pe=observaciones_pe if observaciones_pe else None,
            fk_us_pe=fk_us_pe
        )
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'Pesaje',
            nuevo_pesaje.id_pe,
            f'Se creó pesaje: {animal.codigo_an} - Peso: {peso_decimal} kg - Fecha: {fecha_pe}'
        )
        
        messages.success(request, f"Pesaje de '{animal.codigo_an}' registrado exitosamente. Peso: {peso_decimal} kg")
        return redirect('/listapesaje/')
        
    except Animal.DoesNotExist:
        messages.error(request, "Animal no encontrado")
        return redirect('/nuevapesaje/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect('/nuevapesaje/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevapesaje/')


# ==========================================
# VISTA: EDITAR PESAJE (formulario)
# ==========================================
def editarpesaje(request, id_pe):
    """
    Muestra el formulario de edición con los datos precargados.
    El animal no se puede cambiar.
    """
    pesaje = get_object_or_404(
        Pesaje.objects.select_related('fk_an', 'fk_an__fk_ra', 'fk_us_pe'),
        id_pe=id_pe
    )
    
    # Animales activos (solo para referencia, no se puede cambiar)
    animales = Animal.objects.filter(
        estado_an='activo'
    ).select_related('fk_ra').order_by('codigo_an')
    
    contexto = {
        'pesaje': pesaje,
        'animales': animales,
    }
    
    return render(request, 'catalogos/animal/pesajes/editar_pesaje.html', contexto)


# ==========================================
# VISTA: PROCESAR EDICION PESAJE
# ==========================================
def procesareditarpesaje(request):
    """
    Procesa el formulario de edición de un pesaje existente.
    El animal no se puede modificar.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listapesaje/')
    
    try:
        # Obtener pesaje existente
        id_pe = request.POST.get('id_pe')
        if not id_pe:
            messages.error(request, "ID de pesaje no proporcionado")
            return redirect('/listapesaje/')
        
        pesaje = Pesaje.objects.select_related('fk_an').get(id_pe=id_pe)
        animal = pesaje.fk_an
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Fecha de pesaje (obligatoria)
        fecha_pe = request.POST.get('txt_fecha_pe')
        if not fecha_pe:
            messages.error(request, "La fecha de pesaje es obligatoria")
            return redirect(f'/editarpesaje/{id_pe}')
        
        # Validar que no sea futura
        if fecha_pe > str(date.today()):
            messages.error(request, "La fecha de pesaje no puede ser futura")
            return redirect(f'/editarpesaje/{id_pe}')
        
        # Peso en kg (obligatorio)
        peso_kg_pe = request.POST.get('txt_peso_kg_pe', '').strip()
        if not peso_kg_pe:
            messages.error(request, "El peso es obligatorio")
            return redirect(f'/editarpesaje/{id_pe}')
        
        try:
            peso_decimal = Decimal(peso_kg_pe)
            if peso_decimal <= 0:
                messages.error(request, "El peso debe ser mayor a 0")
                return redirect(f'/editarpesaje/{id_pe}')
            if peso_decimal > 9999.99:
                messages.error(request, "El peso no puede exceder 9999.99 kg")
                return redirect(f'/editarpesaje/{id_pe}')
        except InvalidOperation:
            messages.error(request, "El peso ingresado no es válido")
            return redirect(f'/editarpesaje/{id_pe}')
        
        # Condición corporal (opcional, 1-5)
        condicion_corporal_pe = request.POST.get('txt_condicion_corporal_pe', '').strip()
        condicion_int = None
        if condicion_corporal_pe:
            try:
                condicion_int = int(condicion_corporal_pe)
                if condicion_int < 1 or condicion_int > 5:
                    messages.error(request, "La condición corporal debe estar entre 1 y 5")
                    return redirect(f'/editarpesaje/{id_pe}')
            except ValueError:
                messages.error(request, "La condición corporal debe ser un número entero")
                return redirect(f'/editarpesaje/{id_pe}')
        
        # Método de pesaje (opcional)
        metodo_pe = request.POST.get('sel_metodo_pe', '').strip()
        metodos_validos = ['bascula', 'cinta_metrica', 'estimacion_visual']
        if metodo_pe and metodo_pe not in metodos_validos:
            messages.error(request, "Método de pesaje no válido")
            return redirect(f'/editarpesaje/{id_pe}')
        
        # Observaciones (opcional)
        observaciones_pe = request.POST.get('txt_observaciones_pe', '').strip()
        if observaciones_pe and len(observaciones_pe) > 2000:
            messages.error(request, "Las observaciones exceden 2000 caracteres")
            return redirect(f'/editarpesaje/{id_pe}')
        
        # ==========================================
        # ACTUALIZAR PESAJE
        # ==========================================
        pesaje.fecha_pe = fecha_pe
        pesaje.peso_kg_pe = peso_decimal
        pesaje.condicion_corporal_pe = condicion_int
        pesaje.metodo_pe = metodo_pe if metodo_pe else None
        pesaje.observaciones_pe = observaciones_pe if observaciones_pe else None
        
        pesaje.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'Pesaje',
            pesaje.id_pe,
            f'Se editó pesaje #{id_pe}: {animal.codigo_an} - Peso: {peso_decimal} kg - Fecha: {fecha_pe}'
        )
        
        messages.success(request, f"Pesaje de '{animal.codigo_an}' actualizado exitosamente")
        return redirect('/listapesaje/')
        
    except Pesaje.DoesNotExist:
        messages.error(request, "Pesaje no encontrado")
        return redirect('/listapesaje/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect(f'/editarpesaje/{id_pe}')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarpesaje/{id_pe}')


# ==========================================
# VISTA: ELIMINAR PESAJE
# ==========================================
def eliminapesaje(request, id_pe):
    """
    Elimina un pesaje del sistema.
    """
    pesaje = get_object_or_404(
        Pesaje.objects.select_related('fk_an'),
        id_pe=id_pe
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_pesaje = pesaje.id_pe
    codigo_animal = pesaje.fk_an.codigo_an
    
    try:
        # ==========================================
        # ELIMINAR PESAJE
        # ==========================================
        pesaje.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'Pesaje',
            id_pesaje,
            f'Se eliminó pesaje #{id_pesaje}: {codigo_animal}'
        )
        
        messages.success(request, f"Pesaje de {codigo_animal} eliminado exitosamente")
        
    except Exception as e:
        messages.error(request, f"Error al eliminar: {str(e)}")
    
    return redirect('/listapesaje/')


# ==========================================================
# MÓDULO 6: ADMINISTRACIÓN FINANCIERA
# ==========================================================
def listacosto(request):
    """
    Muestra el listado completo de costos con estadísticas.
    Incluye totales por categoría, mes/año y conteos.
    """
    costo_list = Costo.objects.all().select_related(
        'fk_us_co'
    ).order_by('-fecha_co', '-created_at_co')
    
    # Estadísticas generales
    total_costos = costo_list.count()
    
    # Monto total general
    monto_total = costo_list.aggregate(total=Sum('monto_co'))['total'] or 0
    
    # Totales por categoría
    total_alimentacion = costo_list.filter(categoria_co='alimentacion').aggregate(total=Sum('monto_co'))['total'] or 0
    total_sanidad = costo_list.filter(categoria_co='sanidad').aggregate(total=Sum('monto_co'))['total'] or 0
    total_reproduccion = costo_list.filter(categoria_co='reproduccion').aggregate(total=Sum('monto_co'))['total'] or 0
    total_mano_obra = costo_list.filter(categoria_co='mano_obra').aggregate(total=Sum('monto_co'))['total'] or 0
    total_mantenimiento = costo_list.filter(categoria_co='mantenimiento_infraestructura').aggregate(total=Sum('monto_co'))['total'] or 0
    
    # Costos del mes actual
    hoy = date.today()
    costos_mes = costo_list.filter(
        mes_referencia_co=hoy.month,
        anio_referencia_co=hoy.year
    )
    monto_mes = costos_mes.aggregate(total=Sum('monto_co'))['total'] or 0
    
    contexto = {
        'costo_list': costo_list,
        'total_costos': total_costos,
        'monto_total': round(monto_total, 2),
        'total_alimentacion': round(total_alimentacion, 2),
        'total_sanidad': round(total_sanidad, 2),
        'total_reproduccion': round(total_reproduccion, 2),
        'total_mano_obra': round(total_mano_obra, 2),
        'total_mantenimiento': round(total_mantenimiento, 2),
        'monto_mes': round(monto_mes, 2),
    }
    
    return render(request, 'catalogos/finanzas/costo/lista_costo.html', contexto)


# ==========================================
# VISTA: NUEVO COSTO (formulario)
# ==========================================
def nuevocosto(request):
    """
    Muestra el formulario para registrar un nuevo costo.
    """
    return render(request, 'catalogos/finanzas/costo/nuevo_costo.html')


# ==========================================
# VISTA: GUARDAR COSTO (procesar creación)
# ==========================================
def guardarcosto(request):
    """
    Procesa el formulario de creación de un nuevo costo.
    Valida datos, verifica reglas de negocio y registra auditoría.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevocosto/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Categoría (obligatoria)
        categoria_co = request.POST.get('sel_categoria_co', '').strip()
        categorias_validas = [
            'alimentacion', 'sanidad', 'reproduccion', 'mano_obra',
            'mantenimiento_infraestructura', 'compra_animales', 'impuestos', 'otros'
        ]
        if not categoria_co:
            messages.error(request, "Debe seleccionar una categoría")
            return redirect('/nuevocosto/')
        if categoria_co not in categorias_validas:
            messages.error(request, "Categoría no válida")
            return redirect('/nuevocosto/')
        
        # Monto (obligatorio)
        monto_co = request.POST.get('txt_monto_co', '').strip()
        if not monto_co:
            messages.error(request, "El monto es obligatorio")
            return redirect('/nuevocosto/')
        
        try:
            monto_decimal = Decimal(monto_co)
            if monto_decimal <= 0:
                messages.error(request, "El monto debe ser mayor a 0")
                return redirect('/nuevocosto/')
            if monto_decimal > 99999999.99:
                messages.error(request, "El monto no puede exceder 99,999,999.99")
                return redirect('/nuevocosto/')
        except InvalidOperation:
            messages.error(request, "El monto ingresado no es válido")
            return redirect('/nuevocosto/')
        
        # Fecha (obligatoria)
        fecha_co = request.POST.get('txt_fecha_co')
        if not fecha_co:
            messages.error(request, "La fecha es obligatoria")
            return redirect('/nuevocosto/')
        
        # Descripción (opcional)
        descripcion_co = request.POST.get('txt_descripcion_co', '').strip()
        if descripcion_co and len(descripcion_co) > 2000:
            messages.error(request, "La descripción excede 2000 caracteres")
            return redirect('/nuevocosto/')
        
        # Comprobante (opcional)
        comprobante_co = request.POST.get('txt_comprobante_co', '').strip()
        if comprobante_co and len(comprobante_co) > 255:
            messages.error(request, "El comprobante excede 255 caracteres")
            return redirect('/nuevocosto/')
        
        # Mes referencia (obligatorio, 1-12)
        mes_referencia_co = request.POST.get('txt_mes_referencia_co', '').strip()
        if not mes_referencia_co:
            messages.error(request, "El mes de referencia es obligatorio")
            return redirect('/nuevocosto/')
        try:
            mes_int = int(mes_referencia_co)
            if mes_int < 1 or mes_int > 12:
                messages.error(request, "El mes debe estar entre 1 y 12")
                return redirect('/nuevocosto/')
        except ValueError:
            messages.error(request, "El mes debe ser un número entero")
            return redirect('/nuevocosto/')
        
        # Año referencia (obligatorio)
        anio_referencia_co = request.POST.get('txt_anio_referencia_co', '').strip()
        if not anio_referencia_co:
            messages.error(request, "El año de referencia es obligatorio")
            return redirect('/nuevocosto/')
        try:
            anio_int = int(anio_referencia_co)
            if anio_int < 2000:
                messages.error(request, "El año debe ser 2000 o posterior")
                return redirect('/nuevocosto/')
        except ValueError:
            messages.error(request, "El año debe ser un número entero")
            return redirect('/nuevocosto/')
        
        # Usuario actual (obligatorio)
        try:
            fk_us_co = Usuario.objects.get(id_us=request.session.get('id_us', 1))
        except Usuario.DoesNotExist:
            messages.error(request, "Error de autenticación de usuario")
            return redirect('/nuevocosto/')
        
        # ==========================================
        # CREAR COSTO
        # ==========================================
        nuevo_costo = Costo.objects.create(
            categoria_co=categoria_co,
            monto_co=monto_decimal,
            fecha_co=fecha_co,
            descripcion_co=descripcion_co if descripcion_co else None,
            comprobante_co=comprobante_co if comprobante_co else None,
            mes_referencia_co=mes_int,
            anio_referencia_co=anio_int,
            fk_us_co=fk_us_co
        )
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'Costo',
            nuevo_costo.id_co,
            f'Se creó costo: {categoria_co} - Monto: ${monto_decimal} - Mes: {mes_int}/{anio_int}'
        )
        
        messages.success(request, f"Costo de '{nuevo_costo.get_categoria_co_display()}' registrado exitosamente. Monto: ${monto_decimal}")
        return redirect('/listacosto/')
        
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect('/nuevocosto/')
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevocosto/')


# ==========================================
# VISTA: EDITAR COSTO (formulario)
# ==========================================
def editarcosto(request, id_co):
    """
    Muestra el formulario de edición con los datos precargados.
    """
    costo = get_object_or_404(
        Costo.objects.select_related('fk_us_co'),
        id_co=id_co
    )
    
    contexto = {
        'costo': costo,
    }
    
    return render(request, 'catalogos/finanzas/costo/editar_costo.html', contexto)


# ==========================================
# VISTA: PROCESAR EDICION COSTO
# ==========================================
def procesareditarcosto(request):
    """
    Procesa el formulario de edición de un costo existente.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listacosto/')
    
    try:
        # Obtener costo existente
        id_co = request.POST.get('id_co')
        if not id_co:
            messages.error(request, "ID de costo no proporcionado")
            return redirect('/listacosto/')
        
        costo = Costo.objects.get(id_co=id_co)
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Categoría (obligatoria)
        categoria_co = request.POST.get('sel_categoria_co', '').strip()
        categorias_validas = [
            'alimentacion', 'sanidad', 'reproduccion', 'mano_obra',
            'mantenimiento_infraestructura', 'compra_animales', 'impuestos', 'otros'
        ]
        if not categoria_co:
            messages.error(request, "Debe seleccionar una categoría")
            return redirect(f'/editarcosto/{id_co}')
        if categoria_co not in categorias_validas:
            messages.error(request, "Categoría no válida")
            return redirect(f'/editarcosto/{id_co}')
        
        # Monto (obligatorio)
        monto_co = request.POST.get('txt_monto_co', '').strip()
        if not monto_co:
            messages.error(request, "El monto es obligatorio")
            return redirect(f'/editarcosto/{id_co}')
        
        try:
            monto_decimal = Decimal(monto_co)
            if monto_decimal <= 0:
                messages.error(request, "El monto debe ser mayor a 0")
                return redirect(f'/editarcosto/{id_co}')
            if monto_decimal > 99999999.99:
                messages.error(request, "El monto no puede exceder 99,999,999.99")
                return redirect(f'/editarcosto/{id_co}')
        except InvalidOperation:
            messages.error(request, "El monto ingresado no es válido")
            return redirect(f'/editarcosto/{id_co}')
        
        # Fecha (obligatoria)
        fecha_co = request.POST.get('txt_fecha_co')
        if not fecha_co:
            messages.error(request, "La fecha es obligatoria")
            return redirect(f'/editarcosto/{id_co}')
        
        # Descripción (opcional)
        descripcion_co = request.POST.get('txt_descripcion_co', '').strip()
        if descripcion_co and len(descripcion_co) > 2000:
            messages.error(request, "La descripción excede 2000 caracteres")
            return redirect(f'/editarcosto/{id_co}')
        
        # Comprobante (opcional)
        comprobante_co = request.POST.get('txt_comprobante_co', '').strip()
        if comprobante_co and len(comprobante_co) > 255:
            messages.error(request, "El comprobante excede 255 caracteres")
            return redirect(f'/editarcosto/{id_co}')
        
        # Mes referencia (obligatorio, 1-12)
        mes_referencia_co = request.POST.get('txt_mes_referencia_co', '').strip()
        if not mes_referencia_co:
            messages.error(request, "El mes de referencia es obligatorio")
            return redirect(f'/editarcosto/{id_co}')
        try:
            mes_int = int(mes_referencia_co)
            if mes_int < 1 or mes_int > 12:
                messages.error(request, "El mes debe estar entre 1 y 12")
                return redirect(f'/editarcosto/{id_co}')
        except ValueError:
            messages.error(request, "El mes debe ser un número entero")
            return redirect(f'/editarcosto/{id_co}')
        
        # Año referencia (obligatorio)
        anio_referencia_co = request.POST.get('txt_anio_referencia_co', '').strip()
        if not anio_referencia_co:
            messages.error(request, "El año de referencia es obligatorio")
            return redirect(f'/editarcosto/{id_co}')
        try:
            anio_int = int(anio_referencia_co)
            if anio_int < 2000:
                messages.error(request, "El año debe ser 2000 o posterior")
                return redirect(f'/editarcosto/{id_co}')
        except ValueError:
            messages.error(request, "El año debe ser un número entero")
            return redirect(f'/editarcosto/{id_co}')
        
        # ==========================================
        # ACTUALIZAR COSTO
        # ==========================================
        costo.categoria_co = categoria_co
        costo.monto_co = monto_decimal
        costo.fecha_co = fecha_co
        costo.descripcion_co = descripcion_co if descripcion_co else None
        costo.comprobante_co = comprobante_co if comprobante_co else None
        costo.mes_referencia_co = mes_int
        costo.anio_referencia_co = anio_int
        
        costo.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'Costo',
            costo.id_co,
            f'Se editó costo #{id_co}: {categoria_co} - Monto: ${monto_decimal} - Mes: {mes_int}/{anio_int}'
        )
        
        messages.success(request, f"Costo actualizado exitosamente")
        return redirect('/listacosto/')
        
    except Costo.DoesNotExist:
        messages.error(request, "Costo no encontrado")
        return redirect('/listacosto/')
    except ValueError as e:
        messages.error(request, f"Error en los datos: {str(e)}")
        return redirect(f'/editarcosto/{id_co}')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editarcosto/{id_co}')


# ==========================================
# VISTA: ELIMINAR COSTO
# ==========================================
def eliminacosto(request, id_co):
    """
    Elimina un costo del sistema.
    """
    costo = get_object_or_404(
        Costo.objects.select_related('fk_us_co'),
        id_co=id_co
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_costo = costo.id_co
    categoria = costo.categoria_co
    monto = costo.monto_co
    
    try:
        # ==========================================
        # ELIMINAR COSTO
        # ==========================================
        costo.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'Costo',
            id_costo,
            f'Se eliminó costo #{id_costo}: {categoria} - ${monto}'
        )
        
        messages.success(request, f"Costo eliminado exitosamente")
        
    except Exception as e:
        messages.error(request, f"Error al eliminar: {str(e)}")
    
    return redirect('/listacosto/')

#Ingreso
def listaingreso(request):
    """
    Muestra el listado completo de ingresos con estadísticas.
    Incluye totales por categoría, mes actual, y gráficos de resumen.
    """
    ingresos_list = Ingreso.objects.all().select_related('fk_us_ig').order_by('-fecha_ig', '-created_at_ig')
    
    # Estadísticas generales
    total_ingresos = ingresos_list.count()
    monto_total_general = ingresos_list.aggregate(total=Sum('monto_total_ig'))['total'] or Decimal('0')
    
    # Totales por categoría
    total_venta_leche = ingresos_list.filter(categoria_ig='venta_leche').aggregate(total=Sum('monto_total_ig'))['total'] or Decimal('0')
    total_venta_animales = ingresos_list.filter(categoria_ig='venta_animales').aggregate(total=Sum('monto_total_ig'))['total'] or Decimal('0')
    total_venta_subproductos = ingresos_list.filter(categoria_ig='venta_subproductos').aggregate(total=Sum('monto_total_ig'))['total'] or Decimal('0')
    total_servicios = ingresos_list.filter(categoria_ig='servicios_inseminacion').aggregate(total=Sum('monto_total_ig'))['total'] or Decimal('0')
    total_otros = ingresos_list.filter(categoria_ig='otros').aggregate(total=Sum('monto_total_ig'))['total'] or Decimal('0')
    
    # Mes actual
    hoy = date.today()
    ingresos_mes_actual = ingresos_list.filter(
        fecha_ig__year=hoy.year,
        fecha_ig__month=hoy.month
    )
    monto_mes_actual = ingresos_mes_actual.aggregate(total=Sum('monto_total_ig'))['total'] or Decimal('0')
    cantidad_mes_actual = ingresos_mes_actual.count()
    
    contexto = {
        'ingresos_list': ingresos_list,
        'total_ingresos': total_ingresos,
        'monto_total_general': monto_total_general,
        'total_venta_leche': total_venta_leche,
        'total_venta_animales': total_venta_animales,
        'total_venta_subproductos': total_venta_subproductos,
        'total_servicios': total_servicios,
        'total_otros': total_otros,
        'monto_mes_actual': monto_mes_actual,
        'cantidad_mes_actual': cantidad_mes_actual,
    }
    
    return render(request, 'catalogos/finanzas/ingreso/lista_ingreso.html', contexto)

# ==========================================
# VISTA: NUEVO INGRESO (formulario)
# ==========================================
def nuevoingreso(request):
    """
    Muestra el formulario para registrar un nuevo ingreso.
    """
    return render(request, 'catalogos/finanzas/ingreso/nuevo_ingreso.html')

# ==========================================
# VISTA: GUARDAR INGRESO (procesar creación)
# ==========================================
def guardingreso(request):
    """
    Procesa el formulario de creación de un nuevo ingreso.
    Valida datos, calcula monto total si aplica, registra auditoría.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/nuevoingreso/')
    
    try:
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Categoría (obligatoria)
        categoria_ig = request.POST.get('sel_categoria_ig', '').strip()
        categorias_validas = ['venta_leche', 'venta_animales', 'venta_subproductos', 'servicios_inseminacion', 'otros']
        if not categoria_ig or categoria_ig not in categorias_validas:
            messages.error(request, "Debe seleccionar una categoría válida")
            return redirect('/nuevoingreso/')
        
        # Fecha (obligatoria)
        fecha_ig = request.POST.get('txt_fecha_ig', '').strip()
        if not fecha_ig:
            messages.error(request, "La fecha es obligatoria")
            return redirect('/nuevoingreso/')
        
        # Validar que no sea futura
        if fecha_ig > str(date.today()):
            messages.error(request, "La fecha no puede ser futura")
            return redirect('/nuevoingreso/')
        
        # Cantidad (opcional)
        cantidad_ig = None
        cantidad_str = request.POST.get('txt_cantidad_ig', '').strip()
        if cantidad_str:
            try:
                cantidad_ig = Decimal(cantidad_str)
                if cantidad_ig < 0:
                    messages.error(request, "La cantidad no puede ser negativa")
                    return redirect('/nuevoingreso/')
            except:
                messages.error(request, "La cantidad debe ser un número válido")
                return redirect('/nuevoingreso/')
        
        # Precio unitario (opcional)
        precio_unitario_ig = None
        precio_str = request.POST.get('txt_precio_unitario_ig', '').strip()
        if precio_str:
            try:
                precio_unitario_ig = Decimal(precio_str)
                if precio_unitario_ig < 0:
                    messages.error(request, "El precio unitario no puede ser negativo")
                    return redirect('/nuevoingreso/')
            except:
                messages.error(request, "El precio unitario debe ser un número válido")
                return redirect('/nuevoingreso/')
        
        # Monto total (obligatorio)
        monto_total_str = request.POST.get('txt_monto_total_ig', '').strip()
        if not monto_total_str:
            messages.error(request, "El monto total es obligatorio")
            return redirect('/nuevoingreso/')
        
        try:
            monto_total_ig = Decimal(monto_total_str)
            if monto_total_ig <= 0:
                messages.error(request, "El monto total debe ser mayor a 0")
                return redirect('/nuevoingreso/')
        except:
            messages.error(request, "El monto total debe ser un número válido")
            return redirect('/nuevoingreso/')
        
        # Validar consistencia cantidad × precio ≈ monto total
        if cantidad_ig and precio_unitario_ig:
            calculado = cantidad_ig * precio_unitario_ig
            if abs(calculado - monto_total_ig) > Decimal('0.05'):
                messages.error(request, f"El monto total no coincide con cantidad × precio unitario. Calculado: {calculado}")
                return redirect('/nuevoingreso/')
        
        # Si hay cantidad, debe haber precio (y viceversa)
        if (cantidad_ig and not precio_unitario_ig) or (not cantidad_ig and precio_unitario_ig):
            messages.error(request, "Si ingresa cantidad, debe ingresar precio unitario y viceversa")
            return redirect('/nuevoingreso/')
        
        # Cliente (opcional)
        cliente_ig = request.POST.get('txt_cliente_ig', '').strip() or None
        
        # Comprobante (opcional)
        comprobante_ig = request.POST.get('txt_comprobante_ig', '').strip() or None
        
        # Usuario actual (obligatorio)
        try:
            fk_us_ig = Usuario.objects.get(id_us=request.session.get('id_us', 1))
        except Usuario.DoesNotExist:
            messages.error(request, "Error de autenticación de usuario")
            return redirect('/nuevoingreso/')
        
        # ==========================================
        # CREAR INGRESO
        # ==========================================
        nuevo_ingreso = Ingreso.objects.create(
            categoria_ig=categoria_ig,
            cantidad_ig=cantidad_ig,
            precio_unitario_ig=precio_unitario_ig,
            monto_total_ig=monto_total_ig,
            cliente_ig=cliente_ig,
            fecha_ig=fecha_ig,
            comprobante_ig=comprobante_ig,
            fk_us_ig=fk_us_ig
        )
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'crear',
            'Ingreso',
            nuevo_ingreso.id_ig,
            f'Se creó ingreso: {nuevo_ingreso.get_categoria_ig_display()} - Monto: ${monto_total_ig} - Fecha: {fecha_ig}'
        )
        
        messages.success(request, f"Ingreso de '{nuevo_ingreso.get_categoria_ig_display()}' por ${monto_total_ig} registrado exitosamente")
        return redirect('/listaingreso/')
        
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        return redirect('/nuevoingreso/')

# ==========================================
# VISTA: EDITAR INGRESO (formulario)
# ==========================================
def editaringreso(request, id_ig):
    """
    Muestra el formulario de edición con los datos precargados.
    """
    ingreso = get_object_or_404(
        Ingreso.objects.select_related('fk_us_ig'),
        id_ig=id_ig
    )
    
    contexto = {
        'ingreso': ingreso,
    }
    
    return render(request, 'catalogos/finanzas/ingreso/editar_ingreso.html', contexto)

# ==========================================
# VISTA: PROCESAR EDICIÓN INGRESO
# ==========================================
def procesareditaringreso(request):
    """
    Procesa el formulario de edición de un ingreso existente.
    """
    if request.method != 'POST':
        messages.error(request, "Método no permitido")
        return redirect('/listaingreso/')
    
    try:
        # Obtener ingreso existente
        id_ig = request.POST.get('id_ig')
        if not id_ig:
            messages.error(request, "ID de ingreso no proporcionado")
            return redirect('/listaingreso/')
        
        ingreso = Ingreso.objects.get(id_ig=id_ig)
        
        # ==========================================
        # OBTENER Y VALIDAR DATOS DEL FORMULARIO
        # ==========================================
        
        # Categoría (obligatoria)
        categoria_ig = request.POST.get('sel_categoria_ig', '').strip()
        categorias_validas = ['venta_leche', 'venta_animales', 'venta_subproductos', 'servicios_inseminacion', 'otros']
        if not categoria_ig or categoria_ig not in categorias_validas:
            messages.error(request, "Debe seleccionar una categoría válida")
            return redirect(f'/editaringreso/{id_ig}')
        
        # Fecha (obligatoria)
        fecha_ig = request.POST.get('txt_fecha_ig', '').strip()
        if not fecha_ig:
            messages.error(request, "La fecha es obligatoria")
            return redirect(f'/editaringreso/{id_ig}')
        
        if fecha_ig > str(date.today()):
            messages.error(request, "La fecha no puede ser futura")
            return redirect(f'/editaringreso/{id_ig}')
        
        # Cantidad (opcional)
        cantidad_ig = None
        cantidad_str = request.POST.get('txt_cantidad_ig', '').strip()
        if cantidad_str:
            try:
                cantidad_ig = Decimal(cantidad_str)
                if cantidad_ig < 0:
                    messages.error(request, "La cantidad no puede ser negativa")
                    return redirect(f'/editaringreso/{id_ig}')
            except:
                messages.error(request, "La cantidad debe ser un número válido")
                return redirect(f'/editaringreso/{id_ig}')
        
        # Precio unitario (opcional)
        precio_unitario_ig = None
        precio_str = request.POST.get('txt_precio_unitario_ig', '').strip()
        if precio_str:
            try:
                precio_unitario_ig = Decimal(precio_str)
                if precio_unitario_ig < 0:
                    messages.error(request, "El precio unitario no puede ser negativo")
                    return redirect(f'/editaringreso/{id_ig}')
            except:
                messages.error(request, "El precio unitario debe ser un número válido")
                return redirect(f'/editaringreso/{id_ig}')
        
        # Monto total (obligatorio)
        monto_total_str = request.POST.get('txt_monto_total_ig', '').strip()
        if not monto_total_str:
            messages.error(request, "El monto total es obligatorio")
            return redirect(f'/editaringreso/{id_ig}')
        
        try:
            monto_total_ig = Decimal(monto_total_str)
            if monto_total_ig <= 0:
                messages.error(request, "El monto total debe ser mayor a 0")
                return redirect(f'/editaringreso/{id_ig}')
        except:
            messages.error(request, "El monto total debe ser un número válido")
            return redirect(f'/editaringreso/{id_ig}')
        
        # Validar consistencia
        if cantidad_ig and precio_unitario_ig:
            calculado = cantidad_ig * precio_unitario_ig
            if abs(calculado - monto_total_ig) > Decimal('0.05'):
                messages.error(request, f"El monto total no coincide con cantidad × precio. Calculado: {calculado}")
                return redirect(f'/editaringreso/{id_ig}')
        
        if (cantidad_ig and not precio_unitario_ig) or (not cantidad_ig and precio_unitario_ig):
            messages.error(request, "Si ingresa cantidad, debe ingresar precio unitario y viceversa")
            return redirect(f'/editaringreso/{id_ig}')
        
        # Cliente y comprobante
        cliente_ig = request.POST.get('txt_cliente_ig', '').strip() or None
        comprobante_ig = request.POST.get('txt_comprobante_ig', '').strip() or None
        
        # ==========================================
        # ACTUALIZAR INGRESO
        # ==========================================
        ingreso.categoria_ig = categoria_ig
        ingreso.cantidad_ig = cantidad_ig
        ingreso.precio_unitario_ig = precio_unitario_ig
        ingreso.monto_total_ig = monto_total_ig
        ingreso.cliente_ig = cliente_ig
        ingreso.fecha_ig = fecha_ig
        ingreso.comprobante_ig = comprobante_ig
        
        ingreso.save()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'editar',
            'Ingreso',
            ingreso.id_ig,
            f'Se editó ingreso #{id_ig}: {ingreso.get_categoria_ig_display()} - Monto: ${monto_total_ig}'
        )
        
        messages.success(request, f"Ingreso actualizado exitosamente")
        return redirect('/listaingreso/')
        
    except Ingreso.DoesNotExist:
        messages.error(request, "Ingreso no encontrado")
        return redirect('/listaingreso/')
    except Exception as e:
        messages.error(request, f"Error al actualizar: {str(e)}")
        return redirect(f'/editaringreso/{id_ig}')

# ==========================================
# VISTA: ELIMINAR INGRESO
# ==========================================
def eliminaingreso(request, id_ig):
    """
    Elimina un ingreso del sistema.
    """
    ingreso = get_object_or_404(
        Ingreso.objects.select_related('fk_us_ig'),
        id_ig=id_ig
    )
    
    # Guardar datos antes de eliminar para auditoría
    id_ingreso = ingreso.id_ig
    categoria = ingreso.get_categoria_ig_display()
    monto = ingreso.monto_total_ig
    
    try:
        ingreso.delete()
        
        # ==========================================
        # AUDITORÍA
        # ==========================================
        guardar_auditoria(
            request,
            'eliminar',
            'Ingreso',
            id_ingreso,
            f'Se eliminó ingreso #{id_ingreso}: {categoria} - ${monto}'
        )
        
        messages.success(request, f"Ingreso de {categoria} por ${monto} eliminado exitosamente")
        
    except Exception as e:
        messages.error(request, f"Error al eliminar: {str(e)}")
    
    return redirect('/listaingreso/')

# ==========================================================
# MÓDULO 7: MACHINE LEARNING
# ==========================================================
# MODELOS ML

# ============================================================
# VISTA: NUEVO MODELO ML (formulario)
# ============================================================

# ============================================================
# VISTA: GUARDAR NUEVO MODELO ML
# ============================================================

# ============================================================
# VISTA: EDITAR MODELO ML (formulario)
# ============================================================

# ============================================================
# VISTA: PROCESAR EDICIÓN MODELO ML
# ============================================================

# ============================================================
# VISTA: ACTIVAR / DESACTIVAR MODELO ML (toggle)
# ============================================================

# ============================================================
# VISTA: ELIMINAR MODELO ML
# ============================================================

# ==========================================
# VISTA: DASHBOARD PRINCIPAL ML
# ==========================================
# ==========================================
# VISTA: DASHBOARD PRINCIPAL ML (CON MESES EN ESPAÑOL)
# ==========================================
def dashboardml(request):
    """
    Dashboard de Machine Learning con predicciones automaticas agrupadas por año/mes.
    Muestra historial completo de predicciones para cada animal.
    Incluye modal de detalle del animal al hacer clic.
    """
    from .ml_engine import modelo_esta_entrenado, predecir
    from collections import defaultdict

    estado_ad1 = modelo_esta_entrenado('AD-1')
    estado_ad2 = modelo_esta_entrenado('AD-2')
    estado_rl4 = modelo_esta_entrenado('RL-4')

    metrica_ad1 = metrica_ad2 = metrica_rl4 = None
    try:
        m = ModeloML.objects.filter(codigo_mm='AD-1').first()
        if m: metrica_ad1 = round(float(m.valor_metrica_mm), 4) if m.valor_metrica_mm else None
    except: pass
    try:
        m = ModeloML.objects.filter(codigo_mm='AD-2').first()
        if m: metrica_ad2 = round(float(m.valor_metrica_mm), 4) if m.valor_metrica_mm else None
    except: pass
    try:
        m = ModeloML.objects.filter(codigo_mm='RL-4').first()
        if m: metrica_rl4 = round(float(m.valor_metrica_mm), 4) if m.valor_metrica_mm else None
    except: pass

    # ──────────────────────────────────────────────────────
    # AD-1: TODOS los ordeños, agrupados por AÑO → MES
    # ──────────────────────────────────────────────────────
    predicciones_ad1_agrupadas = {}  # {año: {mes: [predicciones]}}
    if estado_ad1:
        ordenos = Ordeno.objects.filter(
            temperatura_ambiental_or__isnull=False,
            cantidad_concentrado_kg_or__isnull=False,
            temperatura_leche_or__isnull=False
        ).select_related('fk_an', 'fk_an__fk_ra', 'fk_an__fk_potrero_an').order_by('-fecha_or')

        modelo_db_ad1 = ModeloML.objects.filter(codigo_mm='AD-1').first()

        for o in ordenos:
            r = predecir('AD-1', {
                'temperatura_ambiental': float(o.temperatura_ambiental_or),
                'cantidad_concentrado_kg': float(o.cantidad_concentrado_kg_or),
                'temperatura_leche': float(o.temperatura_leche_or)
            })
            if r['exito']:
                anio = o.fecha_or.year
                mes_num = o.fecha_or.month
                # 🔥 NOMBRE DEL MES EN ESPAÑOL
                mes_nombre = nombre_mes_espanol(mes_num)
                mes_anio = f"{mes_nombre} {anio}"

                if anio not in predicciones_ad1_agrupadas:
                    predicciones_ad1_agrupadas[anio] = {}
                if mes_anio not in predicciones_ad1_agrupadas[anio]:
                    predicciones_ad1_agrupadas[anio][mes_anio] = {
                        'mes_num': mes_num,
                        'registros': []
                    }

                animal = o.fk_an
                predicciones_ad1_agrupadas[anio][mes_anio]['registros'].append({
                    'animal_id': animal.id_an if animal else None,
                    'animal_codigo': animal.codigo_an if animal else 'Sin nombre',
                    'animal_nombre': animal.nombre_an or 'Sin nombre' if animal else 'Sin nombre',
                    'animal_raza': animal.fk_ra.nombre_ra if animal and animal.fk_ra else 'N/A',
                    'animal_categoria': animal.categoria_an if animal else 'N/A',
                    'animal_estado': animal.estado_an if animal else 'N/A',
                    'animal_peso': str(animal.peso_actual_kg_an) + ' kg' if animal and animal.peso_actual_kg_an else 'No registrado',
                    'animal_potrero': animal.fk_potrero_an.nombre_po if animal and animal.fk_potrero_an else 'Sin potrero',
                    'animal_foto': animal.foto_an or '' if animal else '',
                    'fecha': o.fecha_or.strftime('%d/%m/%Y'),
                    'temperatura_ambiental': o.temperatura_ambiental_or,
                    'cantidad_concentrado_kg': o.cantidad_concentrado_kg_or,
                    'temperatura_leche': o.temperatura_leche_or,
                    'prediccion': r['prediccion'],
                    'confianza': f"R²: {round(metrica_ad1 * 100, 1)}%" if metrica_ad1 else 'N/A',
                })

                # Guardar prediccion en BD
                if modelo_db_ad1:
                    try:
                        PrediccionML.objects.get_or_create(
                            fk_mm=modelo_db_ad1,
                            fk_an=animal,
                            datos_entrada_pm={
                                'temperatura_ambiental': float(o.temperatura_ambiental_or),
                                'cantidad_concentrado_kg': float(o.cantidad_concentrado_kg_or),
                                'temperatura_leche': float(o.temperatura_leche_or),
                                'fecha_ordeno': str(o.fecha_or)
                            },
                            defaults={
                                'resultado_prediccion_pm': str(r['prediccion']),
                                'probabilidad_pm': None
                            }
                        )
                    except Exception:
                        pass

        # Ordenar años de más reciente a más antiguo
        predicciones_ad1_agrupadas = dict(
            sorted(predicciones_ad1_agrupadas.items(), reverse=True)
        )
        # Ordenar meses dentro de cada año (por número de mes, descendente)
        for anio in predicciones_ad1_agrupadas:
            predicciones_ad1_agrupadas[anio] = dict(
                sorted(
                    predicciones_ad1_agrupadas[anio].items(),
                    key=lambda x: x[1]['mes_num'],
                    reverse=True
                )
            )

    # ──────────────────────────────────────────────────────
    # AD-2: TODAS las inseminaciones pendientes, agrupadas por AÑO → MES
    # ──────────────────────────────────────────────────────
    predicciones_ad2_agrupadas = {}
    if estado_ad2:
        inseminaciones = Inseminacion.objects.filter(
            resultado_in='pendiente',
            condicion_corporal_in__isnull=False,
            fecha_in__isnull=False
        ).select_related('fk_an', 'fk_an__fk_ra', 'fk_an__fk_potrero_an').order_by('-fecha_in')

        modelo_db_ad2 = ModeloML.objects.filter(codigo_mm='AD-2').first()

        for ins in inseminaciones:
            dias = (date.today() - ins.fecha_in).days
            r = predecir('AD-2', {
                'dias_desde_inseminacion': dias,
                'condicion_corporal': ins.condicion_corporal_in,
                'dia_ciclo': ins.dia_ciclo_in or 14
            })
            if r['exito']:
                anio = ins.fecha_in.year
                mes_num = ins.fecha_in.month
                # 🔥 NOMBRE DEL MES EN ESPAÑOL
                mes_nombre = nombre_mes_espanol(mes_num)
                mes_anio = f"{mes_nombre} {anio}"

                if anio not in predicciones_ad2_agrupadas:
                    predicciones_ad2_agrupadas[anio] = {}
                if mes_anio not in predicciones_ad2_agrupadas[anio]:
                    predicciones_ad2_agrupadas[anio][mes_anio] = {
                        'mes_num': mes_num,
                        'registros': []
                    }

                animal = ins.fk_an
                predicciones_ad2_agrupadas[anio][mes_anio]['registros'].append({
                    'animal_id': animal.id_an if animal else None,
                    'animal_codigo': animal.codigo_an if animal else 'Sin nombre',
                    'animal_nombre': animal.nombre_an or 'Sin nombre' if animal else 'Sin nombre',
                    'animal_raza': animal.fk_ra.nombre_ra if animal and animal.fk_ra else 'N/A',
                    'animal_categoria': animal.categoria_an if animal else 'N/A',
                    'animal_estado': animal.estado_an if animal else 'N/A',
                    'animal_peso': str(animal.peso_actual_kg_an) + ' kg' if animal and animal.peso_actual_kg_an else 'No registrado',
                    'animal_potrero': animal.fk_potrero_an.nombre_po if animal and animal.fk_potrero_an else 'Sin potrero',
                    'animal_foto': animal.foto_an or '' if animal else '',
                    'fecha': ins.fecha_in.strftime('%d/%m/%Y'),
                    'dias': dias,
                    'condicion_corporal': ins.condicion_corporal_in,
                    'tipo_inseminacion': ins.tipo_inseminacion_in,
                    'prediccion': r['prediccion'],
                    'confianza': f"{r.get('probabilidad', 0)*100:.1f}%",
                })

                if modelo_db_ad2:
                    try:
                        PrediccionML.objects.get_or_create(
                            fk_mm=modelo_db_ad2,
                            fk_an=animal,
                            datos_entrada_pm={
                                'dias_desde_inseminacion': dias,
                                'condicion_corporal': float(ins.condicion_corporal_in),
                                'dia_ciclo': ins.dia_ciclo_in or 14,
                                'fecha_inseminacion': str(ins.fecha_in)
                            },
                            defaults={
                                'resultado_prediccion_pm': r['prediccion'],
                                'probabilidad_pm': r.get('probabilidad')
                            }
                        )
                    except Exception:
                        pass

        predicciones_ad2_agrupadas = dict(
            sorted(predicciones_ad2_agrupadas.items(), reverse=True)
        )
        for anio in predicciones_ad2_agrupadas:
            predicciones_ad2_agrupadas[anio] = dict(
                sorted(
                    predicciones_ad2_agrupadas[anio].items(),
                    key=lambda x: x[1]['mes_num'],
                    reverse=True
                )
            )

    # ──────────────────────────────────────────────────────
    # RL-4: TODAS las calidades de leche, agrupadas por AÑO → MES
    # ──────────────────────────────────────────────────────
    predicciones_rl4_agrupadas = {}
    if estado_rl4:
        calidades = CalidadLeche.objects.filter(
            grasa_pct_cl__isnull=False,
            proteina_pct_cl__isnull=False,
            ccs_cl__isnull=False
        ).select_related('fk_an', 'fk_an__fk_ra', 'fk_an__fk_potrero_an').order_by('-fecha_muestreo_cl')

        modelo_db_rl4 = ModeloML.objects.filter(codigo_mm='RL-4').first()

        for c in calidades:
            r = predecir('RL-4', {
                'grasa_pct': float(c.grasa_pct_cl),
                'proteina_pct': float(c.proteina_pct_cl),
                'ccs': float(c.ccs_cl)
            })
            if r['exito']:
                anio = c.fecha_muestreo_cl.year
                mes_num = c.fecha_muestreo_cl.month
                # 🔥 NOMBRE DEL MES EN ESPAÑOL
                mes_nombre = nombre_mes_espanol(mes_num)
                mes_anio = f"{mes_nombre} {anio}"

                if anio not in predicciones_rl4_agrupadas:
                    predicciones_rl4_agrupadas[anio] = {}
                if mes_anio not in predicciones_rl4_agrupadas[anio]:
                    predicciones_rl4_agrupadas[anio][mes_anio] = {
                        'mes_num': mes_num,
                        'registros': []
                    }

                animal = c.fk_an
                predicciones_rl4_agrupadas[anio][mes_anio]['registros'].append({
                    'animal_id': animal.id_an if animal else None,
                    'animal_codigo': animal.codigo_an if animal else 'Sin nombre',
                    'animal_nombre': animal.nombre_an or 'Sin nombre' if animal else 'Sin nombre',
                    'animal_raza': animal.fk_ra.nombre_ra if animal and animal.fk_ra else 'N/A',
                    'animal_categoria': animal.categoria_an if animal else 'N/A',
                    'animal_estado': animal.estado_an if animal else 'N/A',
                    'animal_peso': str(animal.peso_actual_kg_an) + ' kg' if animal and animal.peso_actual_kg_an else 'No registrado',
                    'animal_potrero': animal.fk_potrero_an.nombre_po if animal and animal.fk_potrero_an else 'Sin potrero',
                    'animal_foto': animal.foto_an or '' if animal else '',
                    'fecha': c.fecha_muestreo_cl.strftime('%d/%m/%Y'),
                    'grasa': c.grasa_pct_cl,
                    'proteina': c.proteina_pct_cl,
                    'ccs': c.ccs_cl,
                    'prediccion': r['prediccion'],
                    'confianza': f"{r.get('probabilidad', 0)*100:.1f}%",
                })

                if modelo_db_rl4:
                    try:
                        PrediccionML.objects.get_or_create(
                            fk_mm=modelo_db_rl4,
                            fk_an=animal,
                            datos_entrada_pm={
                                'grasa_pct': float(c.grasa_pct_cl),
                                'proteina_pct': float(c.proteina_pct_cl),
                                'ccs': float(c.ccs_cl),
                                'fecha_muestreo': str(c.fecha_muestreo_cl)
                            },
                            defaults={
                                'resultado_prediccion_pm': r['prediccion'],
                                'probabilidad_pm': r.get('probabilidad')
                            }
                        )
                    except Exception:
                        pass

        predicciones_rl4_agrupadas = dict(
            sorted(predicciones_rl4_agrupadas.items(), reverse=True)
        )
        for anio in predicciones_rl4_agrupadas:
            predicciones_rl4_agrupadas[anio] = dict(
                sorted(
                    predicciones_rl4_agrupadas[anio].items(),
                    key=lambda x: x[1]['mes_num'],
                    reverse=True
                )
            )

    return render(request, 'ML/prediccionML/dashboard/dashboard_ml.html', {
        'estado_ad1': estado_ad1, 'estado_ad2': estado_ad2, 'estado_rl4': estado_rl4,
        'metrica_ad1': metrica_ad1, 'metrica_ad2': metrica_ad2, 'metrica_rl4': metrica_rl4,
        'predicciones_ad1_agrupadas': predicciones_ad1_agrupadas,
        'predicciones_ad2_agrupadas': predicciones_ad2_agrupadas,
        'predicciones_rl4_agrupadas': predicciones_rl4_agrupadas,
    })

# ==========================================
# VISTA: DASHBOARD POR MODELO ESPECÍFICO
# ==========================================

# ==========================================
# VISTA: LISTADO DE PREDICCIONES (con filtros)
# ==========================================

# ==========================================
# VISTA: DETALLE PREDICCIÓN (JSON)
# ==========================================

# ==========================================
# VISTA: FEEDBACK PREDICCIÓN (AJAX)
# ==========================================
# ==========================================
# VISTAS DE MACHINE LEARNING - PREDICCION REAL
# ==========================================

def prediccion_ad1(request):
    """
    Vista para probar el modelo AD-1: Prediccion de Litros de Leche.
    Muestra un formulario. Si recibe POST, llama al modelo .pkl y muestra resultado.
    """
    from .ml_engine import predecir, modelo_esta_entrenado
    resultado = None
    error = None
    datos = {}

    if request.method == 'POST':
        datos = {
            'temperatura_ambiental': request.POST.get('temperatura_ambiental', '25'),
            'cantidad_concentrado_kg': request.POST.get('cantidad_concentrado_kg', '5'),
            'temperatura_leche': request.POST.get('temperatura_leche', '36'),
        }
        if not modelo_esta_entrenado('AD-1'):
            error = 'El modelo AD-1 NO esta entrenado. Ejecute en consola: python manage.py entrenar_ml AD-1 --ejemplo'
        else:
            resultado = predecir('AD-1', datos)
            if not resultado['exito']:
                error = resultado['mensaje']
            else:
                from .models import ModeloML, PrediccionML
                try:
                    modelo_db = ModeloML.objects.get(codigo_mm='AD-1')
                    PrediccionML.objects.create(
                        fk_mm=modelo_db,
                        datos_entrada_pm=datos,
                        resultado_prediccion_pm=str(resultado['prediccion']),
                        probabilidad_pm=resultado.get('probabilidad')
                    )
                except Exception:
                    pass

    contexto = {
        'titulo': 'Prediccion AD-1: Litros de Leche',
        'descripcion': 'Ingrese las condiciones del ordeño para predecir la produccion de leche en litros.',
        'campos': [
            {'nombre': 'temperatura_ambiental', 'label': 'Temperatura Ambiental (°C)', 'tipo': 'number', 'paso': '0.1', 'valor': datos.get('temperatura_ambiental', '25')},
            {'nombre': 'cantidad_concentrado_kg', 'label': 'Concentrado (kg)', 'tipo': 'number', 'paso': '0.1', 'valor': datos.get('cantidad_concentrado_kg', '5')},
            {'nombre': 'temperatura_leche', 'label': 'Temperatura de Leche (°C)', 'tipo': 'number', 'paso': '0.1', 'valor': datos.get('temperatura_leche', '36')},
        ],
        'resultado': resultado,
        'error': error,
        'codigo': 'AD-1'
    }
    return render(request, 'ML/prediccionML/nueva_prediccion.html', contexto)


def prediccion_ad2(request):
    """
    Vista para probar el modelo AD-2: Clasificacion Preñada/No Preñada.
    """
    from .ml_engine import predecir, modelo_esta_entrenado
    resultado = None
    error = None
    datos = {}

    if request.method == 'POST':
        datos = {
            'dias_desde_inseminacion': request.POST.get('dias_desde_inseminacion', '60'),
            'condicion_corporal': request.POST.get('condicion_corporal', '3'),
            'dia_ciclo': request.POST.get('dia_ciclo', '14'),
        }
        if not modelo_esta_entrenado('AD-2'):
            error = 'El modelo AD-2 NO esta entrenado. Ejecute: python manage.py entrenar_ml AD-2 --ejemplo'
        else:
            resultado = predecir('AD-2', datos)
            if not resultado['exito']:
                error = resultado['mensaje']
            else:
                from .models import ModeloML, PrediccionML
                try:
                    modelo_db = ModeloML.objects.get(codigo_mm='AD-2')
                    PrediccionML.objects.create(
                        fk_mm=modelo_db,
                        datos_entrada_pm=datos,
                        resultado_prediccion_pm=resultado['prediccion'],
                        probabilidad_pm=resultado.get('probabilidad')
                    )
                except Exception:
                    pass

    contexto = {
        'titulo': 'Prediccion AD-2: Estado de Preñez',
        'descripcion': 'Ingrese los datos de la inseminacion para predecir si la vaca esta preñada.',
        'campos': [
            {'nombre': 'dias_desde_inseminacion', 'label': 'Dias desde Inseminacion', 'tipo': 'number', 'paso': '1', 'valor': datos.get('dias_desde_inseminacion', '60')},
            {'nombre': 'condicion_corporal', 'label': 'Condicion Corporal (1-5)', 'tipo': 'number', 'paso': '1', 'valor': datos.get('condicion_corporal', '3')},
            {'nombre': 'dia_ciclo', 'label': 'Dia del Ciclo (1-21)', 'tipo': 'number', 'paso': '1', 'valor': datos.get('dia_ciclo', '14')},
        ],
        'resultado': resultado,
        'error': error,
        'codigo': 'AD-2'
    }
    return render(request, 'ML/prediccionML/nueva_prediccion.html', contexto)


def prediccion_rl4(request):
    """
    Vista para probar el modelo RL-4: Calidad de Leche (Apto/No Apto).
    """
    from .ml_engine import predecir, modelo_esta_entrenado
    resultado = None
    error = None
    datos = {}

    if request.method == 'POST':
        datos = {
            'grasa_pct': request.POST.get('grasa_pct', '3.5'),
            'proteina_pct': request.POST.get('proteina_pct', '3.2'),
            'ccs': request.POST.get('ccs', '200000'),
        }
        if not modelo_esta_entrenado('RL-4'):
            error = 'El modelo RL-4 NO esta entrenado. Ejecute: python manage.py entrenar_ml RL-4'
        else:
            resultado = predecir('RL-4', datos)
            if not resultado['exito']:
                error = resultado['mensaje']
            else:
                from .models import ModeloML, PrediccionML
                try:
                    modelo_db = ModeloML.objects.get(codigo_mm='RL-4')
                    PrediccionML.objects.create(
                        fk_mm=modelo_db,
                        datos_entrada_pm=datos,
                        resultado_prediccion_pm=resultado['prediccion'],
                        probabilidad_pm=resultado.get('probabilidad')
                    )
                except Exception:
                    pass

    contexto = {
        'titulo': 'Prediccion RL-4: Calidad de Leche',
        'descripcion': 'Ingrese los parametros de calidad para determinar si la leche es apta.',
        'campos': [
            {'nombre': 'grasa_pct', 'label': 'Grasa (%)', 'tipo': 'number', 'paso': '0.1', 'valor': datos.get('grasa_pct', '3.5')},
            {'nombre': 'proteina_pct', 'label': 'Proteina (%)', 'tipo': 'number', 'paso': '0.1', 'valor': datos.get('proteina_pct', '3.2')},
            {'nombre': 'ccs', 'label': 'CCS (Celulas Somáticas)', 'tipo': 'number', 'paso': '1', 'valor': datos.get('ccs', '200000')},
        ],
        'resultado': resultado,
        'error': error,
        'codigo': 'RL-4'
    }
    return render(request, 'ML/prediccionML/nueva_prediccion.html', contexto)

# ==========================================
# VISTA: DASHBOARD GRÁFICO (ESTADÍSTICAS)
# ==========================================

def dashboard_grafico(request):
    """
    Dashboard gráfico con estadísticas generales de la hacienda
    y recomendaciones basadas en Machine Learning.
    """
    from .ml_engine import modelo_esta_entrenado
    from django.db.models.functions import ExtractMonth, ExtractYear

    # === PRODUCCIÓN DE LECHE ===
    produccion_mes = Ordeno.objects.annotate(
        mes=ExtractMonth('fecha_or'),
        anio=ExtractYear('fecha_or')
    ).values('mes', 'anio').annotate(
        total_litros=Sum('litros_or'),
        cantidad=Count('id_or')
    ).order_by('anio', 'mes')[:12]

    produccion_animal = Ordeno.objects.values('fk_an__codigo_an').annotate(
        total_litros=Sum('litros_or'),
        promedio=Avg('litros_or')
    ).order_by('-total_litros')[:5]

    litros_turno = Ordeno.objects.values('turno_or').annotate(
        total=Sum('litros_or')
    )

    # === CALIDAD DE LECHE ===
    calidad_mes = CalidadLeche.objects.annotate(
        mes=ExtractMonth('fecha_muestreo_cl'),
        anio=ExtractYear('fecha_muestreo_cl')
    ).values('mes', 'anio').annotate(
        aptos=Count('id_cl', filter=Q(resultado_cl='apto')),
        no_aptos=Count('id_cl', filter=Q(resultado_cl='no_apto'))
    ).order_by('anio', 'mes')[:12]

    # === ANIMALES ===
    total_animales = Animal.objects.count()
    animales_categoria = Animal.objects.values('categoria_an').annotate(
        cantidad=Count('id_an')
    )
    animales_estado = Animal.objects.values('estado_an').annotate(
        cantidad=Count('id_an')
    )

    # === FINANZAS ===
    total_costos = Costo.objects.aggregate(total=Sum('monto_co'))['total'] or 0
    total_ingresos = Ingreso.objects.aggregate(total=Sum('monto_total_ig'))['total'] or 0
    balance = float(total_ingresos) - float(total_costos)

    costos_categoria = Costo.objects.values('categoria_co').annotate(
        total=Sum('monto_co')
    ).order_by('-total')[:5]

    # === MACHINE LEARNING ===
    ml_estado = {
        'ad1': modelo_esta_entrenado('AD-1'),
        'ad2': modelo_esta_entrenado('AD-2'),
        'rl4': modelo_esta_entrenado('RL-4'),
    }

    # === RECOMENDACIONES ===
    recomendaciones = []

    if produccion_mes:
        ultimos_3 = list(produccion_mes)[-3:]
        if len(ultimos_3) >= 2:
            tendencia = ultimos_3[-1]['total_litros'] - ultimos_3[0]['total_litros']
            if tendencia > 0:
                recomendaciones.append({
                    'tipo': 'success',
                    'icono': 'bi-graph-up-arrow',
                    'titulo': 'Tendencia Positiva en Producción',
                    'texto': 'La producción ha aumentado en los últimos meses. Se recomienda mantener el manejo actual de alimentación.'
                })
            else:
                recomendaciones.append({
                    'tipo': 'warning',
                    'icono': 'bi-graph-down-arrow',
                    'titulo': 'Tendencia Negativa en Producción',
                    'texto': 'La producción ha disminuido. Se recomienda revisar la alimentación y estado de salud del ganado.'
                })

    calidad_total = CalidadLeche.objects.count()
    if calidad_total > 0:
        aptos_pct = CalidadLeche.objects.filter(resultado_cl='apto').count() / calidad_total * 100
        if aptos_pct < 70:
            recomendaciones.append({
                'tipo': 'danger',
                'icono': 'bi-exclamation-triangle',
                'titulo': 'Alerta de Calidad de Leche',
                'texto': f'Solo el {aptos_pct:.1f}% de las muestras son aptas. Revisar higiene y manejo del ordeño.'
            })
        else:
            recomendaciones.append({
                'tipo': 'success',
                'icono': 'bi-check-circle',
                'titulo': 'Calidad de Leche Aceptable',
                'texto': f'El {aptos_pct:.1f}% de las muestras son aptas. Mantener buenas prácticas de ordeño.'
            })

    if balance < 0:
        recomendaciones.append({
            'tipo': 'danger',
            'icono': 'bi-cash-stack',
            'titulo': 'Balance Negativo',
            'texto': f'Los costos superan los ingresos en ${abs(balance):.2f}. Se recomienda revisar gastos operativos.'
        })
    else:
        recomendaciones.append({
            'tipo': 'success',
            'icono': 'bi-cash-stack',
            'titulo': 'Balance Positivo',
            'texto': f'La hacienda tiene una utilidad de ${balance:.2f}. El manejo financiero es adecuado.'
        })

    if ml_estado['ad1'] and ml_estado['rl4']:
        recomendaciones.append({
            'tipo': 'info',
            'icono': 'bi-cpu',
            'titulo': 'Machine Learning Activo',
            'texto': 'Los modelos de predicción están entrenados y listos para apoyar la toma de decisiones.'
        })

    # === PREPARAR DATOS PARA GRÁFICAS ===
    meses_labels = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

    prod_labels = []
    prod_values = []
    for p in produccion_mes:
        label = f"{meses_labels[p['mes']-1]} {p['anio']}"
        prod_labels.append(label)
        prod_values.append(float(p['total_litros'] or 0))

    cal_labels = []
    cal_aptos = []
    cal_no_aptos = []
    for c in calidad_mes:
        label = f"{meses_labels[c['mes']-1]} {c['anio']}"
        cal_labels.append(label)
        cal_aptos.append(c['aptos'])
        cal_no_aptos.append(c['no_aptos'])

    cat_labels = [a['categoria_an'] for a in animales_categoria]
    cat_values = [a['cantidad'] for a in animales_categoria]

    cost_labels = [c['categoria_co'] for c in costos_categoria]
    cost_values = [float(c['total'] or 0) for c in costos_categoria]

    turno_labels = [t['turno_or'] for t in litros_turno]
    turno_values = [float(t['total'] or 0) for t in litros_turno]

    contexto = {
        'prod_labels': prod_labels,
        'prod_values': prod_values,
        'produccion_animal': produccion_animal,
        'turno_labels': turno_labels,
        'turno_values': turno_values,
        'cal_labels': cal_labels,
        'cal_aptos': cal_aptos,
        'cal_no_aptos': cal_no_aptos,
        'total_animales': total_animales,
        'cat_labels': cat_labels,
        'cat_values': cat_values,
        'animales_estado': animales_estado,
        'total_costos': float(total_costos),
        'total_ingresos': float(total_ingresos),
        'balance': balance,
        'cost_labels': cost_labels,
        'cost_values': cost_values,
        'ml_estado': ml_estado,
        'recomendaciones': recomendaciones,
    }

    return render(request, 'dashboard_grafico.html', contexto)


# ==========================================
# PARA ACTUALIZAR ARCHIVOS ML DESDE RENDER
# ==========================================
from .ml_engine import entrenar_modelo

def entrenar_modelos_render(request):
    # Solo funciona si pasas la clave correcta
    clave = request.GET.get('clave', '')
    if clave != 'mi_clave_secreta_123':
        return JsonResponse({'error': 'No autorizado'}, status=403)

    resultados = {}
    resultados['AD-1'] = entrenar_modelo('AD-1', usar_datos_ejemplo=True)
    resultados['AD-2'] = entrenar_modelo('AD-2', usar_datos_ejemplo=True)
    resultados['RL-4'] = entrenar_modelo('RL-4', usar_datos_ejemplo=True)

    return JsonResponse(resultados, safe=False)