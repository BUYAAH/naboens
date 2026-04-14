from django.db import models


class Ingredient(models.Model):
    name = models.CharField(max_length=100)
    unit = models.CharField(max_length=20)  # e.g. "g", "ml", "stk"

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.unit})"


class Pizza(models.Model):
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    note        = models.CharField(max_length=200, blank=True)
    price       = models.PositiveIntegerField()
    cost        = models.PositiveIntegerField(null=True, blank=True, help_text="Råvarepris i kr (valgfrit)")
    image       = models.ImageField(upload_to='pizzas/', blank=True, null=True)
    is_active   = models.BooleanField(default=True)

    @property
    def margin(self):
        """Profit per pizza in kr. None if cost is not set."""
        if self.cost is None:
            return None
        return self.price - self.cost

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class PizzaIngredient(models.Model):
    pizza      = models.ForeignKey(Pizza, on_delete=models.CASCADE, related_name='pizza_ingredients')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name='pizza_ingredients')
    quantity   = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        unique_together = ('pizza', 'ingredient')

    def __str__(self):
        return f"{self.pizza} — {self.quantity} {self.ingredient.unit} {self.ingredient.name}"


class OpeningDay(models.Model):
    date                  = models.DateField()
    start_time            = models.TimeField()
    close_time            = models.TimeField()
    is_published          = models.BooleanField(default=False)

    class Meta:
        ordering = ['date', 'start_time']

    def __str__(self):
        return f"{self.date} ({self.start_time.strftime('%H:%M')}–{self.close_time.strftime('%H:%M')})"

    def total_pizzas_ordered(self):
        return sum(o.total_pizzas for o in self.orders.all())



class Order(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_IGANG   = 'igang'
    STATUS_READY   = 'ready'
    STATUS_PAID    = 'paid'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Afventer'),
        (STATUS_IGANG,   'Igang'),
        (STATUS_READY,   'Klar'),
        (STATUS_PAID,    'Betalt'),
    ]

    opening_day  = models.ForeignKey(OpeningDay, on_delete=models.CASCADE, related_name='orders')
    name         = models.CharField(max_length=100)
    email        = models.EmailField(blank=True)
    phone        = models.CharField(max_length=20)
    pickup_time  = models.TimeField()
    total_pizzas = models.PositiveIntegerField()
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['pickup_time']
        unique_together = [('opening_day', 'pickup_time')]

    def __str__(self):
        plural = 'er' if self.total_pizzas != 1 else ''
        return f"{self.name} — kl. {self.pickup_time.strftime('%H:%M')} ({self.total_pizzas} pizza{plural})"


class OrderStatusLog(models.Model):
    order      = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_logs')
    old_status = models.CharField(max_length=10)
    new_status = models.CharField(max_length=10)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['changed_at']

    def __str__(self):
        return f"#{self.order_id} {self.old_status} → {self.new_status} ({self.changed_at:%Y-%m-%d %H:%M})"


class OrderItem(models.Model):
    order    = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    pizza    = models.ForeignKey(Pizza, on_delete=models.PROTECT, related_name='order_items')
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.quantity}× {self.pizza.name}"


class Extra(models.Model):
    CATEGORY_DRINK   = 'drink'
    CATEGORY_DESSERT = 'dessert'
    CATEGORY_OTHER   = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_DRINK,   'Drikkevare'),
        (CATEGORY_DESSERT, 'Dessert'),
        (CATEGORY_OTHER,   'Andet'),
    ]

    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price       = models.PositiveIntegerField()
    cost        = models.PositiveIntegerField(null=True, blank=True, help_text="Råvarepris i kr (valgfrit)")
    category    = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    image       = models.ImageField(upload_to='extras/', blank=True, null=True)
    is_active   = models.BooleanField(default=True)

    @property
    def margin(self):
        if self.cost is None:
            return None
        return self.price - self.cost

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class ExtraIngredient(models.Model):
    extra      = models.ForeignKey(Extra, on_delete=models.CASCADE, related_name='extra_ingredients')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name='extra_ingredients')
    quantity   = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        unique_together = ('extra', 'ingredient')

    def __str__(self):
        return f"{self.extra} — {self.quantity} {self.ingredient.unit} {self.ingredient.name}"


class ExtraOrderItem(models.Model):
    order    = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='extra_items')
    extra    = models.ForeignKey(Extra, on_delete=models.PROTECT, related_name='order_items')
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.quantity}× {self.extra.name}"
