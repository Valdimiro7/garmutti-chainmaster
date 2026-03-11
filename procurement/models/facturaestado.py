from django.db import models
from django.contrib.auth.models import User
from .purchaseorder import PurchaseOrder
from .cliente import Cliente
from .moeda import Moeda
from .dadobancario import DadoBancario


class FacturaEstado(models.Model):
    nome   = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50)
    cor    = models.CharField(max_length=20, null=True, blank=True, default='#2E3E82')
    ordem  = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        managed  = False
        db_table = 'factura_estados'
        ordering = ['ordem', 'nome']
        verbose_name        = 'Estado da Factura'
        verbose_name_plural = 'Estados de Factura'

    def __str__(self):
        return self.nome