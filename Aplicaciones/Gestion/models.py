from datetime import date
from decimal import Decimal
import json
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
import re
#RAZA
class Raza(models.Model):
    id_ra = models.AutoField(primary_key=True)
    nombre_ra = models.CharField(max_length=100, unique=True)
    descripcion_ra = models.TextField(blank=True)
    origen_ra = models.CharField(max_length=100, blank=True)
    activo_ra = models.BooleanField(default=True)
    created_at_ra = models.DateTimeField(auto_now_add=True)
    updated_at_ra = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'razas'

    def __str__(self):
        return self.nombre_ra
#POTREROS
class Potrero(models.Model):
    ESTADOS_POTRERO = [
        ('disponible', 'Disponible'),
        ('ocupado', 'Ocupado'),
        ('en_descanso', 'En Descanso'),
        ('inactivo', 'Inactivo'),
    ]

    id_po = models.AutoField(primary_key=True)
    codigo_po = models.CharField(
        max_length=20, 
        unique=True,
        verbose_name="Código"
    )
    nombre_po = models.CharField(
        max_length=100,
        verbose_name="Nombre"
    )
    hectareas_po = models.DecimalField(
        max_digits=6, 
        decimal_places=2,
        validators=[MinValueValidator(0.01, "Las hectáreas deben ser mayores a 0")],
        verbose_name="Hectáreas"
    )
    capacidad_maxima_po = models.IntegerField(
        validators=[MinValueValidator(1, "La capacidad mínima es 1 animal")],
        verbose_name="Capacidad Máxima"
    )
    estado_po = models.CharField(
        max_length=20, 
        default='disponible',
        choices=ESTADOS_POTRERO,
        verbose_name="Estado"
    )
    observaciones_po = models.TextField(
        blank=True,
        verbose_name="Observaciones"
    )
    created_at_po = models.DateTimeField(auto_now_add=True)
    updated_at_po = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'potreros'
        ordering = ['codigo_po']
        verbose_name = "Potrero"
        verbose_name_plural = "Potreros"

    def __str__(self):
        return f"{self.codigo_po} - {self.nombre_po}"

    def clean(self):
        # Validar código: solo letras, números y guiones
        if self.codigo_po and not re.match(r'^[a-zA-Z0-9\-]+$', self.codigo_po):
            raise ValidationError({
                'codigo_po': 'El código solo puede contener letras, números y guiones.'
            })
        
        # Validar nombre: mínimo 2 caracteres significativos
        if self.nombre_po and len(self.nombre_po.strip()) < 2:
            raise ValidationError({
                'nombre_po': 'El nombre debe tener al menos 2 caracteres.'
            })

        # Validar que fecha de actualización no sea manipulada (seguridad)
        # La latitud/longitud ya están validadas por los validators

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def animales_actuales(self):
        """Cantidad de animales activos actualmente en este potrero"""
        return self.animales.filter(estado_an='activo').count()

    @property
    def capacidad_disponible(self):
        """Capacidad restante del potrero"""
        return self.capacidad_maxima_po - self.animales_actuales

    @property
    def ocupacion_porcentaje(self):
        """Porcentaje de ocupación del potrero"""
        if self.capacidad_maxima_po == 0:
            return 0
        return (self.animales_actuales / self.capacidad_maxima_po) * 100
#PRODUCTO VETERINARIO
class ProductoVeterinario(models.Model):
    id_pv = models.AutoField(primary_key=True)
    codigo_pv = models.CharField(max_length=20, unique=True)
    nombre_pv = models.CharField(max_length=200)
    tipo_pv = models.CharField(max_length=50)
    presentacion_pv = models.CharField(max_length=100, blank=True)
    stock_pv = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_minimo_pv = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    unidad_medida_pv = models.CharField(max_length=20)
    fecha_vencimiento_pv = models.DateField(null=True, blank=True)
    proveedor_pv = models.CharField(max_length=200, blank=True)
    costo_unitario_pv = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    activo_pv = models.BooleanField(default=True)
    created_at_pv = models.DateTimeField(auto_now_add=True)
    updated_at_pv = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'productos_veterinarios'

    def __str__(self):
        return self.nombre_pv
#INSUMO ALIMENTICIO
class InsumoAlimenticio(models.Model):
    id_ia = models.AutoField(primary_key=True)
    codigo_ia = models.CharField(max_length=20, unique=True)
    nombre_ia = models.CharField(max_length=200)
    tipo_ia = models.CharField(max_length=50)
    marca_ia = models.CharField(max_length=100, blank=True)
    stock_kg_ia = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_minimo_kg_ia = models.DecimalField(max_digits=10, decimal_places=2, default=100)
    costo_kg_ia = models.DecimalField(max_digits=10, decimal_places=2)
    proveedor_ia = models.CharField(max_length=200, blank=True)
    fecha_compra_ia = models.DateField(null=True, blank=True)
    activo_ia = models.BooleanField(default=True)
    created_at_ia = models.DateTimeField(auto_now_add=True)
    updated_at_ia = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'insumos_alimenticios'

    def __str__(self):
        return self.nombre_ia

#DIETA
class Dieta(models.Model):
    id_di = models.AutoField(primary_key=True)
    codigo_di = models.CharField(max_length=20, unique=True)
    nombre_di = models.CharField(max_length=200)
    categoria_objetivo_di = models.CharField(max_length=50)
    materia_seca_kg_di = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    energia_mcal_di = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    proteina_cruda_pct_di = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fibra_cruda_pct_di = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    calcio_pct_di = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fosforo_pct_di = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    costo_diario_estimado_di = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    activa_di = models.BooleanField(default=True)
    created_at_di = models.DateTimeField(auto_now_add=True)
    updated_at_di = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dietas'

    def __str__(self):
        return self.nombre_di
