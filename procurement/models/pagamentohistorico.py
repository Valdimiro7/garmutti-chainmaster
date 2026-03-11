from django.db import models
from django.contrib.auth.models import User
from .pagamento import Pagamento
from .dadobancario import DadoBancario


class PagamentoHistorico(models.Model):

    pagamento = models.ForeignKey(
        Pagamento,
        on_delete=models.DO_NOTHING,
        db_column='pagamento_id',
        related_name='historico',
    )
    dado_bancario = models.ForeignKey(
        DadoBancario,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='dado_bancario_id',
        related_name='pagamento_historico',
    )
    
    factura = models.ForeignKey(
        'Factura',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='factura_id',
        related_name='pagamento_historicos',
    )

    valor_pago = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    data_pagamento = models.DateField()
    referencia = models.CharField(max_length=120, null=True, blank=True)
    banco_origem = models.CharField(max_length=150, null=True, blank=True)
    numero_transaccao = models.CharField(max_length=120, null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)

    registado_por = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='registado_por',
        related_name='pagamento_historicos',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'pagamento_historico'
        ordering = ['-criado_em']
        verbose_name = 'Histórico de Pagamento'
        verbose_name_plural = 'Histórico de Pagamentos'

    def __str__(self):
        return f'{self.pagamento.numero} — {self.valor_pago} em {self.data_pagamento}'