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
    _name = 'account.analytic.account'
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
    def pus_generate_invoice_data(self, period_id):
        """
        Use this function to update invoice information.
        """
        self.ensure_one()
        return {
            'partner_id': self.partner_invoice_id.id or self.partner_id.id,
            'account_id': self.partner_id.property_account_receivable.id,
            'company_id': self.company_id.id,
            'period_id': period_id,
            'origin': self.name,
            'type': 'out_invoice',
            'payment_term': self.invoice_payment_term_id.id,
            'comment': _("Contract: %s.\nService Address: %s") % (
                self.name,
                address_format(self.partner_shipping_id)),
        }

    def pus_generate_invoice(self, cr, uid, ids=None,
                             context=None, period_id=None,
                             validation_signal='invoice_open'):
        inv_obj = self.pool.get('account.invoice')
        pricelist_obj = self.pool.get('product.pricelist')
        inv_line_obj = self.pool.get('account.invoice.line')
        period_obj = self.pool.get('account.period')

        _ids = self.search(cr, uid, [('id', 'in', ids) if ids
                                     else ('id', '>=', 0),
                                     ('use_utilities', '=', 'True'),
                                     ('state', '=', 'open')])

        ids = _ids
        draft_inv_ids = []

        # Take period if not defined
        if not period_id:
            period_id = period_obj.find(cr, uid, today(), context=context)
            if not len(period_id) > 0:
                raise Warning("There is no opening/closing period defined,"
                              " please create one to set the initial balance.")
            period_id = period_id[0]

        period = period_obj.browse(cr, uid, period_id)
        next_period_id = period_obj.next(cr, uid, period, 1)

        if not next_period_id:
            raise Warning("There is no opening/closing period defined,"
                          " please create one to set the initial balance.")

        for con in self.browse(cr, uid, ids):
            # Items to append to invoices.
            def product_line(line, shipping):
                price_unit = pricelist_obj.price_get(
                    cr, uid, [con.pricelist_id.id],
                    line.product_id.id,
                    line.product_uom_qty,
                    con.partner_id.id,
                    {'uom': line.product_uom.id, 'date': today()}
                ).get(con.pricelist_id.id, 0.0) if con.pricelist_id else None
                r = dict(product_id=line.product_id.id,
                         **inv_line_obj.product_id_change(
                             cr, uid, [],
                             line.product_id.id,
                             line.product_uom.id,
                             line.product_uom_qty,
                             price_unit=price_unit,
                             partner_id=con.partner_id.id).get('value', {}))
                r['price_unit'] = price_unit or r['price_unit']
                if 'invoice_line_tax_id' in r:
                    r['invoice_line_tax_id'] = [
                        (6, 0, r['invoice_line_tax_id'])
                    ]
                return r

            products_to_add = [
                (0, 0, product_line(line, con.partner_shipping_id))
                for line in con.utility_product_line_ids
                if line.state == 'installed']

            # No items to append from this contract.
            if not products_to_add:
                continue

            # Take yet exists invoices with this periods and partner.
            inv_ids = inv_obj.search(cr, uid, [
                ('period_id', '=', period_id),
                ('partner_id', '=', con.partner_id.id),
                ('state', '!=', 'cancel')])

            # I had any invoice in the list of invoices in contract?
            if [inv_id for inv_id in inv_ids if inv_id in con.invoice_ids.ids]:
                _logger.info("Invoice yet exists in contract. Ignoring.")
                continue

            # If invoices then take editables.
            inv_ids = [inv['id']
                       for inv in inv_obj.read(cr, uid, inv_ids, ['state'])
                       if inv['state'] == 'draft'] + [False]

            # Take one
            inv_id = inv_ids.pop()

            if not inv_id:
                # If not invoice, create one.
                _logger.info(_("Creating invoice from contract %s.") %
                             conn.name)
                value = con.pus_generate_invoice_data(period_id)
                value.update({
                    'invoice_line': products_to_add,
                    'journal_id': con.invoice_journal_id.id
                    if con.invoice_journal_id
                    else value.get('journal_id', False)
                })
                inv_id = inv_obj.create(cr, uid, value)
            else:
                # Else update it.
                _logger.info(_("Update invoice %i.") % inv_id)
                inv_obj.write(cr, uid, inv_id,
                              {'invoice_line': products_to_add})

            # Take the invoice to return
            draft_inv_ids.append(inv_id)

            # Update contract list of invoices.
            self.write(cr, uid, con.id, {'invoice_ids': [(4, inv_id)]})

            # Automatic validation
            validate = con.invoices_automatic_validation
            if validate and con.invoices_no_change_validation:
                # If change invoice beetween last validated invoice
                # then no validate
                invoices = sorted(con.invoice_ids,
                                  key=attrgetter('date_invoice'))
                if invoices:
                    prev_invoice = invoices[-1]
                    last_invoice = inv_obj.browse(cr, uid, inv_id)
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

            # Can validate?
            if validate:
                inv_obj.signal_workflow(cr, uid, [inv_id], validation_signal)

        return draft_inv_ids

    def get_draft_invoices(self, cr, uid, ids=None, context=None):
        """
        Return all invoices in draft associated to contracts.
        """
        ids = self.search(cr, uid, [
            ('id', 'in', ids) if ids else ('id', '>=', 0),
            ('use_utilities', '=', 'True'),
            ('state', '=', 'open')])

        inv_ids = []

        for con in self.browse(cr, uid, ids):
            for inv in con.invoice_ids:
                if inv.state == 'draft':
                    inv_ids.append(inv.id)

        return inv_ids


account_analytic_account()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
