from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # LOGIN
    path('', views.loginusuario, name='login'),
    path('login/', views.loginusuario, name='login_url'),
    path('logout/', views.logoutusuario, name='logout'),

    # INICIO
    path('inicio/', views.inicio, name='inicio'),
    # Razas
    path('listaraza/', views.listaraza, name='listaraza'),
    path('nuevaraza/', views.nuevaraza, name='nuevaraza'),
    path('guardarraza/', views.guardarraza, name='guardarraza'),
    path('editarraza/<int:id_ra>', views.editarraza, name='editarraza'),
    path('procesareditarraza/', views.procesareditarraza, name='procesareditarraza'),
    path('eliminaraza/<int:id_ra>', views.eliminaraza, name='eliminaraza'),
    # Potreros
    path('listapotrero/', views.listapotrero, name='listapotrero'),
    path('nuevopotrero/', views.nuevopotrero, name='nuevopotrero'),
    path('guardarpotrero/', views.guardarpotrero, name='guardarpotrero'),
    path('eliminarpotrero/<int:id_po>', views.eliminarpotrero, name='eliminarpotrero'),
    path('editarpotrero/<int:id_po>', views.editarpotrero, name='editarpotrero'),
    path('procesareditarpotrero/', views.procesareditarpotrero, name='procesareditarpotrero'),
    #Productos Veterinarios
    path('nuevoprodvet/', views.nuevoprodvet),
    path('listadoprodvet/', views.listadoprodvet),
    path('guardarprodvet/', views.guardarprodvet),
    path('eliminarprodvet/<int:id_pv>', views.eliminarprodvet),
    path('editarprodvet/<int:id_pv>', views.editarprodvet),
    path('procesareditarprodvet/', views.procesareditarprodvet),
    # Insumos Alimenticios
    path('nuevoinsumo/', views.nuevoinsumo),
    path('listadoinsumos/', views.listadoinsumos),
    path('guardarinsumo/', views.guardarinsumo),
    path('eliminarinsumo/<int:id_ia>', views.eliminarinsumo),
    path('editarinsumo/<int:id_ia>', views.editarinsumo),
    path('procesareditarinsumo/', views.procesareditarinsumo),
    # Dietas
    path('nuevadieta/', views.nuevadieta),
    path('listadodietas/', views.listadodietas),
    path('guardardieta/', views.guardardieta),
    path('eliminardieta/<int:id_di>', views.eliminardieta),
    path('editardieta/<int:id_di>', views.editardieta),
    path('procesareditardieta/', views.procesareditardieta),
    # Usuarios y Autenticación
    path('nuevousuario/', views.nuevousuario),
    path('listadousuarios/', views.listadousuarios),
    path('guardarusuario/', views.guardarusuario),
    path('eliminarusuario/<int:id_us>', views.eliminarusuario),
    path('editarusuario/<int:id_us>', views.editarusuario),
    path('procesareditarusuario/', views.procesareditarusuario),
    # Recuperación de contraseña
    path('recuperarcontrasena/', views.recuperarcontrasena),
    path('verificarcodigo/', views.verificarcodigo),
    path('reestablecercontrasena/', views.reestablecercontrasena),
    # Auditoría
    path('historialauditoria/', views.historialauditoria, name='historialauditoria'),
    path('verdetallelog/<int:id_la>/', views.verdetallelog, name='verdetallelog'),
    path('eliminarlog/<int:id_la>/', views.eliminarlog, name='eliminarlog'),
   # Animales
    path('nuevoanimal/', views.nuevoanimal, name='nuevoanimal'),
    path('listaanimal/', views.listaanimal, name='listaanimal'),
    path('guardaranimal/', views.guardaranimal, name='guardaranimal'),
    path('eliminaranimal/<int:id_an>', views.eliminaranimal, name='eliminaranimal'),
    path('editaranimal/<int:id_an>', views.editaranimal, name='editaranimal'),
    path('procesareditanimal/', views.procesareditanimal, name='procesareditanimal'),
    #Movimiento animales
    path('listamovimiento/', views.listamovimiento, name='listamovimiento'),
    path('nuevomovimiento/', views.nuevomovimiento, name='nuevomovimiento'),
    path('guardarmovimiento/', views.guardarmovimiento, name='guardarmovimiento'),
    path('eliminarmovimiento/<int:id_ma>', views.eliminarmovimiento, name='eliminarmovimiento'),
    path('editarmovimiento/<int:id_ma>', views.editarmovimiento, name='editarmovimiento'),
    path('procesareditarmovimiento/', views.procesareditarmovimiento, name='procesareditarmovimiento'),
    #Eventos sanitarios
    path('listaeventosanitario/', views.listaeventosanitario, name='listaeventosanitario'),
    path('nuevoeventosanitario/', views.nuevoeventosanitario, name='nuevoeventosanitario'),
    path('guardareventosanitario/', views.guardareventosanitario, name='guardareventosanitario'),
    path('eliminareventosanitario/<int:id_es>', views.eliminareventosanitario, name='eliminareventosanitario'),
    path('editareventosanitario/<int:id_es>', views.editareventosanitario, name='editareventosanitario'),
    path('procesareditareventosanitario/', views.procesareditareventosanitario, name='procesareditareventosanitario'),
    #Registro clinico
    path('listaregistroclinico/', views.listaregistroclinico, name='listaregistroclinico'),
    path('nuevoregistroclinico/', views.nuevoregistroclinico, name='nuevoregistroclinico'),
    path('guardarregistroclinico/', views.guardarregistroclinico, name='guardarregistroclinico'),
    path('editarregistroclinico/<int:id_rc>', views.editarregistroclinico, name='editarregistroclinico'),
    path('procesareditarregistroclinico/', views.procesareditarregistroclinico, name='procesareditarregistroclinico'),
    path('eliminarregistroclinico/<int:id_rc>', views.eliminarregistroclinico, name='eliminarregistroclinico'),
    #Celo
    path('listacelo/', views.listacelo, name='listacelo'),
    path('nuevocelo/', views.nuevocelo, name='nuevocelo'),
    path('guardarcelo/', views.guardarcelo, name='guardarcelo'),
    path('editarcelo/<int:id_ce>', views.editarcelo, name='editarcelo'),
    path('procesareditarcelo/', views.procesareditarcelo, name='procesareditarcelo'),
    path('eliminarcelo/<int:id_ce>', views.eliminarcelo, name='eliminarcelo'),
    #Inseminacion
    path('listainseminacion/', views.listainseminacion, name='listainseminacion'),
    path('nuevainseminacion/', views.nuevainseminacion, name='nuevainseminacion'),
    path('guardarinseminacion/', views.guardarinseminacion, name='guardarinseminacion'),
    path('eliminainseminacion/<int:id_in>', views.eliminainseminacion, name='eliminainseminacion'),
    path('editarinseminacion/<int:id_in>', views.editarinseminacion, name='editarinseminacion'),
    path('procesareditarinseminacion/', views.procesareditarinseminacion, name='procesareditarinseminacion'),
    # Preñeces
    path('listaprenez/', views.listaprenez, name='listaprenez'),
    path('nuevaprenez/', views.nuevaprenez, name='nuevaprenez'),
    path('guardarprenez/', views.guardarprenez, name='guardarprenez'),
    path('editarprenez/<int:id_pr>', views.editarprenez, name='editarprenez'),
    path('procesareditarprenez/', views.procesareditarprenez, name='procesareditarprenez'),
    path('eliminaprenez/<int:id_pr>', views.eliminaprenez, name='eliminaprenez'),
    #Partos
    path('listapartos/', views.listapartos, name='listapartos'),
    path('nuevoparto/', views.nuevoparto, name='nuevoparto'),
    path('guardarparto/', views.guardarparto, name='guardarparto'),
    path('editarparto/<int:id_pa>', views.editarparto, name='editarparto'),
    path('procesareditarparto/', views.procesareditarparto, name='procesareditarparto'),
    path('eliminaparto/<int:id_pa>', views.eliminaparto, name='eliminaparto'),
    #Abortos
    path('listaabortos/', views.listaabortos, name='listaabortos'),
    path('nuevoaborto/', views.nuevoaborto, name='nuevoaborto'),
    path('guardaraborto/', views.guardaraborto, name='guardaraborto'),
    path('editaraborto/<int:id_ab>', views.editaraborto, name='editaraborto'),
    path('procesareditaraborto/', views.procesareditaraborto, name='procesareditaraborto'),
    path('eliminaaborto/<int:id_ab>', views.eliminaaborto, name='eliminaaborto'),
    #Ordeño
    path('listaordeno/', views.listaordeno, name='listaordeno'),
    path('nuevoordeno/', views.nuevoordeno, name='nuevoordeno'),
    path('guardarordeno/', views.guardarordeno, name='guardarordeno'),
    path('editarordeno/<int:id_or>', views.editarordeno, name='editarordeno'),
    path('procesareditarordeno/', views.procesareditarordeno, name='procesareditarordeno'),
    path('eliminaordeno/<int:id_or>', views.eliminaordeno, name='eliminaordeno'),
    #Calidad de Leche
    path('listacalidadl/', views.listacalidadl, name='listacalidadl'),
    path('nuevacalidadl/', views.nuevacalidadl, name='nuevacalidadl'),
    path('guardarcalidadl/', views.guardarcalidadl, name='guardarcalidadl'),
    path('editarcalidadl/<int:id_cl>', views.editarcalidadl, name='editarcalidadl'),
    path('procesareditarcalidadl/', views.procesareditarcalidadl, name='procesareditarcalidadl'),
    path('eliminacalidadl/<int:id_cl>', views.eliminacalidadl, name='eliminacalidadl'),
    #Secados
    path('listasecado/', views.listasecado, name='listasecado'),
    path('nuevosecado/', views.nuevosecado, name='nuevosecado'),
    path('guardarsecado/', views.guardarsecado, name='guardarsecado'),
    path('editarsecado/<int:id_se>', views.editarsecado, name='editarsecado'),
    path('procesareditarsecado/', views.procesareditarsecado, name='procesareditarsecado'),
    path('eliminasecado/<int:id_se>', views.eliminasecado, name='eliminasecado'),
    #Entrega de leche
    path('listaentrega/', views.listaentrega, name='listaentrega'),
    path('nuevaentrega/', views.nuevaentrega, name='nuevaentrega'),
    path('guardarentrega/', views.guardarentrega, name='guardarentrega'),
    path('editarentrega/<int:id_el>', views.editarentrega, name='editarentrega'),
    path('procesareditarentrega/', views.procesareditarentrega, name='procesareditarentrega'),
    path('eliminaentrega/<int:id_el>', views.eliminaentrega, name='eliminaentrega'),
    # ==========================================================
    # MÓDULO 5: ALIMENTACIÓN Y NUTRICIÓN
    # ==========================================================
    #Racion
    path('listaracion/', views.listaracion, name='listaracion'),
    path('nuevaracion/', views.nuevaracion, name='nuevaracion'),
    path('guardarracion/', views.guardarracion, name='guardarracion'),
    path('editarracion/<int:id_ra>', views.editarracion, name='editarracion'),
    path('procesareditarracion/', views.procesareditarracion, name='procesareditarracion'),
    path('eliminaracion/<int:id_ra>', views.eliminaracion, name='eliminaracion'),
    #Asignacion potrero
    path('listaasignacionp/', views.listaasignacionp, name='listaasignacionp'),
    path('nuevaasignacionp/', views.nuevaasignacionp, name='nuevaasignacionp'),
    path('guardarasignacionp/', views.guardarasignacionp, name='guardarasignacionp'),
    path('editarasignacionp/<int:id_ap>', views.editarasignacionp, name='editarasignacionp'),
    path('procesareditarasignacionp/', views.procesareditarasignacionp, name='procesareditarasignacionp'),
    path('eliminaasignacionp/<int:id_ap>', views.eliminaasignacionp, name='eliminaasignacionp'),
    #Pesajes
    path('listapesaje/', views.listapesaje, name='listapesaje'),
    path('nuevapesaje/', views.nuevapesaje, name='nuevapesaje'),
    path('guardarpesaje/', views.guardarpesaje, name='guardarpesaje'),
    path('editarpesaje/<int:id_pe>', views.editarpesaje, name='editarpesaje'),
    path('procesareditarpesaje/', views.procesareditarpesaje, name='procesareditarpesaje'),
    path('eliminapesaje/<int:id_pe>', views.eliminapesaje, name='eliminapesaje'),
    # ==========================================================
    # MÓDULO 6: ADMINISTRACIÓN FINANCIERA
    # ==========================================================
    # Costos
    path('listacosto/', views.listacosto, name='listacosto'),
    path('nuevocosto/', views.nuevocosto, name='nuevocosto'),
    path('guardarcosto/', views.guardarcosto, name='guardarcosto'),
    path('editarcosto/<int:id_co>', views.editarcosto, name='editarcosto'),
    path('procesareditarcosto/', views.procesareditarcosto, name='procesareditarcosto'),
    path('eliminacosto/<int:id_co>', views.eliminacosto, name='eliminacosto'),
    # Ingresos
    path('listaingreso/', views.listaingreso, name='listaingreso'),
    path('nuevoingreso/', views.nuevoingreso, name='nuevoingreso'),
    path('guardingreso/', views.guardingreso, name='guardingreso'),
    path('editaringreso/<int:id_ig>', views.editaringreso, name='editaringreso'),
    path('procesareditaringreso/', views.procesareditaringreso, name='procesareditaringreso'),
    path('eliminaingreso/<int:id_ig>', views.eliminaingreso, name='eliminaingreso'),
    # ==========================================================
    # MÓDULO 7: MACHINE LEARNING (FUNCIONANDO)
    # ==========================================================
    # Dashboard con predicciones automaticas
    path('dashboardml/', views.dashboardml, name='dashboardml'),
    # Dashboard gráfico con estadísticas
    path('dashboard-estadistico/', views.dashboard_grafico, name='dashboard_grafico'),
    # Predicciones manuales con modelos .pkl entrenados
    path('prediccion/ad1/', views.prediccion_ad1, name='prediccion_ad1'),
    path('prediccion/ad2/', views.prediccion_ad2, name='prediccion_ad2'),
    path('prediccion/rl4/', views.prediccion_rl4, name='prediccion_rl4'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)