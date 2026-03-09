from django.db import models


class Moeda(models.Model):
    codigo      = models.CharField(max_length=3, unique=True)
    nome        = models.CharField(max_length=80)
    simbolo     = models.CharField(max_length=10)
    pais        = models.CharField(max_length=100, null=True, blank=True)
    estado      = models.BooleanField(default=True)
    predefinida = models.BooleanField(default=False)
    criado_em   = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed  = False
        db_table = 'moedas'
        ordering = ['-predefinida', 'codigo']
        verbose_name        = 'Moeda'
        verbose_name_plural = 'Moedas'

    def __str__(self):
        return f'{self.codigo} – {self.nome}'