from django.db import models
from django.contrib.auth.models import User
from .factura import Factura
from .cliente import Cliente
from .moeda import Moeda


class Recibo(models.Model):
    """
    Recibo sempre ligado a uma Factura.
    Pode registar pagamento parcial ou total da factura.
    Numeração: REC-001/2025
    """

    numero = models.CharField(max_length=30, unique=True)

    factura = models.ForeignKey(
        Factura,
        on_delete=models.DO_NOTHING,
        db_column='factura_id',
        related_name='recibos',
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.DO_NOTHING,
        db_column='cliente_id',
        related_name='recibos',
    )
    moeda = models.ForeignKey(
        Moeda,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column='moeda_id',
        related_name='recibos',
    )

    data_recibo      = models.DateField()
    valor_recebido   = models.DecimalField(max_digits=18, decimal_places=2)
    forma_pagamento  = models.CharField(max_length=80, null=True, blank=True)   # ex: Transferência, Cheque, Numerário
    referencia       = models.CharField(max_length=120, null=True, blank=True)  # ref. do pagamento
    observacoes      = models.TextField(null=True, blank=True)
    anulado          = models.BooleanField(default=False)
    motivo_anulacao  = models.CharField(max_length=255, null=True, blank=True)

    criado_por = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column='criado_por',
        related_name='recibos_criados',
    )
    criado_em      = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        managed  = False
        db_table = 'recibos'
        ordering = ['-id']
        verbose_name        = 'Recibo'
        verbose_name_plural = 'Recibos'

    def __str__(self):
        return self.numero