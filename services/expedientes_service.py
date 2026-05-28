from services.supabase_client import get_supabase_client


def _normalizar_numero(valor):
    solo_digitos = "".join(caracter for caracter in str(valor).strip() if caracter.isdigit())
    return solo_digitos.lstrip("0") or solo_digitos


def _normalizar_anio(valor):
    anio = str(valor).strip()
    return f"20{anio}" if len(anio) == 2 and anio.isdigit() else anio


def _variantes_anio(anio_expte):
    anio = str(anio_expte).strip()
    variantes = [anio]
    if len(anio) == 2 and anio.isdigit():
        variantes.append(f"20{anio}")
    elif len(anio) == 4 and anio.startswith("20"):
        variantes.append(anio[-2:])
    return list(dict.fromkeys(variantes))


def _buscar_por_anio_y_filtrar_numero(supabase, n_expte, anio_expte):
    numero_normalizado = _normalizar_numero(n_expte)
    anios_normalizados = {_normalizar_anio(anio) for anio in _variantes_anio(anio_expte)}

    for columna_anio in ["anio_expte", "año_expte"]:
        for anio in _variantes_anio(anio_expte):
            try:
                response = (
                    supabase.table("expedientes_base")
                    .select("*")
                    .eq(columna_anio, anio)
                    .execute()
                )
            except Exception as error:
                if "does not exist" in str(error):
                    break
                raise

            for expediente in response.data or []:
                anio_fila = expediente.get("anio_expte", expediente.get("año_expte"))
                if (
                    _normalizar_numero(expediente.get("n_expte")) == numero_normalizado
                    and _normalizar_anio(anio_fila) in anios_normalizados
                ):
                    return expediente

    return None


def buscar_expediente(n_expte, anio_expte):
    if not n_expte or not anio_expte:
        return None

    supabase = get_supabase_client()
    for columna_anio in ["anio_expte", "año_expte"]:
        for anio in _variantes_anio(anio_expte):
            try:
                response = (
                    supabase.table("expedientes_base")
                    .select("*")
                    .eq("n_expte", str(n_expte).strip())
                    .eq(columna_anio, anio)
                    .limit(1)
                    .execute()
                )
            except Exception as error:
                if "does not exist" in str(error):
                    break
                raise

            if response.data:
                return response.data[0]

    return _buscar_por_anio_y_filtrar_numero(supabase, n_expte, anio_expte)
