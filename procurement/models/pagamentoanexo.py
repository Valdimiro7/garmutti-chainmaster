from django.db import models
from .pagamento import Pagamento


class PagamentoAnexo(models.Model):
    TIPO_CHOICES = [
        ('pop', 'POP'),
        ('comprovativo', 'Comprovativo'),
        ('recibo', 'Recibo'),
        ('outro', 'Outro'),
    ]

    pagamento = models.ForeignKey(
        Pagamento,
        on_delete=models.DO_NOTHING,
        db_column='pagamento_id',
        related_name='anexos',
    )
    tipo_anexo = models.CharField(max_length=30, choices=TIPO_CHOICES, default='pop')
    nome_ficheiro = models.CharField(max_length=255)
    ficheiro = models.FileField(upload_to='pagamentos/')
    observacao = models.CharField(max_length=255, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'pagamento_anexos'
        ordering = ['id']
        verbose_name = 'Anexo do Pagamento'
        verbose_name_plural = 'Anexos dos Pagamentos'

    def __str__(self):
        return f'{self.pagamento.numero} - {self.nome_ficheiro}'