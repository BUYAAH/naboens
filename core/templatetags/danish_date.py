from django import template

register = template.Library()

_TRANSLATIONS = {
    # Full day names
    'Monday':    'Mandag',
    'Tuesday':   'Tirsdag',
    'Wednesday': 'Onsdag',
    'Thursday':  'Torsdag',
    'Friday':    'Fredag',
    'Saturday':  'Lørdag',
    'Sunday':    'Søndag',
    # Abbreviated day names
    'Mon': 'Man',
    'Tue': 'Tir',
    'Wed': 'Ons',
    'Thu': 'Tor',
    'Fri': 'Fre',
    'Sat': 'Lør',
    'Sun': 'Søn',
    # Full month names
    'January':   'januar',
    'February':  'februar',
    'March':     'marts',
    'April':     'april',
    'May':       'maj',
    'June':      'juni',
    'July':      'juli',
    'August':    'august',
    'September': 'september',
    'October':   'oktober',
    'November':  'november',
    'December':  'december',
    # Abbreviated month names
    'Jan': 'jan',
    'Feb': 'feb',
    'Mar': 'mar',
    'Apr': 'apr',
    'Jun': 'jun',
    'Jul': 'jul',
    'Aug': 'aug',
    'Sep': 'sep',
    'Oct': 'okt',
    'Nov': 'nov',
    'Dec': 'dec',
}


@register.filter
def da(value):
    """Translate English day/month names in a formatted date string to Danish.

    Usage: {{ some_date|date:"l d. F Y"|da }}
    """
    s = str(value)
    for english, danish in _TRANSLATIONS.items():
        s = s.replace(english, danish)
    return s
