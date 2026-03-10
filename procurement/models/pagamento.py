from django.db import models
from django.contrib.auth.models import User
from .purchaseorder import PurchaseOrder
from .pagamentoestado import PagamentoEstado
from .cliente import Cliente
from .moeda import Moeda


class Pagamento(models.Model):
    numero = models.CharField(max_length=30, unique=True)

    purchase_order = models.OneToOneField(
        PurchaseOrder,
        on_delete=models.DO_NOTHING,
        db_column='purchase_order_id',
        related_name='pagamento',
    )
    estado = models.ForeignKey(
        PagamentoEstado,
        on_delete=models.DO_NOTHING,
        db_column='estado_id',
        related_name='pagamentos',
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.DO_NOTHING,
        db_column='cliente_id',
        related_name='pagamentos',
    )
    moeda = models.ForeignKey(
        Moeda,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='moeda_id',
        related_name='pagamentos',
    )

    data_pagamento_prevista = models.DateField(null=True, blank=True)
    data_pagamento_recebido = models.DateField(null=True, blank=True)

    valor_po = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    valor_recebido = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    saldo_pendente = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    referencia_pagamento = models.CharField(max_length=120, null=True, blank=True)
    banco_origem = models.CharField(max_length=150, null=True, blank=True)
    numero_transaccao = models.CharField(max_length=120, null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)

    criado_por = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='criado_por',
        related_name='pagamentos_criados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'pagamentos'
        ordering = ['-id']
        verbose_name = 'Pagamento'
        verbose_name_plural = 'Pagamentos'

    def __str__(self):
        return self.numero