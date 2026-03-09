from django.db import models


class Organizacao(models.Model):
    nome = models.CharField(max_length=200)
    slogan = models.CharField(max_length=255, null=True, blank=True)
    nuit = models.CharField(max_length=30, null=True, blank=True)
    email = models.EmailField(max_length=180, null=True, blank=True)
    telefone_1 = models.CharField(max_length=30, null=True, blank=True)
    telefone_2 = models.CharField(max_length=30, null=True, blank=True)
    website = models.CharField(max_length=200, null=True, blank=True)
    endereco = models.CharField(max_length=255, null=True, blank=True)
    cidade = models.CharField(max_length=120, null=True, blank=True)
    pais = models.CharField(max_length=120, default='Moçambique')
    logo = models.CharField(max_length=255, null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(null=True, blank=True)
    actualizado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'organizacao'
        verbose_name = 'Organização'
        verbose_name_plural = 'Organização'

    def __str__(self):
        return self.nome