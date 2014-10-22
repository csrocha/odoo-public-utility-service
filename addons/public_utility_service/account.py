# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp import netsvc
from datetime import datetime
from operator import attrgetter

def today():
    return datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)

class utility_product_lines(osv.osv):
    _name = 'utility.product.line'

    _columns = {
        'contract_id': fields.many2one('account.analytic.account', 'Contract', required=True, ondelete='cascade'),
        'product_id': fields.many2one('product.product', 'Product', required=True, ondelete='restrict'),
        'state': fields.selection([('draft',        'Draft'),
                                   ('to_install',   'Waiting to install'),
                                   ('installed',    'Installed'),
                                   ('to_uninstall', 'Waiting to uninstall'),
                                   ('uninstalled',  'Uninstalled'),
                                   ], string='State of the product')
    }

    _defaults = {
        'state': 'draft',
    }

    _sql_constraints = [
        ('unique_product_line', 'unique(contract_id, product_id)', 'Exists this product for this contract'),
    ]

utility_product_lines()

class account_analytic_account(osv.osv):
    _name = 'account.analytic.account'
    _inherit = 'account.analytic.account'

    def _get_day_of_months(self, cr, uid, context=None):
        return [ ('%i' % i, '%i' % i) for i in range(1,30) ]

    _columns = {
        'use_utilities': fields.boolean('Utilities'),
        'partner_invoice_id': fields.many2one( 'res.partner', 'Invoice Address'),
        'partner_shipping_id': fields.many2one( 'res.partner', 'Delivery Address'),
        'utility_product_line_ids': fields.one2many( 'utility.product.line', 'contract_id', 'Utility Service List'),
        'invoice_journal_id': fields.many2one('account.journal', 'Default journal for invoices'),
        'invoice_ids': fields.many2many('account.invoice', 'contract_fee_invoice', 'contract_fee_id', 'invoice_id', 'Invoices'),
        'invoices_automatic_validation': fields.boolean('Automatic invoice validation'),
        'invoices_no_change_validation': fields.boolean('Only validate no changed invoices'),
	}

    def generate_invoice(self, cr, uid, ids=None, context=None, period_id=None, ):
        inv_obj = self.pool.get('account.invoice')
        period_obj = self.pool.get('account.period')
        wf_service = netsvc.LocalService("workflow")

        ids = self.search(cr, uid, [('id', 'in', ids) if ids else ('id','>=',0),
                                    ('use_utilities','=','True'),
                                    ('state','=','open') ])

        draft_inv_ids = []

        for con in self.browse(cr, uid, ids):
            # Take period if not defined
            if not period_id:
                period_id = period_obj.find(cr, uid, today(), context=context)
                period = period_obj.browse(cr, uid, period_id[0])
                period_id = period_obj.next(cr, uid, period, 1)

                if not period_id:
                    raise osv.except_osv(_('Error!'),_("There is no opening/closing period defined, please create one to set the initial balance."))

            # Items to append to invoices.
            products_to_add = [ (0,0,{
                'name': line.product_id.name,
                'product_id': line.product_id.id,
            }) for line in con.utility_product_line_ids if line.state=='installed' ]

            # No items to append from this contract.
            if not products_to_add:
                continue

            # Take yet exists invoices with this periods and partner.
            import pdb; pdb.set_trace()
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
                    'date_invoice': period_obj.browse(cr, uid, period_id).date_start,
                    'origin': con.name,
                    'type': 'out_invoice',
                }
                if con.invoice_journal_id: value['journal_id'] = con.invoice_journal_id.id
                inv_id = inv_obj.create(cr, uid, value)

            # If invoice is not draft, I cant add any line.
            elif inv_obj.browse(cr, uid, inv_id).state != 'draft':
                continue

            # Update invoice.
            inv_obj.write(cr, uid, inv_id, { 'invoice_line': products_to_add })
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
