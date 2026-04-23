from odoo import models, api


class ReportBalanceGeneral(models.AbstractModel):
    _name = 'report.custom_general_ledger.template_balance_general'
    _description = 'Balance General Agrupado'

    def _get_account_data(self, date_to, target_move, company_id):
        cr = self.env.cr

        move_state = ['posted']
        if target_move == 'all':
            move_state = ['posted', 'draft']

        query = """
            SELECT aml.account_id, SUM(aml.balance)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE aml.company_id = %s
            AND am.state = ANY(%s)
            AND aml.date <= %s
            GROUP BY aml.account_id
        """
        cr.execute(query, (company_id, move_state, date_to))
        data = {row[0]: row[1] for row in cr.fetchall()}

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
        target_move = params.get('target_move', 'posted')
        company_id = params.get('company_id') or self.env.company.id

        lines = self._get_account_data(date_to, target_move, company_id)

        totals = {
            'balance': sum(l.get('balance', 0.0) for l in lines if l['type'] in ['l3', 'total_l2'])
        }

        return {
            'doc_ids': docids,
            'data': params,
            'lines': lines,
            'totals': totals,
            'company': self.env['res.company'].browse(company_id),
        }