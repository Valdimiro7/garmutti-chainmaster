from django.db import models
from .rfq import RFQ
from .unidade import Unidade


class RFQItem(models.Model):
    rfq = models.ForeignKey(
        RFQ,
        on_delete=models.CASCADE,
        db_column='rfq_id',
        related_name='itens',
    )
    linha = models.IntegerField(default=1)
    descricao = models.CharField(max_length=255)
    quantidade = models.DecimalField(max_digits=18, decimal_places=2, default=1)
    unidade = models.ForeignKey(
        Unidade,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='unidade_id',
        related_name='rfq_itens',
    )
    comentarios = models.CharField(max_length=255, null=True, blank=True)
    especificacoes = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'rfq_itens'
        ordering = ['linha', 'id']
        verbose_name = 'Item do RFQ'
        verbose_name_plural = 'Itens do RFQ'

    def __str__(self):
        return f'{self.rfq.numero} - Item {self.linha}'