#USUARIO
class Usuario(models.Model):
    id_us = models.AutoField(primary_key=True)
    username_us = models.CharField(max_length=150, unique=True)
    password_us = models.CharField(max_length=255)
    email_us = models.EmailField(max_length=254, unique=True)
    nombre_us = models.CharField(max_length=100)
    apellido_us = models.CharField(max_length=100)
    telefono_us = models.CharField(max_length=20, blank=True)
    cedula_us = models.CharField(max_length=20, unique=True, null=True, blank=True)
    rol_us = models.CharField(max_length=30)
    activo_us = models.BooleanField(default=True)
    ultimo_acceso_us = models.DateTimeField(null=True, blank=True)
    intentos_fallidos_us = models.IntegerField(default=0)
    bloqueado_hasta_us = models.DateTimeField(null=True, blank=True)
    created_at_us = models.DateTimeField(auto_now_add=True)
    updated_at_us = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'usuarios'

    def __str__(self):
        return f"{self.username_us} ({self.rol_us})"
    
#AUDITORIA

class LogAuditoria(models.Model):
    id_la = models.AutoField(primary_key=True)
    
    # Esto enlaza con tu tabla Usuario (NO es número suelto)
    fk_us_la = models.ForeignKey(
        'Usuario',           # Tu modelo de usuario
        on_delete=models.CASCADE,
        db_column='fk_us_la' # Nombre exacto de la columna en PostgreSQL
    )
    
    # Las acciones en minúsculas (igual que tu CHECK de PostgreSQL)
    accion_la = models.CharField(max_length=50)
    modelo_afectado_la = models.CharField(max_length=50)
    objeto_id_la = models.IntegerField(null=True, blank=True)
    descripcion_la = models.TextField(blank=True)
    ip_address_la = models.GenericIPAddressField(null=True, blank=True)
    fecha_hora_la = models.DateTimeField(auto_now_add=True)
    created_at_la = models.DateTimeField(auto_now_add=True)
    updated_at_la = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'log_auditoria'

    def __str__(self):
        return f"{self.accion_la} - {self.modelo_afectado_la}"


#INICIO DE TABLAS CON CLAVES FORANEAS
# ==========================================================
# MÓDULO 1: GESTIÓN DE INVENTARIO GANADERO
# ==========================================================

# ANIMALES
class Animal(models.Model):
    id_an = models.AutoField(primary_key=True)
    codigo_an = models.CharField(max_length=20, unique=True)
    nombre_an = models.CharField(max_length=100, blank=True, null=True)

    fk_ra = models.ForeignKey(
        'Raza',
        on_delete=models.CASCADE,
        db_column='fk_ra'
    )

    sexo_an = models.CharField(max_length=1)
    fecha_nacimiento_an = models.DateField()

    peso_nacimiento_kg_an = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    peso_actual_kg_an = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    color_an = models.CharField(max_length=50, blank=True, null=True)
    senas_particulares_an = models.TextField(blank=True, null=True)

    fk_madre_an = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hijos_madre',
        db_column='fk_madre_an'
    )

    fk_padre_an = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hijos_padre',
        db_column='fk_padre_an'
    )

    fk_potrero_an = models.ForeignKey(
        'Potrero',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='fk_potrero_an'
    )

    estado_an = models.CharField(max_length=20, default='activo')
    categoria_an = models.CharField(max_length=30)
    condicion_corporal_an = models.IntegerField(null=True, blank=True)

    foto_an = models.CharField(max_length=255, blank=True, null=True)

    fecha_ingreso_an = models.DateField()
    fecha_salida_an = models.DateField(null=True, blank=True)

    motivo_salida_an = models.CharField(max_length=200, blank=True, null=True)

    created_at_an = models.DateTimeField(auto_now_add=True)
    updated_at_an = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'animales'

    def __str__(self):
        return f"{self.codigo_an} - {self.nombre_an or 'Sin nombre'}"


# MOVIMIENTOS ANIMALES
class MovimientoAnimal(models.Model):
    id_ma = models.AutoField(primary_key=True)

    fk_an = models.ForeignKey(
        'Animal',
        on_delete=models.CASCADE,
        db_column='fk_an'
    )

    tipo_movimiento_ma = models.CharField(max_length=20)
    fecha_ma = models.DateField()

    motivo_ma = models.TextField(blank=True, null=True)

    fk_potrero_origen_ma = models.ForeignKey(
        'Potrero',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_origen',
        db_column='fk_potrero_origen_ma'
    )

    fk_potrero_destino_ma = models.ForeignKey(
        'Potrero',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_destino',
        db_column='fk_potrero_destino_ma'
    )

    precio_ma = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    comprador_vendedor_ma = models.CharField(max_length=200, blank=True, null=True)

    documento_soporte_ma = models.CharField(max_length=255, blank=True, null=True)

    fk_us_ma = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_ma'
    )

    created_at_ma = models.DateTimeField(auto_now_add=True)
    updated_at_ma = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'movimientos_animales'

    def __str__(self):
        return f"{self.tipo_movimiento_ma} - {self.fk_an.codigo_an}"


# ==========================================================
# MÓDULO 2: CONTROL SANITARIO Y VETERINARIO
# ==========================================================

# EVENTOS SANITARIOS
class EventoSanitario(models.Model):
    id_es = models.AutoField(primary_key=True)

    fk_an = models.ForeignKey(
        'Animal',
        on_delete=models.CASCADE,
        db_column='fk_an'
    )

    tipo_evento_es = models.CharField(max_length=50)

    fecha_programada_es = models.DateField()

    fecha_ejecutada_es = models.DateField(
        null=True,
        blank=True
    )

    estado_es = models.CharField(
        max_length=20,
        default='pendiente'
    )

    fk_pv = models.ForeignKey(
        'ProductoVeterinario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='fk_pv'
    )

    # ==========================================================
    # DECIMALES CORREGIDOS
    # ==========================================================
    dosis_es = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default=0
    )

    via_administracion_es = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )

    veterinario_responsable_es = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    resultado_es = models.TextField(
        blank=True,
        null=True
    )

    costo_es = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default=0
    )

    fk_us_es = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_es'
    )

    created_at_es = models.DateTimeField(auto_now_add=True)

    updated_at_es = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'eventos_sanitarios'

    def __str__(self):
        return f"{self.tipo_evento_es} - {self.fk_an.codigo_an}"
