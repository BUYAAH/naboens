from collections import defaultdict

from django.contrib import admin
from django.utils.html import format_html, format_html_join

from .models import Ingredient, OpeningDay, Order, OrderItem, Pizza, PizzaIngredient


# ── Ingredient ────────────────────────────────────────────────────────────────

@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ['name', 'unit']
    ordering     = ['name']


# ── Pizza ─────────────────────────────────────────────────────────────────────

class PizzaIngredientInline(admin.TabularInline):
    model  = PizzaIngredient
    extra  = 1
    fields = ['ingredient', 'quantity']


@admin.register(Pizza)
class PizzaAdmin(admin.ModelAdmin):
    list_display  = ['name', 'price', 'cost', 'margin_display', 'is_active']
    list_editable = ['is_active']
    ordering      = ['name']
    inlines       = [PizzaIngredientInline]

    def margin_display(self, obj):
        if obj.margin is None:
            return '—'
        color = '#6b8f6b' if obj.margin >= 0 else '#a0522d'
        return format_html('<span style="color:{};font-weight:600">{} kr</span>', color, obj.margin)
    margin_display.short_description = 'Fortjeneste'


# ── Order inline helpers ──────────────────────────────────────────────────────

class OrderItemInline(admin.TabularInline):
    model           = OrderItem
    extra           = 0
    readonly_fields = ['pizza', 'quantity']
    can_delete      = False


class OrderInline(admin.TabularInline):
    model            = Order
    extra            = 0
    readonly_fields  = ['name', 'phone', 'pickup_time', 'total_pizzas', 'pizza_summary', 'created_at']
    can_delete       = False
    show_change_link = True
    ordering         = ['pickup_time']

    def pizza_summary(self, obj):
        parts = [f"{item.quantity}× {item.pizza.name}" for item in obj.items.all()]
        return ', '.join(parts) if parts else '—'
    pizza_summary.short_description = 'Pizzaer'


# ── OpeningDay ────────────────────────────────────────────────────────────────

@admin.register(OpeningDay)
class OpeningDayAdmin(admin.ModelAdmin):
    list_display    = [
        'date', 'start_time', 'close_time',
        'is_published', 'total_pizzas_ordered', 'capacity_bar',
    ]
    list_editable   = ['is_published']
    readonly_fields = ['ingredient_totals']
    inlines         = [OrderInline]

    def capacity_bar(self, obj):
        from datetime import datetime
        start_dt  = datetime.combine(obj.date, obj.start_time)
        close_dt  = datetime.combine(obj.date, obj.close_time)
        total_cap = int((close_dt - start_dt).total_seconds() / 60) // 5
        total_tak = obj.total_pizzas_ordered()
        if total_cap == 0:
            return '—'
        pct   = int(total_tak / total_cap * 100)
        color = '#a0522d' if pct >= 80 else '#6b8f6b' if pct >= 40 else '#b5aca0'
        return format_html(
            '<div style="display:flex;align-items:center;gap:8px;">'
            '<div style="width:80px;height:8px;background:#eee;border-radius:4px;overflow:hidden;">'
            '<div style="width:{}%;height:100%;background:{};border-radius:4px;"></div>'
            '</div>'
            '<span style="font-size:0.8rem;color:#555;">{} / {} pizzaer</span>'
            '</div>',
            pct, color, total_tak, total_cap,
        )
    capacity_bar.short_description = 'Kapacitet'

    def ingredient_totals(self, obj):
        """Total ingredient quantities needed across all orders for this day."""
        totals = defaultdict(float)
        for order in obj.orders.prefetch_related('items__pizza__pizza_ingredients__ingredient').all():
            for item in order.items.all():
                for pi in item.pizza.pizza_ingredients.select_related('ingredient').all():
                    key = (pi.ingredient.name, pi.ingredient.unit)
                    totals[key] += float(pi.quantity) * item.quantity

        if not totals:
            return 'Ingen ingredienser registreret endnu.'

        rows = format_html_join(
            '',
            '<tr>'
            '<td style="padding:4px 16px 4px 0;font-weight:500">{}</td>'
            '<td style="padding:4px 0;color:#555">{} {}</td>'
            '</tr>',
            sorted((name, f'{qty:g}', unit) for (name, unit), qty in totals.items()),
        )
        return format_html(
            '<table style="border-collapse:collapse;margin-top:4px">'
            '<thead><tr>'
            '<th style="padding:2px 16px 6px 0;font-size:0.75rem;color:#888;text-align:left">Ingrediens</th>'
            '<th style="padding:2px 0 6px;font-size:0.75rem;color:#888;text-align:left">Mængde</th>'
            '</tr></thead>'
            '<tbody>{}</tbody>'
            '</table>',
            rows,
        )
    ingredient_totals.short_description = 'Ingredienser til indkøb'


# ── Order ─────────────────────────────────────────────────────────────────────

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = ['pickup_time', 'name', 'phone', 'total_pizzas', 'pizza_summary', 'opening_day', 'created_at']
    list_filter     = ['opening_day']
    ordering        = ['pickup_time']
    readonly_fields = ['pickup_time', 'total_pizzas', 'created_at']
    inlines         = [OrderItemInline]

    def pizza_summary(self, obj):
        parts = [f"{item.quantity}× {item.pizza.name}" for item in obj.items.all()]
        return ', '.join(parts) if parts else '—'
    pizza_summary.short_description = 'Pizzaer'
