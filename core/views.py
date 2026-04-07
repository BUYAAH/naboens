import json
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import OpeningDay, Order, OrderItem, Pizza
from .forms import OrderForm


def _next_opening():
    return OpeningDay.objects.filter(is_published=True, date__gte=timezone.localdate()).first()


def _pizzas_json(pizzas):
    return json.dumps([
        {
            'id':          p.pk,
            'name':        p.name,
            'description': p.description,
            'price':       p.price,
            'field':       f'pizza_{p.pk}',
        }
        for p in pizzas
    ])


def index(request):
    opening_days = OpeningDay.objects.filter(
        is_published=True, date__gte=timezone.localdate()
    ).order_by('date', 'start_time')
    return render(request, "index.html", {
        'upcoming':     opening_days.first(),
        'opening_days': opening_days,
        'pizzas':       Pizza.objects.filter(is_active=True),
    })



def bestil2(request):
    opening = _next_opening()
    pizzas  = list(Pizza.objects.filter(is_active=True))

    if not opening:
        return render(request, "bestil2.html", {'opening': None})

    start_dt      = datetime.combine(opening.date, opening.start_time)
    close_dt      = datetime.combine(opening.date, opening.close_time)
    total_minutes = int((close_dt - start_dt).total_seconds() / 60)

    taken_offsets = set()
    for order in opening.orders.all():
        order_start = datetime.combine(opening.date, order.pickup_time)
        offset = int((order_start - start_dt).total_seconds() / 60)
        for i in range(order.total_pizzas):
            taken_offsets.add(offset + i * 5)

    timeline_json = json.dumps({
        'total_minutes': total_minutes,
        'taken_offsets': sorted(taken_offsets),
        'start_hour':    opening.start_time.hour,
        'start_minute':  opening.start_time.minute,
    })

    if request.method == 'POST':
        form = OrderForm(request.POST, pizzas=pizzas)
        if form.is_valid():
            data          = form.cleaned_data
            total         = data['total_pizzas']
            slot_time_str = data['slot_time']
            slot_time     = datetime.strptime(slot_time_str, '%H:%M').time()

            slot_start = datetime.combine(opening.date, slot_time)
            offset     = int((slot_start - start_dt).total_seconds() / 60)
            needed     = {offset + i * 5 for i in range(total)}

            if needed & taken_offsets:
                form.add_error('slot_time', 'Desværre er det valgte tidspunkt ikke længere ledigt — prøv et andet.')
            else:
                order = Order.objects.create(
                    opening_day=opening,
                    name=data['name'],
                    phone=data['phone'],
                    pickup_time=slot_time,
                    total_pizzas=total,
                )
                for pizza in pizzas:
                    qty = data.get(f'pizza_{pizza.pk}') or 0
                    if qty > 0:
                        OrderItem.objects.create(order=order, pizza=pizza, quantity=qty)
                return redirect('bekraeftelse', pk=order.pk)
    else:
        form = OrderForm(pizzas=pizzas)

    pizzas_with_fields = [
        {'pizza': p, 'field': form[f'pizza_{p.pk}']}
        for p in pizzas
    ]

    return render(request, "bestil2.html", {
        'opening':            opening,
        'form':               form,
        'timeline_json':      timeline_json,
        'pizzas_json':        _pizzas_json(pizzas),
        'pizzas_with_fields': pizzas_with_fields,
    })


@login_required
def dashboard(request):
    today = timezone.localdate()
    upcoming = OpeningDay.objects.filter(date__gte=today).order_by('date', 'start_time')
    past     = OpeningDay.objects.filter(date__lt=today).order_by('-date', '-start_time')
    return render(request, "dashboard.html", {'upcoming': upcoming, 'past': past})


@login_required
def opening_day(request, pk):
    opening = get_object_or_404(OpeningDay, pk=pk)
    orders  = opening.orders.prefetch_related(
        'items__pizza__pizza_ingredients__ingredient'
    ).order_by('pickup_time')

    # Per-pizza totals
    pizza_totals = {}
    for order in orders:
        for item in order.items.all():
            pizza_totals[item.pizza] = pizza_totals.get(item.pizza, 0) + item.quantity

    # Ingredient shopping list
    from collections import defaultdict
    ingredient_totals = defaultdict(float)
    for order in orders:
        for item in order.items.all():
            for pi in item.pizza.pizza_ingredients.select_related('ingredient').all():
                key = (pi.ingredient.name, pi.ingredient.unit)
                ingredient_totals[key] += float(pi.quantity) * item.quantity
    ingredient_totals = sorted(ingredient_totals.items())  # [((name, unit), qty), …]

    # Capacity
    from datetime import datetime as dt
    start_dt  = dt.combine(opening.date, opening.start_time)
    close_dt  = dt.combine(opening.date, opening.close_time)
    total_cap = int((close_dt - start_dt).total_seconds() / 60) // 5
    total_tak = opening.total_pizzas_ordered()
    capacity_pct = int(total_tak / total_cap * 100) if total_cap else 0

    pizza_financials = [
        {
            'pizza':   pizza,
            'qty':     qty,
            'revenue': pizza.price * qty,
            'cost':    pizza.cost * qty if pizza.cost is not None else None,
            'profit':  pizza.margin * qty if pizza.margin is not None else None,
        }
        for pizza, qty in pizza_totals.items()
    ]
    total_revenue = sum(r['revenue'] for r in pizza_financials)
    total_cost    = sum(r['cost']    for r in pizza_financials if r['cost']   is not None)
    total_profit  = sum(r['profit']  for r in pizza_financials if r['profit'] is not None)
    cost_known    = any(r['cost'] is not None for r in pizza_financials)

    return render(request, "dag.html", {
        'opening':           opening,
        'orders':            orders,
        'pizza_totals':      pizza_totals,
        'pizza_financials':  pizza_financials,
        'ingredient_totals': ingredient_totals,
        'total_cap':         total_cap,
        'total_tak':         total_tak,
        'capacity_pct':      capacity_pct,
        'total_revenue':     total_revenue,
        'total_cost':        total_cost,
        'total_profit':      total_profit,
        'cost_known':        cost_known,
    })


def bekraeftelse(request, pk):
    order = get_object_or_404(Order, pk=pk)
    total_price = sum(item.quantity * item.pizza.price for item in order.items.all())
    return render(request, "bekraeftelse.html", {'order': order, 'total_price': total_price})
