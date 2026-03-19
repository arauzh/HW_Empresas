/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, xml } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

class ObservationDialog extends Component {
    static components = { Dialog };
    static props = {
        close: Function,
        title: { type: String, optional: true },
        value: { type: String, optional: true },
        onSave: Function,
    };

    setup() {
        this.notification = useService("notification");
        this.state = useState({
            text: this.props.value || "",
            saving: false,
        });
    }

    async save() {
        try {
            this.state.saving = true;
            await this.props.onSave(this.state.text);
            this.notification.add("Observación actualizada.", {
                type: "success",
            });
            this.props.close();
        } catch (error) {
            console.error("Error al guardar observación:", error);
            this.notification.add(
                error?.message || "No se pudo actualizar la observación.",
                { type: "danger" }
            );
        } finally {
            this.state.saving = false;
        }
    }
}

ObservationDialog.template = xml`
    <Dialog title="'Observaciones'">
        <div class="p-2">
            <textarea
                class="form-control"
                rows="10"
                t-model="state.text"
                placeholder="Escriba las observaciones aquí..."
            />
        </div>
        <t t-set-slot="footer">
            <button type="button" class="btn btn-secondary" t-on-click="props.close">
                Cancelar
            </button>
            <button
                type="button"
                class="btn btn-primary"
                t-att-disabled="state.saving"
                t-on-click="save"
            >
                Guardar
            </button>
        </t>
    </Dialog>
`;

export class ObservationDialogField extends Component {
    // static template = xml`
    //     <div class="o_field_observation_dialog_button">
    //         <button
    //             type="button"
    //             class="oe_stat_button"
    //             t-on-click="openDialog"
    //             t-att-title="hasValue ? 'Ver / editar observaciones' : 'Agregar observaciones'"
    //         >
    //             <div class="o_stat_info">
    //                 <i t-att-class="hasValue ? 'fa fa-comment' : 'fa fa-comment-o'"/>
    //                 <span class="o_stat_text ms-1">Observaciones</span>
    //             </div>
    //         </button>
    //     </div>
    // `;
    static template = xml`
        <span class="o_field_observation_dialog_button">
            <i
                t-att-class="hasValue ? 'fa fa-comment text-info' : 'fa fa-comment-o text-muted'"
                style="cursor:pointer; font-size:14px;"
                t-on-click="openDialog"
            />
        </span>
    `;

    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.dialog = useService("dialog");
        this.orm = useService("orm");

        this.state = useState({
            currentValue: this._getRecordValue(),
        });
    }

    _getRecordValue() {
        return (
            this.props.record?.data?.observation ??
            this.props.value ??
            ""
        );
    }

    get hasValue() {
        return !!(this.state.currentValue || "").trim();
    }

    async saveToDatabase(newText) {
        const record = this.props.record;

        if (!record?.resModel || !record?.resId) {
            throw new Error("El registro aún no ha sido guardado.");
        }

        await this.orm.write(record.resModel, [record.resId], {
            observation: newText,
        });

        // 1) actualiza el estado local del widget
        this.state.currentValue = newText;

        // 2) actualiza el dato del record en memoria, para que el form quede sincronizado
        if (record.data) {
            record.data.observation = newText;
        }
    }

    openDialog() {
        this.dialog.add(ObservationDialog, {
            title: "Observaciones",
            value: this.state.currentValue,
            onSave: async (newText) => {
                await this.saveToDatabase(newText);
            },
        });
    }
}

export const observationDialogButtonField = {
    component: ObservationDialogField,
    supportedTypes: ["text", "char", "html"],
};

registry.category("fields").add("observation_dialog_button", observationDialogButtonField);