#Registro_clinico
class RegistroClinico(models.Model):
    id_rc = models.AutoField(primary_key=True)

    fk_an = models.ForeignKey(
        'Animal',
        on_delete=models.CASCADE,
        db_column='fk_an'
    )

    fecha_rc = models.DateField()

    sintomas_rc = models.TextField()

    diagnostico_rc = models.TextField(
        blank=True,
        null=True
    )

    tratamiento_rc = models.TextField(
        blank=True,
        null=True
    )

    dias_tratamiento_rc = models.IntegerField(
        null=True,
        blank=True
    )

    resultado_rc = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    costo_tratamiento_rc = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default=0
    )

    veterinario_rc = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    fk_us_rc = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_rc'
    )

    created_at_rc = models.DateTimeField(auto_now_add=True)

    updated_at_rc = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'registros_clinicos'

    def __str__(self):
        return f"Registro Clínico - {self.fk_an.codigo_an}"

# ==========================================================
# MÓDULO 3: REPRODUCCIÓN Y GENÉTICA
# ==========================================================
# ==========================================================
# CELOS
# ==========================================================
class Celo(models.Model):
    id_ce = models.AutoField(primary_key=True)

    fk_an = models.ForeignKey(
        'Animal',
        on_delete=models.CASCADE,
        db_column='fk_an'
    )

    fecha_observacion_ce = models.DateField()

    intensidad_ce = models.CharField(
        max_length=20,
        choices=[
            ('baja', 'Baja'),
            ('media', 'Media'),
            ('alta', 'Alta')
        ],
        null=True,
        blank=True
    )

    duracion_aproximada_horas_ce = models.IntegerField(
        null=True,
        blank=True
    )

    observaciones_ce = models.TextField(
        null=True,
        blank=True
    )

    fk_us_ce = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_ce'
    )

    created_at_ce = models.DateTimeField(auto_now_add=True)
    updated_at_ce = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'celos'
        verbose_name = 'Celo'
        verbose_name_plural = 'Celos'

    def __str__(self):
        return f"Celo - {self.fk_an.codigo_an}"


# ==========================================================
# INSEMINACIONES
# ==========================================================
class Inseminacion(models.Model):
    id_in = models.AutoField(primary_key=True)

    fk_an = models.ForeignKey(
        'Animal',
        on_delete=models.CASCADE,
        related_name='inseminaciones_hembra',
        db_column='fk_an'
    )

    fecha_in = models.DateField()

    tipo_inseminacion_in = models.CharField(
        max_length=20,
        choices=[
            ('natural', 'Natural'),
            ('artificial', 'Artificial')
        ]
    )

    dia_ciclo_in = models.IntegerField(
        null=True,
        blank=True
    )

    fk_toro_in = models.ForeignKey(
        'Animal',
        on_delete=models.SET_NULL,
        related_name='inseminaciones_toro',
        db_column='fk_toro_in',
        null=True,
        blank=True
    )

    lote_semen_in = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    condicion_corporal_in = models.IntegerField(
        null=True,
        blank=True
    )

    resultado_in = models.CharField(
        max_length=20,
        choices=[
            ('preñada', 'Preñada'),
            ('no_preñada', 'No Preñada'),
            ('pendiente', 'Pendiente')
        ],
        null=True,
        blank=True
    )

    fecha_resultado_in = models.DateField(
        null=True,
        blank=True
    )

    veterinario_in = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    costo_in = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )

    fk_us_in = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_in'
    )

    created_at_in = models.DateTimeField(auto_now_add=True)
    updated_at_in = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inseminaciones'
        verbose_name = 'Inseminación'
        verbose_name_plural = 'Inseminaciones'

    def __str__(self):
        return f"Inseminación - {self.fk_an.codigo_an}"


# ==========================================================
# PREÑECES
# ==========================================================
class Prenez(models.Model):
    id_pr = models.AutoField(primary_key=True)

    fk_an = models.ForeignKey(
        'Animal',
        on_delete=models.CASCADE,
        db_column='fk_an'
    )

    fk_in = models.ForeignKey(
        'Inseminacion',
        on_delete=models.SET_NULL,
        db_column='fk_in',
        null=True,
        blank=True
    )

    fecha_confirmacion_pr = models.DateField()

    metodo_diagnostico_pr = models.CharField(
        max_length=50,
        choices=[
            ('palpacion', 'Palpación'),
            ('ultrasonido', 'Ultrasonido'),
            ('sangre', 'Sangre'),
            ('otro', 'Otro')
        ],
        null=True,
        blank=True
    )

    fecha_probable_parto_pr = models.DateField()

    observaciones_pr = models.TextField(
        null=True,
        blank=True
    )

    fk_us_pr = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_pr'
    )

    created_at_pr = models.DateTimeField(auto_now_add=True)
    updated_at_pr = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'preñeces'
        verbose_name = 'Preñez'
        verbose_name_plural = 'Preñeces'

    def __str__(self):
        return f"Preñez - {self.fk_an.codigo_an}"


