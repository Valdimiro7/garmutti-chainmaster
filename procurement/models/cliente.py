from django.db import models
from django.contrib.auth.models import User
from .moeda import Moeda

class Cliente(models.Model):

    TIPO_CHOICES = [
        ('Singular',  'Pessoa Singular'),
        ('Colectivo', 'Pessoa Colectiva'),
    ]

    CATEGORIA_CHOICES = [
        ('A', 'A – Premium'),
        ('B', 'B – Normal'),
        ('C', 'C – Ocasional'),
    ]

    # ── Identificação ──────────────────────────────────────────────────────────
    nome               = models.CharField(max_length=200)
    tipo               = models.CharField(max_length=10, choices=TIPO_CHOICES, default='Colectivo')
    nuit               = models.CharField(max_length=20, unique=True, null=True, blank=True)
    bi_nid             = models.CharField(max_length=30, null=True, blank=True)
    alvara             = models.CharField(max_length=60, null=True, blank=True)
    sector_actividade  = models.CharField(max_length=120, null=True, blank=True)

    # ── Contactos ──────────────────────────────────────────────────────────────
    email              = models.EmailField(max_length=180, null=True, blank=True)
    telefone           = models.CharField(max_length=20, null=True, blank=True)
    telemovel          = models.CharField(max_length=20, null=True, blank=True)
    website            = models.URLField(max_length=200, null=True, blank=True)
    pessoa_contacto    = models.CharField(max_length=120, null=True, blank=True)

    # ── Morada ─────────────────────────────────────────────────────────────────
    provincia          = models.CharField(max_length=80, null=True, blank=True)
    cidade_distrito    = models.CharField(max_length=80, null=True, blank=True)
    bairro             = models.CharField(max_length=100, null=True, blank=True)
    endereco           = models.CharField(max_length=255, null=True, blank=True)
    codigo_postal      = models.CharField(max_length=10, null=True, blank=True)
    pais               = models.CharField(max_length=80, default='Moçambique')

    # ── Financeiro / Comercial ─────────────────────────────────────────────────
    moeda = models.ForeignKey(
        Moeda,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='moeda_id',
        related_name='clientes',
    )
    limite_credito       = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    prazo_pagamento_dias = models.PositiveSmallIntegerField(default=30)
    desconto_geral       = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    conta_bancaria       = models.CharField(max_length=30, null=True, blank=True)
    banco                = models.CharField(max_length=100, null=True, blank=True)

    # ── Estado e classificação ─────────────────────────────────────────────────
    categoria    = models.CharField(max_length=1, choices=CATEGORIA_CHOICES, default='B')
    estado       = models.BooleanField(default=True)
    observacoes  = models.TextField(null=True, blank=True)

    # ── Auditoria ──────────────────────────────────────────────────────────────
    criado_por = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='criado_por',
        related_name='clientes_criados',
    )
    criado_em      = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        managed  = False
        db_table = 'clientes'
        ordering = ['nome']
        verbose_name        = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return self.nome

    @property
    def iniciais(self):
        partes = self.nome.strip().split()
        if len(partes) >= 2:
            return (partes[0][0] + partes[-1][0]).upper()
        return self.nome[:2].upper()