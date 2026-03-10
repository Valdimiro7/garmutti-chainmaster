from django.db import models


class POEstado(models.Model):
    nome = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50)
    cor = models.CharField(max_length=20, null=True, blank=True, default='#2E3E82')
    ordem = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'po_estados'
        ordering = ['ordem', 'nome']
        verbose_name = 'Estado da PO'
        verbose_name_plural = 'Estados das POs'

    def __str__(self):
        return self.nome