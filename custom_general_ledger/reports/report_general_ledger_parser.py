from odoo import models, api, _

class ReportCustomLedger(models.AbstractModel):
    _name = 'report.custom_general_ledger.template_custom_ledger'
    _description = 'Lógica del Reporte de Libro Mayor Agrupado'

    def _get_account_data(self, date_from, date_to, target_move, company_id):
        cr = self.env.cr
        
        # Filtro de estado de asientos
        move_state = ['posted']
        if target_move == 'all':
            move_state = ['posted', 'draft']
            
        # 1. Obtener Saldo Anterior
        query_initial = """
            SELECT 
                aml.account_id, 
                SUM(aml.debit) - SUM(aml.credit) as initial_balance
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE am.date < %s
            AND am.company_id = %s
            AND am.state = ANY(%s)
            GROUP BY aml.account_id
        """
        cr.execute(query_initial, (date_from, company_id, move_state))
        initial_data = {row[0]: row[1] for row in cr.fetchall()}

        # 2. Obtener Movimientos del Periodo
        query_period = """
            SELECT 
                aml.account_id,
                SUM(aml.debit) as debit,
                SUM(aml.credit) as credit
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE am.date >= %s AND am.date <= %s
            AND am.company_id = %s
            AND am.state = ANY(%s)
            GROUP BY aml.account_id
        """
        cr.execute(query_period, (date_from, date_to, company_id, move_state))
        period_data = {row[0]: {'debit': row[1], 'credit': row[2]} for row in cr.fetchall()}

        # 3. Consolidar y Agrupar datos
        accounts = self.env['account.account'].search([('company_id', '=', company_id)])
        
        grouped_results = {}

        for account in accounts:
            initial = initial_data.get(account.id, 0.0)
            debit = period_data.get(account.id, {}).get('debit', 0.0)
            credit = period_data.get(account.id, {}).get('credit', 0.0)

            # Si la cuenta no tiene movimientos ni saldo, la ignoramos
            if initial == 0 and debit == 0 and credit == 0:
                continue

            # --- LÓGICA DE AGRUPACIÓN ---
            group = account.group_id

            if group:
                # Si tiene grupo, usamos el ID del grupo como clave para sumar
                # Usamos el prefijo del grupo
                key = f"group_{group.id}"
                code = group.code_prefix_start # Ej: 101
                name = group.name              # Ej: INMUEBLES
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

        # 4. Calcular saldos finales y convertir a lista
        report_lines = []
        for key, values in grouped_results.items():
            values['final_balance'] = values['initial_balance'] + values['debit'] - values['credit']
            report_lines.append(values)

        # 5. Ordenar por código
        report_lines.sort(key=lambda x: x['code'] or '')

        return report_lines

    @api.model
    def _get_report_values(self, docids, data=None):
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        target_move = data.get('target_move')
        company_id = data.get('company_id')

        lines = self._get_account_data(date_from, date_to, target_move, company_id)

        return {
            'doc_ids': docids,
            'doc_model': 'custom.ledger.wizard',
            'data': data,
            'lines': lines,
            'company': self.env['res.company'].browse(company_id),
        }