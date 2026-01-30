from odoo import models, api, _

class ReportCustomLedger(models.AbstractModel):
    _name = 'report.custom_general_ledger.template_custom_ledger'
    _description = 'Lógica del Reporte de Libro Mayor Agrupado (Fuerza 3 Digitos)'

    def _get_account_data(self, date_from, date_to, target_move, company_id):
        cr = self.env.cr
        company = self.env['res.company'].browse(company_id)
        currency = company.currency_id
        
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
        
        group_names = {}
        for g in all_groups:
            if g.code_prefix_start:
                group_names[g.code_prefix_start] = g.name

        grouped_results = {}

        for account in accounts:
            raw_initial = initial_data.get(account.id, 0.0)
            raw_debit = period_data.get(account.id, {}).get('debit', 0.0)
            raw_credit = period_data.get(account.id, {}).get('credit', 0.0)
            
            if account.internal_group in ['income', 'expense']:
                initial = 0.0
            else:
                initial = currency.round(raw_initial) if raw_initial else 0.0

            debit = currency.round(raw_debit) if raw_debit else 0.0
            credit = currency.round(raw_credit) if raw_credit else 0.0

            if debit == 0 and credit == 0:
                continue

            # Determinamos el prefijo (3 dígitos)
            code_key = account.code[:3] if len(account.code) >= 3 else account.code

            # SI EL GRUPO YA EXISTE EN EL DICCIONARIO, NO CAMBIAMOS EL NOMBRE
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

            # Sumamos los valores (el nombre ya no se toca)
            grouped_results[code_key]['initial_balance'] += initial
            grouped_results[code_key]['debit'] += debit
            grouped_results[code_key]['credit'] += credit

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