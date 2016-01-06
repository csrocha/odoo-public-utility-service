# -*- coding: utf-8 -*-
from openerp import models, fields, api, _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime
from operator import attrgetter
import openerp.addons.decimal_precision as dp

import logging
_logger = logging.getLogger(__name__)


def today():
    return datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)


class utility_product_lines(models.Model):
    _name = 'utility.product.line'

    contract_id = fields.Many2one('account.analytic.account',
                                  string='Contract',
                                  required=True,
                                  ondelete='cascade')
    product_id = fields.Many2one('product.product',
                                 string='Product',
                                 required=True,
                                 ondelete='restrict')
    product_uom = fields.Many2one('product.uom',
                                  string='Unit of Measure ',
                                  required=True)
    product_uom_qty = fields.Float(string='Quantity',
                                   digits_compute=dp.get_precision(
                                       'Product UoS'),
                                   required=True,
                                   default=1.0)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('to_install', 'Waiting to install'),
            ('installed', 'Installed'),
            ('to_uninstall', 'Waiting to uninstall'),
            ('uninstalled', 'Uninstalled')],
        string='State of the product',
        default='draft')

    _sql_constraints = [
        ('unique_product_line',
         'unique(contract_id, product_id)',
         'Exists this product for this contract'),
    ]


def address_format(shipping):
    address = (shipping.street,
               ", %s" % shipping.street2 if shipping.street2 else '',
               shipping.city,
               shipping.state_id.name,
               ' (%s)' % shipping.zip if shipping.zip else '',
               shipping.country_id.name)
    return "%s%s\n%s, %s%s\n%s" % address


class account_invoice(models.Model):
    _inherit = 'account.invoice'

    contract_fee_ids = fields.Many2many(
        'account.analytic.account',
        'contract_fee_invoice',
        'invoice_id',
        'contract_fee_id',
        string='Contracts')