# ==========================================================
# PARTOS
# ==========================================================
class Parto(models.Model):
    TIPO_PARTO_CHOICES = [
        ('normal', 'Normal'),
        ('distocico', 'Distócico'),
        ('cesarea', 'Cesárea'),
    ]

    SEXO_CRIA_CHOICES = [
        ('M', 'Macho'),
        ('H', 'Hembra'),
    ]

    id_pa = models.AutoField(primary_key=True)

    fk_madre_pa = models.ForeignKey(
        'Animal',
        on_delete=models.CASCADE,
        related_name='partos_madre',
        db_column='fk_madre_pa',
        limit_choices_to={'sexo_an': 'H', 'estado_an': 'activo'}
    )

    fk_pr = models.ForeignKey(
        'Prenez',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='fk_pr',
        related_name='parto_asociado'
    )

    fecha_pa = models.DateField()

    tipo_parto_pa = models.CharField(
        max_length=20,
        choices=TIPO_PARTO_CHOICES,
        blank=True,
        null=True
    )

    cria_sexo_pa = models.CharField(
        max_length=1,
        choices=SEXO_CRIA_CHOICES,
        blank=True,
        null=True
    )

    cria_peso_kg_pa = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )

    fk_cria_pa = models.ForeignKey(
        'Animal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='datos_cria',
        db_column='fk_cria_pa'
    )

    asistencia_veterinaria_pa = models.BooleanField(default=False)

    observaciones_pa = models.TextField(
        blank=True,
        null=True
    )

    fk_us_pa = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_pa'
    )

    created_at_pa = models.DateTimeField(auto_now_add=True)
    updated_at_pa = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'partos'
        ordering = ['-fecha_pa', '-created_at_pa']
        verbose_name = 'Parto'
        verbose_name_plural = 'Partos'

    def __str__(self):
        return f"Parto #{self.id_pa} - {self.fk_madre_pa.codigo_an} ({self.fecha_pa})"

    def clean(self):
        from django.core.exceptions import ValidationError
        from datetime import date

        # Validar que la madre sea hembra
        if self.fk_madre_pa and self.fk_madre_pa.sexo_an != 'H':
            raise ValidationError("La madre debe ser una hembra.")

        # Validar que la preñez vinculada corresponda a la misma madre
        if self.fk_pr and self.fk_pr.fk_an_id != self.fk_madre_pa_id:
            raise ValidationError("La preñez seleccionada no corresponde a la madre elegida.")

        # Validar fecha no futura
        if self.fecha_pa and self.fecha_pa > date.today():
            raise ValidationError("La fecha del parto no puede ser futura.")

        # Validar consistencia sexo cría
        if self.fk_cria_pa and self.cria_sexo_pa:
            if self.fk_cria_pa.sexo_an != self.cria_sexo_pa:
                raise ValidationError("El sexo de la cría vinculada no coincide con el sexo registrado.")

        # Validar peso cría rango realista
        if self.cria_peso_kg_pa and (self.cria_peso_kg_pa < 5 or self.cria_peso_kg_pa > 80):
            raise ValidationError("El peso de la cría debe estar entre 5 y 80 kg.")

        super().clean()

# ==========================================================
# ABORTOS
# ==========================================================
class Aborto(models.Model):
    id_ab = models.AutoField(primary_key=True)

    fk_an = models.ForeignKey(
        'Animal',
        on_delete=models.CASCADE,
        db_column='fk_an'
    )

    fecha_ab = models.DateField()

    causa_probable_ab = models.TextField(
        null=True,
        blank=True
    )

    tratamiento_ab = models.TextField(
        null=True,
        blank=True
    )

    destino_madre_ab = models.CharField(
        max_length=50,
        choices=[
            ('reproduccion', 'Reproducción'),
            ('reengorde', 'Reengorde'),
            ('venta', 'Venta'),
            ('baja', 'Baja')
        ],
        null=True,
        blank=True
    )

    fk_us_ab = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_ab'
    )

    created_at_ab = models.DateTimeField(auto_now_add=True)
    updated_at_ab = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'abortos'
        verbose_name = 'Aborto'
        verbose_name_plural = 'Abortos'

    def __str__(self):
        return f"Aborto - {self.fk_an.codigo_an}"


# ==========================================================
# MÓDULO 4: PRODUCCIÓN LÁCTEA
# ==========================================================

# ==========================================================
# ORDEÑOS
# ==========================================================
class Ordeno(models.Model):
    id_or = models.AutoField(primary_key=True)

    fk_an = models.ForeignKey(
        'Animal',
        on_delete=models.CASCADE,
        db_column='fk_an'
    )

    fecha_or = models.DateField()

    turno_or = models.CharField(
        max_length=20,
        choices=[
            ('manana', 'Mañana'),
            ('tarde', 'Tarde'),
            ('unico', 'Único')
        ]
    )

    litros_or = models.DecimalField(
        max_digits=6,
        decimal_places=2
    )

    temperatura_leche_or = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True
    )

    observaciones_or = models.TextField(
        null=True,
        blank=True
    )

    cantidad_concentrado_kg_or = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )

    temperatura_ambiental_or = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True
    )

    fk_us_or = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_or'
    )

    created_at_or = models.DateTimeField(auto_now_add=True)
    updated_at_or = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ordenos'
        verbose_name = 'Ordeño'
        verbose_name_plural = 'Ordeños'
        unique_together = ('fk_an', 'fecha_or', 'turno_or')

    def __str__(self):
        return f"Ordeño - {self.fk_an.codigo_an}"


