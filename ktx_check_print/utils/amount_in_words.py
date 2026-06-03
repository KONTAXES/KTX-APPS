# -*- coding: utf-8 -*-
import unicodedata


def _strip_accents(text):
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


def amount_to_words_es(amount):
    """
    Convierte un monto numérico a letras en español (sin nombre de moneda).
    1500.75  -> 'UN MIL QUINIENTOS CON 75/100'
    1000.00  -> 'UN MIL CON 00/100'
    193809.89 -> 'CIENTO NOVENTA Y TRES MIL OCHOCIENTOS NUEVE CON 89/100'
    """
    try:
        from num2words import num2words as _num2words
        int_part = int(amount)
        dec_part = round((float(amount) - int_part) * 100)
        if dec_part >= 100:
            int_part += 1
            dec_part = 0
        words = _num2words(int_part, lang='es')
        words = _strip_accents(words).upper()
        # num2words uses 'UN' in compounds but 'UNO' standalone — normalize
        if words == 'UNO':
            words = 'UN'
        return '{} CON {:02d}/100'.format(words, dec_part)
    except Exception:
        int_part = int(amount)
        dec_part = round((float(amount) - int_part) * 100)
        return '{:,d} CON {:02d}/100'.format(int_part, dec_part)
