from odoo import models, api, _

class ReportCustomDaily(models.AbstractModel):
    _name = 'report.custom_general_ledger.template_custom_daily'
    _description = 'Lógica del Libro Diario Resumido'

    def _get_account_data(self, date_from, date_to, target_move, company_id):
        cr = self.env.cr
        
        move_state = ['posted']
        if target_move == 'all':
            move_state = ['posted', 'draft']

        query_period = """
            SELECT aml.account_id, SUM(aml.debit) as debit, SUM(aml.credit) as credit
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE am.date >= %s AND am.date <= %s AND am.company_id = %s AND am.state = ANY(%s)
            GROUP BY aml.account_id
        """
        cr.execute(query_period, (date_from, date_to, company_id, move_state))
        period_data = {row[0]: {'debit': row[1], 'credit': row[2]} for row in cr.fetchall()}

        accounts = self.env['account.account'].search([('company_id', '=', company_id)])
        
        all_groups = self.env['account.group'].search([('company_id', '=', company_id)])
        groups_by_prefix = {g.code_prefix_start: g for g in all_groups if g.code_prefix_start}

        grouped_results = {}

        for account in accounts:
            debit = period_data.get(account.id, {}).get('debit', 0.0)
            credit = period_data.get(account.id, {}).get('credit', 0.0)

            if debit == 0 and credit == 0:
                continue

            group = account.group_id
            
            if not group:
                prefix_3 = account.code[:3] 
                prefix_2 = account.code[:2] 
                
                if prefix_3 in groups_by_prefix:
                    group = groups_by_prefix[prefix_3]
                elif prefix_2 in groups_by_prefix:
                    group = groups_by_prefix[prefix_2]

            if group:
                key = f"group_{group.id}"
                code = group.code_prefix_start
                name = group.name
            else:
                key = f"account_{account.id}"
                code = account.code
                name = account.name

            if key not in grouped_results:
                grouped_results[key] = {
                    'code': code,
                    'name': name,
                    'debit': 0.0,
                    'credit': 0.0,
                }

            grouped_results[key]['debit'] += debit
            grouped_results[key]['credit'] += credit

        report_lines = list(grouped_results.values())
        report_lines.sort(key=lambda x: x['code'] or '')

        return report_lines

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'custom.daily.wizard',
            'data': data,
            'lines': self._get_account_data(data['date_from'], data['date_to'], data['target_move'], data['company_id']),
            'company': self.env['res.company'].browse(data['company_id']),
        }