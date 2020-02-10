# -*- coding: utf-8 -*-
# Copyright 2018 Halltic eSolutions S.L.
# © 2018 Halltic eSolutions S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import datetime
import logging
import inspect
import os
from datetime import datetime, timedelta

from odoo.addons.component.core import Component
from odoo.addons.queue_job.job import FAILED, STARTED, ENQUEUED, DONE

AMAZON_SAVE_OLD_FEED = 10000
AMAZON_SAVE_OLD_FEED_TO_THROW = 50000
AMAZON_SAVE_OLD_SQS_MESSAGES = 10000
AMAZON_SAVE_OLD_HISTORIC_OFFERS = 5
AMAZON_DELETE_JOBS_OLD_THAN = 10  # It is on days
AMAZON_MAX_DELETE_JOBS = 10000

_logger = logging.getLogger(__name__)


class ProductFixData(Component):
    _name = 'amazon.fix.data.importer'
    _inherit = 'amazon.importer'
    _apply_on = ['amazon.backend']
    _usage = 'amazon.fix.data'

    def _delete_old_done_failed_jobs(self):
        _logger.info('connector_amazon [%s][%s][%s] log: Delete old done and failed jobs' % (os.getpid(), os.getpid(), inspect.stack()[0][3]))

        time_from = (datetime.now() - timedelta(days=AMAZON_DELETE_JOBS_OLD_THAN)).strftime("%Y-%m-%d %H:%M:%S")
        self.env['queue.job'].search([('channel', '=', 'root.amazon'),
                                      ('date_created', '<', time_from),
                                      '|',
                                      ('state', '=', 'done'),
                                      ('state', '=', 'failed')],
                                     limit=AMAZON_MAX_DELETE_JOBS).unlink()

        _logger.info('connector_amazon [%s][%s][%s] log: Finish delete old done and failed jobs' % (os.getpid(), os.getpid(), inspect.stack()[0][3]))

    def _set_pending_hang_jobs(self):
        _logger.info('connector_amazon [%s][%s] log: Set the Amazon hang jobs to pending' % (os.getpid(), inspect.stack()[0][3]))
        time_to_requeue = datetime.now() - timedelta(hours=2)
        jobs = self.env['queue.job'].search(['&',
                                             ('channel', 'like', 'root.amazon'),
                                             '|',
                                             ('date_started', '>', time_to_requeue.isoformat(sep=' ')),
                                             ('date_enqueued', '>', time_to_requeue.isoformat(sep=' ')),
                                             '|',
                                             ('state', '=', STARTED),
                                             ('state', '=', ENQUEUED), ])

        for job in jobs:
            job.requeue()

        _logger.info('connector_amazon [%s][%s] log: Finish set the Amazon hang jobs to pending' % (os.getpid(), inspect.stack()[0][3]))

    def _clean_old_quota_control_data(self):
        _logger.info('connector_amazon [%s][%s] log: Clean Amazon old quota control' % (os.getpid(), inspect.stack()[0][3]))
        time_to_requeue = datetime.now() - timedelta(days=1)
        self.env['amazon.control.date.request'].search([('request_date', '<', time_to_requeue.isoformat(sep=' '))]).unlink()
        _logger.info('connector_amazon [%s][%s] log: Finish clean Amazon old quota control' % (os.getpid(), inspect.stack()[0][3]))

    def _delete_old_feeds(self):
        _logger.info('connector_amazon [%s][%s] log: Delete Amazon old feeds' % (os.getpid(), inspect.stack()[0][3]))
        count_feeds = self.env['amazon.feed'].search_count([])

        if count_feeds > AMAZON_SAVE_OLD_FEED:
            self.env['amazon.feed'].search([], order='create_date asc', limit=count_feeds - AMAZON_SAVE_OLD_FEED).unlink()

        count_feeds_to_throw = self.env['amazon.feed.tothrow'].search_count([('launched', '=', True)])

        if count_feeds_to_throw > AMAZON_SAVE_OLD_FEED_TO_THROW:
            self.env['amazon.feed.tothrow'].search([('launched', '=', True)],
                                                   order='create_date asc',
                                                   limit=count_feeds_to_throw - AMAZON_SAVE_OLD_FEED).unlink()

        _logger.info('connector_amazon [%s][%s] log: Finish delete Amazon old feeds' % (os.getpid(), inspect.stack()[0][3]))

    def _delete_old_sqs_messages(self):
        _logger.info('connector_amazon [%s][%s] log: Delete Amazon old SQS messages' % (os.getpid(), inspect.stack()[0][3]))
        count_messages = self.env['amazon.config.sqs.message'].search_count([('processed', '=', True)])

        if count_messages > AMAZON_SAVE_OLD_SQS_MESSAGES:
            self.env['amazon.config.sqs.message'].search([('processed', '=', True)],
                                                         order='create_date asc',
                                                         limit=count_messages - AMAZON_SAVE_OLD_SQS_MESSAGES).unlink()

        _logger.info('connector_amazon [%s][%s] log: Finish delete Amazon old SQS messages' % (os.getpid(), inspect.stack()[0][3]))

    def _delete_old_offers(self):
        _logger.info('connector_amazon [%s][%s] log: Delete Amazon old offers' % (os.getpid(), inspect.stack()[0][3]))
        amazon_historic_offer_env = self.env['amazon.historic.product.offer']
        amazon_historic_offer_env._cr.execute(""" SELECT
                                            id
                                        FROM
                                            amazon_historic_product_offer 
                                        WHERE product_detail_id IN 
                                            (SELECT 
                                                product_detail_id 
                                             FROM 
                                                amazon_historic_product_offer 
                                             GROUP BY 
                                                product_detail_id HAVING count(product_detail_id)>5)
                                        ORDER BY 
                                            product_detail_id, offer_date ASC
                                                """)

        historic_offer_ids = amazon_historic_offer_env._cr.dictfetchall()
        id_hist = ''
        i = 0
        list_historic_ids = []
        for historic_offer in historic_offer_ids:

            # If there is a change or it is the first time
            if id_hist != historic_offer['id']:
                id_hist = historic_offer['id']
                i = 0

            # Check if delete the offer
            if i > AMAZON_SAVE_OLD_HISTORIC_OFFERS:
                list_historic_ids.append(historic_offer['id'])

            i += 1

        amazon_historic_offer_env.browse(list_historic_ids).unlink()

        _logger.info('connector_amazon [%s][%s] log: Finish delete Amazon old offers' % (os.getpid(), inspect.stack()[0][3]))

    def _throw_concurrent_jobs(self):
        """
        Get failed jobs of amazon that have an exception for concurrent and throw this again
        :return:
        """
        _logger.info('connector_amazon [%s][%s] log: Throw Amazon concurrent jobs' % (os.getpid(), inspect.stack()[0][3]))
        jobs = self.env['queue.job'].search(['&', ('state', '=', FAILED), ('channel', '=', 'root.amazon'),
                                             '|',
                                             ('exc_info', 'ilike',
                                              'InternalError: current transaction is aborted, commands ignored until end of transaction block'),
                                             ('exc_info', 'ilike',
                                              'TransactionRollbackError: could not serialize access due to concurrent update'),
                                             ])

        for job in jobs:
            job.requeue()

        _logger.info('connector_amazon [%s][%s] log: Finish throw Amazon concurrent jobs' % (os.getpid(), inspect.stack()[0][3]))

    def _clean_duplicate_jobs(self):
        """
        Clean duplicate jobs
        :return:
        """
        _logger.info('connector_amazon [%s][%s] log: Clean Amazon duplicate jobs' % (os.getpid(), inspect.stack()[0][3]))
        queue_job_env = self.env['queue.job']
        queue_job_env._cr.execute(""" SELECT 
                                            id, func_string
                                        FROM 
                                            queue_job
                                        WHERE
                                            func_string in
                                                (SELECT 
                                                    func_string
                                                FROM 
                                                    queue_job
                                                WHERE 
                                                    channel = 'root.amazon'
                                                    and state in ('pending', 'started', 'enqueued')
                                                GROUP BY func_string
                                                HAVING COUNT(func_string)>1)
                                        AND state in ('pending', 'started', 'enqueued')
                                        ORDER BY func_string
                                                """)

        jobs_ids = queue_job_env._cr.dictfetchall()
        task = ''
        list_ids = []
        i = 0
        for id_job in jobs_ids:
            if task == id_job['func_string']:
                list_ids.append(id_job['id'])
                i += 1
                if i > AMAZON_MAX_DELETE_JOBS:
                    break

            task = id_job['func_string']

        queue_job_env.browse(list_ids).unlink()

        _logger.info('connector_amazon [%s][%s] log: Finish clean Amazon duplicate jobs' % (os.getpid(), inspect.stack()[0][3]))

    def _get_service_level_order_or_partner_name(self):
        _logger.info('connector_amazon [%s][%s] log: Start get service level of Amazon orders' % (os.getpid(), inspect.stack()[0][3]))

        orders_count = 0
        amazon_sales = []

        while orders_count < 150:
            orders = self.env['amazon.sale.order'].search([('shipment_service_level_category', '=', False),
                                                           ('order_status_id.name', '=', 'Unshipped'),
                                                           ('backend_id', '=', self.backend_record.id)], limit=50) \
                     or \
                     self.env['amazon.sale.order'].search(
                         [('amazon_partner_id.name', '=', False),
                          ('backend_id', '=', self.backend_record.id)], limit=50) \
                     or \
                     self.env['amazon.sale.order'].search(
                         [('shipment_service_level_category', '=', False),
                          ('backend_id', '=', self.backend_record.id)], limit=50)

            orders_count += 50

            if orders:
                order_ids = orders.mapped('id_amazon_order')
                importer_sale_order = self.work.component(model_name='amazon.sale.order', usage='amazon.sale.data.import')
                json_orders = importer_sale_order.get_orders(ids=[order_ids])
                if json_orders and not isinstance(json_orders, list):
                    json_orders = [json_orders]
                amazon_sales.extend(json_orders)

            if len(orders) < 50:
                break

        for amazon_sale_dict in amazon_sales:
            sale = self.env['amazon.sale.order'].search([('id_amazon_order', '=', amazon_sale_dict['order_id'])])
            if not sale.amazon_partner_id.name:
                importer_partner = self.work.component(model_name='amazon.res.partner', usage='record.importer')
                importer_partner.amazon_record = amazon_sale_dict['partner']
                importer_partner.run(external_id=amazon_sale_dict['partner']['email'])

            vals = {'shipment_service_level_category':amazon_sale_dict['shipment_service_level_category']}
            sale.write(vals)

        _logger.info('connector_amazon [%s][%s] log: Finish get service level of Amazon orders' % (os.getpid(), inspect.stack()[0][3]))

    def _clean_duplicate_amazon_products(self):

        """
            Clean duplicate jobs
            :return:
        """
        _logger.info('connector_amazon [%s][%s] log: Clean Amazon duplicate products' % (os.getpid(), inspect.stack()[0][3]))
        amz_prod_env = self.env['amazon.product.product']
        amz_prod_env._cr.execute(""" SELECT 
                                            id, asin 
                                      FROM 
                                            amazon_product_product 
                                      WHERE 
                                            asin in (SELECT 
                                                        asin 
                                                     FROM amazon_product_product 
                                                     GROUP BY 
                                                        asin 
                                                     HAVING count(asin)>1) 
                                      ORDER BY asin, create_date
                                                        """)

        amz_product_ids = amz_prod_env._cr.dictfetchall()
        asin = ''
        list_ids = []
        i = 0
        for prod in amz_product_ids:
            if asin == prod['asin']:
                # TODO create feed to delete product

                list_ids.append(prod['id'])
                i += 1

            asin = prod['asin']

        amz_prod_env.browse(list_ids).unlink()

        _logger.info('connector_amazon [%s][%s] log: Finish clean Amazon duplicate products' % (os.getpid(), inspect.stack()[0][3]))
        return

    def run(self):

        ''' TODO Finish to develop the method
        try:
            self._clean_duplicate_amazon_products()
        except Exception as e:
            _logger.error('Connector_amazon log: exception executing _clean_duplicate_jobs [%s]' % e.message)

        try:
            self._clean_duplicate_jobs()
        except Exception as e:
            _logger.error('Connector_amazon log: exception executing _clean_duplicate_jobs [%s]' % e.message)
        try:
            self._throw_concurrent_jobs()
        except Exception as e:
            _logger.error('Connector_amazon log: exception executing _throw_concurrent_jobs [%s]' % e.message)
        try:
            self._delete_old_feeds()
        except Exception as e:
            _logger.error('Connector_amazon log: exception executing _delete_old_feeds [%s]' % e.message)
        try:
            self._delete_old_sqs_messages()
        except Exception as e:
            _logger.error('Connector_amazon log: exception executing _delete_old_sqs_messages [%s]' % e.message)
        try:
            self._delete_old_offers()
        except Exception as e:
            _logger.error('Connector_amazon log: exception executing _delete_old_offers [%s]' % e.message)
        try:
            self._clean_old_quota_control_data()
        except Exception as e:
            _logger.error('Connector_amazon log: exception executing _clean_old_quota_control_data [%s]' % e.message)
        try:
            self._set_pending_hang_jobs()
        except Exception as e:
            _logger.error('Connector_amazon log: exception executing _set_pending_hang_jobs [%s]' % e.message)
        try:
            self._get_service_level_order_or_partner_name()
        except Exception as e:
            _logger.error('Connector_amazon log: exception executing _get_service_level_order [%s]' % e.message)
        '''
        try:
            self._delete_old_done_failed_jobs()
        except Exception as e:
            _logger.error('Connector_amazon log: exception executing _delete_old_done_failed_jobs [%s]' % e.message)
