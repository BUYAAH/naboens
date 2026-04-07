from django.db import migrations, models
import django.db.models.deletion


# Hardcoded seed data matching the previous PIZZA_CHOICES / PIZZA_FIELDS constants.
# The data migration creates these Pizza records and re-links existing OrderItems.
PIZZA_SEED = [
    ('margherita', 'Naboens Margherita',      'San Marzano · mozzarella · basilikum · olivenolie',                    80),
    ('rustica',    'Naboens Rustica',          'Salsiccia · San Marzano · mozzarella · basilikum',                    90),
    ('calabrese',  'Naboens Calabrese',        'Ventricina-salami · San Marzano · mozzarella',                        90),
    ('tris',       'Naboens Tris di Formaggi', 'Mozzarella · Grana Padano · Gorgonzola · salsiccia · rosmarin',      95),
    ('bambino',    'Naboens Bambino',          'San Marzano · mozzarella · cocktailpølser',                           85),
]


def create_pizzas_and_migrate(apps, schema_editor):
    Pizza     = apps.get_model('core', 'Pizza')
    OrderItem = apps.get_model('core', 'OrderItem')

    slug_to_pizza = {}
    for slug, name, description, price in PIZZA_SEED:
        pizza = Pizza.objects.create(name=name, description=description, price=price, is_active=True)
        slug_to_pizza[slug] = pizza

    for item in OrderItem.objects.all():
        if item.pizza_old in slug_to_pizza:
            item.pizza_new = slug_to_pizza[item.pizza_old]
            item.save()


def reverse_migrate(apps, schema_editor):
    OrderItem = apps.get_model('core', 'OrderItem')
    SLUG_MAP = {name: slug for slug, name, _, _ in PIZZA_SEED}
    for item in OrderItem.objects.select_related('pizza_new').all():
        item.pizza_old = SLUG_MAP.get(item.pizza_new.name, '')
        item.save()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_openingday_pizzas_per_slot_and_more'),
    ]

    operations = [
        # ── 1. New models ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Ingredient',
            fields=[
                ('id',   models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('unit', models.CharField(max_length=20)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='Pizza',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name',        models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('price',       models.PositiveIntegerField()),
                ('is_active',   models.BooleanField(default=True)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='PizzaIngredient',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity',   models.DecimalField(decimal_places=2, max_digits=8)),
                ('ingredient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pizza_ingredients', to='core.ingredient')),
                ('pizza',      models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pizza_ingredients', to='core.pizza')),
            ],
            options={'unique_together': {('pizza', 'ingredient')}},
        ),

        # ── 2. Rename existing CharField so data migration can reference it ──
        migrations.RenameField(
            model_name='orderitem',
            old_name='pizza',
            new_name='pizza_old',
        ),

        # ── 3. Add nullable FK for new Pizza reference ───────────────────────
        migrations.AddField(
            model_name='orderitem',
            name='pizza_new',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='order_items',
                to='core.pizza',
            ),
        ),

        # ── 4. Data migration: create Pizza rows, populate pizza_new ─────────
        migrations.RunPython(create_pizzas_and_migrate, reverse_migrate),

        # ── 5. Make FK non-nullable ──────────────────────────────────────────
        migrations.AlterField(
            model_name='orderitem',
            name='pizza_new',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='order_items',
                to='core.pizza',
            ),
        ),

        # ── 6. Drop old CharField ────────────────────────────────────────────
        migrations.RemoveField(
            model_name='orderitem',
            name='pizza_old',
        ),

        # ── 7. Rename pizza_new → pizza ──────────────────────────────────────
        migrations.RenameField(
            model_name='orderitem',
            old_name='pizza_new',
            new_name='pizza',
        ),
    ]
