# -*- coding: utf-8 -*-
# Copyright 2017 Halltic eSolutions S.L. ()
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Amazon Connector',
    'version': '0.1.0',
    'author': 'Halltic eSolutions S.L.',
    'maintainer': 'True',
    'website': 'False',
    'license': '',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml # noqa
    # for the full list
    'category': 'Connector', 'summary': 'It is a connector to MWS Amazon account',
    'description': """

""",

    # any module necessary for this one to work correctly
    'depends': ['connector',
                'base_technical_user',
                'sale_stock',
                'product_margin',
                'delivery',
                # 'product_brand',
                # 'product_dimension',
                'partner_address_street3',
                'connector_ecommerce'],

    # always loaded
    'data':[
        'security/connector_security.xml',
        'security/ir.model.access.csv',
        'wizards/wizard_import_orders.xml',
        'wizards/wizard_export_products.xml',
        'wizards/wizard_set_change_prices_margins_flag.xml',
        'views/amazon_config_views.xml',
        'views/amazon_backend_views.xml',
        'views/amazon_order_views.xml',
        'views/amazon_partner_views.xml',
        'views/amazon_product_views.xml',
        'views/amazon_return_views.xml',
        'views/amazon_feed_views.xml',
        'views/connector_amazon_menu.xml',
        'views/product_views.xml',
        'views/res_partner_views.xml',
        'data/amazon_scheduler.xml',
        'data/amazon_connector_data.xml',
        'data/amazon_connector_config_settings.xml',
        'data/quota_mws_data.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        # 'demo/demo.xml'
    ],

    'js': [],
    'css': [],
    'qweb': [],

    'installable': True,
    # Install this module automatically if all dependency have been previously
    # and independently installed.  Used for synergetic or glue modules.
    'auto_install': False,
    'application': True,
}
