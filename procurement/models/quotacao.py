from django.db import models
from django.contrib.auth.models import User
from .cliente import Cliente
from .rfq import RFQ
from .moeda import Moeda



class Quotacao(models.Model):

    ESTADO_CHOICES = [
        ('rascunho',  'Rascunho'),
        ('enviada',   'Enviada'),
        ('aceite',    'Aceite'),
        ('recusada',  'Recusada'),
        ('expirada',  'Expirada'),
        ('cancelada', 'Cancelada'),
    ]

    # ── Identificação ──────────────────────────────────────────────────────────
    numero  = models.CharField(max_length=30, unique=True)
    estado  = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='rascunho')

    # ── Relações ───────────────────────────────────────────────────────────────
    rfq = models.ForeignKey(
        RFQ,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='rfq_id',
        related_name='quotacoes',
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.DO_NOTHING,
        db_column='cliente_id',
        related_name='quotacoes',
    )
    moeda = models.ForeignKey(
        Moeda,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='moeda_id',
        related_name='quotacoes',
    )

    # ── Datas ──────────────────────────────────────────────────────────────────
    data_quotacao = models.DateField()
    validade      = models.DateField(null=True, blank=True)
    prazo_entrega = models.CharField(max_length=100, null=True, blank=True)

    # ── Entrega / Contacto ────────────────────────────────────────────────────
    local_entrega    = models.CharField(max_length=255, null=True, blank=True)
    pessoa_contacto  = models.CharField(max_length=120, null=True, blank=True)
    email_cliente    = models.EmailField(max_length=180, null=True, blank=True)
    telefone_cliente = models.CharField(max_length=30, null=True, blank=True)

    # ── Financeiro ────────────────────────────────────────────────────────────
    cambio              = models.DecimalField(max_digits=18, decimal_places=6, default=1)
    percentagem_iva     = models.DecimalField(max_digits=5, decimal_places=2, default=16)
    pagamento_condicoes = models.CharField(max_length=100, null=True, blank=True)
    entidade            = models.CharField(max_length=100, null=True, blank=True)

    subtotal  = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_iva = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total     = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    # ── Referências / Obs ─────────────────────────────────────────────────────
    referencia_cliente = models.CharField(max_length=120, null=True, blank=True)
    observacoes        = models.TextField(null=True, blank=True)
    termos_condicoes   = models.TextField(null=True, blank=True)

    # ── Auditoria ─────────────────────────────────────────────────────────────
    criado_por = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='criado_por',
        related_name='quotacoes_criadas',
    )
    criado_em      = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        managed  = False
        db_table = 'quotacoes'
        ordering = ['-id']
        verbose_name        = 'Quotação'
        verbose_name_plural = 'Quotações'

    def __str__(self):
        return self.numero

    # Cor do estado para badge no template
    @property
    def estado_cor(self):
        cores = {
            'rascunho':  '#6c757d',
            'enviada':   '#0d6efd',
            'aceite':    '#198754',
            'recusada':  '#dc3545',
            'expirada':  '#fd7e14',
            'cancelada': '#adb5bd',
        }
        return cores.get(self.estado, '#6c757d')

    @property
    def estado_label(self):
        return dict(self.ESTADO_CHOICES).get(self.estado, self.estado)