class account_analytic_account(models.Model):
    _inherit = 'account.analytic.account'

    def _get_day_of_months(self, cr, uid, context=None):
        return [('%i' % i, '%i' % i) for i in range(1, 30)]

    use_utilities = fields.Boolean(string='Utilities')
    partner_invoice_id = fields.Many2one('res.partner',
                                         string='Invoice Address')
    partner_shipping_id = fields.Many2one('res.partner',
                                          string='Delivery Address')
    pricelist_id = fields.Many2one('product.pricelist',
                                   string='Price list')
    utility_product_line_ids = fields.One2many('utility.product.line',
                                               'contract_id',
                                               string='Utility Service List')
    invoice_journal_id = fields.Many2one('account.journal',
                                         string='Default journal for invoices')
    invoice_ids = fields.Many2many('account.invoice',
                                   'contract_fee_invoice',
                                   'contract_fee_id',
                                   'invoice_id',
                                   string='Invoices')
    invoices_automatic_validation = fields.Boolean(
        string='Automatic invoice validation')
    invoices_no_change_validation = fields.Boolean(
        string='Only validate no changed invoices')
    invoice_payment_term_id = fields.Many2one(
        'account.payment.term',
        string='Payment term')

    @api.multi
    def _pus_generate_invoice_data(self, period):
        """
        Use this function to update invoice information.
        """
        self.ensure_one()
        values = {
            'partner_id': self.partner_invoice_id.id or self.partner_id.id,
            'account_id': self.partner_id.property_account_receivable.id,
            'company_id': self.company_id.id,
            'period_id': period.id,
            'origin': self.name,
            'type': 'out_invoice',
            'payment_term': self.invoice_payment_term_id.id,
            'comment': _("Contract: %s.\nService Address: %s") % (
                self.name,
                address_format(self.partner_shipping_id)),
            'origin': self.name,
            'journal_id': self.invoice_journal_id.id
            if self.invoice_journal_id else False,
            'invoice_line': self._pus_get_invoice_lines(),
        }
        return { k: v for k,v, in values.items() if v }

    @api.multi
    def _pus_auto_validation(self, inv):
        """
        Check if invoice can auto validated.
        """
        self.ensure_one()
        con = self

        # Automatic validation
        validate = con.invoices_automatic_validation
        if validate and con.invoices_no_change_validation:
            # If change invoice beetween last validated invoice
            # then no validate
            invoices = sorted(con.invoice_ids,
                              key=attrgetter('date_invoice'))
            if invoices:
                prev_invoice = invoices[-1]
                last_invoice = inv
                # Compute taxes before comparation
                last_invoice.button_compute()
                # If last is validate then check, else no validate
                validate = prev_invoice.state != 'draft'
                # Compare last two invoices
                # - first by amounts
                validate = validate and (
                    prev_invoice.amount_total == last_invoice.amount_total)
                # - late by partner
                validate = validate and (
                    prev_invoice.partner_id.id
                    == last_invoice.partner_id.id)
            else:
                validate = False

        return validate

    @api.multi
    def pus_operations(self, period):
        # Take all valid contracts
        contracts = self.search([
            ('id', 'in', self.ids) if self.ids else ('1', '=', '1')
            ('use_utilities', '=', 'True'),
            ('state', '=', 'open')
        ])

        # Take period if not defined
        period = period or period.find()

        operation = {
            'update': self.browse([]),
            'create': self.browse([]),
            'none': self.browse([]),
        }

        for con in contracts:
            period_ids = con.invoice_ids.mapped('period_id').ids
            op = 'update' if (
                period.id in period_ids and
                set(con.invoice_ids.filtered(
                    lambda i: i.period_id == period
                ).mapped('state')) == set(['draft'])
            ) else 'create' if (period.id not in period_ids) else 'none'

            operation[op] |= con

        return operation

    @api.multi
    def _pus_get_invoice_lines(self):
        """
        Return invoice lines from contract
        """
        self.ensure_one()
        inv_line_obj = self.env['account.invoice.line']

        def product_line(con, line):
            price_unit = con.pricelist_id.with_context(
                uom=line.product_uom.id, date=today()
            ).price_get(
                line.product_id.id,
                line.product_uom_qty,
                con.partner_id.id,
            ).get(con.pricelist_id.id, 0.0) if con.pricelist_id else None

            r = dict(product_id=line.product_id.id,
                     **inv_line_obj.product_id_change(
                         line.product_id.id,
                         line.product_uom.id,
                         line.product_uom_qty,
                         price_unit=price_unit,
                         partner_id=con.partner_id.id).get('value', {}))
            r['price_unit'] = price_unit or r['price_unit']
            if 'invoice_line_tax_id' in r:
                r['invoice_line_tax_id'] = [(6, 0, r['invoice_line_tax_id'])]
            return r

        return [(0, 0, product_line(self, line))
                for line in self.utility_product_line_ids
                if line.state == 'installed']

    @api.multi
    def _pus_create_invoice(self, period):
        self.ensure_one()
        inv_obj = self.env['account.invoice']

        products_to_add = self._pus_get_invoice_lines()

        # No items to append from this contract.
        if not products_to_add:
            _logger.info(_("Contract %s without installed products.")
                         % self.name)
            return inv_obj.browse([])

        # Take yet exists invoices with this periods and partner.
        invs = inv_obj.search([
            ('period_id', '=', period.id),
            ('contract_fee_ids', 'in', self.id),
            ('state', '!=', 'cancel')])

        # If not invoice, create one.
        if not invs:
            _logger.info(_("Creating invoice for contract %s.") % self.name)
            inv = inv_obj.create(self._pus_generate_invoice_data(period))
            self.write({'invoice_ids': [(4, inv.id)]})
            return inv

        return inv_obj.browse([])

    @api.multi
    def _pus_update_invoice(self, period):
        self.ensure_one()
        inv_obj = self.env['account.invoice']

        products_to_add = self.pus_get_invoice_lines()

        # No items to append from this contract.
        if not products_to_add:
            _logger.info(_("Contract %s without installed products.")
                         % self.name)
            return inv_obj.browse([])

        # Take yet exists invoices with this periods and partner.
        invs = inv_obj.search([
            ('period_id', '=', period.id),
            ('contract_fee_ids', 'in', self.id),
            ('state', '=', 'draft')])

        # If not editables then ignore all.
        if not invs:
            _logger.info(_("No invoices update for %s.") % self.name)
            return inv_obj.browse([])

        # Else update it.
        invs.ensure_one()
        _logger.info(_("Update invoice %i.") % invs.id)
        invs.write({'invoice_line': [(5, 0, 0)] + products_to_add})

        return invs

    @api.multi
    @api.model
    def pus_generate_invoice(self,
                             period_id=None,
                             operations=None,
                             validation_signal='invoice_open'):
        per_obj = self.env['account.period']

        period = per_obj.browse(period_id) if period_id else per_obj.find()
        operations = operations if operations else self.pus_operations(period)

        _logger.info("Contracts to create %i, %i to update and %i for none" %
                     (len(operations['create']),
                      len(operations['update']),
                      len(operations['none'])))

        ret_inv = self.env['account.invoice'].browse([])

        for con in operations['create']:
            inv = con._pus_create_invoice(period)

            if validation_signal and con._pus_auto_validation(inv):
                _logger.info(_("Send signal %s to invoice %s.") %
                             (validation_signal, inv.id))
                inv.signal_workflow(validation_signal)

            ret_inv |= inv

        for con in operations['update']:
            inv = con._pus_update_invoice(period)

            ret_inv |= inv

        return ret_inv.ids

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
