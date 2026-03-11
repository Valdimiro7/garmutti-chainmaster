from django.db import models


class GuiaEstado(models.Model):
    nome = models.CharField(max_length=80)
    codigo = models.CharField(max_length=40, unique=True)
    cor = models.CharField(max_length=20, default='#2E3E82')
    activo = models.BooleanField(default=True)
    ordem = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'guia_estados'
        ordering = ['ordem', 'nome']
        verbose_name = 'Estado da Guia'
        verbose_name_plural = 'Estados das Guias'

    def __str__(self):
        return self.nome