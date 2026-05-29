def texto(valor):
    return "" if valor is None else str(valor)


def limpiar(valor):
    return texto(valor).strip()


def normalizar_estado_cierre(estado, vista="operativa"):
    estado_limpio = limpiar(estado)
    if not estado_limpio:
        return estado_limpio

    if vista == "global":
        if estado_limpio == "Entregado":
            return "Cerrado"
    return estado_limpio


def es_cierre_positivo(estado):
    estado_limpio = limpiar(estado)
    return estado_limpio in {"Entregado", "Cerrado"}


def es_cierre_negativo(estado):
    return limpiar(estado) == "Cancelado"
