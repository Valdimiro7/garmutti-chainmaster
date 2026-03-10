from django.db import models
from .unidade import Unidade
from .quotacao import Quotacao

class QuotacaoItem(models.Model):

    quotacao = models.ForeignKey(
        Quotacao,
        on_delete=models.CASCADE,
        db_column='quotacao_id',
        related_name='itens',
    )
    linha           = models.IntegerField(default=1)
    descricao       = models.CharField(max_length=500)
    quantidade      = models.DecimalField(max_digits=18, decimal_places=2, default=1)
    unidade         = models.ForeignKey(
        Unidade,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='unidade_id',
        related_name='quotacao_itens',
    )
    preco_unitario  = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    percentagem_iva = models.DecimalField(max_digits=5, decimal_places=2, default=16)
    total_liquido   = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    comentarios     = models.CharField(max_length=255, null=True, blank=True)
    especificacoes  = models.TextField(null=True, blank=True)

    class Meta:
        managed  = False
        db_table = 'quotacao_itens'
        ordering = ['linha', 'id']
        verbose_name        = 'Item da Quotação'
        verbose_name_plural = 'Itens da Quotação'

    def __str__(self):
        return f'{self.quotacao.numero} – Item {self.linha}'

    def save(self, *args, **kwargs):
        self.total_liquido = self.quantidade * self.preco_unitario
        super().save(*args, **kwargs)