# Serviq Portaal

Portal for installers and distributors under `/my/installations`:

| URL | Page |
| --- | --- |
| `/my` | tiles "Installaties" and "Open interventies" |
| `/my/installations` | installations (search, status filter) |
| `/my/installations/<id>` | installation: components, serial numbers, interventions |
| `/my/installations/interventions` | interventions, one tab per intervention type |
| `/my/installations/planning` | planning calendar (month / week / day) |
| `/my/installations/intervention/<id>` | intervention: data, flows, report, time & km, mark done |

A portal user is matched through its **commercial partner** (its company):
it sees the installations where that company is the distributor or the
installer, and the interventions where it is the installer or the
distributor (`serviq_is_distributor` / `serviq_is_installer` on the contact
or the company). Internal users see everything. The pages read with
`sudo()` after an explicit access check; record rules
(`security/security.xml`) keep direct access in line with that.

On a tablet or phone (below 1200px wide) the intervention lists show every
row as a card (label / value lines, the action as a full-width button).

The planning calendar colours an open intervention with the colour of its
intervention type (`serviq.intervention.type.color`, Odoo colour index,
same palette as the backend planning) and a finished one green, with a
legend. Finished or cancelled interventions leave "Nog niet ingepland".

## Time and kilometres

The "Tijd & km" card of the intervention page logs, in one form:

| Field | Timesheet line (`serviq_time_type`) |
| --- | --- |
| Vertrek naar klant -> Aankomst bij klant (optional) | `Heenrit` (`travel`), with "Km heen" |
| Aankomst bij klant -> Vertrek bij klant | `Interventie` (`intervention`) |
| Vertrek bij klant -> Terug aangekomen (optional) | `Terugrit` (`travel_back`), with "Km terug" |

The lines are created in that order and listed chronologically (portal and
the timesheet tab of the task, with columns for the type and the km). Each
line keeps its start and end (`serviq_start` / `serviq_end`, UTC); the
kilometres are stored on the line of their ride (`serviq_km`, total on the
task as `serviq_km_total`).

Whenever timed lines are added, changed or removed, the planning of the
task follows the time on site: planned start = first arrival, end = last
departure (without a planned start field: the deadline = first arrival).
The rides do not move the planning.

Timesheets need an employee: an installer without one gets an employee
record (no user, linked to the contact as work contact, job title "Externe
installateur") the first time they log time; the contact form shows it and
offers "Werknemer aanmaken". The rights popup of the hours overview
(`res.partner.serviq_get_installer_rights`) is extended with the portal
access, role, users, employee and the available flows.

## Scanning serial numbers

Any `input` or `select` with the class `sq-scan` gets a camera button
(`static/src/interactions/serial_scanner.js`, Odoo's barcode dialog;
hidden when the browser has no camera). On an input the scanned value is
filled in and `input` / `change` are fired, so live checks run; on a select
the option whose `data-scan-value` (else its text) matches is selected.
The serial fields of the bundled flows use it.

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
