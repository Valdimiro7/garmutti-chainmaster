from django.db import models


class PagamentoEstado(models.Model):
    nome = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50)
    cor = models.CharField(max_length=20, null=True, blank=True, default='#2E3E82')
    ordem = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'pagamento_estados'
        ordering = ['ordem', 'nome']
        verbose_name = 'Estado do Pagamento'
        verbose_name_plural = 'Estados de Pagamento'

    def __str__(self):
        return self.nome