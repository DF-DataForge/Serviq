"""Dutch labels for the record states shown on the dashboards, and the
product type (component role) and segment (installation category)
helpers shared by all dashboards.

The dashboards are in Dutch regardless of the user's language, so the
state labels are mapped here instead of taken from the (English) field
selection. Unknown states fall back to the selection label.

Product types and segments are data, not code: the product type of a
product is the code of its component role (serviq.component.role,
ordered by sequence, labelled by name; "none" for products without
role), the segment the code of its installation category
(serviq.installation.category).
"""

STATE_LABELS = {
    'stock.picking': {
        'draft': 'Concept',
        'waiting': 'Wacht op andere bewerking',
        'confirmed': 'Wachtend',
        'assigned': 'Gereed',
        'done': 'Afgewerkt',
        'cancel': 'Geannuleerd',
    },
    'purchase.order': {
        'draft': 'Offerteaanvraag',
        'sent': 'Offerteaanvraag verzonden',
        'to approve': 'Te keuren',
        'purchase': 'Inkooporder',
        'done': 'Vergrendeld',
        'cancel': 'Geannuleerd',
    },
    'sale.order': {
        'draft': 'Offerte',
        'sent': 'Offerte verzonden',
        'sale': 'Verkooporder',
        'done': 'Vergrendeld',
        'cancel': 'Geannuleerd',
    },
}


def state_label(record):
    state = record.state
    label = STATE_LABELS.get(record._name, {}).get(state)
    if label:
        return label
    return dict(record._fields['state'].selection).get(state, state)


# ----------------------------------------------------------------------
# Product types (component roles)
# ----------------------------------------------------------------------
NO_TYPE = 'none'
NO_TYPE_LABEL = 'Niet ingedeeld'


def _roles(env):
    return env['serviq.component.role'].sudo().with_context(active_test=False).search(
        [], order='sequence, id')


def type_order(env):
    """Product type keys in display order: the component roles by
    sequence, products without role last."""
    return [role.code for role in _roles(env) if role.code] + [NO_TYPE]


def type_labels(env):
    """Product type key -> label (the role name)."""
    labels = {role.code: role.name for role in _roles(env) if role.code}
    labels[NO_TYPE] = NO_TYPE_LABEL
    return labels


def type_rank(order, key):
    """Sort key of a product type in `order` (see type_order); unknown
    keys just before "none"."""
    if key in order:
        return order.index(key)
    return len(order) - 1


def product_type(product):
    """Product type key of a product (product.product or template)."""
    tmpl = product.product_tmpl_id if product._name == 'product.product' else product
    return tmpl.serviq_role_code or NO_TYPE


def product_types(lines):
    """Sorted product type keys of order lines / stock moves ("none" for
    products without role), for the type filter of the dashboards."""
    keys = set()
    for line in lines:
        if getattr(line, 'display_type', False) or not line.product_id:
            continue
        keys.add(product_type(line.product_id))
    return sorted(keys)


# ----------------------------------------------------------------------
# Segments (installation categories)
# ----------------------------------------------------------------------
ALL_SEGMENTS = 'all'


def segment_domain(subgroup, path='product_id.product_tmpl_id'):
    """Domain restricting `path` (a product template path) to the segment
    `subgroup` (an installation category code); none for "all"."""
    if not subgroup or subgroup == ALL_SEGMENTS:
        return []
    return [(path + '.serviq_category_code', '=', subgroup)]
