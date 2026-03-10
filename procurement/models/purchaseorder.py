from django.db import models
from django.contrib.auth.models import User
from .poestado import POEstado
from .quotacao import Quotacao
from .cliente import Cliente
from .moeda import Moeda


class PurchaseOrder(models.Model):
    numero = models.CharField(max_length=30, unique=True)

    estado = models.ForeignKey(
        POEstado,
        on_delete=models.DO_NOTHING,
        db_column='estado_id',
        related_name='purchase_orders',
    )
    quotacao = models.ForeignKey(
        Quotacao,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='quotacao_id',
        related_name='purchase_orders',
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.DO_NOTHING,
        db_column='cliente_id',
        related_name='purchase_orders',
    )
    moeda = models.ForeignKey(
        Moeda,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='moeda_id',
        related_name='purchase_orders',
    )

    po_cliente_numero = models.CharField(max_length=120, null=True, blank=True)
    referencia_cliente = models.CharField(max_length=120, null=True, blank=True)
    data_po = models.DateField()
    data_recebida = models.DateField(null=True, blank=True)
    valor_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    email_remetente = models.EmailField(max_length=180, null=True, blank=True)
    assunto_email = models.CharField(max_length=255, null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)

    criado_por = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='criado_por',
        related_name='purchase_orders_criadas',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'purchase_orders'
        ordering = ['-id']
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'

    def __str__(self):
        return self.numero