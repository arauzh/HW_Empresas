from odoo import models, api, _, fields
from datetime import datetime

class ReportCustomLedger(models.AbstractModel):
    _name = 'report.custom_general_ledger.template_custom_ledger'
    _description = 'Lógica del Reporte de Libro Mayor Agrupado (Fuerza 3 Dígitos)'

    def _get_account_data(self, date_from, date_to, target_move, company_id):
        """
        Obtiene los datos de las cuentas agrupadas por los primeros 3 dígitos
        """
        cr = self.env.cr
        
        # Configurar estados de asiento contable
        move_state = ['posted']
        if target_move == 'all':
            move_state = ['posted', 'draft']
        
        # Obtener información de la compañía
        company = self.env['res.company'].browse(company_id)
        
        # Determinar fecha de inicio del año fiscal
        try:
            # Método específico de Odoo 17 para obtener fechas del año fiscal
            fiscalyear_dates = company.compute_fiscalyear_dates(date_from)
            fiscal_year_start = fiscalyear_dates['date_from']
        except (AttributeError, Exception):
            # Fallback: primer día del año calendario
            fiscal_year_start = datetime.strptime(date_from, '%Y-%m-%d').replace(month=1, day=1)
            fiscal_year_start = fiscal_year_start.strftime('%Y-%m-%d')
        
        # ==============================================
        # 1. CONSULTA SALDO INICIAL PARA CUENTAS DE BALANCE
        # (Activo, Pasivo, Patrimonio) - Saldo histórico completo
        # ==============================================
        query_balance_accounts = """
            SELECT
                aml.account_id,
                SUM(aml.balance) AS initial_balance
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.date < %s
            AND aml.company_id = %s
            AND am.state = ANY(%s)
            AND aa.internal_group IN ('asset', 'liability', 'equity')
            AND aa.deprecated = FALSE
            GROUP BY aml.account_id
        """
        
        cr.execute(query_balance_accounts, (date_from, company_id, move_state))
        initial_balance_data = {row[0]: row[1] for row in cr.fetchall()}
        
        # ==============================================
        # 2. CONSULTA SALDO INICIAL PARA CUENTAS DE RESULTADOS
        # (Ingresos, Gastos) - Solo desde inicio del año fiscal
        # ==============================================
        query_pnl_accounts = """
            SELECT
                aml.account_id,
                SUM(aml.balance) AS initial_balance
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.date >= %s
            AND aml.date < %s
            AND aml.company_id = %s
            AND am.state = ANY(%s)
            AND aa.internal_group IN ('income', 'expense')
            AND aa.deprecated = FALSE
            GROUP BY aml.account_id
        """
        
        cr.execute(query_pnl_accounts, (fiscal_year_start, date_from, company_id, move_state))
        initial_pnl_data = {row[0]: row[1] for row in cr.fetchall()}
        
        # Combinar ambos diccionarios
        initial_data = {**initial_balance_data, **initial_pnl_data}
        
        # ==============================================
        # 3. CONSULTA MOVIMIENTOS DEL PERIODO ACTUAL
        # ==============================================
        query_period = """
            SELECT
                aml.account_id,
                SUM(aml.debit) AS debit,
                SUM(aml.credit) AS credit,
                SUM(aml.balance) AS period_balance
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.date >= %s
            AND aml.date <= %s
            AND aml.company_id = %s
            AND am.state = ANY(%s)
            AND aa.deprecated = FALSE
            GROUP BY aml.account_id
        """
        
        cr.execute(query_period, (date_from, date_to, company_id, move_state))
        period_data = {}
        for row in cr.fetchall():
            period_data[row[0]] = {
                'debit': row[1] or 0.0,
                'credit': row[2] or 0.0,
                'period_balance': row[3] or 0.0
            }
        
        # ==============================================
        # 4. OBTENER TODAS LAS CUENTAS Y GRUPOS
        # ==============================================
        accounts = self.env['account.account'].search([
            ('company_id', '=', company_id),
            ('deprecated', '=', False)
        ])
        
        # Obtener nombres de grupos contables
        all_groups = self.env['account.group'].search([('company_id', '=', company_id)])
        group_names = {}
        for group in all_groups:
            if group.code_prefix_start:
                group_names[group.code_prefix_start] = group.name
        
        # Diccionario para resultados agrupados
        grouped_results = {}
        
        # ==============================================
        # 5. PROCESAR CADA CUENTA Y AGRUPAR POR 3 DÍGITOS
        # ==============================================
        for account in accounts:
            account_id = account.id
            
            # Obtener datos
            initial_balance = initial_data.get(account_id, 0.0) or 0.0
            period_info = period_data.get(account_id, {})
            debit = period_info.get('debit', 0.0) or 0.0
            credit = period_info.get('credit', 0.0) or 0.0
            
            # Determinar si la cuenta tiene actividad
            has_activity = (
                abs(initial_balance) >= 0.01 or 
                abs(debit) >= 0.01 or 
                abs(credit) >= 0.01
            )
            
            if not has_activity:
                continue
            
            # Obtener clave de agrupación (primeros 3 dígitos del código)
            account_code = account.code or ''
            code_key = account_code[:3] if len(account_code) >= 3 else account_code
            
            # Si no hay clave, saltar esta cuenta
            if not code_key:
                continue
            
            # Crear o actualizar el grupo
            if code_key not in grouped_results:
                # Buscar nombre del grupo
                name_to_use = group_names.get(code_key)
                if not name_to_use:
                    # Intentar obtener del grupo asignado a la cuenta
                    name_to_use = account.group_id.name if account.group_id else f"GRUPO {code_key}"
                
                # Inicializar grupo
                grouped_results[code_key] = {
                    'code': code_key,
                    'name': name_to_use,
                    'initial_debit': 0.0,
                    'initial_credit': 0.0,
                    'debit': 0.0,
                    'credit': 0.0,
                    'final_debit': 0.0,
                    'final_credit': 0.0,
                    'accounts': []  # Para detalle si lo necesitas después
                }
            
            # Acumular saldos según naturaleza de la cuenta
            group = grouped_results[code_key]
            
            # Saldo inicial: determinar si es deudor o acreedor
            if initial_balance >= 0:
                group['initial_debit'] += initial_balance
            else:
                group['initial_credit'] += abs(initial_balance)
            
            # Movimientos del período
            group['debit'] += debit
            group['credit'] += credit
            
            # Calcular saldo final
            final_balance = initial_balance + debit - credit
            if final_balance >= 0:
                group['final_debit'] += final_balance
            else:
                group['final_credit'] += abs(final_balance)
            
            # Agregar cuenta al detalle del grupo (opcional)
            group['accounts'].append({
                'code': account.code,
                'name': account.name,
                'initial_balance': initial_balance,
                'debit': debit,
                'credit': credit,
                'final_balance': final_balance
            })
        
        # ==============================================
        # 6. CALCULAR TOTALES Y PREPARAR RESULTADOS
        # ==============================================
        report_lines = []
        
        for key, values in grouped_results.items():
            # Calcular saldo inicial neto
            initial_net = values['initial_debit'] - values['initial_credit']
            
            # Calcular saldo final neto
            final_net = values['final_debit'] - values['final_credit']
            
            # Preparar línea para el reporte
            report_line = {
                'code': values['code'],
                'name': values['name'],
                'initial_debit': values['initial_debit'],
                'initial_credit': values['initial_credit'],
                'initial_balance': initial_net,
                'debit': values['debit'],
                'credit': values['credit'],
                'final_debit': values['final_debit'],
                'final_credit': values['final_credit'],
                'final_balance': final_net,
                # Opcional: incluir detalle de cuentas si lo necesitas
                'has_details': len(values['accounts']) > 1,
                'account_count': len(values['accounts']),
            }
            
            report_lines.append(report_line)
        
        # Ordenar por código de grupo
        report_lines.sort(key=lambda x: x['code'])
        
        return report_lines
    
    def _calculate_totals(self, report_lines):
        """
        Calcula los totales generales del reporte
        """
        totals = {
            'initial_debit': 0.0,
            'initial_credit': 0.0,
            'debit': 0.0,
            'credit': 0.0,
            'final_debit': 0.0,
            'final_credit': 0.0,
        }
        
        for line in report_lines:
            totals['initial_debit'] += line.get('initial_debit', 0.0)
            totals['initial_credit'] += line.get('initial_credit', 0.0)
            totals['debit'] += line.get('debit', 0.0)
            totals['credit'] += line.get('credit', 0.0)
            totals['final_debit'] += line.get('final_debit', 0.0)
            totals['final_credit'] += line.get('final_credit', 0.0)
        
        # Calcular saldos netos
        totals['initial_balance'] = totals['initial_debit'] - totals['initial_credit']
        totals['final_balance'] = totals['final_debit'] - totals['final_credit']
        
        return totals
    
    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Método principal llamado por el sistema de reportes de Odoo
        """
        if not data:
            data = {}
        
        # Extraer parámetros del wizard
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        target_move = data.get('target_move', 'posted')
        company_id = data.get('company_id')
        
        # Obtener líneas del reporte
        report_lines = self._get_account_data(date_from, date_to, target_move, company_id)
        
        # Calcular totales
        totals = self._calculate_totals(report_lines)
        
        # Obtener información de la compañía
        company = self.env['res.company'].browse(company_id)
        
        # Preparar contexto para el template
        return {
            'doc_ids': docids or [],
            'doc_model': 'custom.ledger.wizard',
            'data': data,
            'lines': report_lines,
            'totals': totals,
            'company': company,
            'date_from': date_from,
            'date_to': date_to,
            'target_move': target_move,
            'currency': company.currency_id,
            'today': fields.Date.context_today(self),
        }