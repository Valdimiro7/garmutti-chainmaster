from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django import template

register = template.Library()


@register.filter
def contabil(value):
    """
    Formata:
    1000 -> 1.000,00
    25450.7 -> 25.450,70
    """
    if value in (None, ""):
        return "0,00"

    try:
        value = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return "0,00"

    value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    negativo = value < 0
    value = abs(value)

    texto = f"{value:.2f}"
    inteiro, decimal = texto.split(".")

    grupos = []
    while inteiro:
        grupos.append(inteiro[-3:])
        inteiro = inteiro[:-3]

    inteiro_formatado = ".".join(reversed(grupos))
    resultado = f"{inteiro_formatado},{decimal}"

    if negativo:
        resultado = f"-{resultado}"

    return resultado