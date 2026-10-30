# Serviq Portaal

Portal for installers and distributors under `/my/installations`:

| URL | Page |
| --- | --- |
| `/my` | tiles "Installaties" and "Open interventies" |
| `/my/installations` | installations (search, status filter) |
| `/my/installations/<id>` | installation: components, serial numbers, interventions |
| `/my/installations/interventions` | interventions, one tab per intervention type |
| `/my/installations/planning` | planning calendar (month / week / day) |
| `/my/installations/intervention/<id>` | intervention: data, flows, report, hours, mark done |

A portal user is matched through its **commercial partner** (its company):
it sees the installations where that company is the distributor or the
installer, and the interventions where it is the installer or the
distributor (`serviq_is_distributor` / `serviq_is_installer` on the contact
or the company). Internal users see everything. The pages read with
`sudo()` after an explicit access check; record rules
(`security/security.xml`) keep direct access in line with that.

## Flows

The intervention page is extended by **flows**: first installation,
commissioning, replacement, ... Each flow is a separate module and a record
of `serviq.portal.flow` (Installaties > Configuratie > Flows), where it can
be enabled / disabled (`active`) and linked to intervention types and,
optionally, installation categories.

For every active flow that applies to the intervention (in `sequence`
order) the page renders the flow's template. Its form posts to

    POST /my/installations/intervention/<task_id>/flow/<code>

which checks the access to the intervention, that the flow exists, is
active and applies (404 otherwise), and calls the handler of the flow
inside a savepoint (a `UserError` / `ValidationError` rolls back and is
shown on the page). An optional live check is available on

    GET /my/installations/intervention/<task_id>/flow/<code>/check

### Handler contract (`serviq.portal.flow.handler`)

| Method | Returns | Default |
| --- | --- | --- |
| `_flow_applies(task, flow)` | bool | type of the task in `flow.intervention_type_ids` (any when empty) and category of its installation in `flow.installation_category_ids` (when set and known) |
| `_flow_values(task, flow, partner, is_internal)` | dict merged into the values of the template | `{}` |
| `_flow_submit(task, flow, partner, is_internal, post)` | `(message, error)` or a URL to redirect to | error "no form" |
| `_flow_check(task, flow, partner, is_internal, params)` | JSON dict, `{'ok', 'message'}` | `{'ok': False}` |

The handler is called with `sudo()`; `partner` is the contact of the user,
`is_internal` tells whether it is an internal user. Helpers:
`_flow_distributors`, `_flow_available_lots`, `_flow_find_lot`,
`_flow_post` (chatter message in the name of the user).

The template is rendered with the values of the intervention page (`task`,
`installation`, `partner`, `is_internal`, `is_closed`, `state_labels`, ...),
`flow`, `flow_action` (the POST URL) and the values of `_flow_values`
(prefix their keys with the code of the flow). Forms must include the CSRF
token.

### Writing a flow addon

`serviq_flow_example/__manifest__.py`:

```python
{
    'name': 'Serviq Flow: voorbeeld',
    'version': '19.0.1.0.0',
    'author': 'Data Forge',
    'website': 'https://www.data-forge.be',
    'depends': ['serviq_portal'],
    'data': [
        'views/flow_templates.xml',
        'data/flow_data.xml',
    ],
    'license': 'LGPL-3',
}
```

`models/flow_handler.py` (imported from `models/__init__.py`):

```python
from odoo import _, api, models


class ExampleFlow(models.AbstractModel):
    _name = 'serviq.portal.flow.handler.example'
    _inherit = 'serviq.portal.flow.handler'
    _description = 'Portaalflow: voorbeeld'

    @api.model
    def _flow_values(self, task, flow, partner, is_internal):
        return {'ex_note': task.serviq_installation_id.note}

    @api.model
    def _flow_submit(self, task, flow, partner, is_internal, post):
        remark = (post.get('remark') or '').strip()
        if not remark:
            return None, _('Vul een opmerking in.')
        self._flow_post(task, partner, remark)
        return _('Opmerking bewaard.'), None
```

`views/flow_templates.xml`:

```xml
<odoo>
    <template id="flow_section" name="Flow: voorbeeld">
        <form method="post" t-att-action="flow_action">
            <input type="hidden" name="csrf_token" t-att-value="request.csrf_token()"/>
            <input type="text" name="remark" class="form-control mb-2"/>
            <button type="submit" class="btn btn-primary">Bewaren</button>
        </form>
    </template>
</odoo>
```

`data/flow_data.xml` (`noupdate` so enabling / disabling survives updates):

```xml
<odoo noupdate="1">
    <record id="flow_example" model="serviq.portal.flow">
        <field name="name">Voorbeeld</field>
        <field name="code">example</field>
        <field name="sequence">50</field>
        <field name="intervention_type_ids"
               eval="[(6, 0, [ref('serviq_installation.intervention_type_other')])]"/>
        <field name="handler_model">serviq.portal.flow.handler.example</field>
        <field name="template">serviq_flow_example.flow_section</field>
        <field name="button_label">Voorbeeld</field>
        <field name="icon">fa-star</field>
        <field name="module">serviq_flow_example</field>
    </record>
</odoo>
```

Uninstalling the addon removes its flow record and handler. To offer it as
a checkbox in the settings, add a `module_serviq_flow_example` boolean to
`res.config.settings` and a setting in the "Flows in het portaal" block.

Available flows: `serviq_flow_first_installation`,
`serviq_flow_commissioning`, `serviq_flow_replacement`.
