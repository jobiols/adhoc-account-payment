# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api
from openerp.tools.misc import formatLang
from ast import literal_eval


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    checkbook_ids = fields.One2many(
        'account.checkbook',
        'journal_id',
        'Checkbooks',
    )

    @api.model
    def create(self, vals):
        rec = super(AccountJournal, self).create(vals)
        issue_checks = self.env.ref(
            'account_check.account_payment_method_issue_check')
        if (issue_checks in rec.outbound_payment_method_ids and
                not rec.checkbook_ids):
            rec._create_checkbook()
        return rec

    @api.one
    def _create_checkbook(self):
        """ Create a check sequence for the journal """
        checkbook = self.checkbook_ids.create({
            'journal_id': self.id,
        })
        checkbook.state = 'active'

    @api.model
    def _enable_issue_check_on_bank_journals(self):
        """ Enables issue checks payment method
            Called upon module installation via data file.
        """
        issue_checks = self.env.ref(
            'account_check.account_payment_method_issue_check')
        domain = [('type', '=', 'bank')]
        force_company_id = self._context.get('force_company_id')
        if force_company_id:
            domain += [('company_id', '=', force_company_id)]
        bank_journals = self.search(domain)
        for bank_journal in bank_journals:
            if not bank_journal.checkbook_ids:
                bank_journal._create_checkbook()
            bank_journal.write({
                'outbound_payment_method_ids': [(4, issue_checks.id, None)],
            })

###############
# For dashboard
###############

    @api.multi
    def get_journal_dashboard_datas(self):
        domain_holding_third_checks = [
            # ('payment_method_id.code', '=', 'received_third_check'),
            ('type', '=', 'third_check'),
            ('journal_id', '=', self.id),
            # ('check_state', '=', 'holding')
            ('state', '=', 'holding')
        ]
        domain_handed_issue_checks = [
            # ('payment_method_id.code', '=', 'issue_check'),
            ('type', '=', 'issue_check'),
            ('journal_id', '=', self.id),
            ('state', '=', 'handed')
            # ('check_state', '=', 'handed')
        ]
        handed_checks = self.env['account.check'].search(
            domain_handed_issue_checks)
        holding_checks = self.env['account.check'].search(
            domain_holding_third_checks)
        return dict(
            super(AccountJournal, self).get_journal_dashboard_datas(),
            num_holding_third_checks=len(holding_checks),
            show_third_checks=(
                'received_third_check' in
                self.inbound_payment_method_ids.mapped('code')),
            show_issue_checks=(
                'issue_check' in
                self.outbound_payment_method_ids.mapped('code')),
            num_handed_issue_checks=len(handed_checks),
            handed_amount=formatLang(
                self.env, sum(handed_checks.mapped('amount')),
                currency_obj=self.currency_id or self.company_id.currency_id),
            holding_amount=formatLang(
                self.env, sum(holding_checks.mapped('amount')),
                currency_obj=self.currency_id or self.company_id.currency_id),
        )

    @api.multi
    def open_action_checks(self):
        check_type = self.env.context.get('check_type', False)
        if check_type == 'third_check':
            action_name = 'account_check.action_third_check'
        elif check_type == 'issue_check':
            action_name = 'account_check.action_issue_check'
        else:
            return False
        actions = self.env.ref(action_name)
        action_read = actions.read()[0]
        context = literal_eval(action_read['context'])
        context['search_default_journal_id'] = self.id
        action_read['context'] = context
        return action_read
