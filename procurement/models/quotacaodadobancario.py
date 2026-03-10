from django.db import models
from .quotacao import Quotacao
from .dadobancario import DadoBancario

class QuotacaoDadoBancario(models.Model):
    quotacao      = models.ForeignKey(Quotacao,    on_delete=models.CASCADE,  db_column='quotacao_id')
    dado_bancario = models.ForeignKey(DadoBancario, on_delete=models.CASCADE, db_column='dado_bancario_id')

    class Meta:
        managed  = False
        db_table = 'quotacao_dados_bancarios'
        unique_together = ('quotacao', 'dado_bancario')
