/** @odoo-module **/
import { SectionAndNoteListRenderer } from "@account/components/section_and_note_fields_backend/section_and_note_fields_backend";
import { patch } from "@web/core/utils/patch";

patch(SectionAndNoteListRenderer.prototype, {
    _getFieldNames() {
        const cols = this.state?.columns || [];
        return new Set(cols.filter((c) => c.type === "field" && c.name).map((c) => c.name));
    },

    /**
     * Devuelve configuración según campos disponibles.
     * subtotalFields: lista de campos que se mostrarán en la sección
     * sumFields: lista de campos que se sumarán en líneas normales (mismo orden que subtotalFields)
     */
    _resolveSubtotalConfig() {
        const fields = this._getFieldNames();

        // approval.budget: planned + executed
        if (fields.has("planned_amount") && fields.has("executed_amount")) {
            return {
                subtotalFields: ["planned_subtotal", "executed_subtotal"],
                sumFields: ["planned_amount", "executed_amount"],
            };
        }

        // approval.budget: solo planned
        if (fields.has("planned_amount")) {
            return {
                subtotalFields: ["planned_subtotal"],
                sumFields: ["planned_amount"],
            };
        }

        // sale/purchase/account
        if (fields.has("price_subtotal")) {
            return {
                subtotalFields: ["price_subtotal"],
                sumFields: ["price_subtotal"],
            };
        }

        return null;
    },

    isSectionOrNote(record = null) {
        record = record || this.record;

        if (!record?.data) {
            return super.isSectionOrNote(record);
        }

        const cfg = this._resolveSubtotalConfig();
        if (!cfg) {
            return super.isSectionOrNote(record);
        }

        const allRows = this.list?.records;
        if (!allRows) {
            return super.isSectionOrNote(record);
        }

        // Calcular subtotales solo para secciones
        if (record.data.display_type === "line_section") {
            const myIndex = allRows.findIndex((r) => r === record);
            const totals = cfg.sumFields.map(() => 0.0);

            if (myIndex >= 0) {
                for (let i = myIndex + 1; i < allRows.length; i++) {
                    const row = allRows[i].data;

                    if (row.display_type === "line_section") break;

                    // sumar solo líneas normales
                    if (!row.display_type) {
                        for (let k = 0; k < cfg.sumFields.length; k++) {
                            const f = cfg.sumFields[k];
                            totals[k] += row[f] || 0.0;
                        }
                    }
                }
            }

            // escribir los subtotales en la fila sección (en los campos visibles)
            for (let k = 0; k < cfg.subtotalFields.length; k++) {
                record.data[cfg.subtotalFields[k]] = totals[k];
            }
        }

        return super.isSectionOrNote(record);
    },

    getCellClass(column, record) {
        const cfg = this._resolveSubtotalConfig();
        if (!cfg) {
            return super.getCellClass(column, record);
        }

        let classNames = super.getCellClass(column, record);

        const keepVisible =
            column.widget === "handle" ||
            column.name === this.titleField ||
            cfg.subtotalFields.includes(column.name);

        if (this.isSectionOrNote(record) && !keepVisible) {
            return `${classNames} o_hidden`;
        }

        // asegurar que los subtotales no queden ocultos
        if (cfg.subtotalFields.includes(column.name) && classNames.includes("o_hidden")) {
            classNames = classNames.replace("o_hidden", "").trim();
        }

        return classNames;
    },

    getColumns(record) {
        const cfg = this._resolveSubtotalConfig();
        if (!cfg) {
            return super.getColumns(record);
        }

        const columns = this.state?.columns || [];

        if (this.isSectionOrNote(record)) {
            if (record?.data?.display_type === "line_note") {
                return this.getSectionColumns(columns);
            }
            return this._getSubtotalSectionColumns(columns, cfg.subtotalFields);
        }

        return columns;
    },

    _getSubtotalSectionColumns(columns, subtotalFields) {
        const sectionCols = columns.filter(
            (col) =>
                col.widget === "handle" ||
                (col.type === "field" && subtotalFields.includes(col.name)) ||
                (col.type === "field" && col.name === this.titleField)
        );

        return sectionCols.map((col) => {
            if (col.name === this.titleField) {
                return { ...col, colspan: columns.length - sectionCols.length + 1 };
            }
            return { ...col };
        });
    },
});