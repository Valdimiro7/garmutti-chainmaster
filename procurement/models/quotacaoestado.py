from django.db import models

# ──────────────────────────────────────────────────────────────────────────────
# Estado da Quotação  (tabela DB)
# ──────────────────────────────────────────────────────────────────────────────
class QuotacaoEstado(models.Model):
    codigo = models.CharField(max_length=30, unique=True)
    nome   = models.CharField(max_length=80)
    cor    = models.CharField(max_length=10, default='#6c757d')
    ordem  = models.IntegerField(default=0)

    class Meta:
        managed  = False
        db_table = 'quotacao_estados'
        ordering = ['ordem']
        verbose_name        = 'Estado de Quotação'
        verbose_name_plural = 'Estados de Quotação'

    def __str__(self):
        return self.nome