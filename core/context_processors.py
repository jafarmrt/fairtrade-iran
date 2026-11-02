from django.utils.translation import get_language, get_language_bidi


def site_context(request):
    lang = (get_language() or "fa")[:2]
    return {
        "LANG": lang,
        "IS_EN": lang == "en",
        "DIR": "rtl" if get_language_bidi() else "ltr",
    }
