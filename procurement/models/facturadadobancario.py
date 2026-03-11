from django.db import models
from .factura import Factura
from .dadobancario import DadoBancario


class FacturaDadoBancario(models.Model):
    factura = models.ForeignKey(
        Factura,
        on_delete=models.DO_NOTHING,
        db_column='factura_id',
        related_name='factura_dados_bancarios',
    )
    dado_bancario = models.ForeignKey(
        DadoBancario,
        on_delete=models.DO_NOTHING,
        db_column='dado_bancario_id',
        related_name='factura_dados_bancarios',
    )
    ordem = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'factura_dado_bancario'
        ordering = ['ordem', 'id']
        verbose_name = 'Conta Bancária da Factura'
        verbose_name_plural = 'Contas Bancárias da Factura'

    def __str__(self):
        return f'{self.factura.numero} - {self.dado_bancario}'