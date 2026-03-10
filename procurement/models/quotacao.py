from django.db import models
from django.contrib.auth.models import User
from .quotacaoestado import QuotacaoEstado
from .cliente import Cliente
from .rfq import RFQ
from .moeda import Moeda
from .condicaopagamento import CondicaoPagamento
from .dadobancario import DadoBancario


class Quotacao(models.Model):

    numero = models.CharField(max_length=30, unique=True)   # formato 018/2026

    # db_column='estado' — coluna na BD chama-se 'estado' (não 'estado_id')
    estado = models.ForeignKey(
        QuotacaoEstado,
        on_delete=models.DO_NOTHING,
        db_column='estado',
        related_name='quotacoes',
    )
    rfq = models.ForeignKey(
        RFQ,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column='rfq_id',
        related_name='quotacoes',
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.DO_NOTHING,
        db_column='cliente_id',
        related_name='quotacoes',
    )
    moeda = models.ForeignKey(
        Moeda,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column='moeda_id',
        related_name='quotacoes',
    )
    condicao_pagamento = models.ForeignKey(
        CondicaoPagamento,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column='condicao_pagamento_id',
        related_name='quotacoes',
    )

    # Dados bancários seleccionados (M2M via pivot)
    dados_bancarios = models.ManyToManyField(
        DadoBancario,
        through='QuotacaoDadoBancario',
        related_name='quotacoes',
        blank=True,
    )

    # Datas
    data_quotacao = models.DateField()
    validade      = models.DateField(null=True, blank=True)
    prazo_entrega = models.CharField(max_length=100, null=True, blank=True)

    # Entrega / Contacto
    local_entrega    = models.CharField(max_length=255, null=True, blank=True)
    pessoa_contacto  = models.CharField(max_length=120, null=True, blank=True)
    email_cliente    = models.EmailField(max_length=180, null=True, blank=True)
    telefone_cliente = models.CharField(max_length=30, null=True, blank=True)

    # Financeiro
    cambio          = models.DecimalField(max_digits=18, decimal_places=6, default=1)
    percentagem_iva = models.DecimalField(max_digits=5,  decimal_places=2, default=16)

    # Totais
    subtotal  = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_iva = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total     = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    # Refs / Obs
    referencia_cliente = models.CharField(max_length=120, null=True, blank=True)
    observacoes        = models.TextField(null=True, blank=True)

    # Auditoria
    criado_por = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column='criado_por',
        related_name='quotacoes_criadas',
    )
    criado_em      = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        managed  = False
        db_table = 'quotacoes'
        ordering = ['-id']
        verbose_name        = 'Quotação'
        verbose_name_plural = 'Quotações'

    def __str__(self):
        return self.numero