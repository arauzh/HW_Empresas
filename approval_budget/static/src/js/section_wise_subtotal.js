/** @odoo-module **/
import { SectionAndNoteListRenderer } from "@account/components/section_and_note_fields_backend/section_and_note_fields_backend";
import { patch } from "@web/core/utils/patch";

patch(SectionAndNoteListRenderer.prototype, {
    setup() {
        super.setup();
        this.titleField = "name";
    },

    _getFieldNames() {
        const cols = this.state?.columns || [];
        return new Set(
            cols.filter((c) => c.type === "field" && c.name).map((c) => c.name)
        );
    },

    _resolveSubtotalConfig() {
        const fields = this._getFieldNames();

        if (
            fields.has("planned_subtotal") &&
            fields.has("executed_subtotal") &&
            fields.has("planned_amount") &&
            fields.has("executed_amount")
        ) {
            return {
                subtotalFields: ["planned_subtotal", "executed_subtotal"],
                sumFields: ["planned_amount", "executed_amount"],
            };
        }

        if (fields.has("planned_subtotal") && fields.has("planned_amount")) {
            return {
                subtotalFields: ["planned_subtotal"],
                sumFields: ["planned_amount"],
            };
        }

        if (fields.has("price_subtotal")) {
            return {
                subtotalFields: ["price_subtotal"],
                sumFields: ["price_subtotal"],
            };
        }

        return null;
    },

    _getSectionLayoutInfo(columns, cfg) {
        const handleIndex = columns.findIndex((col) => col.widget === "handle");
        const titleIndex = columns.findIndex(
            (col) => col.type === "field" && col.name === this.titleField
        );
        const firstSubtotalIndex = columns.findIndex(
            (col) => col.type === "field" && cfg.subtotalFields.includes(col.name)
        );

        // Primera columna visible antes del primer subtotal donde "inyectaremos" name
        const leadIndex = columns.findIndex(
            (col, idx) =>
                idx > handleIndex &&
                idx < firstSubtotalIndex &&
                col.type === "field"
        );

        return {
            handleIndex,
            titleIndex,
            firstSubtotalIndex,
            leadIndex: leadIndex >= 0 ? leadIndex : titleIndex,
        };
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

        if (record.data.display_type === "line_section") {
            const myIndex = allRows.findIndex((r) => r === record);
            const totals = cfg.sumFields.map(() => 0.0);

            if (myIndex >= 0) {
                for (let i = myIndex + 1; i < allRows.length; i++) {
                    const row = allRows[i].data;

                    if (row.display_type === "line_section") {
                        break;
                    }

                    if (!row.display_type) {
                        for (let k = 0; k < cfg.sumFields.length; k++) {
                            const fieldName = cfg.sumFields[k];
                            totals[k] += row[fieldName] || 0.0;
                        }
                    }
                }
            }

            for (let k = 0; k < cfg.subtotalFields.length; k++) {
                record.data[cfg.subtotalFields[k]] = totals[k];
            }
        }

        return super.isSectionOrNote(record);
    },

    getColumns(record) {
        const cfg = this._resolveSubtotalConfig();
        if (!cfg) {
            return super.getColumns(record);
        }

        const columns = this.state?.columns || [];

        if (record?.data?.display_type === "line_note") {
            return super.getColumns(record);
        }

        if (record?.data?.display_type === "line_section") {
            const info = this._getSectionLayoutInfo(columns, cfg);

            if (
                info.firstSubtotalIndex < 0 ||
                info.titleIndex < 0 ||
                info.leadIndex < 0 ||
                info.firstSubtotalIndex <= info.leadIndex
            ) {
                return columns;
            }

            const titleColumn = columns[info.titleIndex];

            return columns
                .map((col, index) => {
                    if (col.widget === "handle") {
                        return { ...col, colspan: 1 };
                    }

                    // Aquí movemos visualmente la columna `name`
                    // a la primera columna antes del subtotal
                    if (index === info.leadIndex) {
                        return {
                            ...titleColumn,
                            colspan: info.firstSubtotalIndex - info.leadIndex,
                        };
                    }

                    // ocultamos todas las columnas absorbidas por el colspan
                    if (index > info.leadIndex && index < info.firstSubtotalIndex) {
                        return {
                            ...col,
                            colspan: 0,
                        };
                    }

                    return {
                        ...col,
                        colspan: 1,
                    };
                })
                .filter((col) => col.colspan !== 0);
        }

        return columns;
    },

    getCellClass(column, record) {
        const cfg = this._resolveSubtotalConfig();
        if (!cfg) {
            return super.getCellClass(column, record);
        }

        let classNames = super.getCellClass(column, record);

        if (!(this.isSectionOrNote(record) && record?.data?.display_type === "line_section")) {
            return classNames;
        }

        // limpiar estados heredados
        classNames = classNames.replace(/\bo_hidden\b/g, "").trim();
        classNames = classNames.replace(/\bo_section_subtotal_placeholder\b/g, "").trim();

        const keepVisible =
            column.widget === "handle" ||
            column.name === this.titleField ||
            cfg.subtotalFields.includes(column.name);

        if (!keepVisible) {
            return `${classNames} o_section_subtotal_placeholder`.trim();
        }

        return classNames.trim();
    },
});