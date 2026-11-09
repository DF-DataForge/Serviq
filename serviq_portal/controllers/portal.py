# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from urllib.parse import quote, urlencode

import pytz
from werkzeug.exceptions import NotFound

from odoo import _, fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
from odoo.tools import html2plaintext, plaintext2html

from odoo.addons.portal.controllers.portal import (
    CustomerPortal, pager as portal_pager,
)

_logger = logging.getLogger(__name__)

PAGE_STEP = 20
CLOSED_TASK_STATES = ('1_done', '1_canceled')


class ServiqPortal(CustomerPortal):

    # ------------------------------------------------------------------
    # Who is the user
    # ------------------------------------------------------------------
    @staticmethod
    def _serviq_user_info():
        """(partner, commercial partner, is_internal, is_distributor,
        is_installer) of the current user. The roles are read on the
        commercial partner (the company) as well as on the contact."""
        user = request.env.user
        partner = user.partner_id.sudo()
        commercial = partner.commercial_partner_id
        return (
            partner, commercial, not user.share,
            bool(partner.serviq_is_distributor
                 or commercial.serviq_is_distributor),
            bool(partner.serviq_is_installer
                 or commercial.serviq_is_installer),
        )

    def _serviq_has_portal_access(self):
        _partner, _commercial, is_internal, is_distributor, is_installer = \
            self._serviq_user_info()
        return is_internal or is_distributor or is_installer

    def _serviq_installation_domain(self):
        """Top-level installations visible to the user."""
        _partner, commercial, is_internal, is_distributor, is_installer = \
            self._serviq_user_info()
        domain = [('parent_line_id', '=', False)]
        if is_internal:
            return domain
        parts = []
        if is_distributor:
            parts.append([('distributor_id', 'child_of', commercial.id)])
        if is_installer:
            parts.append([('installer_id', 'child_of', commercial.id)])
        if not parts:
            return [('id', '=', 0)]
        if len(parts) == 2:
            return domain + ['|'] + parts[0] + parts[1]
        return domain + parts[0]

    def _serviq_intervention_domain(self):
        """Interventions visible to the user."""
        _partner, commercial, is_internal, is_distributor, is_installer = \
            self._serviq_user_info()
        domain = [('serviq_intervention_type_id', '!=', False)]
        if is_internal:
            return domain
        parts = []
        if is_distributor:
            parts.append([('serviq_distributor_id', 'child_of',
                           commercial.id)])
        if is_installer:
            parts.append([('serviq_installer_id', 'child_of',
                           commercial.id)])
        if not parts:
            return [('id', '=', 0)]
        if len(parts) == 2:
            return domain + ['|'] + parts[0] + parts[1]
        return domain + parts[0]

    @staticmethod
    def _serviq_same_company(partner_a, partner_b):
        return bool(partner_a and partner_b
                    and partner_a.commercial_partner_id
                    == partner_b.commercial_partner_id)

    def _check_installation_access(self, installation):
        if not installation.exists():
            return False
        _partner, commercial, is_internal, is_distributor, is_installer = \
            self._serviq_user_info()
        if is_internal:
            return True
        return bool(
            (is_distributor and self._serviq_same_company(
                installation.distributor_id, commercial))
            or (is_installer and self._serviq_same_company(
                installation.installer_id, commercial)))

    def _check_intervention_access(self, task):
        if not task.exists() or not task.serviq_intervention_type_id:
            return False
        _partner, commercial, is_internal, is_distributor, is_installer = \
            self._serviq_user_info()
        if is_internal:
            return True
        if is_installer and self._serviq_same_company(
                task.serviq_installer_id, commercial):
            return True
        if is_distributor and (
                self._serviq_same_company(
                    task.serviq_distributor_id, commercial)
                or self._serviq_same_company(
                    task.serviq_installation_id.distributor_id, commercial)):
            return True
        return False

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _serviq_values(self, page_name, **kw):
        partner, commercial, is_internal, is_distributor, is_installer = \
            self._serviq_user_info()
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': page_name,
            'partner': partner,
            'commercial_partner': commercial,
            'is_internal': is_internal,
            'is_distributor': is_distributor,
            'is_installer': is_installer,
            'state_labels': dict(request.env['serviq.installation']
                                 ._fields['state'].selection),
            'task_state_labels': dict(request.env['project.task']
                                      ._fields['state'].selection),
        })
        values.update(kw)
        return values

    def _serviq_no_access(self):
        return request.render('serviq_portal.portal_no_access',
                              self._serviq_values('serviq_no_access'))

    @staticmethod
    def _intervention_url(task_id, anchor='', message=None, error=None):
        params = {}
        if message:
            params['message'] = str(message)
        if error:
            params['error'] = str(error)
        url = '/my/installations/intervention/%d' % int(task_id)
        if params:
            url += '?' + urlencode(params)
        if anchor:
            url += '#' + anchor
        return url

    def _intervention_redirect(self, task_id, anchor='', message=None,
                               error=None):
        return request.redirect(self._intervention_url(
            task_id, anchor=anchor, message=message, error=error))

    @staticmethod
    def _task_maps_url(task):
        """Google Maps directions to the address of the customer."""
        customer = task.partner_id
        if not customer:
            return ''
        destination = ', '.join(part for part in (
            customer.street, customer.street2, customer.zip, customer.city,
            customer.country_id.name) if part)
        if not destination:
            return ''
        return 'https://www.google.com/maps/dir/?api=1&destination=%s' \
            % quote(destination)

    @staticmethod
    def _task_is_closed(task):
        return task.state in CLOSED_TASK_STATES \
            or task._serviq_is_finished()

    # ------------------------------------------------------------------
    # /my home tiles
    # ------------------------------------------------------------------
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        wanted = {'serviq_installation_count', 'serviq_intervention_count'}
        if not wanted & set(counters):
            return values
        has_access = self._serviq_has_portal_access()
        if 'serviq_installation_count' in counters:
            values['serviq_installation_count'] = \
                request.env['serviq.installation'].sudo().search_count(
                    self._serviq_installation_domain()) if has_access else 0
        if 'serviq_intervention_count' in counters:
            values['serviq_intervention_count'] = \
                request.env['project.task'].sudo().search_count(
                    self._serviq_intervention_domain()
                    + [('state', 'not in', list(CLOSED_TASK_STATES))]) \
                if has_access else 0
        return values

    # ------------------------------------------------------------------
    # Installations
    # ------------------------------------------------------------------
    @http.route(['/my/installations',
                 '/my/installations/page/<int:page>'],
                type='http', auth='user', website=True)
    def serviq_installations(self, page=1, state=None, search=None, **kw):
        if not self._serviq_has_portal_access():
            return self._serviq_no_access()
        Installation = request.env['serviq.installation'].sudo()
        domain = self._serviq_installation_domain()
        state_labels = dict(Installation._fields['state'].selection)
        if state and state in state_labels:
            domain += [('state', '=', state)]
        else:
            state = None
        search = (search or '').strip()
        if search:
            domain += ['|', '|', '|', ('name', 'ilike', search),
                       ('customer_id', 'ilike', search),
                       ('lot_id.name', 'ilike', search),
                       ('line_ids.lot_id.name', 'ilike', search)]
        total = Installation.search_count(domain)
        url_args = {key: value for key, value in
                    (('state', state), ('search', search)) if value}
        pager = portal_pager(url='/my/installations', total=total,
                             page=page, step=PAGE_STEP, url_args=url_args)
        installations = Installation.search(
            domain, limit=PAGE_STEP, offset=pager['offset'],
            order='create_date desc, id desc')
        return request.render(
            'serviq_portal.portal_installation_list',
            self._serviq_values(
                'serviq_installations', installations=installations,
                pager=pager, state=state, search=search))

    @http.route(['/my/installations/<int:installation_id>'],
                type='http', auth='user', website=True)
    def serviq_installation_detail(self, installation_id, **kw):
        installation = request.env['serviq.installation'].sudo().browse(
            installation_id)
        if not self._check_installation_access(installation):
            return self._serviq_no_access()
        tasks = installation.task_ids.sorted(
            lambda t: (t.create_date or datetime.min), reverse=True)
        return request.render(
            'serviq_portal.portal_installation_detail',
            self._serviq_values(
                'serviq_installation', installation=installation,
                tasks=tasks))

    # ------------------------------------------------------------------
    # Interventions
    # ------------------------------------------------------------------
    @http.route(['/my/installations/interventions',
                 '/my/installations/interventions/page/<int:page>'],
                type='http', auth='user', website=True)
    def serviq_interventions(self, page=1, type_id=None, status='open',
                             **kw):
        if not self._serviq_has_portal_access():
            return self._serviq_no_access()
        Task = request.env['project.task'].sudo()
        base_domain = self._serviq_intervention_domain()
        if status == 'open':
            base_domain += [('state', 'not in', list(CLOSED_TASK_STATES))]
        elif status == 'done':
            base_domain += [('state', '=', '1_done')]
        else:
            status = 'all'

        # Filter tabs: the intervention types (data, not hardcoded) with
        # their number of interventions.
        counts = dict(
            (itype.id, count) for itype, count in Task._read_group(
                base_domain, groupby=['serviq_intervention_type_id'],
                aggregates=['__count']))
        types = request.env['serviq.intervention.type'].sudo().search([])
        type_tabs = [{'type': itype, 'count': counts.get(itype.id, 0)}
                     for itype in types]
        try:
            type_id = int(type_id or 0)
        except (TypeError, ValueError):
            type_id = 0
        domain = list(base_domain)
        if type_id:
            domain += [('serviq_intervention_type_id', '=', type_id)]

        total = Task.search_count(domain)
        url_args = {'status': status}
        if type_id:
            url_args['type_id'] = type_id
        pager = portal_pager(url='/my/installations/interventions',
                             total=total, page=page, step=PAGE_STEP,
                             url_args=url_args)
        plan_field = Task._serviq_plan_field()
        tasks = Task.search(
            domain, limit=PAGE_STEP, offset=pager['offset'],
            order='%s asc, create_date desc' % plan_field)
        task_flows = {
            task.id: request.env['serviq.portal.flow']
            ._get_applicable_flows(task)[:1]
            for task in tasks}
        return request.render(
            'serviq_portal.portal_intervention_list',
            self._serviq_values(
                'serviq_interventions', tasks=tasks, pager=pager,
                type_tabs=type_tabs, type_id=type_id, status=status,
                total_all=sum(counts.values()), task_flows=task_flows,
                plan_field=plan_field))

    @http.route(['/my/installations/planning'],
                type='http', auth='user', website=True)
    def serviq_planning(self, scope='month', date=None, installer_id=None,
                        **kw):
        """Planning calendar (month / week / day) built on the calendar
        data of the core, narrowed to the interventions of the user."""
        if not self._serviq_has_portal_access():
            return self._serviq_no_access()
        _partner, commercial, is_internal, is_distributor, _is_installer = \
            self._serviq_user_info()
        try:
            anchor = fields.Date.to_date(date) if date else False
        except ValueError:
            anchor = False
        try:
            installer_id = int(installer_id or 0)
        except (TypeError, ValueError):
            installer_id = 0
        if scope not in ('month', 'week', 'day'):
            scope = 'month'

        data = request.env['serviq.installation'].sudo() \
            .get_planning_calendar_data(
                scope=scope, anchor=anchor and fields.Date.to_string(anchor),
                installer_id=installer_id or False)
        if not is_internal:
            allowed = set(request.env['project.task'].sudo().search(
                self._serviq_intervention_domain()).ids)
            data['tasks_by_day'] = {
                day: [t for t in tasks if t['id'] in allowed]
                for day, tasks in data['tasks_by_day'].items()}
            data['without_date'] = [
                t for t in data['without_date'] if t['id'] in allowed]
            if is_distributor:
                installers = request.env['res.partner'].sudo().search([
                    ('serviq_is_installer', '=', True),
                    ('serviq_can_install_for_ids', 'child_of',
                     commercial.id)], order='name')
                data['installers'] = [[p.id, p.display_name]
                                      for p in installers]
            else:
                data['installers'] = []
        self._serviq_planning_mark_done(data)

        def url(scope_, day, installer=installer_id):
            args = {'scope': scope_, 'date': day}
            if installer:
                args['installer_id'] = installer
            return '/my/installations/planning?' + urlencode(args)

        return request.render(
            'serviq_portal.portal_planning',
            self._serviq_values(
                'serviq_planning', cal=data, scope=scope,
                installer_id=installer_id, url=url,
                legend=data.get('legend') or [],
                weekday_labels=[_('Ma'), _('Di'), _('Wo'), _('Do'),
                                _('Vr'), _('Za'), _('Zo')]))

    @staticmethod
    def _serviq_planning_mark_done(data):
        """Calendar chips are green once the intervention is finished
        (end date, done / folded stage or field service 'done'), and
        finished or cancelled interventions without a date leave the
        'Nog niet ingepland' list."""
        items = [item for day_items in data['tasks_by_day'].values()
                 for item in day_items] + data['without_date']
        tasks = request.env['project.task'].sudo().browse(
            list({item['id'] for item in items})).exists()
        finished = {task.id for task in tasks
                    if task.date_end or task._serviq_is_finished()}
        canceled = {task.id for task in tasks
                    if task.state == '1_canceled'}
        for item in items:
            item['done'] = bool(item.get('done')) or item['id'] in finished
        data['without_date'] = [
            item for item in data['without_date']
            if not item['done'] and item['id'] not in canceled]

    # ------------------------------------------------------------------
    # Intervention page
    # ------------------------------------------------------------------
    def _serviq_flow_sections(self, task, partner, is_internal):
        """[{'flow', 'template', 'values'}] of the active flows applying
        to `task`. A failing flow is logged and left out, so one broken
        flow does not take the page down."""
        sections = []
        for flow in request.env['serviq.portal.flow']._get_applicable_flows(
                task):
            try:
                with request.env.cr.savepoint():
                    flow_values = flow._get_handler()._flow_values(
                        task, flow, partner, is_internal) or {}
            except Exception:
                _logger.exception('Serviq portal: flow %s failed on task %s',
                                  flow.code, task.id)
                continue
            sections.append({
                'flow': flow,
                'template': flow.template,
                'values': dict(flow_values, flow=flow),
                'action': '/my/installations/intervention/%d/flow/%s'
                          % (task.id, flow.code),
            })
        return sections

    @http.route(['/my/installations/intervention/<int:task_id>'],
                type='http', auth='user', website=True, methods=['GET'])
    def serviq_intervention_detail(self, task_id, message=None, error=None,
                                   **kw):
        task = request.env['project.task'].sudo().browse(task_id)
        if not self._check_intervention_access(task):
            return self._serviq_no_access()
        partner, _commercial, is_internal, _dist, _inst = \
            self._serviq_user_info()
        timesheets_enabled = 'timesheet_ids' in task._fields \
            and 'account.analytic.line' in request.env
        timesheets = task._serviq_timesheets_chronological() \
            if timesheets_enabled else False
        return request.render(
            'serviq_portal.portal_intervention_detail',
            self._serviq_values(
                'serviq_intervention', task=task,
                installation=task.serviq_installation_id,
                is_closed=self._task_is_closed(task),
                report_text=html2plaintext(task.description or ''),
                maps_url=self._task_maps_url(task),
                plan_field=task._serviq_plan_field(),
                timesheets_enabled=timesheets_enabled,
                timesheets=timesheets,
                time_type_labels=dict(
                    request.env['account.analytic.line']
                    ._fields['serviq_time_type']._description_selection(
                        request.env)) if timesheets_enabled else {},
                flow_sections=self._serviq_flow_sections(
                    task, partner, is_internal),
                message=message, error=error))

    def _serviq_task_for_post(self, task_id):
        task = request.env['project.task'].sudo().browse(task_id)
        return task if self._check_intervention_access(task) else None

    @http.route(['/my/installations/intervention/<int:task_id>/report'],
                type='http', auth='user', website=True, methods=['POST'])
    def serviq_intervention_report(self, task_id, **post):
        """Save the report / notes of the intervention (its
        description)."""
        task = self._serviq_task_for_post(task_id)
        if not task:
            return self._serviq_no_access()
        partner = self._serviq_user_info()[0]
        report = (post.get('report') or '').strip()
        task.write({'description': plaintext2html(report) if report
                    else False})
        task.message_post(
            body=_('Rapport bijgewerkt via het portaal.'),
            author_id=partner.id)
        return self._intervention_redirect(
            task.id, anchor='report', message=_('Rapport opgeslagen.'))

    @staticmethod
    def _serviq_employee(partner, company=None, create=False):
        """Employee linked to the user or to its contact. With `create`, an
        external installer without one gets an employee record of their own
        (no user, linked to their contact), since timesheets need an
        active employee; later registrations reuse it."""
        if 'hr.employee' not in request.env:
            return None
        Employee = request.env['hr.employee'].sudo()
        employee = Employee.search(
            [('user_id', '=', request.env.user.id)], limit=1)
        if not employee:
            employee = partner.sudo().serviq_employee_id
        if not employee and create:
            employee = partner.sudo()._serviq_get_or_create_employee(
                company, origin=_('uurregistratie in het portaal'))
        return employee

    @staticmethod
    def _serviq_parse_local(value):
        """datetime of a datetime-local input ('YYYY-MM-DDTHH:MM'), None
        when empty; raises ValueError when invalid."""
        value = (value or '').strip()
        return datetime.strptime(value, '%Y-%m-%dT%H:%M') if value else None

    @staticmethod
    def _serviq_parse_km(value):
        """Kilometres of a number input (',' accepted as decimal mark);
        raises ValueError when invalid or negative."""
        km = float((value or '0').strip().replace(',', '.') or 0)
        if km < 0:
            raise ValueError(km)
        return km

    @http.route(['/my/installations/intervention/<int:task_id>/hours'],
                type='http', auth='user', website=True, methods=['POST'])
    def serviq_intervention_hours(self, task_id, **post):
        """Log the time of an intervention as timesheet lines, in
        chronological order: the ride there ('Heenrit', departure to the
        customer -> arrival, optional), the time on site (arrival ->
        departure at the customer) and the ride back ('Terugrit', departure
        at the customer -> back, optional), with the kilometres of each
        ride. The time on site sets the planning of the intervention."""
        task = self._serviq_task_for_post(task_id)
        if not task:
            return self._serviq_no_access()
        partner = self._serviq_user_info()[0]

        def back(message=None, error=None):
            return self._intervention_redirect(
                task.id, anchor='hours', message=message, error=error)

        if 'timesheet_ids' not in task._fields:
            return back(error=_('Uren loggen is niet beschikbaar.'))
        try:
            travel_start = self._serviq_parse_local(post.get('travel_start'))
            arrival = self._serviq_parse_local(post.get('arrival'))
            departure = self._serviq_parse_local(post.get('departure'))
            back_end = self._serviq_parse_local(post.get('back_end'))
        except ValueError:
            return back(error=_('Vul geldige tijden in.'))
        if not arrival or not departure:
            return back(error=_('Vul een geldige aankomst- en vertrektijd '
                                'in.'))
        if departure <= arrival:
            return back(error=_('De vertrektijd moet na de aankomsttijd '
                                'liggen.'))
        if travel_start and travel_start >= arrival:
            return back(error=_('Het vertrek naar de klant moet voor de '
                                'aankomst liggen.'))
        if back_end and back_end <= departure:
            return back(error=_('De aankomst na de terugrit moet na het '
                                'vertrek bij de klant liggen.'))
        try:
            km_out = self._serviq_parse_km(post.get('km_out'))
            km_back = self._serviq_parse_km(post.get('km_back'))
        except ValueError:
            return back(error=_('Ongeldig aantal kilometers.'))
        # The kilometres are logged on the line of their ride.
        if km_out and not travel_start:
            return back(error=_('Vul het vertrek naar de klant in om de '
                                'kilometers van de heenrit te loggen.'))
        if km_back and not back_end:
            return back(error=_('Vul de aankomst na de terugrit in om de '
                                'kilometers van de terugrit te loggen.'))
        if not task.project_id:
            return back(error=_('Deze interventie hoort bij geen project.'))
        employee = self._serviq_employee(
            partner, company=task.company_id or request.env.company,
            create=True)
        if not employee:
            return back(error=_('Uren loggen is niet beschikbaar.'))

        # The form holds local times; store UTC like every Odoo datetime.
        tz = pytz.timezone(request.env.user.tz or 'UTC')

        def to_utc(local):
            return tz.localize(local).astimezone(pytz.utc) \
                .replace(tzinfo=None)

        def hours_between(begin, end):
            return (end - begin).total_seconds() / 3600.0

        def line(begin, end, time_type, label, km=0.0):
            return {
                'task_id': task.id,
                'project_id': task.project_id.id,
                'employee_id': employee.id,
                'date': begin.date(),
                'unit_amount': round(hours_between(begin, end), 2),
                'name': _('%(label)s %(start)s - %(end)s', label=label,
                          start=begin.strftime('%H:%M'),
                          end=end.strftime('%H:%M')),
                'serviq_start': to_utc(begin),
                'serviq_end': to_utc(end),
                'serviq_time_type': time_type,
                'serviq_km': round(km, 1),
            }

        # Chronological: ride there, time on site, ride back.
        vals_list = []
        if travel_start:
            vals_list.append(line(travel_start, arrival, 'travel',
                                  _('Heenrit'), km_out))
        vals_list.append(line(arrival, departure, 'intervention',
                              _('Interventie')))
        if back_end:
            vals_list.append(line(departure, back_end, 'travel_back',
                                  _('Terugrit'), km_back))
        try:
            with request.env.cr.savepoint():
                request.env['account.analytic.line'].sudo().create(vals_list)
        except (UserError, ValidationError, AccessError) as exc:
            return back(error=exc.args[0] if exc.args else str(exc))

        parts = [_('Tijd gelogd door %(name)s:', name=employee.name)]
        if travel_start:
            parts.append(_('heenrit %(hours).2f u (vertrek %(start)s)',
                           hours=hours_between(travel_start, arrival),
                           start=travel_start.strftime('%H:%M')))
        parts.append(_('interventie %(hours).2f u (%(start)s - %(end)s)',
                       hours=hours_between(arrival, departure),
                       start=arrival.strftime('%d/%m/%Y %H:%M'),
                       end=departure.strftime('%H:%M')))
        if back_end:
            parts.append(_('terugrit %(hours).2f u (terug %(end)s)',
                           hours=hours_between(departure, back_end),
                           end=back_end.strftime('%H:%M')))
        if km_out or km_back:
            parts.append(_('km heen %(out).1f, km terug %(back).1f',
                           out=km_out, back=km_back))
        task.message_post(body=' '.join(parts[:1]) + ' '
                          + ', '.join(parts[1:]) + '.',
                          author_id=partner.id)
        return back(message=_('Tijd gelogd.'))

    @http.route(['/my/installations/intervention/<int:task_id>/state'],
                type='http', auth='user', website=True, methods=['POST'])
    def serviq_intervention_state(self, task_id, action=None, **post):
        """Mark the intervention as done, or reopen it."""
        task = self._serviq_task_for_post(task_id)
        if not task:
            return self._serviq_no_access()
        partner = self._serviq_user_info()[0]
        if action == 'done':
            task.write({'state': '1_done',
                        'date_end': fields.Datetime.now()})
            body = _('Interventie afgerond door %s.', partner.name)
            message = _('Interventie afgerond.')
        elif action == 'reopen':
            task.write({'state': '01_in_progress', 'date_end': False})
            body = _('Interventie heropend door %s.', partner.name)
            message = _('Interventie heropend.')
        else:
            return self._intervention_redirect(
                task.id, error=_('Onbekende actie.'))
        task.message_post(body=body, author_id=partner.id)
        return self._intervention_redirect(task.id, message=message)

    # ------------------------------------------------------------------
    # Flows
    # ------------------------------------------------------------------
    def _serviq_flow_for(self, task, code):
        """Active flow `code` applying to `task`, else raises NotFound."""
        flow = request.env['serviq.portal.flow'].sudo().search(
            [('code', '=', code)], limit=1)
        if not flow or not flow._get_handler()._flow_applies(task, flow):
            raise NotFound()
        return flow

    @http.route(['/my/installations/intervention/<int:task_id>/flow/'
                 '<string:code>'],
                type='http', auth='user', website=True, methods=['POST'])
    def serviq_intervention_flow(self, task_id, code, **post):
        """Generic entry point of the forms of the flows: dispatches to
        the handler of the flow."""
        task = self._serviq_task_for_post(task_id)
        if not task:
            return self._serviq_no_access()
        flow = self._serviq_flow_for(task, code)
        partner, _commercial, is_internal, _dist, _inst = \
            self._serviq_user_info()
        anchor = 'flow-%s' % flow.code
        post.pop('csrf_token', None)
        try:
            with request.env.cr.savepoint():
                result = flow._get_handler()._flow_submit(
                    task, flow, partner, is_internal, post)
        except (UserError, ValidationError, AccessError) as exc:
            return self._intervention_redirect(
                task.id, anchor=anchor,
                error=exc.args[0] if exc.args else _('Actie mislukt.'))
        if isinstance(result, str):
            return request.redirect(result)
        message, error = result if result else (None, None)
        return self._intervention_redirect(
            task.id, anchor=anchor, message=message, error=error)

    @http.route(['/my/installations/intervention/<int:task_id>/flow/'
                 '<string:code>/check'],
                type='http', auth='user', methods=['GET'])
    def serviq_intervention_flow_check(self, task_id, code, **params):
        """Live check of a flow (JSON), see _flow_check."""
        task = self._serviq_task_for_post(task_id)
        if not task:
            return request.make_json_response(
                {'ok': False, 'message': _('Geen toegang.')}, status=403)
        flow = self._serviq_flow_for(task, code)
        partner, _commercial, is_internal, _dist, _inst = \
            self._serviq_user_info()
        try:
            result = flow._get_handler()._flow_check(
                task, flow, partner, is_internal, params)
        except (UserError, ValidationError, AccessError) as exc:
            result = {'ok': False,
                      'message': exc.args[0] if exc.args else ''}
        return request.make_json_response(result)
