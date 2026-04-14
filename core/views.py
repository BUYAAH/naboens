import json
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Extra, ExtraOrderItem, OpeningDay, Order, OrderItem, OrderStatusLog, Pizza
from .forms import OrderForm
from .templatetags.danish_date import _TRANSLATIONS


def _danish_date(date):
    s = date.strftime('%A d. %-d. %B %Y')
    for en, da in _TRANSLATIONS.items():
        s = s.replace(en, da)
    return s


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


def _extras_json(extras):
    return json.dumps([
        {
            'id':          e.pk,
            'name':        e.name,
            'description': e.description,
            'price':       e.price,
            'field':       f'extra_{e.pk}',
        }
        for e in extras
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



def bestil(request):
    opening = _next_opening()
    pizzas  = list(Pizza.objects.filter(is_active=True))
    extras  = list(Extra.objects.filter(is_active=True))

    if not opening:
        return render(request, "bestil.html", {'opening': None})

    start_dt      = datetime.combine(opening.date, opening.start_time)
    close_dt      = datetime.combine(opening.date, opening.close_time)
    total_minutes = int((close_dt - start_dt).total_seconds() / 60)

    taken_slots = {
        order.pickup_time.strftime('%H:%M')
        for order in opening.orders.all()
    }

    timeline_json = json.dumps({
        'total_minutes': total_minutes,
        'taken_slots':   sorted(taken_slots),
        'start_hour':    opening.start_time.hour,
        'start_minute':  opening.start_time.minute,
    })

    if request.method == 'POST':
        form = OrderForm(request.POST, pizzas=pizzas, extras=extras)
        if form.is_valid():
            data          = form.cleaned_data
            total         = data['total_pizzas']
            slot_time_str = data['slot_time']
            pickup_time   = datetime.strptime(slot_time_str, '%H:%M').time()

            if slot_time_str in taken_slots:
                form.add_error('slot_time', 'Desværre er det valgte tidspunkt ikke længere ledigt — prøv et andet.')
            else:
                order = Order.objects.create(
                    opening_day=opening,
                    name=data['name'],
                    email=data.get('email', ''),
                    phone=data['phone'],
                    pickup_time=pickup_time,
                    total_pizzas=total,
                )
                for pizza in pizzas:
                    qty = data.get(f'pizza_{pizza.pk}') or 0
                    if qty > 0:
                        OrderItem.objects.create(order=order, pizza=pizza, quantity=qty)
                for extra in extras:
                    qty = data.get(f'extra_{extra.pk}') or 0
                    if qty > 0:
                        ExtraOrderItem.objects.create(order=order, extra=extra, quantity=qty)

                items       = list(order.items.select_related('pizza').all())
                extra_items = list(order.extra_items.select_related('extra').all())
                pizza_lines = '\n'.join(f'  {item.quantity}× {item.pizza.name} ({item.quantity * item.pizza.price} kr)' for item in items)
                extra_lines = '\n'.join(f'  {item.quantity}× {item.extra.name} ({item.quantity * item.extra.price} kr)' for item in extra_items)
                lines       = pizza_lines + ('\n' + extra_lines if extra_lines else '')
                total_price = sum(item.quantity * item.pizza.price for item in items) + sum(item.quantity * item.extra.price for item in extra_items)

                all_orders = opening.orders.prefetch_related('items__pizza', 'extra_items__extra').order_by('pickup_time')
                day_lines = []
                for o in all_orders:
                    o_parts = [f'{i.quantity}× {i.pizza.name}' for i in o.items.all()]
                    o_parts += [f'{i.quantity}× {i.extra.name}' for i in o.extra_items.all()]
                    day_lines.append(f'  kl. {o.pickup_time.strftime("%H:%M")}  {o.name} ({o.phone})  —  {", ".join(o_parts)}')
                day_summary = '\n'.join(day_lines) if day_lines else '  Ingen andre ordrer endnu.'

                try:
                    send_mail(
                        subject=f'Ny bestilling #{order.id} — {order.name} kl. {slot_time_str}',
                        message=(
                            f'Ny bestilling modtaget!\n\n'
                            f'#{order.id}  {order.name}  ·  {order.phone}\n'
                            f'Afhentning: kl. {slot_time_str}\n\n'
                            f'{lines}\n'
                            f'I alt: {total_price} kr\n\n'
                            f'{"─" * 40}\n'
                            f'Alle ordrer på {opening.date.strftime("%-d/%-m")}:\n'
                            f'{day_summary}\n'
                        ),
                        from_email=None,
                        recipient_list=['naboenspizza@gmail.com'],
                        fail_silently=True,
                    )
                except Exception:
                    pass

                if order.email:
                    try:
                        send_mail(
                            subject=f'Bestilling #{order.id} modtaget — Naboens Pizza',
                            message=(
                                f'Hej {order.name},\n\n'
                                f'Din bestilling er modtaget!\n\n'
                                f'Ordrenr.: #{order.id}\n'
                                f'Dato: {_danish_date(opening.date)}\n'
                                f'Afhentning: kl. {slot_time_str} på Tranevej 50, Grindsted\n\n'
                                f'Du har bestilt:\n{lines}\n\n'
                                f'I alt: {total_price} kr\n'
                                f'Betaling: Kort eller MobilePay ved afhentning\n\n'
                                f'Vi ses!\n— Naboens Pizza'
                            ),
                            from_email=None,
                            recipient_list=[order.email],
                            fail_silently=True,
                        )
                    except Exception:
                        pass

                return redirect('bekraeftelse', pk=order.pk)
    else:
        form = OrderForm(pizzas=pizzas, extras=extras)

    pizzas_with_fields = [
        {'pizza': p, 'field': form[f'pizza_{p.pk}']}
        for p in pizzas
    ]
    extras_with_fields = [
        {'extra': e, 'field': form[f'extra_{e.pk}']}
        for e in extras
    ]

    return render(request, "bestil.html", {
        'opening':            opening,
        'is_today':           opening.date == timezone.localdate(),
        'form':               form,
        'timeline_json':      timeline_json,
        'pizzas_json':        _pizzas_json(pizzas),
        'extras_json':        _extras_json(extras),
        'pizzas_with_fields': pizzas_with_fields,
        'extras_with_fields': extras_with_fields,
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
        'items__pizza__pizza_ingredients__ingredient',
        'extra_items__extra__extra_ingredients__ingredient',
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
        for item in order.extra_items.all():
            for ei in item.extra.extra_ingredients.select_related('ingredient').all():
                key = (ei.ingredient.name, ei.ingredient.unit)
                ingredient_totals[key] += float(ei.quantity) * item.quantity
    ingredient_totals = sorted(ingredient_totals.items())  # [((name, unit), qty), …]

    # Capacity (15-min slot model: 1 order per slot)
    from datetime import datetime as dt
    start_dt  = dt.combine(opening.date, opening.start_time)
    close_dt  = dt.combine(opening.date, opening.close_time)
    total_cap = int((close_dt - start_dt).total_seconds() / 60) // 15
    total_tak = opening.orders.count()
    capacity_pct = int(total_tak / total_cap * 100) if total_cap else 0

    # Per-extra totals
    extra_totals = {}
    for order in orders:
        for item in order.extra_items.all():
            extra_totals[item.extra] = extra_totals.get(item.extra, 0) + item.quantity

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
    extra_financials = [
        {
            'extra':   extra,
            'qty':     qty,
            'revenue': extra.price * qty,
            'cost':    extra.cost * qty if extra.cost is not None else None,
            'profit':  extra.margin * qty if extra.margin is not None else None,
        }
        for extra, qty in extra_totals.items()
    ]
    all_financials      = pizza_financials + extra_financials
    total_pizzas_count  = sum(pizza_totals.values())
    total_revenue = sum(r['revenue'] for r in all_financials)
    total_cost    = sum(r['cost']    for r in all_financials if r['cost']   is not None)
    total_profit  = sum(r['profit']  for r in all_financials if r['profit'] is not None)
    cost_known    = any(r['cost'] is not None for r in all_financials)

    open_orders    = [o for o in orders if o.status != Order.STATUS_PAID]
    paid_orders    = [o for o in orders if o.status == Order.STATUS_PAID]
    pending_count  = sum(1 for o in orders if o.status == Order.STATUS_PENDING)
    paid_count     = len(paid_orders)

    status_logs = OrderStatusLog.objects.filter(
        order__opening_day=opening
    ).select_related('order').order_by('-changed_at')

    return render(request, "opening_day.html", {
        'opening':           opening,
        'open_orders':       open_orders,
        'paid_orders':       paid_orders,
        'total_orders':      len(open_orders) + len(paid_orders),
        'pending_count':     pending_count,
        'paid_count':        paid_count,
        'pizza_totals':      pizza_totals,
        'extra_totals':      extra_totals,
        'pizza_financials':  pizza_financials,
        'extra_financials':  extra_financials,
        'ingredient_totals': ingredient_totals,
        'total_cap':          total_cap,
        'total_tak':          total_tak,
        'capacity_pct':       capacity_pct,
        'total_pizzas_count': total_pizzas_count,
        'total_revenue':      total_revenue,
        'total_cost':        total_cost,
        'total_profit':      total_profit,
        'cost_known':        cost_known,
        'status_logs':       status_logs,
    })


@login_required
@require_POST
def set_order_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    new_status = request.POST.get('status')
    if new_status not in (Order.STATUS_PENDING, Order.STATUS_IGANG, Order.STATUS_READY, Order.STATUS_PAID):
        return HttpResponse(status=400)

    old_status = order.status
    order.status = new_status
    order.save(update_fields=['status'])
    OrderStatusLog.objects.create(order=order, old_status=old_status, new_status=new_status)

    crosses_lists = (old_status == Order.STATUS_PAID) != (new_status == Order.STATUS_PAID)

    if crosses_lists:
        orders = order.opening_day.orders.prefetch_related('items__pizza', 'extra_items__extra').order_by('pickup_time')
        open_orders = [o for o in orders if o.status != Order.STATUS_PAID]
        paid_orders = [o for o in orders if o.status == Order.STATUS_PAID]
        html = render_to_string('_order_lists.html', {
            'open_orders': open_orders,
            'paid_orders': paid_orders,
        }, request=request)
        response = HttpResponse(html)
        response['HX-Retarget'] = '#orders-section'
        response['HX-Reswap'] = 'innerHTML'
        return response

    return HttpResponse(render_to_string('_order_card.html', {'order': order}, request=request))


def bekraeftelse(request, pk):
    order = get_object_or_404(Order, pk=pk)
    total_price = (
        sum(item.quantity * item.pizza.price for item in order.items.all()) +
        sum(item.quantity * item.extra.price for item in order.extra_items.select_related('extra').all())
    )
    return render(request, "bekraeftelse.html", {'order': order, 'total_price': total_price})
