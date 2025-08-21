# -*- coding: utf-8 -*-
from odoo import api, models, _
import logging

_logger = logging.getLogger(__name__)

class AccountReportInherit(models.Model):
    _inherit = 'account.report'

    def get_options(self, previous_options=None):
        options = super().get_options(previous_options=previous_options)

        context = self.env.context

        if context.get('custom_handler_model_name'):
            # El usuario hizo clic en el menú "Filtrado". Forzamos nuestro handler.
            options['custom_handler_model_name'] = context.get('custom_handler_model_name')
            options.pop('no_filter', None)  # Limpiamos la bandera de no-filtrar
        
        elif context.get('no_filter'):
            # El usuario hizo clic en el menú "Original". Forzamos la bandera de no-filtrar.
            options['no_filter'] = True
            # Limpiamos nuestro handler por si venía de las opciones anteriores.
            options.pop('custom_handler_model_name', None)
            
        elif previous_options:
            # No hay contexto de menú, así que estamos continuando una sesión (ej. cambiando fecha).
            # Persistimos el estado de las opciones anteriores.
            if previous_options.get('custom_handler_model_name'):
                options['custom_handler_model_name'] = previous_options.get('custom_handler_model_name')
            if previous_options.get('no_filter'):
                options['no_filter'] = previous_options.get('no_filter')

        return options

class TrialBalanceCustomHandlerFiltered(models.AbstractModel):
    _inherit = 'account.trial.balance.report.handler'

    def _get_grupos_permitidos(self):
        """Obtiene los prefijos de cuenta de 3 cifras de account.group"""
        account_groups = self.env['account.group'].search([])
        code_prefixes = account_groups.mapped('code_prefix_start')
        filtered_prefixes = [prefix for prefix in code_prefixes if prefix and len(prefix) == 3]
        return set(filtered_prefixes)

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        grupos_permitidos = self._get_grupos_permitidos()
        if options.get('no_filter') or options.get('custom_handler_model_name') != 'account.trial.balance.report.handler.filtered':
            return super()._dynamic_lines_generator(report, options, all_column_groups_expression_totals, warnings=warnings)
        
        original_lines = super()._dynamic_lines_generator(report, options, all_column_groups_expression_totals, warnings=warnings)
        lines_by_id = {}
        for idx, (index, line) in enumerate(original_lines):
            if isinstance(line, dict) and 'id' in line:
                lines_by_id[line['id']] = (index, line)

        filtered_lines = []
        padres_a_incluir = set()

        for idx, (index, line) in enumerate(original_lines):
            if not isinstance(line, dict):
                continue

            nombre_linea = line.get('name', '')
            codigo = nombre_linea.split(' ')[0].strip() if nombre_linea else ''

            if idx == len(original_lines) - 1 or line.get('id') == 'total':
                filtered_lines.append((index, line))
                continue

            if any(codigo.startswith(pref) for pref in grupos_permitidos):
                filtered_lines.append((index, line))

                padre_id = line.get('parent_id')
                while padre_id:
                    if padre_id in padres_a_incluir:
                        break
                    padres_a_incluir.add(padre_id)
                    padre_line = lines_by_id.get(padre_id)
                    if not padre_line:
                        break
                    padre_id = padre_line[1].get('parent_id')

        padres_filtrados = []
        for padre_id in padres_a_incluir:
            padre_line = lines_by_id.get(padre_id)
            if padre_line:
                nombre_padre = padre_line[1].get('name', '')
                codigo_padre = nombre_padre.split(' ')[0].strip() if nombre_padre else ''
                if any(codigo_padre.startswith(pref) for pref in grupos_permitidos):
                    padres_filtrados.append(padre_line)

        todas_líneas = {line[1].get('id'): line for line in filtered_lines}
        for padre in padres_filtrados:
            todas_líneas[padre[1].get('id')] = padre

        resultado_final = sorted(todas_líneas.values(), key=lambda x: x[0])
        return resultado_final

    def _custom_line_postprocessor(self, report, options, lines, warnings=None):
        grupos_permitidos = self._get_grupos_permitidos()
        processed = super()._custom_line_postprocessor(report, options, lines, warnings=warnings)

        if options.get('hierarchy') and options.get('custom_handler_model_name') == 'account.trial.balance.report.handler.filtered':
            filtered = []
            total_line = processed[-1] if processed else None

            for line in processed:
                if not isinstance(line, dict):
                    filtered.append(line)
                    continue

                nombre_linea = line.get('name', '')
                codigo = nombre_linea.split(' ')[0].strip() if nombre_linea else ''

                if line is total_line or line.get('id') == 'total':
                    filtered.append(line)
                    continue

                if any(codigo.startswith(pref) for pref in grupos_permitidos):
                    filtered.append(line)

            return filtered

        return processed