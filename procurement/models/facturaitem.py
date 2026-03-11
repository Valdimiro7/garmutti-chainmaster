from django.db import models
from .factura import Factura

class FacturaItem(models.Model):
    factura     = models.ForeignKey(
        Factura,
        on_delete=models.DO_NOTHING,
        db_column='factura_id',
        related_name='itens',
    )
    descricao   = models.CharField(max_length=500)
    unidade     = models.CharField(max_length=50, null=True, blank=True)
    quantidade  = models.DecimalField(max_digits=14, decimal_places=4, default=1)
    preco_unit  = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_linha = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    ordem       = models.IntegerField(default=0)

    class Meta:
        managed  = False
        db_table = 'factura_itens'
        ordering = ['ordem', 'id']
        verbose_name        = 'Item da Factura'
        verbose_name_plural = 'Itens da Factura'

    def __str__(self):
        return f'{self.factura.numero} — {self.descricao}'


