from django.db import models


class QuotacaoDescricaoSugerida(models.Model):
    descricao = models.CharField(max_length=500, unique=True)
    vezes     = models.PositiveIntegerField(default=1)

    class Meta:
        managed  = False
        db_table = 'quotacao_descricoes_sugeridas'
        ordering = ['-vezes', 'descricao']
        verbose_name        = 'Descrição Sugerida'
        verbose_name_plural = 'Descrições Sugeridas'

    def __str__(self):
        return self.descricao