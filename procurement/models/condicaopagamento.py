from django.db import models

class CondicaoPagamento(models.Model):
    nome      = models.CharField(max_length=120)
    descricao = models.TextField(null=True, blank=True)   # termos e condições
    activo    = models.BooleanField(default=True)
    ordem     = models.IntegerField(default=0)

    class Meta:
        managed  = False
        db_table = 'condicoes_pagamento'
        ordering = ['ordem', 'nome']
        verbose_name        = 'Condição de Pagamento'
        verbose_name_plural = 'Condições de Pagamento'

    def __str__(self):
        return self.nome