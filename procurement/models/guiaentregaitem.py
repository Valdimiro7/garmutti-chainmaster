from django.db import models
from .guiaentrega import GuiaEntrega


class GuiaEntregaItem(models.Model):
    guia_entrega = models.ForeignKey(
        GuiaEntrega,
        on_delete=models.CASCADE,
        db_column='guia_entrega_id',
        related_name='itens',
    )
    descricao = models.CharField(max_length=255)
    unidade = models.CharField(max_length=30, null=True, blank=True)
    quantidade = models.DecimalField(max_digits=18, decimal_places=4, default=1)
    preco_unit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_linha = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    ordem = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'guia_entrega_itens'
        ordering = ['ordem', 'id']
        verbose_name = 'Item da Guia'
        verbose_name_plural = 'Itens da Guia'

    def __str__(self):
        return self.descricao