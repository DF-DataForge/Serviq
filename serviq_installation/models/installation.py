# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html_escape
from odoo.tools.misc import format_date

# Statuses that move to 'Inbedrijfstelling gepland' / 'Actief' with the
# commissioning, and to 'Service' while an intervention is planned.
COMMISSIONING_FROM_STATES = ('delivered', 'installation')
SERVICE_FROM_STATES = ('active', 'offline')


class Installation(models.Model):
    _name = 'serviq.installation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Installatie'
    _rec_name = 'name'
    _order = 'code desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    code = fields.Char('Referentie', copy=False, index=True)
    state = fields.Selection([
        ('delivered', 'Geleverd'),
        ('installation', 'Installatie bezig'),
        ('commissioning', 'Inbedrijfstelling gepland'),
        ('active', 'Actief'),
        ('service', 'Service'),
        ('offline', 'Offline'),
        ('out_of_service', 'Buiten dienst'),
    ], string='Status', default='delivered', tracking=True, copy=False)
    state_before_commissioning = fields.Selection(
        selection='_state_selection',
        string='Status voor inbedrijfstelling', copy=False, readonly=True,
        help='Status the installation had before it was set to '
             'Inbedrijfstelling gepland automatically; it goes back to it '
             'when the commissioning is no longer planned.')
    state_before_service = fields.Selection(
        selection='_state_selection',
        string='Status voor service', copy=False, readonly=True,
        help='Status the installation had before it was put in service '
             'automatically for a planned intervention; it goes back to it '
             'once no intervention is planned any more.')
    company_id = fields.Many2one(
        'res.company', string='Bedrijf',
        default=lambda self: self.env.company, required=True)
    category_id = fields.Many2one(
        'serviq.installation.category', string='Categorie', tracking=True,
        index=True)
    product_tmpl_id = fields.Many2one(
        'product.template', 'Product', required=True, index=True,
        check_company=True, domain="[('type', '=', 'consu')]")
    product_qty = fields.Float(
        'Hoeveelheid', default=1.0, digits='Product Unit', required=True)
    product_uom = fields.Many2one(
        'uom.uom', 'Eenheid', related='product_tmpl_id.uom_id')
    line_ids = fields.One2many(
        'serviq.installation.line', 'installation_id', string='Componenten')
    customer_id = fields.Many2one(
        'res.partner', string='Klant', tracking=True, index=True)
    distributor_id = fields.Many2one(
        'res.partner', string='Distributeur', tracking=True, index=True,
        domain=[('serviq_is_distributor', '=', True)])
    installer_id = fields.Many2one(
        'res.partner', string='Installateur', tracking=True, index=True,
        domain=[('serviq_is_installer', '=', True)])
    parent_line_id = fields.Many2one(
        'serviq.installation.line', string='Bovenliggende componentlijn',
        ondelete='cascade', index=True)
    lot_id = fields.Many2one(
        'stock.lot', string='Lot/Serienummer', tracking=True)
    lot_ids = fields.One2many(
        'stock.lot', 'serviq_installation_id',
        string='Gekoppelde lot/serienummers')
    contact_person_name = fields.Char(string='Contactpersoon')
    contact_person_phone = fields.Char(string='Telefoon contactpersoon')
    note = fields.Html(string='Notities')
    is_locked = fields.Boolean(string='Vergrendeld')
    delivery_picking_id = fields.Many2one(
        'stock.picking', string='Aangemaakt door levering', readonly=True,
        copy=False, index=True)
    task_ids = fields.One2many(
        'project.task', 'serviq_installation_id', string='Interventies')
    sn_registration_count = fields.Integer(
        string='Open SN-registraties',
        compute='_compute_sn_registration_count', store=True)
    sale_order_count = fields.Integer(
        string='Verkooporders', compute='_compute_related_order_counts')
    purchase_order_count = fields.Integer(
        string='Inkooporders', compute='_compute_related_order_counts')
    # Interventions split by the group of their type, each with its own
    # smart button.
    intervention_count = fields.Integer(
        string='Interventies', compute='_compute_intervention_count')
    repair_count = fields.Integer(
        string='Herstellingen', compute='_compute_intervention_count')
    replacement_count = fields.Integer(
        string='Vervangingen', compute='_compute_intervention_count')

    @api.model
    def _state_selection(self):
        return self._fields['state'].selection

    # ------------------------------------------------------------------
    # Overview dashboard
    # ------------------------------------------------------------------
    @api.model
    def get_overview_dashboard_data(self):
        """Aggregates for the overview dashboard: overall counts plus the
        same counts per distributor and per installer."""
        def _bucket():
            return {'total': 0, 'active': 0, 'commissioning': 0,
                    'service': 0, 'not_registered': 0}

        top = [('parent_line_id', '=', False)]
        overall = _bucket()
        overall['total'] = self.search_count(top)
        for state, count in self._read_group(
                top, groupby=['state'], aggregates=['__count']):
            if state in ('active', 'commissioning', 'service'):
                overall[state] = count
        overall['not_registered'] = self.search_count(
            top + [('sn_registration_count', '>', 0)])

        def _per_partner(field):
            # Aggregate on the commercial entity so contacts and
            # sub-addresses of the same company end up in one row.
            data = {}

            def entry(partner):
                partner = partner.commercial_partner_id if partner \
                    else partner
                key = partner.id if partner else 0
                if key not in data:
                    data[key] = dict(
                        _bucket(),
                        id=partner.id if partner else False,
                        name=partner.display_name if partner
                        else _('Niet ingesteld'))
                return data[key]

            for partner, state, count in self._read_group(
                    top, groupby=[field, 'state'], aggregates=['__count']):
                bucket = entry(partner)
                bucket['total'] += count
                if state in ('active', 'commissioning', 'service'):
                    bucket[state] += count
            for partner, count in self._read_group(
                    top + [('sn_registration_count', '>', 0)],
                    groupby=[field], aggregates=['__count']):
                entry(partner)['not_registered'] += count
            return sorted(
                data.values(),
                key=lambda d: (-d['total'], (d['name'] or '').lower()))

        return {
            'overall': overall,
            'per_distributor': _per_partner('distributor_id'),
            'per_installer': _per_partner('installer_id'),
            # Counts only: the records behind a tile open with the user's
            # own rights.
            'sections': self.sudo()._dashboard_sections(),
        }

    # ------------------------------------------------------------------
    # Dashboard: planning calendar (same layout as the portal)
    # ------------------------------------------------------------------
    @api.model
    def _local_time(self, task, fname):
        """'HH:MM' of a datetime field of `task` in the user's timezone."""
        value = task[fname] if fname in task._fields else False
        if not isinstance(value, datetime):
            return ''
        return fields.Datetime.context_timestamp(self, value).strftime('%H:%M')

    @api.model
    def _task_plan_date(self, task):
        """Day a task is shown on: planned start, then deadline, then
        start date, in the user's timezone; False when it has none."""
        for fname in ('planned_date_begin', 'date_deadline', 'date_start'):
            if fname not in task._fields or not task[fname]:
                continue
            value = task[fname]
            if isinstance(value, datetime):
                return fields.Datetime.context_timestamp(self, value).date()
            return value
        return False

    @api.model
    def get_planning_calendar_data(self, scope='month', anchor=False,
                                   task_id=False, installer_id=False):
        """Interventions of installations for the month / week / day
        around `anchor` (YYYY-MM-DD, default today), bucketed per day;
        `task_id` is the intervention being planned (slot picker);
        `installer_id` narrows them to one installer (-1: no installer)."""
        today = fields.Date.context_today(self)
        if scope not in ('month', 'week', 'day'):
            scope = 'month'
        anchor = fields.Date.to_date(anchor) if anchor else today

        weeks = []
        if scope == 'month':
            first = anchor.replace(day=1)
            next_month = (first + timedelta(days=32)).replace(day=1)
            cursor = first - timedelta(days=first.weekday())
            while cursor < next_month:
                weeks.append([cursor + timedelta(days=i) for i in range(7)])
                cursor += timedelta(days=7)
            start, end = weeks[0][0], weeks[-1][-1]
            label = format_date(self.env, first, date_format='MMMM y')
            prev_anchor = first - timedelta(days=1)
            next_anchor = next_month
        elif scope == 'week':
            start = anchor - timedelta(days=anchor.weekday())
            weeks.append([start + timedelta(days=i) for i in range(7)])
            end = weeks[0][-1]
            label = _('Week %(start)s - %(end)s',
                      start=start.strftime('%d/%m'),
                      end=end.strftime('%d/%m/%Y'))
            prev_anchor = start - timedelta(days=7)
            next_anchor = start + timedelta(days=7)
        else:
            start = end = anchor
            label = format_date(self.env, anchor,
                                date_format='EEEE d MMMM y')
            prev_anchor = anchor - timedelta(days=1)
            next_anchor = anchor + timedelta(days=1)

        Task = self.env['project.task']
        tasks_by_day, without_date = {}, []
        # A first installation has no installation yet: an intervention
        # type is enough.
        domain = Task._serviq_intervention_domain()
        if installer_id == -1:
            domain.append(('serviq_installer_id', '=', False))
        elif installer_id:
            domain.append(('serviq_installer_id', '=', installer_id))
        for task in Task.search(domain, order='create_date desc',
                                limit=2000):
            info = {
                'id': task.id,
                'name': task.name,
                'type': task.serviq_intervention_type_id.name or '',
                'done': bool(task.date_end),
                'installation': task.serviq_installation_id.name or '',
                'partner': task.partner_id.name or '',
                'city': task.partner_id.city or '',
                'start': self._local_time(task, 'planned_date_begin'),
                'end': self._local_time(task, 'date_deadline'),
                'current': task.id == task_id,
            }
            day = self._task_plan_date(task)
            if not day:
                without_date.append(info)
            elif start <= day <= end:
                tasks_by_day.setdefault(fields.Date.to_string(day), []) \
                    .append(info)

        def iso(day):
            return fields.Date.to_string(day)

        return {
            'scope': scope,
            'label': label,
            'today': iso(today),
            'anchor': iso(anchor),
            'anchor_month': anchor.month,
            'prev': iso(prev_anchor),
            'next': iso(next_anchor),
            'weeks': [[{'date': iso(d), 'day': d.day, 'month': d.month,
                        'weekday': d.weekday()} for d in week]
                      for week in weeks],
            'day': iso(anchor),
            'tasks_by_day': tasks_by_day,
            'without_date': without_date,
            'task_context': self._intervention_task_context(),
            'installer_id': installer_id or False,
            'installers': [
                [partner.id, partner.display_name]
                for partner in self.env['res.partner'].search(
                    [('serviq_is_installer', '=', True)], order='name')],
        }

    # ------------------------------------------------------------------
    # Dashboard: extra sections (interventions, logged hours, ...)
    # ------------------------------------------------------------------
    # Each section is {'key', 'title', 'icon', 'tiles'}, optionally with an
    # 'action' opening all its records; a tile is {'key', 'label', 'value',
    # 'action'} where 'action' opens the records behind the number. Other
    # modules append sections by extending _dashboard_sections.
    TASK_CLOSED_STATES = ('1_done', '1_canceled')

    @api.model
    def _dashboard_periods(self):
        """(week start, month start, today) in the user's timezone."""
        today = fields.Date.context_today(self)
        return today - timedelta(days=today.weekday()), \
            today.replace(day=1), today

    @api.model
    def _dashboard_action(self, name, model, domain, views=('list', 'form'),
                          context=None):
        """Window action on `model`; a view may be given as (xmlid, type)
        to use that view instead of the default one."""
        view_list = []
        for view in views:
            xmlid, view_type = view if isinstance(view, tuple) \
                else (False, view)
            record = xmlid and self.env.ref(xmlid, raise_if_not_found=False)
            view_list.append([record.id if record else False, view_type])
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': model,
            'domain': domain,
            'views': view_list,
            'target': 'current',
            'context': context or {},
        }

    @api.model
    def _intervention_project(self):
        """Project interventions are created in: the one set in the
        settings, else the field service project when Field Service is
        installed."""
        Project = self.env['project.project'].sudo()
        project_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'serviq_installation.intervention_project_id') or 0)
        project = Project.browse(project_id).exists() if project_id \
            else Project
        if not project:
            project = self.env.ref(
                'industry_fsm.fsm_project', raise_if_not_found=False) \
                or Project
        if not project and 'is_fsm' in Project._fields:
            project = Project.search([('is_fsm', '=', True)], limit=1)
        return project

    @api.model
    def _intervention_task_context(self):
        """Context of intervention lists: 'New' creates the task in the
        interventions project (a field service task when FSM is used)."""
        context = {}
        if 'is_fsm' in self.env['project.task']._fields:
            context['fsm_mode'] = True
        project = self._intervention_project()
        if project:
            context['default_project_id'] = project.id
        return context

    @api.model
    def _dashboard_datetime(self, day):
        """Start of `day` in the user's timezone, as a UTC string."""
        local = fields.Datetime.context_timestamp(
            self, datetime.combine(day, time.min))
        start = datetime.combine(day, time.min) - local.utcoffset()
        return fields.Datetime.to_string(start)

    @api.model
    def _dashboard_sections(self):
        sections = [self._dashboard_interventions()]
        if 'repair.order' in self.env:
            sections.append(self._dashboard_repairs())
        if 'account.analytic.line' in self.env \
                and 'task_id' in self.env['account.analytic.line']._fields:
            sections.append(self._dashboard_hours())
        return sections

    @api.model
    def _dashboard_repairs(self):
        """Repair orders of the Repair app that are not repaired yet. The
        numbers open the Repair app's own view, narrowed to the orders
        behind them."""
        Repair = self.env['repair.order']
        open_states = ('draft', 'confirmed', 'under_repair')

        def action(name, domain):
            try:
                vals = self.env['ir.actions.act_window']._for_xml_id(
                    'repair.action_repair_order_tree')
            except ValueError:
                return self._dashboard_action(
                    name, 'repair.order', domain,
                    ('list', 'kanban', 'form'))
            vals.update(name=name, domain=domain, context={},
                        target='current')
            vals.pop('id', None)
            return vals

        tiles = []
        for key, label, states in (
                ('open', _('Totaal'), open_states),
                ('draft', _('Nieuw'), ('draft',)),
                ('confirmed', _('Bevestigd'), ('confirmed',)),
                ('under_repair', _('In reparatie'), ('under_repair',))):
            domain = [('state', 'in', list(states))]
            tiles.append({
                'key': key,
                'label': label,
                'value': Repair.search_count(domain),
                'action': action(
                    _('Producten in reparatie - %s', label), domain),
            })
        return {'key': 'repairs', 'title': _('Producten in reparatie'),
                'icon': 'fa-wrench', 'tiles': tiles,
                'action': action(_('Producten in reparatie'),
                                 [('state', 'in', list(open_states))])}

    @api.model
    def _dashboard_interventions(self, key='interventions', title=None,
                                 icon='fa-calendar-check-o', domain=None):
        """Interventions on installations (narrowed by `domain`): open,
        planned this week, not planned and finished this month."""
        Task = self.env['project.task']
        title = title or _('Interventies')
        plan_field = Task._serviq_plan_field()
        week_start, month_start, _today = self._dashboard_periods()
        week_end = week_start + timedelta(days=7)
        base = Task._serviq_intervention_domain() + (domain or [])
        open_ = [('state', 'not in', list(self.TASK_CLOSED_STATES))]
        planned_this_week = open_ + [
            (plan_field, '>=', self._dashboard_datetime(week_start)),
            (plan_field, '<', self._dashboard_datetime(week_end)),
        ]
        unplanned = open_ + [(plan_field, '=', False)]
        done_this_month = [
            ('state', '=', '1_done'),
            ('date_end', '>=', self._dashboard_datetime(month_start)),
        ]
        tiles = []
        for tile_key, label, tile_domain in (
                ('open', _('Open'), open_),
                ('week', _('Gepland deze week'), planned_this_week),
                ('unplanned', _('Niet ingepland'), unplanned),
                ('done_month', _('Afgerond deze maand'), done_this_month)):
            full = base + tile_domain
            tiles.append({
                'key': tile_key,
                'label': label,
                'value': Task.search_count(full),
                'action': self._dashboard_action(
                    '%s - %s' % (title, label), 'project.task', full,
                    ('list', 'kanban', 'form'),
                    context=self._intervention_task_context()),
            })
        return {'key': key, 'title': title, 'icon': icon, 'tiles': tiles}

    @api.model
    def _timesheet_views(self):
        return (('hr_timesheet.hr_timesheet_line_tree', 'list'),
                ('hr_timesheet.hr_timesheet_line_form', 'form'))

    @api.model
    def _dashboard_hours(self):
        Line = self.env['account.analytic.line']
        week_start, month_start, _today = self._dashboard_periods()
        base = ['|', ('task_id.serviq_installation_id', '!=', False),
                ('task_id.serviq_intervention_type_id', '!=', False)]
        tiles = []
        for key, label, start in (
                ('week', _('Deze week'), week_start),
                ('month', _('Deze maand'), month_start)):
            domain = base + [('date', '>=', fields.Date.to_string(start))]
            hours = Line._read_group(
                domain, aggregates=['unit_amount:sum'])[0][0] or 0.0
            tiles.append({
                'key': key,
                'label': label,
                'value': self._hours_label(hours),
                'action': self._dashboard_action(
                    _('Gelogde uren interventies - %s', label),
                    'account.analytic.line', domain,
                    self._timesheet_views()),
            })
        return {'key': 'hours', 'title': _('Gelogde uren op interventies'),
                'icon': 'fa-clock-o', 'tiles': tiles,
                'action': {
                    'type': 'ir.actions.client',
                    'tag': 'serviq_installation.hours_overview',
                    'name': _('Urenoverzicht interventies'),
                }}

    # ------------------------------------------------------------------
    # Hours overview ('Urenoverzicht interventies')
    # ------------------------------------------------------------------
    HOURS_PERIODS = ('week', 'last_week', 'month', 'last_month', 'year',
                     'custom')

    @api.model
    def _hours_period(self, period, date_from, date_to):
        """(start, end, label) of a period, in the user's timezone; both
        days included."""
        today = fields.Date.context_today(self)
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        if period == 'last_week':
            start = week_start - timedelta(days=7)
            return start, start + timedelta(days=6), _('Vorige week')
        if period == 'month':
            return month_start, today, _('Deze maand')
        if period == 'last_month':
            end = month_start - timedelta(days=1)
            return end.replace(day=1), end, _('Vorige maand')
        if period == 'year':
            return today.replace(month=1, day=1), today, _('Dit jaar')
        if period == 'custom' and date_from and date_to:
            start = fields.Date.to_date(date_from)
            end = fields.Date.to_date(date_to)
            if end < start:
                start, end = end, start
            return start, end, '%s - %s' % (
                format_date(self.env, start), format_date(self.env, end))
        return week_start, week_start + timedelta(days=6), _('Deze week')

    @api.model
    def get_hours_overview_data(self, period='week', date_from=False,
                                date_to=False):
        """Hours logged on interventions of installations in a period:
        totals, and per installer, per employee, per distributor and per
        type of intervention; each group carries the domain of its
        timesheet lines."""
        if period not in self.HOURS_PERIODS:
            period = 'week'
        start, end, label = self._hours_period(period, date_from, date_to)
        domain = [
            '|', ('task_id.serviq_installation_id', '!=', False),
            ('task_id.serviq_intervention_type_id', '!=', False),
            ('date', '>=', fields.Date.to_string(start)),
            ('date', '<=', fields.Date.to_string(end)),
        ]
        Line = self.env['account.analytic.line'].sudo()
        rows = Line._read_group(domain, ['task_id', 'employee_id'],
                                ['unit_amount:sum'])
        Task = self.env['project.task']
        unset = _('Niet ingesteld')
        groups = {key: {} for key in
                  ('installer', 'employee', 'distributor', 'type')}

        def add(group, key, name, hours, task, domain_part):
            entry = groups[group].setdefault(key, {
                'key': str(key), 'name': name, 'hours': 0.0,
                'task_ids': set(), 'domain_part': domain_part})
            entry['hours'] += hours
            entry['task_ids'].add(task.id)

        total = 0.0
        tasks = Task
        for task, employee, hours in rows:
            hours = hours or 0.0
            total += hours
            tasks |= task
            installer = task.serviq_installer_id
            distributor = (task.serviq_distributor_id
                           or task.serviq_installation_id.distributor_id) \
                .commercial_partner_id
            itype = task.serviq_intervention_type_id
            add('installer', installer.id or 0, installer.name or unset,
                hours, task, None)
            add('employee', employee.id or 0, employee.name or unset,
                hours, task, [('employee_id', '=', employee.id or False)])
            add('distributor', distributor.id or 0,
                distributor.name or unset, hours, task, None)
            add('type', itype.id or 0, itype.name or unset, hours, task,
                None)

        def rows_of(group):
            result = []
            for entry in sorted(groups[group].values(),
                                key=lambda e: -e['hours']):
                part = entry.pop('domain_part') or [
                    ('task_id', 'in', sorted(entry['task_ids']))]
                count = len(entry.pop('task_ids'))
                result.append(dict(
                    entry,
                    hours_label=self._hours_label(entry['hours']),
                    share=round(entry['hours'] / total * 100) if total else 0,
                    interventions=count,
                    action=self._dashboard_action(
                        _('Uren %(name)s - %(period)s', name=entry['name'],
                          period=label),
                        'account.analytic.line', domain + part,
                        self._timesheet_views()),
                ))
            return result

        count = len(tasks)
        return {
            'period': period,
            'label': label,
            'date_from': fields.Date.to_string(start),
            'date_to': fields.Date.to_string(end),
            'total': self._hours_label(total),
            'interventions': count,
            'average': self._hours_label(total / count if count else 0),
            'action': self._dashboard_action(
                _('Gelogde uren interventies - %s', label),
                'account.analytic.line', domain, self._timesheet_views()),
            'groups': [
                {'key': 'installer', 'title': _('Per installateur'),
                 'icon': 'fa-wrench', 'rows': rows_of('installer')},
                {'key': 'employee', 'title': _('Per medewerker'),
                 'icon': 'fa-user', 'rows': rows_of('employee')},
                {'key': 'distributor', 'title': _('Per distributeur'),
                 'icon': 'fa-truck', 'rows': rows_of('distributor')},
                {'key': 'type', 'title': _('Per type interventie'),
                 'icon': 'fa-tags', 'rows': rows_of('type')},
            ],
        }

    @api.model
    def _hours_label(self, hours):
        minutes = int(round((hours or 0) * 60))
        return '%d:%02d' % divmod(minutes, 60)

    # ------------------------------------------------------------------
    # Constraints / computes
    # ------------------------------------------------------------------
    @api.constrains('state', 'category_id')
    def _check_state_category(self):
        """Categories without commissioning never get the 'Inbedrijfstelling
        gepland' status."""
        for rec in self:
            if rec.state == 'commissioning' and rec.category_id \
                    and not rec.category_id.requires_commissioning:
                raise ValidationError(_(
                    'Installaties van categorie "%s" worden niet in bedrijf '
                    'gesteld; de status "Inbedrijfstelling gepland" is hier '
                    'niet van toepassing.', rec.category_id.display_name))

    @api.depends('product_tmpl_id', 'code')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s (%s)' % (rec.product_tmpl_id.name, rec.code) \
                if rec.code else rec.product_tmpl_id.name

    def _get_sn_registration_lines(self):
        """Component lines whose serial was verified via photo in the portal
        but that still miss a real lot/serial."""
        self.ensure_one()
        return self.line_ids.filtered(
            lambda l: l.serial_photo and not l.lot_id).sorted('id')

    @api.depends('line_ids.lot_id', 'line_ids.serial_photo')
    def _compute_sn_registration_count(self):
        for rec in self:
            rec.sn_registration_count = len(
                rec._get_sn_registration_lines())

    def action_open_sn_registration(self):
        self.ensure_one()
        if not self._get_sn_registration_lines():
            raise UserError(_(
                'Alle componenten met een serienummerfoto hebben al een '
                'serienummer.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('SN-registratie'),
            'res_model': 'serviq.sn.registration.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_installation_id': self.id},
        }

    # ------------------------------------------------------------------
    # Related SO's / PO's via the serial numbers on the installation
    # ------------------------------------------------------------------
    def _get_related_lots(self):
        """All serials tied to this installation: component lines, the
        installation-level serial and the reverse-linked lots."""
        self.ensure_one()
        return self.line_ids.lot_id | self.lot_id | self.lot_ids

    def _get_related_orders(self):
        """Sale and purchase orders whose stock moves touched one of this
        installation's serial numbers."""
        self.ensure_one()
        Sale = self.env['sale.order'].sudo()
        Purchase = self.env['purchase.order'].sudo()
        lots = self._get_related_lots()
        if not lots:
            return Sale.browse(), Purchase.browse()
        moves = self.env['stock.move.line'].sudo().search(
            [('lot_id', 'in', lots.ids)]).move_id
        sales = moves.sale_line_id.order_id | moves.picking_id.sale_id
        purchases = (moves.purchase_line_id.order_id
                     | moves.picking_id.purchase_id)
        return sales, purchases

    def _compute_related_order_counts(self):
        for rec in self:
            sales, purchases = rec._get_related_orders()
            rec.sale_order_count = len(sales)
            rec.purchase_order_count = len(purchases)

    @api.depends('task_ids', 'task_ids.serviq_intervention_type_id.group')
    def _compute_intervention_count(self):
        for rec in self:
            groups = rec.task_ids.mapped(
                lambda t: t.serviq_intervention_type_id.group
                or 'intervention')
            rec.repair_count = groups.count('repair')
            rec.replacement_count = groups.count('replacement')
            rec.intervention_count = groups.count('intervention')

    def _order_action(self, res_model, name, orders):
        action = {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': res_model,
            'domain': [('id', 'in', orders.ids)],
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'context': {'create': False},
        }
        if len(orders) == 1:
            action.update(res_id=orders.id, view_mode='form',
                          views=[(False, 'form')])
        return action

    def action_view_related_sale_orders(self):
        self.ensure_one()
        return self._order_action(
            'sale.order', _('Verkooporders'), self._get_related_orders()[0])

    def action_view_related_purchase_orders(self):
        self.ensure_one()
        return self._order_action(
            'purchase.order', _('Inkooporders'),
            self._get_related_orders()[1])

    def action_open_interventions(self):
        """Interventions of the installation. The smart buttons pass
        'serviq_intervention_group' in the context to show one group only
        (and to pre-fill the type when the group has a single one)."""
        self.ensure_one()
        group = self.env.context.get('serviq_intervention_group')
        names = dict(self.env['serviq.intervention.type']
                     ._fields['group']._description_selection(self.env))
        context = dict(self._intervention_task_context(),
                       default_serviq_installation_id=self.id)
        domain = [('serviq_installation_id', '=', self.id)]
        if group:
            types = self.env['serviq.intervention.type'].search(
                [('group', '=', group)])
            if len(types) == 1:
                context['default_serviq_intervention_type_id'] = types.id
            if group == 'intervention':
                domain += ['|', ('serviq_intervention_type_id', '=', False),
                           ('serviq_intervention_type_id.group', '=', group)]
            else:
                domain += [('serviq_intervention_type_id.group', '=', group)]
        return {
            'name': names.get(group, _('Interventies')),
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': domain,
            'context': context,
        }

    def action_plan_intervention(self):
        """New intervention for this installation, pre-filled with its
        customer, distributor and installer."""
        self.ensure_one()
        context = dict(self._intervention_task_context(),
                       default_serviq_installation_id=self.id)
        if self.customer_id:
            context['default_partner_id'] = self.customer_id.id
        if self.distributor_id:
            context['default_serviq_distributor_id'] = self.distributor_id.id
        if self.installer_id:
            context['default_serviq_installer_id'] = self.installer_id.id
        form = self.env.ref(
            'industry_fsm.project_task_view_form', raise_if_not_found=False)
        return {
            'name': _('Interventie plannen'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'view_mode': 'form',
            'views': [(form.id if form else False, 'form')],
            'target': 'current',
            'context': context,
        }

    # ------------------------------------------------------------------
    # Serial-number validation (shared with the portal flows)
    # ------------------------------------------------------------------
    def _validate_lot_for_line(self, lot, line=None,
                               expected_product_tmpl=None):
        """Reject `lot` if it cannot be used as a serial inside this
        installation:

        * lot must not be linked to another installation, unless it's
          already this one;
        * lot must not be used on a line of another installation;
        * lot must match the line's product template (when provided);
        * when the distributor stock check is on (settings), a stock.quant
          > 0 must exist for the lot in the distributor's customer location
          (or in the customer's location once delivered), unless the line
          opted to search outside that stock.
        """
        self.ensure_one()
        if not lot or self.env.context.get('skip_lot_validation'):
            return

        # A component holding a sub-installation shares its serial with
        # that sub-installation: they count as the same installation.
        family = self | self.parent_line_id.installation_id \
            | self.line_ids.sub_installation_id
        if lot.serviq_installation_id \
                and lot.serviq_installation_id not in family:
            raise ValidationError(_(
                'Serienummer "%(serial)s" is al gekoppeld aan installatie '
                '"%(installation)s".',
                serial=lot.name,
                installation=lot.serviq_installation_id.display_name))

        Line = self.env['serviq.installation.line'].sudo()
        clash_domain = [('lot_id', '=', lot.id),
                        ('installation_id', 'not in', family.ids)]
        if line and line.id:
            clash_domain += [('id', '!=', line.id)]
        clash = Line.search(clash_domain, limit=1)
        if clash:
            raise ValidationError(_(
                'Serienummer "%(serial)s" is al gebruikt op installatie '
                '"%(installation)s".',
                serial=lot.name,
                installation=clash.installation_id.display_name))

        if expected_product_tmpl and lot.product_id \
                and lot.product_id.product_tmpl_id != expected_product_tmpl:
            raise ValidationError(_(
                'Serienummer "%(serial)s" hoort bij product "%(actual)s", '
                'verwacht "%(expected)s".',
                serial=lot.name,
                actual=lot.product_id.product_tmpl_id.display_name,
                expected=expected_product_tmpl.display_name))

        check_stock = self.env['ir.config_parameter'].sudo().get_param(
            'serviq_installation.check_distributor_stock')
        outside_stock = bool(line and line.search_outside_stock)
        if check_stock and not outside_stock and self.distributor_id \
                and self.distributor_id.property_stock_customer:
            allowed = self.distributor_id.property_stock_customer
            if self.customer_id.property_stock_customer:
                allowed |= self.customer_id.property_stock_customer
            quant = self.env['stock.quant'].sudo().search([
                ('lot_id', '=', lot.id),
                ('location_id', 'in', allowed.ids),
                ('quantity', '>', 0),
            ], limit=1)
            if not quant:
                raise ValidationError(_(
                    'Serienummer "%(serial)s" bevindt zich niet in de '
                    'voorraad van distributeur "%(distributor)s".',
                    serial=lot.name,
                    distributor=self.distributor_id.display_name))

    @api.constrains('lot_id', 'distributor_id', 'customer_id', 'line_ids',
                    'line_ids.lot_id')
    def _check_installation_lots(self):
        """Validate the installation-level serial, plus reject duplicates
        across the lines of the same installation."""
        for rec in self:
            if rec.lot_id:
                rec._validate_lot_for_line(rec.lot_id)
            seen = set()
            for line in rec.line_ids.filtered('lot_id'):
                if line.lot_id.id in seen:
                    raise ValidationError(_(
                        'Serienummer "%(serial)s" is twee keer gebruikt in '
                        'installatie "%(installation)s".',
                        serial=line.lot_id.name,
                        installation=rec.display_name))
                seen.add(line.lot_id.id)
            if rec.lot_id and rec.lot_id.id in seen:
                raise ValidationError(_(
                    'Serienummer "%s" wordt zowel als serienummer van de '
                    'installatie als op een componentlijn gebruikt.',
                    rec.lot_id.name))

    # ------------------------------------------------------------------
    # Bill of materials -> component lines
    # ------------------------------------------------------------------
    @api.model
    def _bom_line_commands(self, product_tmpl):
        """Create commands for one component line per unit of the bill of
        materials of `product_tmpl` (empty without a BoM or without MRP)."""
        if not product_tmpl or 'mrp.bom' not in self.env:
            return []
        bom = self.env['mrp.bom'].sudo().search(
            [('product_tmpl_id', '=', product_tmpl.id)], limit=1)
        commands = []
        for bom_line in bom.bom_line_ids:
            for _unit in range(max(int(bom_line.product_qty), 1)):
                commands.append((0, 0, {
                    'product_tmpl_id': bom_line.product_id.product_tmpl_id.id,
                    'product_qty': 1,
                }))
        return commands

    def _process_sub_bom_for_line(self, line):
        """A component with its own bill of materials becomes a
        sub-installation holding its components (recursively)."""
        if not line.product_tmpl_id or line.sub_installation_id:
            return
        commands = self._bom_line_commands(line.product_tmpl_id)
        if not commands:
            return
        child = self.create({
            'product_tmpl_id': line.product_tmpl_id.id,
            'parent_line_id': line.id,
            'category_id': self.category_id.id,
            'customer_id': self.customer_id.id,
            'distributor_id': self.distributor_id.id,
            'installer_id': self.installer_id.id,
            'line_ids': commands,
        })
        line.sub_installation_id = child

    @api.onchange('product_tmpl_id')
    def _onchange_product_tmpl_id(self):
        self.line_ids = [(5, 0, 0)] + self._bom_line_commands(
            self.product_tmpl_id)
        if self.product_tmpl_id.serviq_category_id:
            self.category_id = self.product_tmpl_id.serviq_category_id

    def _propagate_partners(self, vals):
        """Customer, distributor and installer follow on the
        sub-installations."""
        partner_vals = {key: vals[key] for key in
                        ('customer_id', 'distributor_id', 'installer_id')
                        if key in vals}
        subs = self.line_ids.sub_installation_id
        if partner_vals and subs:
            subs.write(partner_vals)

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        """With 'serviq_customer_id' in the context (e.g. the installation
        of a task), the dropdown only offers the installations of that
        customer; 'Search More...' still lists every installation."""
        customer_id = self.env.context.get('serviq_customer_id')
        if customer_id:
            customer = self.env['res.partner'].browse(customer_id)
            domain = list(domain or []) + [(
                'customer_id', 'child_of',
                customer.commercial_partner_id.id or customer.id)]
        return super().name_search(
            name=name, domain=domain, operator=operator, limit=limit)

    # ------------------------------------------------------------------
    # Status following the interventions
    # ------------------------------------------------------------------
    # * 'Geleverd' / 'Installatie bezig' -> 'Inbedrijfstelling gepland' once
    #   a commissioning intervention is planned (categories that require
    #   it; back to the previous status when that date goes);
    # * -> 'Actief' once the commissioning is finished;
    # * 'Actief' / 'Offline' -> 'Service' while an intervention of a type
    #   that counts as service is planned and open, and back to the
    #   previous status once none is left.
    # A status set by hand is never reverted.
    def _service_tasks(self):
        """Open interventions with a planned date that put this
        installation in service."""
        self.ensure_one()
        Task = self.env['project.task'].sudo()
        lead = int(self.env['ir.config_parameter'].sudo().get_param(
            'serviq_installation.service_lead_days') or 14)
        horizon = fields.Datetime.now() + timedelta(days=lead)
        plan_field = Task._serviq_plan_field()
        return Task.search([
            ('serviq_installation_id', '=', self.id),
            (plan_field, '!=', False),
            (plan_field, '<=', horizon),
            ('date_end', '=', False),
            ('serviq_intervention_type_id.counts_as_service', '=', True),
        ]).filtered(lambda t: not t._serviq_is_finished()
                    and t.state != '1_canceled')

    def _commissioning_tasks_state(self):
        """(planned, finished): an open commissioning intervention with a
        planned date exists / a commissioning intervention is finished."""
        self.ensure_one()
        Task = self.env['project.task'].sudo()
        tasks = Task.search([
            ('serviq_installation_id', '=', self.id),
            ('serviq_intervention_type_id.is_commissioning', '=', True),
            ('state', '!=', '1_canceled'),
        ])
        finished = tasks.filtered(
            lambda t: t.date_end or t._serviq_is_finished())
        planned = (tasks - finished).filtered(Task._serviq_plan_field())
        return bool(planned), bool(finished)

    def _sync_commissioning_state(self):
        self.ensure_one()
        planned, finished = self._commissioning_tasks_state()
        if finished and self.state in COMMISSIONING_FROM_STATES \
                + ('commissioning',):
            self.write({'state': 'active',
                        'state_before_commissioning': False})
        elif planned and self.state in COMMISSIONING_FROM_STATES \
                and (not self.category_id
                     or self.category_id.requires_commissioning):
            self.write({'state_before_commissioning': self.state,
                        'state': 'commissioning'})
        elif not planned and not finished \
                and self.state == 'commissioning' \
                and self.state_before_commissioning:
            self.write({'state': self.state_before_commissioning,
                        'state_before_commissioning': False})

    def _sync_service_state(self):
        """Status of each installation following its interventions: the
        commissioning first, then service."""
        for rec in self.sudo().with_context(serviq_service_sync=True):
            rec._sync_commissioning_state()
            if rec._service_tasks():
                if rec.state in SERVICE_FROM_STATES:
                    rec.write({'state_before_service': rec.state,
                               'state': 'service'})
            elif rec.state == 'service' and rec.state_before_service:
                rec.write({'state': rec.state_before_service,
                           'state_before_service': False})

    @api.model
    def _cron_sync_service_state(self):
        """Daily: interventions entering their service window,
        installations in automatic service whose intervention is gone, and
        installations not active yet (their commissioning)."""
        Task = self.env['project.task'].sudo()
        plan_field = Task._serviq_plan_field()
        planned = Task.search([
            ('serviq_installation_id', '!=', False),
            (plan_field, '!=', False),
            ('date_end', '=', False),
        ]).serviq_installation_id
        auto = self.sudo().search([
            '|', ('state_before_service', '!=', False),
            ('state', 'in', list(COMMISSIONING_FROM_STATES)
             + ['commissioning']),
        ])
        (planned | auto)._sync_service_state()

    # ------------------------------------------------------------------
    # Chatter
    # ------------------------------------------------------------------
    def _post_creation_summary(self, origin=None):
        """Chatter summary of the key data of a freshly created
        installation + a toast notification to the user who triggered the
        creation. Flows that add component lines right after create() pass
        the ``defer_creation_summary`` context flag and call this afterwards
        so the component/serial info is included."""
        state_labels = dict(self._fields['state'].selection)

        def esc(value):
            return html_escape(value or '-')

        for rec in self:
            lines = rec.line_ids
            serials = [l.lot_id.name for l in lines if l.lot_id]
            parts = [
                esc(_('Nieuwe installatie aangemaakt:')),
                Markup('• %s: <b>%s</b>') % (_('Referentie'), rec.code or '-'),
                Markup('• %s: <b>%s</b>') % (
                    _('Product'), rec.product_tmpl_id.display_name or '-'),
                Markup('• %s: <b>%s</b>') % (
                    _('Categorie'), rec.category_id.display_name or '-'),
                Markup('• %s: <b>%s</b>') % (
                    _('Status'), state_labels.get(rec.state) or '-'),
                Markup('• %s: <b>%s</b>') % (
                    _('Distributeur'), rec.distributor_id.display_name or '-'),
                Markup('• %s: <b>%s</b>') % (
                    _('Klant'), rec.customer_id.display_name or '-'),
                Markup('• %s: <b>%s</b>') % (
                    _('Installateur'), rec.installer_id.display_name or '-'),
            ]
            if lines:
                parts.append(Markup('• %s: <b>%d</b>') % (
                    _('Componenten'), len(lines)))
            if serials:
                shown = ', '.join(serials[:10])
                if len(serials) > 10:
                    shown += ' …'
                parts.append(Markup('• %s (%d): %s') % (
                    _('Serienummers'), len(serials), shown))
            if origin:
                parts.append(Markup('• %s: %s') % (_('Bron'), origin))
            rec.message_post(body=Markup('<br/>').join(parts))

            # Toast for the user who triggered the creation (e.g. the
            # warehouse operator validating a delivery). Best effort.
            try:
                self.env['bus.bus']._sendone(
                    self.env.user.partner_id, 'simple_notification', {
                        'type': 'success',
                        'title': _('Installatie aangemaakt'),
                        'message': _(
                            '%(code)s - %(customer)s (%(count)d '
                            'componenten)',
                            code=rec.code or rec.display_name,
                            customer=rec.customer_id.display_name or '-',
                            count=len(lines)),
                    })
            except Exception:
                pass

    def _log_line_changes(self, commands, old_lines):
        """Trace added / changed / removed component lines in the
        chatter."""
        Template = self.env['product.template']
        Lot = self.env['stock.lot']
        for command in commands:
            if not isinstance(command, (list, tuple)) or not command:
                continue
            if command[0] == 0:
                line_vals = command[2]
                body = Markup('%s<br/>• %s: <b>%s</b><br/>• %s: <b>%s</b>') % (
                    _('Component toegevoegd:'), _('Component'),
                    Template.browse(line_vals.get('product_tmpl_id'))
                    .display_name or '-',
                    _('Hoeveelheid'), line_vals.get('product_qty', 1))
                if line_vals.get('lot_id'):
                    body += Markup('<br/>• %s: <b>%s</b>') % (
                        _('Lot/Serienummer'),
                        Lot.browse(line_vals['lot_id']).name)
                self.message_post(body=body)
            elif command[0] == 1:
                old = old_lines.get(command[1], {})
                new_vals = command[2]
                changes = []
                if 'product_qty' in new_vals:
                    changes.append(Markup('• %s: <b>%s</b> → <b>%s</b>') % (
                        _('Hoeveelheid'), old.get('qty'),
                        new_vals['product_qty']))
                if 'lot_id' in new_vals:
                    changes.append(Markup('• %s: <b>%s</b> → <b>%s</b>') % (
                        _('Lot/Serienummer'), old.get('lot') or '-',
                        Lot.browse(new_vals['lot_id']).name
                        if new_vals['lot_id'] else '-'))
                if 'product_tmpl_id' in new_vals:
                    changes.append(Markup('• %s: <b>%s</b> → <b>%s</b>') % (
                        _('Component'), old.get('product') or '-',
                        Template.browse(new_vals['product_tmpl_id'])
                        .display_name or '-'))
                if changes:
                    self.message_post(
                        body=Markup('<br/>').join(
                            [html_escape(_('Component gewijzigd:'))] + changes))
            elif command[0] == 2:
                old = old_lines.get(command[1])
                if old:
                    self.message_post(body=Markup(
                        '%s<br/>• %s: <b>%s</b><br/>• %s: <b>%s</b><br/>'
                        '• %s: <b>%s</b>') % (
                        _('Component verwijderd:'), _('Component'),
                        old.get('product'), _('Hoeveelheid'), old.get('qty'),
                        _('Lot/Serienummer'), old.get('lot') or '-'))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        Sequence = self.env['ir.sequence']
        Template = self.env['product.template']
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = Sequence.next_by_code('serviq.installation')
            if not vals.get('category_id') and vals.get('product_tmpl_id'):
                category = Template.browse(
                    vals['product_tmpl_id']).serviq_category_id
                if category:
                    vals['category_id'] = category.id
        records = super().create(vals_list)
        for record in records:
            for line in record.line_ids:
                record._process_sub_bom_for_line(line)
            if record.lot_id:
                record.lot_id.serviq_installation_id = record
            # Sub-installations spawned per component line would be noise;
            # only summarize top-level installations.
            if not record.parent_line_id \
                    and not self.env.context.get('defer_creation_summary'):
                record._post_creation_summary()
        return records

    def write(self, vals):
        # A status set by hand ends the automatic service.
        if 'state' in vals and not self.env.context.get('serviq_service_sync'):
            vals = dict(vals, state_before_service=False,
                        state_before_commissioning=False)
        old_lines = {
            line.id: {
                'product': line.product_tmpl_id.display_name,
                'qty': line.product_qty,
                'lot': line.lot_id.name,
            }
            for line in self.line_ids
        } if 'line_ids' in vals else {}
        res = super().write(vals)
        if 'product_tmpl_id' in vals or 'line_ids' in vals:
            for rec in self:
                for line in rec.line_ids:
                    rec._process_sub_bom_for_line(line)
        if vals.get('lot_id'):
            self.lot_id.serviq_installation_id = self[:1]
            if not self.env.context.get('call_from_line'):
                self.parent_line_id.with_context(
                    call_from_installation=True).lot_id = vals['lot_id']
        self._propagate_partners(vals)
        if 'line_ids' in vals and len(self) == 1:
            self._log_line_changes(vals['line_ids'], old_lines)
        return res

