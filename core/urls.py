from django.urls import path
from core import views

urlpatterns = [
    path("",                              views.index,        name="index"),
    path("bestil/bekraeftelse/<int:pk>/", views.bekraeftelse, name="bekraeftelse"),
    path("bestil/",                      views.bestil,      name="bestil"),
    path("bestil_test/",                 views.bestil_test, name="bestil_test"),
    path("dashboard/",                    views.dashboard,    name="dashboard"),
    path("opening_day/<int:pk>/",          views.opening_day,       name="opening_day"),
    path("order/<int:pk>/status/",         views.set_order_status,  name="set_order_status"),
]
