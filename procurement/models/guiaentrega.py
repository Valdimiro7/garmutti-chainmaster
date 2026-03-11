from django.db import models
from django.contrib.auth.models import User
from .purchaseorder import PurchaseOrder
from .cliente import Cliente
from .moeda import Moeda
from .guiaestado import GuiaEstado
from .factura import Factura


class GuiaEntrega(models.Model):
    numero = models.CharField(max_length=30, unique=True)

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='purchase_order_id',
        related_name='guias_entrega',
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.DO_NOTHING,
        db_column='cliente_id',
        related_name='guias_entrega',
    )
    moeda = models.ForeignKey(
        Moeda,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='moeda_id',
        related_name='guias_entrega',
    )
    estado = models.ForeignKey(
        GuiaEstado,
        on_delete=models.DO_NOTHING,
        db_column='estado_id',
        related_name='guias_entrega',
    )
    factura = models.ForeignKey(
        Factura,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='factura_id',
        related_name='guias_entrega',
    )

    data_guia = models.DateField()
    data_entrega = models.DateField(null=True, blank=True)

    recebido_por = models.CharField(max_length=180, null=True, blank=True)
    contacto_recebedor = models.CharField(max_length=120, null=True, blank=True)
    local_entrega = models.CharField(max_length=255, null=True, blank=True)

    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    observacoes = models.TextField(null=True, blank=True)

    criado_por = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='criado_por',
        related_name='guias_entrega_criadas',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'guias_entrega'
        ordering = ['-id']
        verbose_name = 'Guia de Entrega'
        verbose_name_plural = 'Guias de Entrega'

    def __str__(self):
        return self.numero