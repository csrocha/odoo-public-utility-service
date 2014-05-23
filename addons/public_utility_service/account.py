# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP Module, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#    Service Utility Module
#    Copyright (C) 2004-2010 CT Moldeo Interactive L (<http://moldeo.coop>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields, osv
from openerp.tools.translate import _
from datetime import date
from openerp import netsvc

class account_analytic_account(osv.osv):
    _name = 'account.analytic.account'
    _inherit = 'account.analytic.account'

    _columns = {
        'address': fields.many2one( 'res.partner', 'Address'),
        'day_of_invoice': fields.integer('Day of month for invoice'),
        'use_utilities': fields.boolean('Utilities'),
        'product_ids': fields.many2many( 'product.product', 'contract_product_rel', 'product_id', 'account_analytic_account_id', 'Utility List'),
	}

account_analytic_account()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
