# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp import netsvc
from datetime import datetime
from operator import attrgetter
import openerp.addons.decimal_precision as dp

def today():
    return datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)

class utility_product_lines(osv.osv):
    _name = 'utility.product.line'

    _columns = {
        'contract_id': fields.many2one('account.analytic.account', 'Contract', required=True, ondelete='cascade'),
        'product_id': fields.many2one('product.product', 'Product', required=True, ondelete='restrict'),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure ', required=True),
        'product_uom_qty': fields.float('Quantity', digits_compute= dp.get_precision('Product UoS'), required=True),
        'state': fields.selection([('draft',        'Draft'),
                                   ('to_install',   'Waiting to install'),
                                   ('installed',    'Installed'),
                                   ('to_uninstall', 'Waiting to uninstall'),
                                   ('uninstalled',  'Uninstalled'),
                                   ], string='State of the product')
    }

    _defaults = {
        'state': 'draft',
        'product_uom_qty': 1.0,
    }

    _sql_constraints = [
        ('unique_product_line', 'unique(contract_id, product_id)', 'Exists this product for this contract'),
    ]

utility_product_lines()

def address_format(shipping):
    address = (shipping.street,
               ", %s" % shipping.street2 if shipping.street2 else '',
               shipping.city,
               shipping.state_id.name,
               ' (%s)' % shipping.zip if shipping.zip else '',
               shipping.country_id.name)
    return "%s%s\n%s, %s%s\n%s" % address

class account_invoice(osv.osv):
    _inherit = 'account.invoice'

    _columns = {
        'contract_fee_ids': fields.many2many('account.analytic.account', 'contract_fee_invoice', 'invoice_id', 'contract_fee_id', 'Contracts'),
    }
account_invoice()

