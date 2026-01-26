from odoo import models, api, _

class ReportCustomLedger(models.AbstractModel):
    _name = 'report.custom_general_ledger.template_custom_ledger'
    _description = 'Lógica del Reporte de Libro Mayor Agrupado (Fuerza 3 Digitos)'

    def _get_account_data(self, date_from, date_to, target_move, company_id):
        cr = self.env.cr
        
        move_state = ['posted']
        if target_move == 'all':
            move_state = ['posted', 'draft']
            
        # 1. Consulta
        query_initial = """
            SELECT aml.account_id, SUM(aml.debit) - SUM(aml.credit) as initial_balance
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE am.date < %s AND am.company_id = %s AND am.state = ANY(%s)
            GROUP BY aml.account_id
        """
        cr.execute(query_initial, (date_from, company_id, move_state))
        initial_data = {row[0]: row[1] for row in cr.fetchall()}

        query_period = """
            SELECT aml.account_id, SUM(aml.debit) as debit, SUM(aml.credit) as credit
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE am.date >= %s AND am.date <= %s AND am.company_id = %s AND am.state = ANY(%s)
            GROUP BY aml.account_id
        """
        cr.execute(query_period, (date_from, date_to, company_id, move_state))
        period_data = {row[0]: {'debit': row[1], 'credit': row[2]} for row in cr.fetchall()}

        # 2. Carga de Cuentas y Grupos
        accounts = self.env['account.account'].search([('company_id', '=', company_id)])
        all_groups = self.env['account.group'].search([('company_id', '=', company_id)])
        
        group_map = {}
        for g in all_groups:
            if g.code_prefix_start:
                group_map[g.code_prefix_start] = g.name
                if len(g.code_prefix_start) > 3:
                     group_map[g.code_prefix_start[:3]] = g.name

        grouped_results = {}

        for account in accounts:
            initial = initial_data.get(account.id, 0.0)
            debit = period_data.get(account.id, {}).get('debit', 0.0)
            credit = period_data.get(account.id, {}).get('credit', 0.0)

            if initial == 0 and debit == 0 and credit == 0:
                continue

            code_key = account.code[:3] if len(account.code) >= 3 else account.code

            group_name = group_map.get(code_key, False)
            
            if not group_name:
                if account.group_id:
                    group_name = account.group_id.name
                else:
                    group_name = f"GRUPO {code_key}"

            # Diccionario
            key = f"prefix_{code_key}"

            if key not in grouped_results:
                grouped_results[key] = {
                    'code': code_key,    
                    'name': group_name,  
                    'initial_balance': 0.0,
                    'debit': 0.0,
                    'credit': 0.0,
                    'final_balance': 0.0,
                }

            # Suma
            grouped_results[key]['initial_balance'] += initial
            grouped_results[key]['debit'] += debit
            grouped_results[key]['credit'] += credit

        # 3. Totales y Orden
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