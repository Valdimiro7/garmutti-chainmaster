from django.db import models


class RFQEstado(models.Model):
    nome = models.CharField(max_length=80)
    codigo = models.CharField(max_length=40)
    cor = models.CharField(max_length=20, default='#6c757d')
    ordem = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'rfq_estados'
        ordering = ['ordem', 'nome']
        verbose_name = 'Estado de RFQ'
        verbose_name_plural = 'Estados de RFQ'

    def __str__(self):
        return self.nome