class account_analytic_account(osv.osv):
    _name = 'account.analytic.account'
    _inherit = 'account.analytic.account'

    def _get_day_of_months(self, cr, uid, context=None):
        return [ ('%i' % i, '%i' % i) for i in range(1,30) ]

    _columns = {
        'use_utilities': fields.boolean('Utilities'),
        'partner_invoice_id': fields.many2one( 'res.partner', 'Invoice Address'),
        'partner_shipping_id': fields.many2one( 'res.partner', 'Delivery Address'),
        'pricelist_id': fields.many2one( 'product.pricelist', 'Price list'),
        'utility_product_line_ids': fields.one2many( 'utility.product.line', 'contract_id', 'Utility Service List'),
        'invoice_journal_id': fields.many2one('account.journal', 'Default journal for invoices'),
        'invoice_ids': fields.many2many('account.invoice', 'contract_fee_invoice', 'contract_fee_id', 'invoice_id', 'Invoices'),
        'invoices_automatic_validation': fields.boolean('Automatic invoice validation'),
        'invoices_no_change_validation': fields.boolean('Only validate no changed invoices'),
        'invoice_payment_term_id': fields.many2one('account.payment.term', 'Payment term'),
	}

    def pus_generate_invoice(self, cr, uid, ids=None, context=None, period_id=None, ):
        inv_obj = self.pool.get('account.invoice')
        pricelist_obj = self.pool.get('product.pricelist')
        inv_line_obj = self.pool.get('account.invoice.line')
        period_obj = self.pool.get('account.period')
        wf_service = netsvc.LocalService("workflow")

        _ids = self.search(cr, uid, [('id', 'in', ids) if ids else ('id','>=',0),
                                    ('use_utilities','=','True'),
                                    ('state','=','open') ])

        ids = _ids
        draft_inv_ids = []

        # Take period if not defined
        if not period_id:
            period_id = period_obj.find(cr, uid, today(), context=context)
            if not len(period_id) > 0:
                raise osv.except_osv(_('Error!'),_("There is no opening/closing period defined, please create one to set the initial balance."))
            period_id = period_id[0]

        period = period_obj.browse(cr, uid, period_id)
        next_period_id = period_obj.next(cr, uid, period, 1)

        if not next_period_id:
            raise osv.except_osv(_('Error!'),_("There is no opening/closing period defined, please create one to set the initial balance."))

        for con in self.browse(cr, uid, ids):
            # Items to append to invoices.

            def product_line(line, shipping):
                price_unit = pricelist_obj.price_get(cr, uid, [con.pricelist_id.id],
                                                     line.product_id.id,
                                                     line.product_uom_qty,
                                                     con.partner_id.id, { 'uom': line.product_uom.id, 'date': today(), }
                                                    ).get(con.pricelist_id.id, 0.0) if con.pricelist_id else None
                r = dict(product_id=line.product_id.id,
                         **inv_line_obj.product_id_change(cr, uid, [],
                                                          line.product_id.id,
                                                          line.product_uom.id,
                                                          line.product_uom_qty,
                                                          price_unit=price_unit,
                                                          partner_id=con.partner_id.id).get('value',{}))
                r['price_unit'] = price_unit or r['price_unit']
                if 'invoice_line_tax_id' in r:
                    r['invoice_line_tax_id'] = [ (6, 0, r['invoice_line_tax_id']) ]
                return r

            products_to_add = [ (0,0, product_line(line, con.partner_shipping_id)) for line in con.utility_product_line_ids if line.state=='installed']

            # No items to append from this contract.
            if not products_to_add:
                continue

            # Take yet exists invoices with this periods and partner.
            inv_id = inv_obj.search(cr, uid, [('period_id','=',period_id),('partner_id', '=', con.partner_id.id),('state','!=','cancel')])
            inv_id = inv_id and inv_id.pop() or False

            # I had this invoice in contract invoices?
            if inv_id in [ i.id for i in con.invoice_ids ]:
                continue

            # If not invoice, create one.
            if not inv_id:
                value = {
                    'partner_id': con.partner_invoice_id.id or con.partner_id.id,
                    'account_id': con.partner_id.property_account_receivable.id,
                    'company_id': con.company_id.id,
                    'period_id': period_id,
                    'origin': con.name,
                    'type': 'out_invoice',
                    'invoice_line': products_to_add,
                    'payment_term': con.invoice_payment_term_id.id,
                    'comment': _("Contract: %s.\nService Address: %s") % (con.name,
                                                                          address_format(con.partner_shipping_id)),
                    # Solo para la localización argentina. Muy triste :-(
                    'afip_service_start': period.date_start,
                    'afip_service_end': period.date_stop,
                }
                if con.invoice_journal_id: value['journal_id'] = con.invoice_journal_id.id
                inv_id = inv_obj.create(cr, uid, value)

            # If invoice is not draft, I cant add any line.
            elif inv_obj.browse(cr, uid, inv_id).state != 'draft':
                continue

            # Update invoice.
            else:
                inv_obj.write(cr, uid, inv_id, { 'invoice_line': products_to_add })

            # Take the invoice to return
            draft_inv_ids.append(inv_id)

            # Update contract list of invoices.
            self.write(cr, uid, con.id, { 'invoice_ids': [ (4,inv_id) ] })

            # Automatic validation
            validate = con.invoices_automatic_validation
            if validate and con.invoices_no_change_validation:
                # If change invoice beetween last validated invoice then no validate
                invoices = sorted(con.invoice_ids, key=attrgetter('date_invoice'))
                if invoices:
                    prev_invoice = invoices[-1]
                    last_invoice = inv_obj.browse(cr, uid, inv_id)
                    # If last is validate then check, else no validate
                    validate = prev_invoice.state != 'draft'
                    # Compute taxes before comparation
                    last_invoice.button_compute()
                    # Compare last two invoices
                    ## first by amounts
                    validate = validate and (prev_invoice.amount_total == last_invoice.amount_total)
                    ## late by partner
                    validate = validate and (prev_invoice.partner_id.id == last_invoice.partner_id.id)
                else:
                    validate = False

            # Can validate?
            if validate:
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'account.invoice', inv_id, 'invoice_open', cr)

        return draft_inv_ids

    def get_draft_invoices(self, cr, uid, ids=None, context= None):
        """
        Return all invoices in draft associated to contracts.
        """
        inv_obj = self.pool.get('account.invoice')

        ids = self.search(cr, uid, [('id', 'in', ids) if ids else ('id','>=',0),
                                    ('use_utilities','=','True'),
                                    ('state','=','open') ])

        inv_ids = []

        for con in self.browse(cr, uid, ids):
            for inv in con.invoice_ids:
                if inv.state == 'draft':
                    inv_ids.append(inv.id)

        return inv_ids


account_analytic_account()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
