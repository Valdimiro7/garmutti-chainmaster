from django.db import models
from django.contrib.auth.models import User
from .cliente import Cliente
from .rfq_estado import RFQEstado


class RFQ(models.Model):
    ORIGEM_CHOICES = [
        ('manual', 'Manual'),
        ('api', 'API / Website'),
    ]

    numero = models.CharField(max_length=30, unique=True)
    origem = models.CharField(max_length=20, choices=ORIGEM_CHOICES, default='manual')

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.DO_NOTHING,
        db_column='cliente_id',
        related_name='rfqs',
    )
    estado = models.ForeignKey(
        RFQEstado,
        on_delete=models.DO_NOTHING,
        db_column='estado_id',
        related_name='rfqs',
    )

    data_rfq = models.DateField()
    prazo_entrega = models.DateField(null=True, blank=True)
    local_entrega = models.CharField(max_length=255, null=True, blank=True)

    email_cliente = models.EmailField(max_length=180, null=True, blank=True)
    telefone_cliente = models.CharField(max_length=30, null=True, blank=True)
    pessoa_contacto = models.CharField(max_length=120, null=True, blank=True)

    referencia_externa = models.CharField(max_length=120, null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)

    criado_por = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='criado_por',
        related_name='rfqs_criados',
    )
    criado_em = models.DateTimeField(null=True, blank=True)
    actualizado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'rfqs'
        ordering = ['-id']
        verbose_name = 'RFQ'
        verbose_name_plural = 'RFQs'

    def __str__(self):
        return self.numero