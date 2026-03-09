from django.db import models


class Unidade(models.Model):
    nome = models.CharField(max_length=80)
    sigla = models.CharField(max_length=20)
    activo = models.BooleanField(default=True)
    ordem = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = 'unidades'
        ordering = ['ordem', 'nome']
        verbose_name = 'Unidade'
        verbose_name_plural = 'Unidades'

    def __str__(self):
        return f'{self.nome} ({self.sigla})'