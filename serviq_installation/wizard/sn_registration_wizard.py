# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SnRegistrationWizard(models.TransientModel):
    """Guided flow to finalise the serial-number registration of installation
    components that were verified via photo in the installer portal
    (serial_photo set) but never got a real stock.lot assigned.

    The wizard walks through those lines one by one: it shows the photo,
    lets the user type the serial and runs three checks before the serial
    can be accepted:

    1. is the serial known in the system (stock.lot)?
    2. is the serial currently in a customer location?
    3. is it in the *correct* customer location, i.e. the customer-specific
       location of the system's distributor?

    Only serials in the correct customer location can be accepted. Unknown
    serials can be created directly in that location; serials sitting in
    another customer location can be moved; serials still in internal stock
    are blocked until the delivery to the distributor is checked.
    """
    _name = 'serviq.sn.registration.wizard'
    _description = "SN-registratie installatie"

    installation_id = fields.Many2one(
        'serviq.installation', string='Installatie', required=True,
        readonly=True, ondelete='cascade')
    line_id = fields.Many2one(
        'serviq.installation.line', string='Component', readonly=True,
        ondelete='cascade')

    product_tmpl_id = fields.Many2one(
        related='line_id.product_tmpl_id', string='Component product')
    rack_number = fields.Integer(
        related='line_id.rack_number', string='Rack')
    photo = fields.Image(
        related='line_id.serial_photo', string='Serienummer foto')
    photo_filename = fields.Char(
        related='line_id.serial_photo_filename')
    distributor_id = fields.Many2one(
        related='installation_id.distributor_id', string='Distributor')
    correct_location_id = fields.Many2one(
        'stock.location', string='Juiste klantlocatie',
        compute='_compute_correct_location')
    pending_count = fields.Integer(
        string='Nog te registreren', compute='_compute_pending_count')

    serial_number = fields.Char(string='Serienummer')

    state = fields.Selection([
        ('draft', 'Niet gecontroleerd'),
        ('ok', 'OK - juiste klantlocatie'),
        ('unknown', 'Onbekend serienummer'),
        ('wrong_location', 'Verkeerde klantlocatie'),
        ('internal', 'In interne voorraad'),
        ('no_stock', 'Geen voorraad gevonden'),
        ('blocked', 'Geblokkeerd'),
    ], default='draft', readonly=True)

    lot_id = fields.Many2one('stock.lot', string='Gevonden lot', readonly=True)
    current_location_id = fields.Many2one(
        'stock.location', string='Huidige locatie', readonly=True)
    check_known = fields.Boolean(
        string='Serienummer bekend in het systeem', readonly=True)
    check_in_customer_location = fields.Boolean(
        string='Serienummer in een klantlocatie', readonly=True)
    check_correct_location = fields.Boolean(
        string='Serienummer in de juiste klantlocatie (distributeur)',
        readonly=True)
    status_message = fields.Text(string='Resultaat', readonly=True)

    # ------------------------------------------------------------------
    # Setup / navigation
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        system_id = res.get('installation_id') \
            or self.env.context.get('default_installation_id')
        if system_id and not res.get('line_id'):
            system = self.env['serviq.installation'].browse(system_id)
            lines = system._get_sn_registration_lines()
            if not lines:
                raise UserError(_(
                    'Alle componenten met een serienummerfoto hebben al '
                    'een serienummer.'))
            res['line_id'] = lines[0].id
        return res

    @api.depends('installation_id.distributor_id')
    def _compute_correct_location(self):
        for wiz in self:
            wiz.correct_location_id = \
                wiz.distributor_id.property_stock_customer

    @api.depends('installation_id.line_ids.lot_id',
                 'installation_id.line_ids.serial_photo')
    def _compute_pending_count(self):
        for wiz in self:
            wiz.pending_count = len(
                wiz.installation_id._get_sn_registration_lines()) \
                if wiz.installation_id else 0

    @api.onchange('serial_number')
    def _onchange_serial_number(self):
        self.state = 'draft'
        self.lot_id = False
        self.current_location_id = False
        self.check_known = False
        self.check_in_customer_location = False
        self.check_correct_location = False
        self.status_message = False

    def _reopen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('SN-registratie'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }

    def _next_or_close(self):
        """Jump to the next pending line, or close with a notification when
        everything has been registered."""
        self.ensure_one()
        lines = self.installation_id._get_sn_registration_lines()
        if not lines:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('SN-registratie afgerond'),
                    'message': _(
                        'Alle serienummers van %s zijn geregistreerd.',
                        self.installation_id.display_name),
                    'type': 'success',
                    'next': {'type': 'ir.actions.act_window_close'},
                },
            }
        self.write({
            'line_id': lines[0].id,
            'serial_number': False,
            'state': 'draft',
            'lot_id': False,
            'current_location_id': False,
            'check_known': False,
            'check_in_customer_location': False,
            'check_correct_location': False,
            'status_message': False,
        })
        return self._reopen()

    def action_skip(self):
        """Move to the next pending component without registering this one."""
        self.ensure_one()
        lines = self.installation_id._get_sn_registration_lines()
        after = lines.filtered(lambda l: l.id > self.line_id.id)
        nxt = after[0] if after else (
            lines[0] if lines and lines[0] != self.line_id else False)
        if not nxt or nxt == self.line_id:
            return {'type': 'ir.actions.act_window_close'}
        self.write({
            'line_id': nxt.id,
            'serial_number': False,
            'state': 'draft',
            'lot_id': False,
            'current_location_id': False,
            'check_known': False,
            'check_in_customer_location': False,
            'check_correct_location': False,
            'status_message': False,
        })
        return self._reopen()

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------
    def _get_correct_location(self):
        self.ensure_one()
        distributor = self.installation_id.distributor_id
        if not distributor:
            raise UserError(_(
                'Het installatie heeft geen distributeur; de juiste '
                'klantlocatie kan niet bepaald worden.'))
        location = distributor.property_stock_customer
        if not location:
            raise UserError(_(
                'Distributeur "%s" heeft geen klantlocatie gekoppeld.',
                distributor.display_name))
        return location

    def action_check(self):
        """Run the three checks for the typed serial and set the state that
        decides which action buttons become available."""
        self.ensure_one()
        serial = (self.serial_number or '').strip()
        if not serial:
            raise UserError(_('Geef eerst een serienummer in.'))
        correct_loc = self._get_correct_location()

        vals = {
            'lot_id': False,
            'current_location_id': False,
            'check_known': False,
            'check_in_customer_location': False,
            'check_correct_location': False,
        }

        lots = self.env['stock.lot'].sudo().search([('name', '=', serial)])
        lot = lots.filtered(
            lambda l: l.product_id.product_tmpl_id
            == self.line_id.product_tmpl_id)[:1] or lots[:1]

        if not lot:
            vals.update(
                state='unknown',
                status_message=_(
                    'Serienummer "%(serial)s" is niet gekend in het systeem. '
                    'U kunt het rechtstreeks aanmaken in klantlocatie '
                    '"%(location)s".',
                    serial=serial, location=correct_loc.display_name))
            self.write(vals)
            return self._reopen()

        vals.update(lot_id=lot.id, check_known=True)

        clash_line = self.env['serviq.installation.line'].sudo().search([
            ('lot_id', '=', lot.id), ('id', '!=', self.line_id.id),
        ], limit=1)
        if lot.product_id.product_tmpl_id != self.line_id.product_tmpl_id:
            vals.update(
                state='blocked',
                status_message=_(
                    'Serienummer "%(serial)s" hoort bij product "%(actual)s", '
                    'verwacht "%(expected)s".',
                    serial=serial,
                    actual=lot.product_id.product_tmpl_id.display_name,
                    expected=self.line_id.product_tmpl_id.display_name))
        elif lot.installation_id \
                and lot.installation_id != self.installation_id:
            vals.update(
                state='blocked',
                status_message=_(
                    'Serienummer "%(serial)s" is al gekoppeld aan '
                    'installatie "%(system)s".',
                    serial=serial,
                    system=lot.installation_id.display_name))
        elif clash_line:
            vals.update(
                state='blocked',
                status_message=_(
                    'Serienummer "%(serial)s" is al gebruikt op '
                    'installatie "%(system)s".',
                    serial=serial,
                    system=clash_line.installation_id.display_name))
        else:
            quants = self.env['stock.quant'].sudo().search([
                ('lot_id', '=', lot.id), ('quantity', '>', 0),
            ])
            correct_quants = quants.filtered(
                lambda q: q.location_id == correct_loc)
            customer_quants = quants.filtered(
                lambda q: q.location_id.usage == 'customer')
            internal_quants = quants.filtered(
                lambda q: q.location_id.usage == 'internal')
            if correct_quants:
                vals.update(
                    state='ok',
                    check_in_customer_location=True,
                    check_correct_location=True,
                    current_location_id=correct_loc.id,
                    status_message=_(
                        'Serienummer "%(serial)s" bevindt zich in de juiste '
                        'klantlocatie "%(location)s" en kan geaccepteerd '
                        'worden.',
                        serial=serial, location=correct_loc.display_name))
            elif customer_quants:
                current = customer_quants[0].location_id
                vals.update(
                    state='wrong_location',
                    check_in_customer_location=True,
                    current_location_id=current.id,
                    status_message=_(
                        'Serienummer "%(serial)s" bevindt zich in '
                        'klantlocatie "%(current)s" in plaats van '
                        '"%(correct)s". U kunt het verplaatsen naar de '
                        'juiste klantlocatie.',
                        serial=serial, current=current.display_name,
                        correct=correct_loc.display_name))
            elif internal_quants:
                current = internal_quants[0].location_id
                vals.update(
                    state='internal',
                    current_location_id=current.id,
                    status_message=_(
                        'Serienummer "%(serial)s" bevindt zich nog in de '
                        'interne voorraad ("%(current)s"). Controleer de '
                        'levering: een serienummer kan niet geïnstalleerd '
                        'worden zolang het niet aan de distributeur geleverd '
                        'is.',
                        serial=serial, current=current.display_name))
            else:
                vals.update(
                    state='no_stock',
                    status_message=_(
                        'Serienummer "%(serial)s" is gekend maar er is geen '
                        'voorraad gevonden. U kunt het in klantlocatie '
                        '"%(location)s" plaatsen.',
                        serial=serial, location=correct_loc.display_name))

        self.write(vals)
        return self._reopen()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _assign_lot(self, lot):
        """Write the accepted lot on the component line (the line's
        constraint re-validates it), confirm it to the user and continue
        with the next one."""
        self.ensure_one()
        line = self.line_id
        line.write({'lot_id': lot.id})
        self.installation_id.message_post(body=_(
            'Serienummer "%(serial)s" geregistreerd op component '
            '"%(component)s" via SN-registratie.',
            serial=lot.name,
            component=line.product_tmpl_id.display_name))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Serienummer geregistreerd'),
                'message': _(
                    'Serienummer "%(serial)s" is toegevoegd aan component '
                    '"%(component)s".',
                    serial=lot.name,
                    component=line.product_tmpl_id.display_name),
                'type': 'success',
                'next': self._next_or_close(),
            },
        }

    def action_accept(self):
        self.ensure_one()
        if self.state != 'ok' or not self.lot_id:
            raise UserError(_(
                'Alleen serienummers in de juiste klantlocatie kunnen '
                'geaccepteerd worden. Voer eerst de controle uit.'))
        return self._assign_lot(self.lot_id)

    def action_create_serial(self):
        """Create the unknown serial directly in the distributor's customer
        location (or place a known-but-stockless serial there)."""
        self.ensure_one()
        if self.state not in ('unknown', 'no_stock'):
            raise UserError(_(
                'Deze actie is alleen mogelijk voor onbekende serienummers '
                'of serienummers zonder voorraad.'))
        serial = (self.serial_number or '').strip()
        correct_loc = self._get_correct_location()
        lot = self.lot_id
        if not lot:
            product = self.line_id.product_tmpl_id.product_variant_id
            if not product:
                raise UserError(_(
                    'Component "%s" heeft geen productvariant; het '
                    'serienummer kan niet aangemaakt worden.',
                    self.line_id.product_tmpl_id.display_name))
            lot = self.env['stock.lot'].sudo().create({
                'name': serial,
                'product_id': product.id,
                'company_id': self.env.company.id,
            })
        self.env['stock.quant'].sudo()._update_available_quantity(
            lot.product_id, correct_loc, 1, lot_id=lot)
        self.lot_id = lot
        return self._assign_lot(lot)

    def action_move_serial(self):
        """Move the serial from the wrong customer location to the
        distributor's customer location, then accept it."""
        self.ensure_one()
        if self.state != 'wrong_location' or not self.lot_id \
                or not self.current_location_id:
            raise UserError(_(
                'Deze actie is alleen mogelijk voor serienummers in een '
                'verkeerde klantlocatie.'))
        correct_loc = self._get_correct_location()
        Quant = self.env['stock.quant'].sudo()
        Quant._update_available_quantity(
            self.lot_id.product_id, self.current_location_id, -1,
            lot_id=self.lot_id)
        Quant._update_available_quantity(
            self.lot_id.product_id, correct_loc, 1, lot_id=self.lot_id)
        return self._assign_lot(self.lot_id)