# ==========================================================
# CALIDAD LECHE
# ==========================================================
class CalidadLeche(models.Model):
    id_cl = models.AutoField(primary_key=True)

    fk_an = models.ForeignKey(
        'Animal',
        on_delete=models.CASCADE,
        db_column='fk_an',
        verbose_name='Animal'
    )

    fecha_muestreo_cl = models.DateField(
        verbose_name='Fecha de muestreo'
    )

    grasa_pct_cl = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Grasa (%)'
    )

    proteina_pct_cl = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Proteína (%)'
    )

    ccs_cl = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='CCS (Células Somáticas)'
    )

    ufc_cl = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='UFC (Unidades Formadoras de Colonias)'
    )

    RESULTADO_CHOICES = [
        ('apto', 'Apto'),
        ('no_apto', 'No Apto'),
        ('pendiente', 'Pendiente'),
    ]
    resultado_cl = models.CharField(
        max_length=20,
        choices=RESULTADO_CHOICES,
        blank=True,
        null=True,
        verbose_name='Resultado'
    )

    laboratorio_cl = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Laboratorio'
    )

    costo_analisis_cl = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Costo del análisis'
    )

    fk_us_cl = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_cl',
        verbose_name='Registrado por'
    )

    created_at_cl = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de creación'
    )
    updated_at_cl = models.DateTimeField(
        auto_now=True,
        verbose_name='Última modificación'
    )

    class Meta:
        db_table = 'calidad_leche'
        verbose_name = 'Calidad de Leche'
        verbose_name_plural = 'Calidades de Leche'
        ordering = ['-fecha_muestreo_cl', '-created_at_cl']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(resultado_cl__in=['apto', 'no_apto', 'pendiente']),
                name='check_resultado_cl'
            ),
        ]

    def __str__(self):
        return f"Calidad Leche - {self.fk_an.codigo_an} - {self.fecha_muestreo_cl}"

#Secados
class Secado(models.Model):
    id_se = models.AutoField(primary_key=True)

    fk_an = models.ForeignKey(
        'Animal',
        on_delete=models.CASCADE,
        db_column='fk_an',
        verbose_name='Animal'
    )

    fecha_ultimo_ordeno_se = models.DateField(
        verbose_name='Fecha último ordeño'
    )

    CAUSA_CHOICES = [
        ('preñez_avanzada', 'Preñez Avanzada'),
        ('baja_produccion', 'Baja Producción'),
        ('enfermedad', 'Enfermedad'),
        ('programado', 'Programado'),
        ('otro', 'Otro'),
    ]
    causa_se = models.CharField(
        max_length=50,
        choices=CAUSA_CHOICES,
        blank=True,
        null=True,
        verbose_name='Causa del secado'
    )

    observaciones_se = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observaciones'
    )

    fk_us_se = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_se',
        verbose_name='Registrado por'
    )

    created_at_se = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de creación'
    )
    updated_at_se = models.DateTimeField(
        auto_now=True,
        verbose_name='Última modificación'
    )

    class Meta:
        db_table = 'secados'
        verbose_name = 'Secado'
        verbose_name_plural = 'Secados'
        ordering = ['-fecha_ultimo_ordeno_se', '-created_at_se']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(causa_se__in=['preñez_avanzada', 'baja_produccion', 'enfermedad', 'programado', 'otro']),
                name='check_causa_se'
            ),
        ]

    def __str__(self):
        return f"Secado - {self.fk_an.codigo_an} - {self.fecha_ultimo_ordeno_se}"

#Entrega de leche
class EntregaLeche(models.Model):
    id_el = models.AutoField(primary_key=True)

    fecha_el = models.DateField(
        verbose_name='Fecha de entrega'
    )

    litros_totales_el = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name='Litros totales'
    )

    cliente_el = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Cliente'
    )

    precio_litro_el = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Precio por litro'
    )

    monto_total_el = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Monto total'
    )

    guia_remision_el = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Guía de remisión'
    )

    observaciones_el = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observaciones'
    )

    fk_us_el = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_el',
        verbose_name='Registrado por'
    )

    created_at_el = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de creación'
    )
    updated_at_el = models.DateTimeField(
        auto_now=True,
        verbose_name='Última modificación'
    )

    class Meta:
        db_table = 'entregas_leche'
        verbose_name = 'Entrega de Leche'
        verbose_name_plural = 'Entregas de Leche'
        ordering = ['-fecha_el', '-created_at_el']

    def __str__(self):
        return f"Entrega Leche - {self.fecha_el} - {self.litros_totales_el}L"
    
# ==========================================================
# MÓDULO 5: ALIMENTACIÓN Y NUTRICIÓN
# ==========================================================
#Racion
class Racion(models.Model):
    id_ra = models.AutoField(primary_key=True)

    fk_an = models.ForeignKey(
        'Animal',
        on_delete=models.CASCADE,
        db_column='fk_an',
        related_name='raciones_animal'
    )

    fk_di = models.ForeignKey(
        'Dieta',
        on_delete=models.CASCADE,
        db_column='fk_di',
        related_name='raciones_dieta'
    )

    fk_ia = models.ForeignKey(
        'InsumoAlimenticio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='fk_ia',
        related_name='raciones_insumo'
    )

    fecha_inicio_ra = models.DateField()

    fecha_fin_ra = models.DateField(
        null=True,
        blank=True
    )

    cantidad_ofrecida_kg_ra = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0.01, "La cantidad ofrecida debe ser mayor a 0")]
    )

    cantidad_consumida_kg_ra = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0, "La cantidad consumida no puede ser negativa")]
    )

    desperdicio_kg_ra = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0, "El desperdicio no puede ser negativo")]
    )

    dias_en_potrero_ra = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0, "Los días en potrero no pueden ser negativos")]
    )

    fk_us_ra = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_ra',
        related_name='raciones_usuario'
    )

    created_at_ra = models.DateTimeField(auto_now_add=True)
    updated_at_ra = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'raciones'
        verbose_name = 'Ración'
        verbose_name_plural = 'Raciones'
        ordering = ['-fecha_inicio_ra', '-created_at_ra']

    def __str__(self):
        return f"Ración #{self.id_ra} - {self.fk_an.codigo_an}"

    def clean(self):
        """Validaciones a nivel de modelo"""
        from django.core.exceptions import ValidationError
        
        # Validar que fecha_fin no sea anterior a fecha_inicio
        if self.fecha_fin_ra and self.fecha_inicio_ra:
            if self.fecha_fin_ra < self.fecha_inicio_ra:
                raise ValidationError({
                    'fecha_fin_ra': 'La fecha de fin no puede ser anterior a la fecha de inicio.'
                })
        
        # Validar que cantidad_consumida no supere cantidad_ofrecida
        if self.cantidad_consumida_kg_ra and self.cantidad_ofrecida_kg_ra:
            if self.cantidad_consumida_kg_ra > self.cantidad_ofrecida_kg_ra:
                raise ValidationError({
                    'cantidad_consumida_kg_ra': 'La cantidad consumida no puede superar la cantidad ofrecida.'
                })
        
        # Validar que desperdicio no supere lo no consumido
        if self.desperdicio_kg_ra and self.cantidad_ofrecida_kg_ra and self.cantidad_consumida_kg_ra:
            no_consumido = self.cantidad_ofrecida_kg_ra - self.cantidad_consumida_kg_ra
            if self.desperdicio_kg_ra > no_consumido:
                raise ValidationError({
                    'desperdicio_kg_ra': f'El desperdicio no puede superar los {no_consumido} kg no consumidos.'
                })

    def calcular_eficiencia(self):
        """Calcula el porcentaje de eficiencia de consumo"""
        if self.cantidad_ofrecida_kg_ra and self.cantidad_ofrecida_kg_ra > 0:
            if self.cantidad_consumida_kg_ra:
                return round((self.cantidad_consumida_kg_ra / self.cantidad_ofrecida_kg_ra) * 100, 2)
        return None

    def calcular_desperdicio_pct(self):
        """Calcula el porcentaje de desperdicio"""
        if self.cantidad_ofrecida_kg_ra and self.cantidad_ofrecida_kg_ra > 0:
            if self.desperdicio_kg_ra:
                return round((self.desperdicio_kg_ra / self.cantidad_ofrecida_kg_ra) * 100, 2)
        return None

