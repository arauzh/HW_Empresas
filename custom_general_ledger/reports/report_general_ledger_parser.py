from odoo import models, api, _

class ReportCustomLedger(models.AbstractModel):
    _name = 'report.custom_general_ledger.template_custom_ledger'
    _description = 'Lógica del Reporte de Libro Mayor Agrupado'

    def _get_account_data(self, date_from, date_to, target_move, company_id):
        cr = self.env.cr
        
        move_state = ['posted']
        if target_move == 'all':
            move_state = ['posted', 'draft']
            
        # 1. Obtener Saldo Anterior
        query_initial = """
            SELECT aml.account_id, SUM(aml.debit) - SUM(aml.credit) as initial_balance
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE am.date < %s AND am.company_id = %s AND am.state = ANY(%s)
            GROUP BY aml.account_id
        """
        cr.execute(query_initial, (date_from, company_id, move_state))
        initial_data = {row[0]: row[1] for row in cr.fetchall()}

        # 2. Obtener Movimientos del Periodo
        query_period = """
            SELECT aml.account_id, SUM(aml.debit) as debit, SUM(aml.credit) as credit
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE am.date >= %s AND am.date <= %s AND am.company_id = %s AND am.state = ANY(%s)
            GROUP BY aml.account_id
        """
        cr.execute(query_period, (date_from, date_to, company_id, move_state))
        period_data = {row[0]: {'debit': row[1], 'credit': row[2]} for row in cr.fetchall()}

        # 3. Consolidar y Agrupar
        accounts = self.env['account.account'].search([('company_id', '=', company_id)])
        
        # Buscamos grupos que tengan código definido
        all_groups = self.env['account.group'].search([('company_id', '=', company_id)])
        groups_by_prefix = {g.code_prefix_start: g for g in all_groups if g.code_prefix_start}

        grouped_results = {}

        for account in accounts:
            initial = initial_data.get(account.id, 0.0)
            debit = period_data.get(account.id, {}).get('debit', 0.0)
            credit = period_data.get(account.id, {}).get('credit', 0.0)

            if initial == 0 and debit == 0 and credit == 0:
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
                    'initial_balance': 0.0,
                    'debit': 0.0,
                    'credit': 0.0,
                    'final_balance': 0.0,
                }

            grouped_results[key]['initial_balance'] += initial
            grouped_results[key]['debit'] += debit
            grouped_results[key]['credit'] += credit

        # 4. Calcular saldos finales y ordenar
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