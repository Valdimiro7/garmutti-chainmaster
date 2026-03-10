
from django.db import models

class DadoBancario(models.Model):
    banco       = models.CharField(max_length=150)
    moeda       = models.CharField(max_length=10, default='MZN')
    conta       = models.CharField(max_length=60, null=True, blank=True)
    nib         = models.CharField(max_length=60, null=True, blank=True)
    swift       = models.CharField(max_length=20, null=True, blank=True)
    iban        = models.CharField(max_length=40, null=True, blank=True)
    titular     = models.CharField(max_length=200, null=True, blank=True)
    predefinido = models.BooleanField(default=False)
    activo      = models.BooleanField(default=True)
    ordem       = models.IntegerField(default=0)

    class Meta:
        managed  = False
        db_table = 'dados_bancarios'
        ordering = ['ordem', 'banco']
        verbose_name        = 'Dado Bancário'
        verbose_name_plural = 'Dados Bancários'

    def __str__(self):
        return f'{self.banco} ({self.moeda})'

    @property
    def label_completo(self):
        partes = [self.banco, f'({self.moeda})']
        if self.conta:
            partes.append(f'Conta: {self.conta}')
        if self.nib:
            partes.append(f'NIB: {self.nib}')
        return ' | '.join(partes)