#Asignacion potrero
class AsignacionPotrero(models.Model):
    id_ap = models.AutoField(primary_key=True)

    fk_po = models.ForeignKey(
        'Potrero',
        on_delete=models.CASCADE,
        db_column='fk_po',
        related_name='asignaciones_potrero'
    )

    fk_an = models.ForeignKey(
        'Animal',
        on_delete=models.CASCADE,
        db_column='fk_an',
        related_name='asignaciones_animal'
    )

    fecha_ingreso_ap = models.DateField()

    fecha_salida_estimada_ap = models.DateField(
        null=True,
        blank=True
    )

    fecha_salida_real_ap = models.DateField(
        null=True,
        blank=True
    )

    dias_descanso_posterior_ap = models.IntegerField(
        default=30,
        validators=[MinValueValidator(0, "Los días de descanso no pueden ser negativos")]
    )

    observaciones_ap = models.TextField(
        blank=True,
        null=True
    )

    fk_us_ap = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_ap',
        related_name='asignaciones_usuario'
    )

    created_at_ap = models.DateTimeField(auto_now_add=True)
    updated_at_ap = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asignaciones_potrero'
        verbose_name = 'Asignación de Potrero'
        verbose_name_plural = 'Asignaciones de Potrero'
        ordering = ['-fecha_ingreso_ap', '-created_at_ap']

    def __str__(self):
        return f"{self.fk_an.codigo_an} -> {self.fk_po.nombre_po}"

    def clean(self):
        """Validaciones a nivel de modelo"""
        from django.core.exceptions import ValidationError
        
        # Validar que fecha_salida_real no sea anterior a fecha_ingreso
        if self.fecha_salida_real_ap and self.fecha_ingreso_ap:
            if self.fecha_salida_real_ap < self.fecha_ingreso_ap:
                raise ValidationError({
                    'fecha_salida_real_ap': 'La fecha de salida real no puede ser anterior a la fecha de ingreso.'
                })
        
        # Validar que fecha_salida_estimada no sea anterior a fecha_ingreso
        if self.fecha_salida_estimada_ap and self.fecha_ingreso_ap:
            if self.fecha_salida_estimada_ap < self.fecha_ingreso_ap:
                raise ValidationError({
                    'fecha_salida_estimada_ap': 'La fecha de salida estimada no puede ser anterior a la fecha de ingreso.'
                })
        
        # Validar que fecha_salida_real no sea futura
        if self.fecha_salida_real_ap and self.fecha_salida_real_ap > date.today():
            raise ValidationError({
                'fecha_salida_real_ap': 'La fecha de salida real no puede ser futura.'
            })

    @property
    def estado(self):
        """Estado de la asignación basado en fechas"""
        hoy = date.today()
        if self.fecha_salida_real_ap:
            return 'finalizada'
        elif self.fecha_salida_estimada_ap and self.fecha_salida_estimada_ap < hoy:
            return 'vencida'
        else:
            return 'activa'

    @property
    def dias_en_potrero(self):
        """Días que lleva el animal en el potrero"""
        hoy = date.today()
        if self.fecha_salida_real_ap:
            return (self.fecha_salida_real_ap - self.fecha_ingreso_ap).days
        return (hoy - self.fecha_ingreso_ap).days

    @property
    def dias_restantes(self):
        """Días restantes estimados en el potrero"""
        if self.fecha_salida_estimada_ap:
            hoy = date.today()
            return (self.fecha_salida_estimada_ap - hoy).days
        return None

#Pesajes
class Pesaje(models.Model):
    id_pe = models.AutoField(primary_key=True)

    fk_an = models.ForeignKey(
        'Animal',
        on_delete=models.CASCADE,
        db_column='fk_an'
    )

    fecha_pe = models.DateField()

    peso_kg_pe = models.DecimalField(
        max_digits=6,
        decimal_places=2
    )

    condicion_corporal_pe = models.IntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(1, "La condición corporal mínima es 1"),
            MaxValueValidator(5, "La condición corporal máxima es 5")
        ]
    )

    METODO_CHOICES = [
        ('bascula', 'Báscula'),
        ('cinta_metrica', 'Cinta Métrica'),
        ('estimacion_visual', 'Estimación Visual'),
    ]

    metodo_pe = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        choices=METODO_CHOICES
    )

    observaciones_pe = models.TextField(
        blank=True,
        null=True
    )

    fk_us_pe = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_pe'
    )

    created_at_pe = models.DateTimeField(auto_now_add=True)
    updated_at_pe = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pesajes'

    def __str__(self):
        return f"Pesaje - {self.fk_an.codigo_an}"

