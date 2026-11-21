from django.urls import path
from compras_api import views
urlpatterns = [
    path('health', views.health),
    path('openapi.yaml', views.documentacion),
    path('api/proveedores', views.proveedores),
    path('api/proveedores/<int:identificador>', views.proveedor),
    path('api/proveedores/<int:identificador>/estado', views.proveedor_estado),
    path('api/proveedores/<int:identificador>/productos', views.proveedor_productos),
    path('api/compras', views.compras),
    path('api/compras/<int:identificador>', views.compra),
    path('api/compras/<int:identificador>/estado', views.compra_estado),
    path('api/compras/<int:identificador>/recepciones', views.recepciones),
]
