from datetime import datetime

from django import forms

from .models import Pizza


class OrderForm(forms.Form):
    slot_time = forms.CharField(max_length=5,   label='Tidspunkt')
    name      = forms.CharField(max_length=100, label='Navn')
    phone     = forms.CharField(max_length=20,  label='Telefonnummer')

    def __init__(self, *args, pizzas=None, **kwargs):
        super().__init__(*args, **kwargs)
        if pizzas is None:
            pizzas = list(Pizza.objects.filter(is_active=True))
        self.pizzas = pizzas
        for pizza in self.pizzas:
            self.fields[f'pizza_{pizza.pk}'] = forms.IntegerField(
                min_value=0, max_value=4, initial=0, required=False,
                label=pizza.name,
            )

    def clean_slot_time(self):
        value = self.cleaned_data.get('slot_time', '').strip()
        try:
            datetime.strptime(value, '%H:%M')
        except ValueError:
            raise forms.ValidationError("Ugyldigt tidspunkt.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        total = sum(cleaned_data.get(f'pizza_{p.pk}', 0) or 0 for p in self.pizzas)
        if total == 0:
            raise forms.ValidationError("Vælg mindst én pizza.")
        if total > 4:
            raise forms.ValidationError("Du kan max bestille 4 pizzaer ad gangen.")
        cleaned_data['total_pizzas'] = total
        return cleaned_data