# ==========================================================
# MÓDULO 6: ADMINISTRACIÓN FINANCIERA
# ==========================================================
class Costo(models.Model):
    id_co = models.AutoField(primary_key=True)

    CATEGORIA_CHOICES = [
        ('alimentacion', 'Alimentación'),
        ('sanidad', 'Sanidad'),
        ('reproduccion', 'Reproducción'),
        ('mano_obra', 'Mano de Obra'),
        ('mantenimiento_infraestructura', 'Mantenimiento Infraestructura'),
        ('compra_animales', 'Compra de Animales'),
        ('impuestos', 'Impuestos'),
        ('otros', 'Otros'),
    ]

    categoria_co = models.CharField(
        max_length=50,
        choices=CATEGORIA_CHOICES
    )

    monto_co = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'), "El monto debe ser mayor a 0")]
    )

    fecha_co = models.DateField()

    descripcion_co = models.TextField(
        blank=True,
        null=True
    )

    comprobante_co = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    mes_referencia_co = models.IntegerField(
        validators=[
            MinValueValidator(1, "El mes debe estar entre 1 y 12"),
            MaxValueValidator(12, "El mes debe estar entre 1 y 12")
        ]
    )

    anio_referencia_co = models.IntegerField(
        validators=[MinValueValidator(2000, "El año debe ser válido")]
    )

    fk_us_co = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_co'
    )

    created_at_co = models.DateTimeField(auto_now_add=True)
    updated_at_co = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'costos'

    def __str__(self):
        return f"{self.get_categoria_co_display()} - ${self.monto_co}"
    
#Ingresos    
class Ingreso(models.Model):
    CATEGORIA_CHOICES = [
        ('venta_leche', 'Venta de Leche'),
        ('venta_animales', 'Venta de Animales'),
        ('venta_subproductos', 'Venta de Subproductos'),
        ('servicios_inseminacion', 'Servicios de Inseminación'),
        ('otros', 'Otros'),
    ]

    id_ig = models.AutoField(primary_key=True)
    
    categoria_ig = models.CharField(
        max_length=50,
        choices=CATEGORIA_CHOICES,
        verbose_name='Categoría'
    )
    
    cantidad_ig = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'), "La cantidad no puede ser negativa")],
        verbose_name='Cantidad'
    )
    
    precio_unitario_ig = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'), "El precio no puede ser negativo")],
        verbose_name='Precio Unitario'
    )
    
    monto_total_ig = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'), "El monto total debe ser mayor a 0")],
        verbose_name='Monto Total'
    )
    
    cliente_ig = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Cliente'
    )
    
    fecha_ig = models.DateField(
        verbose_name='Fecha'
    )
    
    comprobante_ig = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Comprobante'
    )
    
    fk_us_ig = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='fk_us_ig',
        verbose_name='Registrado por'
    )
    
    created_at_ig = models.DateTimeField(auto_now_add=True)
    updated_at_ig = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ingresos'
        verbose_name = 'Ingreso'
        verbose_name_plural = 'Ingresos'
        ordering = ['-fecha_ig', '-created_at_ig']

    def __str__(self):
        return f"{self.get_categoria_ig_display()} - ${self.monto_total_ig}"

    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Validar que fecha no sea futura
        if self.fecha_ig and self.fecha_ig > date.today():
            raise ValidationError({'fecha_ig': 'La fecha no puede ser futura.'})
        
        # Validar consistencia: si hay cantidad y precio, el monto debe coincidir (aprox)
        if self.cantidad_ig and self.precio_unitario_ig and self.monto_total_ig:
            calculado = self.cantidad_ig * self.precio_unitario_ig
            # Permitir pequeña diferencia por redondeo (0.05)
            if abs(calculado - self.monto_total_ig) > Decimal('0.05'):
                raise ValidationError({
                    'monto_total_ig': f'El monto total ({self.monto_total_ig}) no coincide con cantidad × precio ({calculado}).'
                })
        
        # Si no hay cantidad ni precio, el monto total es obligatorio (ya lo es por el campo)
        # Si hay cantidad, debe haber precio unitario (y viceversa)
        if (self.cantidad_ig and not self.precio_unitario_ig) or (not self.cantidad_ig and self.precio_unitario_ig):
            raise ValidationError('Si ingresa cantidad, debe ingresar precio unitario y viceversa.')
        
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

