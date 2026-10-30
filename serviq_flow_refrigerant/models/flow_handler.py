# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RefrigerantFlow(models.AbstractModel):
    """Registration of a refrigeration system (koeltechnisch systeem) in
    the portal: its refrigerant data (type, nominal charge, hermetic, leak
    detection, date in service), and the handlings of the logbook (charge,
    addition, recovery, leak check, repair, maintenance, failure,
    decommissioning) by a certified technician of a certified company."""
    _name = 'serviq.portal.flow.handler.refrigerant'
    _inherit = 'serviq.portal.flow.handler'
    _description = 'Portaalflow: koudemiddelregistratie'

    @api.model
    def _flow_applies(self, task, flow):
        installation = task.serviq_installation_id
        if installation and not installation.has_refrigerant:
            return False
        if not installation and not (
                task.serviq_intervention_type_id.is_first_installation):
            return False
        return super()._flow_applies(task, flow)

    # ------------------------------------------------------------------
    # Technician / company
    # ------------------------------------------------------------------
    @api.model
    def _rf_contractor(self, partner, is_internal):
        """Company doing the work: the company of the portal user, or our
        own company for internal users."""
        if is_internal:
            return self.env.company.partner_id
        return partner.commercial_partner_id

    @api.model
    def _rf_cylinders(self, installation, contractor):
        domain = [('owner_id', '=', contractor.id)]
        if installation.refrigerant_id:
            domain.append(('refrigerant_id', '=', installation.refrigerant_id.id))
        return self.env['serviq.refrigerant.cylinder'].search(domain)

    @api.model
    def _flow_values(self, task, flow, partner, is_internal):
        installation = task.serviq_installation_id
        Log = self.env['serviq.refrigerant.log']
        contractor = self._rf_contractor(partner, is_internal)
        return {
            'rf_installation': installation,
            'rf_refrigerants': self.env['serviq.refrigerant'].search([]),
            'rf_entry_types': Log._fields['entry_type']
            ._description_selection(self.env),
            'rf_origins': Log._fields['origin']._description_selection(
                self.env),
            'rf_leak_results': Log._fields['leak_result']
            ._description_selection(self.env),
            'rf_check_states': dict(installation._fields['fgas_check_state']
                                    ._description_selection(self.env)),
            'rf_logs': installation.refrigerant_log_ids,
            'rf_cylinders': self._rf_cylinders(installation, contractor)
            if installation else self.env['serviq.refrigerant.cylinder'],
            'rf_technician': partner,
            'rf_contractor': contractor,
            'rf_technician_valid': partner._serviq_fgas_certificate_valid(),
            'rf_contractor_valid':
                contractor._serviq_fgas_certificate_valid(),
            'rf_today': fields.Date.to_string(
                fields.Date.context_today(self)),
            'rf_logbook_url': '/my/installations/%d/refrigerant-logbook.pdf'
                              % installation.id if installation else False,
        }

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------
    @api.model
    def _rf_float(self, value, label):
        try:
            return float((value or '0').replace(',', '.'))
        except ValueError:
            raise UserError(_('%s is geen geldig getal.', label))

    @api.model
    def _rf_id(self, value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @api.model
    def _flow_submit(self, task, flow, partner, is_internal, post):
        installation = task.serviq_installation_id
        if not installation:
            raise UserError(_(
                'Registreer eerst de installatie; daarna kunnen de '
                'koudemiddelgegevens ingevuld worden.'))
        if post.get('rf_action') == 'system':
            return self._rf_submit_system(task, installation, partner, post)
        return self._rf_submit_log(task, installation, partner,
                                   is_internal, post)

    @api.model
    def _rf_submit_system(self, task, installation, partner, post):
        refrigerant = self.env['serviq.refrigerant'].browse(
            self._rf_id(post.get('refrigerant_id'))).exists()
        if not refrigerant:
            raise UserError(_('Kies het koudemiddel van de installatie.'))
        if installation.refrigerant_log_ids \
                and refrigerant != installation.refrigerant_id:
            raise UserError(_(
                'Het logboek van deze installatie bevat al handelingen met '
                '%s; het koudemiddel kan niet meer gewijzigd worden.',
                installation.refrigerant_id.name))
        charge = self._rf_float(post.get('charge_kg'),
                                _('De nominale inhoud'))
        if charge <= 0:
            raise UserError(_('Geef de nominale inhoud in kg op.'))
        vals = {
            'refrigerant_id': refrigerant.id,
            'refrigerant_charge_kg': charge,
            'refrigerant_hermetic': bool(post.get('hermetic')),
            'refrigerant_leak_detection': bool(post.get('leak_detection')),
        }
        if post.get('commissioning_date'):
            vals['refrigerant_commissioning_date'] = fields.Date.to_date(
                post['commissioning_date'])
        installation.write(vals)
        self._flow_post(task, partner, _(
            'Koudemiddelgegevens geregistreerd: %(refrigerant)s, %(kg)s kg '
            '(%(co2)s t CO2-eq).', refrigerant=refrigerant.name, kg=charge,
            co2=installation.refrigerant_co2_eq))
        message = _('Koeltechnisch systeem geregistreerd: %(co2)s t CO2-eq.',
                    co2=installation.refrigerant_co2_eq)
        if installation.fgas_logbook_required:
            message = _('%(message)s Logboekplichtig, lekcontrole elke '
                        '%(months)s maanden.', message=message,
                        months=installation.fgas_leak_check_months)
        if installation.fgas_detection_missing:
            message = _('%s Opgelet: een vast lekdetectiesysteem is '
                        'verplicht vanaf 500 t CO2-eq.', message)
        return message, None

    @api.model
    def _rf_submit_log(self, task, installation, partner, is_internal, post):
        if not installation.refrigerant_id:
            raise UserError(_(
                'Vul eerst het koudemiddel en de nominale inhoud van de '
                'installatie in.'))
        contractor = self._rf_contractor(partner, is_internal)
        technician_cert = (post.get('technician_certificate')
                           or partner.serviq_fgas_certificate or '').strip()
        contractor_cert = (post.get('contractor_certificate')
                           or contractor.serviq_fgas_certificate or '').strip()
        if not technician_cert or not contractor_cert:
            raise UserError(_(
                'Het certificaatnummer van de technicus en van het bedrijf '
                'zijn verplicht.'))
        # Remember a certificate typed in, for the next registrations.
        if not partner.serviq_fgas_certificate:
            partner.serviq_fgas_certificate = technician_cert
        if not contractor.serviq_fgas_certificate:
            contractor.serviq_fgas_certificate = contractor_cert
        if not partner._serviq_fgas_certificate_valid():
            raise UserError(_('Het certificaat van de technicus is '
                              'vervallen.'))
        if not contractor._serviq_fgas_certificate_valid():
            raise UserError(_('Het certificaat van het bedrijf is '
                              'vervallen.'))

        cylinder = self._rf_cylinders(installation, contractor).filtered(
            lambda c: c.id == self._rf_id(post.get('cylinder_id')))
        vals = {
            'installation_id': installation.id,
            'task_id': task.id,
            'date': fields.Date.to_date(post.get('date'))
            or fields.Date.context_today(self),
            'entry_type': post.get('entry_type'),
            'refrigerant_id': installation.refrigerant_id.id,
            'quantity_kg': self._rf_float(post.get('quantity_kg'),
                                          _('De hoeveelheid')),
            'origin': post.get('origin') or False,
            'facility_name': (post.get('facility_name') or '').strip()
            or False,
            'facility_address': (post.get('facility_address') or '').strip()
            or False,
            'cylinder_id': cylinder.id,
            'leak_result': post.get('leak_result') or False,
            'leak_location': (post.get('leak_location') or '').strip()
            or False,
            'follow_up_date': fields.Date.to_date(post.get('follow_up_date'))
            if post.get('follow_up_date') else False,
            'description': (post.get('description') or '').strip() or False,
            'technician_id': partner.id,
            'technician_name': partner.name,
            'technician_certificate': technician_cert,
            'contractor_id': contractor.id,
            'contractor_name': contractor.name,
            'contractor_certificate': contractor_cert,
        }
        Log = self.env['serviq.refrigerant.log']
        if vals['entry_type'] not in dict(Log._fields['entry_type']
                                          .selection):
            raise UserError(_('Kies de handeling.'))
        if vals['entry_type'] not in ('initial_charge', 'addition'):
            vals.update(origin=False, facility_name=False,
                        facility_address=False)
        if vals['entry_type'] != 'leak_check':
            vals.update(leak_result=False)
        log = Log.create(vals)
        if log.entry_type == 'initial_charge' \
                and not installation.refrigerant_commissioning_date:
            installation.refrigerant_commissioning_date = log.date
        return _('Geregistreerd in het logboek: %s', log._summary()), None
