from django import template

register = template.Library()

@register.filter
def replace(value, arg):
    # Replaces all occurrences of the first part of arg with the second
    try:
        old, new = arg.split(',')
        return value.replace(old, new)
    except ValueError:
        return value


@register.filter
def title(value):
    if not isinstance(value, str):
        return value
    return value.title()


@register.filter
def get_item(dictionary, key):
    """Access dictionary item by variable key in templates"""
    value = dictionary.get(key, '')
    if key == 'client_name':
        return title(value)
    if key == 'loan_tenor':
        try:
            # Round and append 'M' (months)
            return f"{round(float(value), 0):.0f} M"
        except (ValueError, TypeError):
            return value
    if key in ['loan_amount','total_ecl','capital_balance','arrears_amount','exposure']:
        try:
            return f"{float(value):,.2f}"
        except (ValueError, TypeError):
            return value
    if key in ['model_pd','final_pd','ltpd_yr1','ltpd_yr2','ltpd_yr3','ltpd_yr4','ltpd_yr5','computed_lgd']:
        try:
            return f"{float(value):,.6f}"
        except (ValueError, TypeError):
            return value
    if key == 'days_past_due':
        try:
            return f"{float(value):,.0f}"
        except (ValueError, TypeError):
            return value
    return value