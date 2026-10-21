// Shared library component types for Vue template validation and editor completion.
export {};
declare module "vue" {
  export interface GlobalComponents {
    UiCollapsible: (typeof import("./index"))["UiCollapsible"];
    UiButton: (typeof import("./index"))["UiButton"];
    UiInput: (typeof import("./index"))["UiInput"];
    UiInputNumber: (typeof import("./index"))["UiInputNumber"];
    UiForm: (typeof import("./index"))["UiForm"];
    UiFormItem: (typeof import("./index"))["UiFormItem"];
    UiSelect: (typeof import("./index"))["UiSelect"];
    UiOption: (typeof import("./index"))["UiOption"];
    UiCheckbox: (typeof import("./index"))["UiCheckbox"];
    UiSwitch: (typeof import("./index"))["UiSwitch"];
    UiRadioGroup: (typeof import("./index"))["UiRadioGroup"];
    UiRadioButton: (typeof import("./index"))["UiRadioButton"];
    UiDialog: (typeof import("./index"))["UiDialog"];
    UiIcon: (typeof import("./index"))["UiIcon"];
    UiTag: (typeof import("./index"))["UiTag"];
    UiProgress: (typeof import("./index"))["UiProgress"];
    UiEmpty: (typeof import("./index"))["UiEmpty"];
    UiAlert: (typeof import("./index"))["UiAlert"];
    UiDivider: (typeof import("./index"))["UiDivider"];
    UiButtonGroup: (typeof import("./index"))["UiButtonGroup"];
    UiDropdown: (typeof import("./index"))["UiDropdown"];
    UiDropdownMenu: (typeof import("./index"))["UiDropdownMenu"];
    UiDropdownItem: (typeof import("./index"))["UiDropdownItem"];
    UiTable: (typeof import("./index"))["UiTable"];
    UiTableColumn: (typeof import("./index"))["UiTableColumn"];
    UiTabs: (typeof import("./index"))["UiTabs"];
    UiTabPane: (typeof import("./index"))["UiTabPane"];
    UiPagination: (typeof import("./index"))["UiPagination"];
    UiDatePicker: (typeof import("./index"))["UiDatePicker"];
    UiUpload: (typeof import("./index"))["UiUpload"];
    UiCard: (typeof import("./index"))["UiCard"];
    UiLink: (typeof import("./index"))["UiLink"];
    UiKbd: (typeof import("./index"))["UiKbd"];
    UiSimpleTable: (typeof import("./index"))["UiSimpleTable"];
    UiTableRow: (typeof import("./index"))["UiTableRow"];
    UiTableCell: (typeof import("./index"))["UiTableCell"];
  }
}
