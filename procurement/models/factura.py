from django.db import models
from django.contrib.auth.models import User
from .purchaseorder import PurchaseOrder
from .quotacao import Quotacao
from .cliente import Cliente
from .moeda import Moeda
from .dadobancario import DadoBancario
from .facturaestado import FacturaEstado


class Factura(models.Model):
    numero = models.CharField(max_length=30, unique=True)

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column='purchase_order_id',
        related_name='facturas',
    )
    quotacao = models.ForeignKey(
        Quotacao,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column='quotacao_id',
        related_name='facturas',
    )
    estado = models.ForeignKey(
        FacturaEstado,
        on_delete=models.DO_NOTHING,
        db_column='estado_id',
        related_name='facturas',
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.DO_NOTHING,
        db_column='cliente_id',
        related_name='facturas',
    )
    moeda = models.ForeignKey(
        Moeda,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column='moeda_id',
        related_name='facturas',
    )

    # Mantido por compatibilidade, mas o sistema passará a usar factura_dado_bancario
    dado_bancario = models.ForeignKey(
        DadoBancario,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column='dado_bancario_id',
        related_name='facturas',
    )

    data_emissao = models.DateField()
    data_vencimento = models.DateField(null=True, blank=True)

    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    desconto = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    desconto_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    iva_pct = models.DecimalField(max_digits=5, decimal_places=2, default=16)
    iva_valor = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    observacoes = models.TextField(null=True, blank=True)
    termos = models.TextField(null=True, blank=True)

    pdf_gerado = models.FileField(upload_to='facturas/pdf/', null=True, blank=True)

    criado_por = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column='criado_por',
        related_name='facturas_criadas',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'facturas'
        ordering = ['-id']
        verbose_name = 'Factura'
        verbose_name_plural = 'Facturas'

    def __str__(self):
        return self.numero
