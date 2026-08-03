from odoo import models, api, _

class ReportCustomDaily(models.AbstractModel):
    _name = 'report.custom_general_ledger.template_custom_daily'
    _description = 'Lógica del Libro Diario Resumido (Fuerza 3 Digitos)'

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

        # Mapa de nombres de grupos
        group_names = {}
        for g in all_groups:
            if g.code_prefix_start:
                group_names[g.code_prefix_start] = g.name

        grouped_results = {}

        for account in accounts:
            debit = period_data.get(account.id, {}).get('debit', 0.0)
            credit = period_data.get(account.id, {}).get('credit', 0.0)

            if debit == 0 and credit == 0:
                continue

            code = account.code or ''
            code_key = code[:3] if len(code) >= 3 else code

            if code_key not in grouped_results:
                # Se busca el nombre de la cuenta
                name_to_use = group_names.get(code_key) or (account.group_id.name if account.group_id else f"GRUPO {code_key}")
                
                grouped_results[code_key] = {
                    'code': code_key,
                    'name': name_to_use,
                    'debit': 0.0,
                    'credit': 0.0,
                }

            # Sumamos montos
            grouped_results[code_key]['debit'] += debit
            grouped_results[code_key]['credit'] += credit

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