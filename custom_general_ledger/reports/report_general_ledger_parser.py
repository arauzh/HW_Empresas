from odoo import models, api, _, fields
import logging

_logger = logging.getLogger(__name__)

class ReportCustomLedger(models.AbstractModel):
    _name = 'report.custom_general_ledger.template_custom_ledger'
    _description = 'Lógica del Reporte de Libro Mayor Agrupado'

    def _get_account_data(self, date_from, date_to, target_move, company_id):
        cr = self.env.cr
        if not date_from or not date_to:
            return []

        # 1. Preparacion de datos
        move_state = ['posted']
        if target_move == 'all':
            move_state = ['posted', 'draft']
        
        if isinstance(company_id, list):
            company_id = company_id[0]
        company = self.env['res.company'].browse(company_id)

        # 2. Determinar fechas fiscales
        try:
            fiscal_year_start = company.compute_fiscalyear_dates(fields.Date.from_string(date_from))['date_from']
        except:
            fiscal_year_start = fields.Date.from_string(date_from).replace(month=1, day=1)

        # 3. Calculo de resultados
        query_pnl_hist = """
            SELECT SUM(aml.balance)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.company_id = %s
            AND am.state = ANY(%s)
            AND aa.internal_group IN ('income', 'expense')
            AND aml.date < %s
        """
        cr.execute(query_pnl_hist, (company_id, move_state, fiscal_year_start))
        res_hist = cr.fetchone()
        pnl_historico = (res_hist[0] or 0.0) if res_hist else 0.0

        # 4. Consulta de saldos iniciales
        query_initial = """
            SELECT aml.account_id, SUM(aml.balance)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.company_id = %s AND am.state = ANY(%s)
            AND (
                (aa.internal_group IN ('asset', 'liability', 'equity') AND aml.date < %s)
                OR
                (aa.internal_group IN ('income', 'expense') AND aml.date >= %s AND aml.date < %s)
            )
            GROUP BY aml.account_id
        """
        cr.execute(query_initial, (company_id, move_state, date_from, fiscal_year_start, date_from))
        initial_data = {row[0]: row[1] for row in cr.fetchall()}

        # 5. Consulta de movimientos en el rango de fechas
        query_period = """
            SELECT aml.account_id, SUM(aml.debit), SUM(aml.credit)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE aml.company_id = %s AND am.state = ANY(%s)
            AND aml.date >= %s AND aml.date <= %s
            GROUP BY aml.account_id
        """
        cr.execute(query_period, (company_id, move_state, date_from, date_to))
        period_data = {row[0]: {'debit': row[1], 'credit': row[2]} for row in cr.fetchall()}

        # 6. Agrupacion
        all_accounts = self.env['account.account'].search([('company_id', '=', company_id)])
        groups = self.env['account.group'].search([('company_id', '=', company_id)])
        group_names = {g.code_prefix_start: g.name for g in groups if g.code_prefix_start}
        
        # Buscar cuenta de resultados
        unaffected_acc = self.env['account.account'].search([
            ('account_type', '=', 'equity_unaffected'),
            ('company_id', '=', company_id)
        ], limit=1)

        grouped_results = {}

        for account in all_accounts:
            init_bal = initial_data.get(account.id, 0.0) or 0.0
            p_deb = period_data.get(account.id, {}).get('debit', 0.0) or 0.0
            p_cre = period_data.get(account.id, {}).get('credit', 0.0) or 0.0

            if abs(init_bal) < 0.001 and abs(p_deb) < 0.001 and abs(p_cre) < 0.001:
                if not (unaffected_acc and account.id == unaffected_acc.id):
                    continue

            code_key = account.code[:3] if account.code else 'S/N'
            if code_key not in grouped_results:
                grouped_results[code_key] = {
                    'code': code_key, 
                    'name': group_names.get(code_key) or f"Grupo {code_key}", 
                    'initial_balance': 0.0, 'debit': 0.0, 'credit': 0.0
                }
            
            grouped_results[code_key]['initial_balance'] += init_bal
            grouped_results[code_key]['debit'] += p_deb
            grouped_results[code_key]['credit'] += p_cre

        # 7. Datos de la cuenta resultados
        if unaffected_acc:
            code_3 = unaffected_acc.code[:3]
        else:
            code_3 = '399'

        if code_3 not in grouped_results:
            grouped_results[code_3] = {'code': code_3, 'name': 'RESULTADOS ACUMULADOS', 'initial_balance': 0.0, 'debit': 0.0, 'credit': 0.0}
        grouped_results[code_3]['initial_balance'] += pnl_historico

        # 8. Formato XML
        report_lines = []
        for key in sorted(grouped_results.keys()):
            vals = grouped_results[key]
            f_bal = vals['initial_balance'] + vals['debit'] - vals['credit']
            
            if abs(vals['initial_balance']) < 0.01 and \
               abs(vals['debit']) < 0.01 and \
               abs(vals['credit']) < 0.01 and \
               abs(f_bal) < 0.01:
                continue
            
            report_lines.append({
                'code': vals['code'],
                'name': vals['name'],
                'initial_balance': vals['initial_balance'],
                'final_balance': f_bal,
                'initial_debit': vals['initial_balance'] if vals['initial_balance'] > 0 else 0.0,
                'initial_credit': abs(vals['initial_balance']) if vals['initial_balance'] < 0 else 0.0,
                'debit': vals['debit'],
                'credit': vals['credit'],
                'final_debit': f_bal if f_bal > 0 else 0.0,
                'final_credit': abs(f_bal) if f_bal < 0 else 0.0,
            })
        return report_lines

    @api.model
    def _get_report_values(self, docids, data=None):
        if data and data.get('form'):
            params = data.get('form')
        else:
            params = data or {}

        date_from = params.get('date_from')
        date_to = params.get('date_to')
        target_move = params.get('target_move', 'posted')
        company_id = params.get('company_id') or self.env.company.id

        lines = self._get_account_data(date_from, date_to, target_move, company_id)
        
        totals = {
            'init_d': sum(l['initial_debit'] for l in lines),
            'init_c': sum(l['initial_credit'] for l in lines),
            'deb': sum(l['debit'] for l in lines),
            'cre': sum(l['credit'] for l in lines),
            'fin_d': sum(l['final_debit'] for l in lines),
            'fin_c': sum(l['final_credit'] for l in lines),
        }

        return {
            'doc_ids': docids,
            'data': params,
            'lines': lines,
            'totals': totals,
            'company': self.env['res.company'].browse(company_id) if not isinstance(company_id, list) else self.env['res.company'].browse(company_id[0]),
        }