from odoo import models, api, _

class ReportCustomLedger(models.AbstractModel):
    _name = 'report.custom_general_ledger.template_custom_ledger'
    _description = 'Lógica del Reporte de Libro Mayor Agrupado (Fuerza 3 Digitos)'

    def _get_account_data(self, date_from, date_to, target_move, company_id):
        cr = self.env.cr
        
        move_state = ['posted']
        if target_move == 'all':
            move_state = ['posted', 'draft']
            
        # 1. Consulta Saldo Inicial
        query_initial = """
            SELECT
                aml.account_id,
                SUM(aml.debit - aml.credit) AS initial_balance
            FROM account_move_line aml
            WHERE aml.date < %s
            AND aml.company_id = %s
            AND aml.parent_state = ANY(%s)
            AND aml.display_type IN ('product', 'tax', 'payment_term')
            GROUP BY aml.account_id
        """
        cr.execute(query_initial, (date_from, company_id, move_state))
        initial_data = {row[0]: row[1] for row in cr.fetchall()}

        # 2. Consulta Movimientos del Periodo
        query_period = """
            SELECT
                aml.account_id,
                SUM(aml.debit) AS debit,
                SUM(aml.credit) AS credit
            FROM account_move_line aml
            WHERE aml.date >= %s
            AND aml.date <= %s
            AND aml.company_id = %s
            AND aml.parent_state = ANY(%s)
            AND aml.display_type IN ('product', 'tax', 'payment_term')
            GROUP BY aml.account_id
        """
        cr.execute(query_period, (date_from, date_to, company_id, move_state))
        period_data = {row[0]: {'debit': row[1], 'credit': row[2]} for row in cr.fetchall()}

        # 3. Carga de Cuentas y Grupos
        accounts = self.env['account.account'].search([('company_id', '=', company_id)])
        all_groups = self.env['account.group'].search([('company_id', '=', company_id)])
        
        group_names = {}
        for g in all_groups:
            if g.code_prefix_start:
                group_names[g.code_prefix_start] = g.name

        grouped_results = {}

        for account in accounts:
            initial = initial_data.get(account.id, 0.0) or 0.0
            debit = period_data.get(account.id, {}).get('debit', 0.0) or 0.0
            credit = period_data.get(account.id, {}).get('credit', 0.0) or 0.0

            if initial == 0 and debit == 0 and credit == 0:
                continue

            code_key = account.code[:3] if len(account.code) >= 3 else account.code

            if code_key not in grouped_results:
                name_to_use = group_names.get(code_key) or (account.group_id.name if account.group_id else f"GRUPO {code_key}")
                
                grouped_results[code_key] = {
                    'code': code_key,
                    'name': name_to_use,
                    'initial_balance': 0.0,
                    'debit': 0.0,
                    'credit': 0.0,
                    'final_balance': 0.0,
                }

            grouped_results[code_key]['initial_balance'] += initial
            grouped_results[code_key]['debit'] += debit
            grouped_results[code_key]['credit'] += credit

        # 4. Totales y Orden
        report_lines = []
        for key, values in grouped_results.items():
            values['final_balance'] = values['initial_balance'] + values['debit'] - values['credit']
            report_lines.append(values)

        report_lines.sort(key=lambda x: x['code'] or '')

        return report_lines

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'custom.ledger.wizard',
            'data': data,
            'lines': self._get_account_data(data['date_from'], data['date_to'], data['target_move'], data['company_id']),
            'company': self.env['res.company'].browse(data['company_id']),
        }