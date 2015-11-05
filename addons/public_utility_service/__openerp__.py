# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#    Service Utility Module
#    Copyright (C) 2004-2010 Moldeo Interactive (<http://moldeo.coop>).
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
{
    'name': 'Service Utility',
    'version': '8.0.0.1',
    'category': 'Account',
    'description': "Manage subscriptions to a utility service as contract.",
    'author': 'Moldeo Interactive',
    'website': 'http://moldeo.coop/',
    'images': [],
    'depends': [
        'base',
        'account',
        'sale',
        'account_analytic_analysis',
        'project',
    ],
    'demo': [],
    'data': [
        'data/cron_action.xml',
        'data/product_view.xml',
        'data/contract_view.xml',
        'wizard/invoice_contract_data.xml',
    ],
    'test': [ 'test/generate_invoice.yml' ],
    'installable': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
