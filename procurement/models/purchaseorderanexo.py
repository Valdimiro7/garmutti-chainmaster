from django.db import models
from .purchaseorder import PurchaseOrder


class PurchaseOrderAnexo(models.Model):
    TIPO_CHOICES = [
        ('po', 'PO'),
        ('email', 'Conversa de Email'),
        ('outro', 'Outro'),
    ]

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.DO_NOTHING,
        db_column='purchase_order_id',
        related_name='anexos',
    )
    tipo_anexo = models.CharField(max_length=30, choices=TIPO_CHOICES, default='po')
    nome_ficheiro = models.CharField(max_length=255)
    ficheiro = models.FileField(upload_to='purchase_orders/')
    observacao = models.CharField(max_length=255, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'purchase_order_anexos'
        ordering = ['id']