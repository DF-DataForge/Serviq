/** @odoo-module **/
/*
 * Installation kanban and list with the bar of standard filters above
 * them: category, installer and distributor. The selections are combined
 * (AND) with each other and with the regular search bar, and shared with
 * the overview dashboard (the choice is remembered per browser).
 */
import { Domain } from "@web/core/domain";
import { registry } from "@web/core/registry";
import { SearchModel } from "@web/search/search_model";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { SystemFilterBar, loadSystemFilters, systemFiltersDomain } from "./system_filters";

export class InstallationSearchModel extends SearchModel {
    setup(services) {
        super.setup(services);
        this.sqFilters = loadSystemFilters();
    }

    setSqFilters(filters) {
        this.sqFilters = { ...filters };
        this._notify();
    }

    _getDomain(params = {}) {
        const domain = Domain.and([
            super._getDomain({ ...params, raw: true }),
            new Domain(systemFiltersDomain(this.sqFilters)),
        ]);
        return params.raw ? domain : domain.toList(this.domainEvalContext);
    }

    // Keep the filters when coming back through the breadcrumbs.
    exportState() {
        return { ...super.exportState(), sqFilters: { ...this.sqFilters } };
    }

    _importState(state) {
        super._importState(state);
        if (state.sqFilters) {
            this.sqFilters = { ...state.sqFilters };
        }
    }
}

/** What the kanban and list controllers share: the filter bar. */
function withSystemFilters(Controller, template) {
    return class extends Controller {
        static template = template;
        static components = { ...Controller.components, SystemFilterBar };

        get sqFilters() {
            return this.env.searchModel.sqFilters;
        }

        onSqFiltersChange(filters) {
            this.env.searchModel.setSqFilters(filters);
        }
    };
}

export const InstallationKanbanController = withSystemFilters(
    KanbanController, "serviq_installation.InstallationKanbanView"
);
export const InstallationListController = withSystemFilters(
    ListController, "serviq_installation.InstallationListView"
);

registry.category("views").add("serviq_installation_kanban", {
    ...kanbanView,
    Controller: InstallationKanbanController,
    SearchModel: InstallationSearchModel,
});

registry.category("views").add("serviq_installation_list", {
    ...listView,
    Controller: InstallationListController,
    SearchModel: InstallationSearchModel,
});