# ==========================================================
# MÓDULO 7: MACHINE LEARNING
# ==========================================================
# MODELOS ML
class ModeloML(models.Model):

    CODIGO_CHOICES = [
        ('AD-1', 'AD-1 - Árbol de Decisión Regresión (Ordenos)'),
        ('AD-2', 'AD-2 - Árbol de Decisión Clasificación (Inseminaciones)'),
        ('AD-3', 'AD-3 - Árbol de Decisión Regresión (Costos)'),
        ('RL-4', 'RL-4 - Regresión Logística (Calidad Leche)'),
        ('RL-5', 'RL-5 - Regresión Logística (Raciones)'),
        ('RL-6', 'RL-6 - Regresión Logística (Módulo 6)'),
    ]

    TIPO_MODELO_CHOICES = [
        ('decision_tree_regressor',   'Árbol de Decisión - Regresor'),
        ('decision_tree_classifier',  'Árbol de Decisión - Clasificador'),
        ('logistic_regression',       'Regresión Logística'),
    ]

    METRICA_CHOICES = [
        ('accuracy',  'Accuracy'),
        ('precision', 'Precision'),
        ('recall',    'Recall'),
        ('f1_score',  'F1 Score'),
        ('r2_score',  'R² Score'),
        ('mse',       'MSE'),
        ('rmse',      'RMSE'),
        ('mae',       'MAE'),
    ]

    MODULO_CHOICES = [
        ('produccion_lactea',    'Producción Láctea'),
        ('reproduccion',         'Reproducción y Genética'),
        ('administracion',       'Administración Financiera'),
        ('calidad_leche',        'Calidad de Leche'),
        ('alimentacion',         'Alimentación y Nutrición'),
        ('sanitario',            'Control Sanitario'),
    ]

    id_mm = models.AutoField(primary_key=True)

    nombre_mm = models.CharField(
        max_length=100,
        verbose_name='Nombre del Modelo'
    )

    codigo_mm = models.CharField(
        max_length=20,
        unique=True,
        choices=CODIGO_CHOICES,
        verbose_name='Código del Modelo'
    )

    tipo_modelo_mm = models.CharField(
        max_length=30,
        choices=TIPO_MODELO_CHOICES,
        verbose_name='Tipo de Modelo'
    )

    modulo_aplicacion_mm = models.CharField(
        max_length=50,
        choices=MODULO_CHOICES,
        verbose_name='Módulo de Aplicación'
    )

    descripcion_mm = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descripción'
    )

    metrica_principal_mm = models.CharField(
        max_length=20,
        choices=METRICA_CHOICES,
        blank=True,
        null=True,
        verbose_name='Métrica Principal'
    )

    valor_metrica_mm = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name='Valor de Métrica'
    )

    fecha_entrenamiento_mm = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Entrenamiento'
    )

    archivo_modelo_mm = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Ruta del Archivo (.pkl)'
    )

    activo_mm = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )

    created_at_mm = models.DateTimeField(auto_now_add=True)
    updated_at_mm = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'modelos_ml'
        verbose_name = 'Modelo ML'
        verbose_name_plural = 'Modelos ML'
        ordering = ['codigo_mm']

    def __str__(self):
        return f"{self.codigo_mm} - {self.nombre_mm}"

    # ============================================================
    # PROPIEDADES CALCULADAS
    # ============================================================

    @property
    def tipo_modelo_display(self):
        """Retorna el label legible del tipo de modelo."""
        return dict(self.TIPO_MODELO_CHOICES).get(self.tipo_modelo_mm, self.tipo_modelo_mm)

    @property
    def metrica_display(self):
        """Retorna el label legible de la métrica principal."""
        if self.metrica_principal_mm:
            return dict(self.METRICA_CHOICES).get(self.metrica_principal_mm, self.metrica_principal_mm)
        return '---'

    @property
    def modulo_display(self):
        """Retorna el label legible del módulo de aplicación."""
        return dict(self.MODULO_CHOICES).get(self.modulo_aplicacion_mm, self.modulo_aplicacion_mm)

    @property
    def tiene_archivo(self):
        """Indica si el modelo tiene archivo .pkl asociado."""
        return bool(self.archivo_modelo_mm and self.archivo_modelo_mm.strip())

    @property
    def esta_entrenado(self):
        """Indica si el modelo ha sido entrenado (tiene fecha de entrenamiento)."""
        return self.fecha_entrenamiento_mm is not None

    @property
    def rendimiento_porcentaje(self):
        """
        Para accuracy, precision, recall, f1: el valor ya es 0-1, retorna en %.
        Para r2_score: igual. Para MSE/RMSE/MAE: retorna el valor directo.
        """
        if self.valor_metrica_mm is None:
            return None
        metricas_porcentaje = ['accuracy', 'precision', 'recall', 'f1_score', 'r2_score']
        if self.metrica_principal_mm in metricas_porcentaje:
            return round(float(self.valor_metrica_mm) * 100, 2)
        return float(self.valor_metrica_mm)

# PREDICCIONES ML
class PrediccionML(models.Model):
    id_pm = models.AutoField(primary_key=True)

    fk_mm = models.ForeignKey(
        'ModeloML',
        on_delete=models.CASCADE,
        db_column='fk_mm'
    )

    fk_an = models.ForeignKey(
        'Animal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='fk_an'
    )

    datos_entrada_pm = models.JSONField(
        null=True,
        blank=True
    )

    resultado_prediccion_pm = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    probabilidad_pm = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True
    )

    valor_real_pm = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    acierto_pm = models.BooleanField(
        null=True,
        blank=True
    )

    fecha_prediccion_pm = models.DateTimeField(auto_now_add=True)

    fk_us_pm = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='fk_us_pm'
    )

    created_at_pm = models.DateTimeField(auto_now_add=True)
    updated_at_pm = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'predicciones_ml'
        verbose_name = 'Predicción ML'
        verbose_name_plural = 'Predicciones ML'

    def __str__(self):
        return f"Predicción #{self.id_pm} - {self.fk_mm.codigo_mm}"

    @property
    def precision_formateada(self):
        """Retorna la probabilidad como porcentaje"""
        if self.probabilidad_pm:
            return f"{float(self.probabilidad_pm) * 100:.2f}%"
        return "---"

    @property
    def estado_clase(self):
        """Retorna clase CSS según acierto"""
        if self.acierto_pm is True:
            return "success"
        elif self.acierto_pm is False:
            return "danger"
        return "secondary"

    @property
    def estado_texto(self):
        """Retorna texto según acierto"""
        if self.acierto_pm is True:
            return "Acierto"
        elif self.acierto_pm is False:
            return "Fallo"
        return "Sin evaluar"

    @property
    def datos_entrada_formateados(self):
        """Retorna JSON formateado para mostrar"""
        if self.datos_entrada_pm:
            return json.dumps(self.datos_entrada_pm, indent=2, ensure_ascii=False)
        return "No hay datos de entrada"
    

