from odoo import models, api, _, fields
from datetime import datetime

class ReportCustomLedger(models.AbstractModel):
    _name = 'report.custom_general_ledger.template_custom_ledger'
    _description = 'Lógica del Reporte de Libro Mayor Agrupado (Fuerza 3 Dígitos)'

    def _get_account_data(self, date_from, date_to, target_move, company_id):
        cr = self.env.cr
        company = self.env['res.company'].browse(company_id)
        
        move_state = ['posted']
        if target_move == 'all':
            move_state = ['posted', 'draft']

        try:
            fiscalyear_dates = company.compute_fiscalyear_dates(date_from)
            fiscal_year_start = fiscalyear_dates['date_from']
        except Exception:
            dt_from = fields.Date.from_string(date_from)
            fiscal_year_start = dt_from.replace(month=1, day=1).strftime('%Y-%m-%d')

        # 1. SALDOS INICIALES
        query_initial = """
            SELECT 
                aml.account_id,
                SUM(aml.balance) as initial_balance
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.company_id = %s
            AND am.state = ANY(%s)
            AND (
                (aa.internal_group IN ('asset', 'liability', 'equity') AND aml.date < %s)
                OR
                (aa.internal_group IN ('income', 'expense') AND aml.date >= %s AND aml.date < %s)
            )
            GROUP BY aml.account_id
        """
        cr.execute(query_initial, (company_id, move_state, date_from, fiscal_year_start, date_from))
        initial_data = {row[0]: row[1] for row in cr.fetchall()}

        # 2. MOVIMIENTOS DEL PERIODO
        query_period = """
            SELECT 
                aml.account_id,
                SUM(aml.debit) as debit,
                SUM(aml.credit) as credit,
                SUM(aml.balance) as balance
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE aml.company_id = %s
            AND am.state = ANY(%s)
            AND aml.date >= %s AND aml.date <= %s
            GROUP BY aml.account_id
        """
        cr.execute(query_period, (company_id, move_state, date_from, date_to))
        period_data = {row[0]: {'debit': row[1], 'credit': row[2], 'balance': row[3]} for row in cr.fetchall()}

        # 3. IDENTIFICAR CUENTA DE RESULTADOS
        unaffected_earnings_account = self.env['account.account'].search([
            ('company_id', '=', company_id),
            ('account_type', '=', 'equity_unaffected')
        ], limit=1)

        pnl_net_result = 0.0
        all_accounts = self.env['account.account'].search([
            ('company_id', '=', company_id),
            ('deprecated', '=', False)
        ])
        
        grouped_results = {}
        all_groups = self.env['account.group'].search([('company_id', '=', company_id)])
        group_names = {g.code_prefix_start: g.name for g in all_groups if g.code_prefix_start}

        # 4. PROCESAR CADA CUENTA
        for account in all_accounts:
            init_bal = initial_data.get(account.id, 0.0) or 0.0
            p_debit = period_data.get(account.id, {}).get('debit', 0.0) or 0.0
            p_credit = period_data.get(account.id, {}).get('credit', 0.0) or 0.0
            p_bal = period_data.get(account.id, {}).get('balance', 0.0) or 0.0
            
            # Acumular para el Resultado del Ejercicio
            if account.internal_group in ('income', 'expense'):
                pnl_net_result += (init_bal + p_bal)

            is_unaffected = unaffected_earnings_account and account.id == unaffected_earnings_account.id
            
            # Filtro de actividad
            if not is_unaffected and abs(init_bal) < 0.01 and abs(p_debit) < 0.01 and abs(p_credit) < 0.01:
                continue

            code_key = account.code[:3] if account.code else False
            if not code_key: continue

            if code_key not in grouped_results:
                name_to_use = group_names.get(code_key) or (account.group_id.name if account.group_id else f"GRUPO {code_key}")
                grouped_results[code_key] = {
                    'code': code_key,
                    'name': name_to_use,
                    'initial_balance': 0.0,
                    'debit': 0.0,
                    'credit': 0.0
                }

            grouped_results[code_key]['initial_balance'] += init_bal
            grouped_results[code_key]['debit'] += p_debit
            grouped_results[code_key]['credit'] += p_credit

        # Inyectar el resultado en el patrimonio
        if unaffected_earnings_account:
            code_key_earnings = unaffected_earnings_account.code[:3]
            if code_key_earnings in grouped_results:
                grouped_results[code_key_earnings]['initial_balance'] += pnl_net_result

        # 5. PREPARAR LÍNEAS FINALES
        report_lines = []
        for key, values in grouped_results.items():
            final_bal = values['initial_balance'] + values['debit'] - values['credit']
            
            report_lines.append({
                'code': values['code'],
                'name': values['name'],
                'initial_balance': values['initial_balance'],
                'debit': values['debit'],
                'credit': values['credit'],
                'final_balance': final_bal,
                'initial_debit': values['initial_balance'] if values['initial_balance'] > 0 else 0.0,
                'initial_credit': abs(values['initial_balance']) if values['initial_balance'] < 0 else 0.0,
                'final_debit': final_bal if final_bal > 0 else 0.0,
                'final_credit': abs(final_bal) if final_bal < 0 else 0.0,
            })

        report_lines.sort(key=lambda x: x['code'])
        return report_lines

    def _calculate_totals(self, report_lines):
        totals = {
            'initial_debit': 0.0, 'initial_credit': 0.0,
            'debit': 0.0, 'credit': 0.0,
            'final_debit': 0.0, 'final_credit': 0.0,
        }
        for line in report_lines:
            totals['initial_debit'] += line['initial_debit']
            totals['initial_credit'] += line['initial_credit']
            totals['debit'] += line['debit']
            totals['credit'] += line['credit']
            totals['final_debit'] += line['final_debit']
            totals['final_credit'] += line['final_credit']
        return totals

    @api.model
    def _get_report_values(self, docids, data=None):
        """ MÉTODO QUE FALTABA: Este método es el que llama Odoo al generar el PDF """
        if not data:
            data = {}
        
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        company_id = data.get('company_id') or self.env.company.id
        target_move = data.get('target_move', 'posted')

        lines = self._get_account_data(date_from, date_to, target_move, company_id)
        totals = self._calculate_totals(lines)
        company = self.env['res.company'].browse(company_id)

        return {
            'doc_ids': docids,
            'doc_model': 'custom.ledger.wizard',
            'data': data,
            'lines': lines,
            'totals': totals,
            'company': company,
            'currency': company.currency_id,
        }