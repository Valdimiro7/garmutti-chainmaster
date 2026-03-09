from django.db import models
from django.contrib.auth.models import User
from .rfq import RFQ


class RFQAnexo(models.Model):
    rfq = models.ForeignKey(
        RFQ,
        on_delete=models.CASCADE,
        db_column='rfq_id',
        related_name='anexos',
    )
    ficheiro = models.CharField(max_length=255)
    nome_original = models.CharField(max_length=255, null=True, blank=True)
    tamanho = models.BigIntegerField(null=True, blank=True)
    content_type = models.CharField(max_length=120, null=True, blank=True)

    carregado_por = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='carregado_por',
        related_name='rfq_anexos_carregados',
    )
    carregado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'rfq_anexos'
        ordering = ['-id']
        verbose_name = 'Anexo de RFQ'
        verbose_name_plural = 'Anexos de RFQ'

    def __str__(self):
        return self.nome_original or self.ficheiro