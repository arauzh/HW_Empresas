from odoo import models, api, fields
from datetime import datetime

class ReportBalanceGeneral(models.AbstractModel):
    _name = 'report.custom_general_ledger.template_balance_general'
    _description = 'Balance General Agrupado'

    def _get_account_data(self, date_to, target_move, company_id):
        cr = self.env.cr

        move_state = ['posted']
        if target_move == 'all':
            move_state = ['posted', 'draft']

        if isinstance(company_id, list):
            company_id = company_id[0]
        company = self.env['res.company'].browse(company_id)

        try:
            fiscal_year_start = company.compute_fiscalyear_dates(fields.Date.from_string(date_to))['date_from']
        except:
            fiscal_year_start = fields.Date.from_string(date_to).replace(month=1, day=1)

        # 1. Cuentas de Balance (Activo, Pasivo, Patrimonio)
        query = """
            SELECT aml.account_id, SUM(aml.balance)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.company_id = %s
            AND am.state = ANY(%s)
            AND aml.date <= %s
            AND aa.internal_group IN ('asset', 'liability', 'equity')
            GROUP BY aml.account_id
        """
        cr.execute(query, (company_id, move_state, date_to))
        data = {row[0]: row[1] for row in cr.fetchall()}

        # 2. PnL Histórico
        query_pnl_hist = """
            SELECT SUM(aml.balance)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.company_id = %s
            AND am.state = ANY(%s)
            AND aml.date < %s
            AND aa.internal_group IN ('income', 'expense')
        """
        cr.execute(query_pnl_hist, (company_id, move_state, fiscal_year_start))
        res_hist = cr.fetchone()
        pnl_hist = res_hist[0] if res_hist and res_hist[0] else 0.0

        # 3. PnL del Ejercicio
        query_pnl_curr = """
            SELECT SUM(aml.balance)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.company_id = %s
            AND am.state = ANY(%s)
            AND aml.date >= %s AND aml.date <= %s
            AND aa.internal_group IN ('income', 'expense')
        """
        cr.execute(query_pnl_curr, (company_id, move_state, fiscal_year_start, date_to))
        res_curr = cr.fetchone()
        pnl_curr = res_curr[0] if res_curr and res_curr[0] else 0.0

        unaffected_acc = self.env['account.account'].search([
            ('account_type', '=', 'equity_unaffected'),
            ('company_id', '=', company_id)
        ], limit=1)

        if unaffected_acc:
            data[unaffected_acc.id] = data.get(unaffected_acc.id, 0.0) + pnl_hist + pnl_curr

        accounts = self.env['account.account'].search([
            ('company_id', '=', company_id)
        ])

        groups = self.env['account.group'].search([
            ('company_id', '=', company_id)
        ])

        group_map = {
            g.code_prefix_start: g.name
            for g in groups if g.code_prefix_start
        }

        level1 = {}
        level2 = {}
        level3 = {}

        for acc in accounts:
            if acc.internal_group not in ('asset', 'liability', 'equity'):
                continue
                
            balance = data.get(acc.id, 0.0) or 0.0

            if abs(balance) < 0.01:
                continue

            code = acc.code or ''

            l1 = code[:1]
            l2 = code[:2]
            l3 = code[:3]

            if l1 not in level1:
                level1[l1] = {
                    'name': group_map.get(l1, f'Grupo {l1}'),
                    'balance': 0.0
                }
            level1[l1]['balance'] += balance

            if l2 not in level2:
                level2[l2] = {
                    'name': group_map.get(l2, f'Subgrupo {l2}'),
                    'balance': 0.0,
                    'parent': l1
                }
            level2[l2]['balance'] += balance

            group_name_l3 = group_map.get(l3)

            if l3 not in level3:
                level3[l3] = {
                    'code': l3,
                    'name': group_name_l3 or acc.name,
                    'balance': 0.0,
                    'parent': l2
                }

            level3[l3]['balance'] += balance

        if not unaffected_acc and (abs(pnl_hist) >= 0.01 or abs(pnl_curr) >= 0.01):
            code = '399'
            balance = pnl_hist + pnl_curr
            l1 = code[:1]
            l2 = code[:2]
            l3 = code[:3]
            
            if l1 not in level1:
                level1[l1] = {'name': group_map.get(l1, f'Grupo {l1}'), 'balance': 0.0}
            level1[l1]['balance'] += balance
            
            if l2 not in level2:
                level2[l2] = {'name': group_map.get(l2, f'Subgrupo {l2}'), 'balance': 0.0, 'parent': l1}
            level2[l2]['balance'] += balance
            
            if l3 not in level3:
                level3[l3] = {'code': l3, 'name': 'RESULTADOS ACUMULADOS', 'balance': 0.0, 'parent': l2}
            level3[l3]['balance'] += balance

        lines = []

        for l1_key in sorted(level1.keys()):
            l1 = level1[l1_key]

            lines.append({
                'type': 'l1',
                'name': l1['name']
            })

            for l2_key in sorted(level2.keys()):
                l2 = level2[l2_key]

                if l2['parent'] != l1_key:
                    continue

                lines.append({
                    'type': 'l2',
                    'name': l2['name']
                })

                for l3_key in sorted(level3.keys()):
                    l3 = level3[l3_key]

                    if l3['parent'] != l2_key:
                        continue

                    lines.append({
                        'type': 'l3',
                        'code': l3['code'],
                        'name': l3['name'],
                        'balance': l3['balance']
                    })

                lines.append({
                    'type': 'total_l2',
                    'name': f"TOTAL {l2['name']}",
                    'balance': l2['balance']
                })

        return lines

    @api.model
    def _get_report_values(self, docids, data=None):
        params = data.get('form') if data and data.get('form') else data
    
        date_to = params.get('date_to')
        date_obj = datetime.strptime(date_to, "%Y-%m-%d")
        target_move = params.get('target_move', 'posted')
        company_id = params.get('company_id') or self.env.company.id

        lines = self._get_account_data(date_to, target_move, company_id)

        meses = {
            1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
            5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
            9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
        }

        periodo = f"Mes de {meses[date_obj.month]} {date_obj.year}"

        summary = {}

        for line in lines:
            if line['type'] == 'l3':
                code = line.get('code', '')
                l1 = code[:1]

                if l1 not in summary:
                    summary[l1] = {
                        'name': None,
                        'balance': 0.0
                    }

                summary[l1]['balance'] += line.get('balance', 0.0)

        groups = self.env['account.group'].search([
            ('company_id', '=', company_id)
        ])

        group_map = {
            g.code_prefix_start: g.name
            for g in groups if g.code_prefix_start
        }

        for key in summary:
            summary[key]['name'] = group_map.get(key, f'Grupo {key}')

        totals = {
            'balance': sum(l.get('balance', 0.0) for l in lines if l['type'] in ['l3', 'total_l2'])
        }

        total_general = sum(v['balance'] for v in summary.values())

        folio = params.get('folio')
        folio_base = int(folio) if folio else 0

        return {
            'doc_ids': docids,
            'data': params,
            'lines': lines,
            'totals': totals,
            'summary': summary,
            'total_general': total_general,
            'company': self.env['res.company'].browse(company_id),
            'periodo': periodo,
            'folio_base': folio_base,
        }