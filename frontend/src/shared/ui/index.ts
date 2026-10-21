import {
  defineComponent,
  h,
  ref,
  computed,
  provide,
  inject,
  useId,
  Fragment,
  isVNode,
  type App,
  type VNode,
  type PropType,
} from "vue";
import {
  CollapsibleRoot,
  CollapsibleTrigger,
  CollapsibleContent,
  Primitive,
  Label,
  DialogRoot,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogClose,
  PopoverRoot,
  PopoverTrigger,
  PopoverPortal,
  PopoverContent,
  ListboxRoot,
  ListboxContent,
  ListboxItem,
  ListboxItemIndicator,
  CheckboxRoot,
  CheckboxIndicator,
  SwitchRoot,
  SwitchThumb,
  RadioGroupRoot,
  RadioGroupItem,
  ProgressRoot,
  ProgressIndicator,
  DropdownMenuRoot,
  DropdownMenuTrigger,
  DropdownMenuPortal,
  DropdownMenuContent,
  DropdownMenuItem,
  Separator,
  TabsRoot,
  TabsList,
  TabsTrigger,
  TabsContent,
  NumberFieldRoot,
  NumberFieldInput,
} from "reka-ui";
import {
  ArrowLeft,
  ArrowRight,
  ChevronDown,
  Check,
  X,
  LoaderCircle,
  Plus,
  Trash2,
  Undo2,
  Redo2,
  Settings,
  CircleHelp,
  Download,
  Users,
  Folder,
  Image,
  ChartPie,
  Crosshair,
  Clock,
  ScanLine,
  House,
  Server,
  BookOpen,
  Search,
  LayoutGrid,
  List,
  PanelLeft,
  LogOut,
  Save,
  Eye,
  EyeOff,
  Lock,
  User,
  Maximize,
  ZoomIn,
  ZoomOut,
  MousePointer2,
  Hand,
  Square,
  Pentagon,
  Upload,
  Play,
  Layers,
  Activity,
} from "@lucide/vue";

const icons: Record<string, any> = {
  ArrowLeft,
  ArrowRight,
  ArrowDown: ChevronDown,
  Plus,
  Delete: Trash2,
  RefreshLeft: Undo2,
  RefreshRight: Redo2,
  Setting: Settings,
  QuestionFilled: CircleHelp,
  Download,
  User,
  Users,
  Folder,
  Picture: Image,
  Image,
  PieChart: ChartPie,
  DataAnalysis: Activity,
  Aim: Crosshair,
  Clock,
  Select: Check,
  Back: ArrowLeft,
  Loading: LoaderCircle,
  ScanLine,
  House,
  Server,
  BookOpen,
  Search,
  LayoutGrid,
  List,
  PanelLeft,
  LogOut,
  Save,
  Eye,
  EyeOff,
  Lock,
  Maximize,
  ZoomIn,
  ZoomOut,
  MousePointer2,
  Hand,
  Square,
  Pentagon,
  Upload,
  Play,
  Layers,
  Activity,
  Check,
  X,
};
export const UiIcon = defineComponent({
  props: { name: String, size: [String, Number] },
  setup(p, { slots, attrs }) {
    return () =>
      p.name
        ? h(icons[p.name] || CircleHelp, {
            size: p.size || 16,
            "aria-hidden": true,
            ...attrs,
          })
        : h(
            "span",
            { ...attrs, class: ["ui-icon", attrs.class] },
            slots.default?.(),
          );
  },
});
const fieldKey = Symbol("field"),
  disabledKey = Symbol("disabled");
export const UiButton = defineComponent({
  inheritAttrs: false,
  props: {
    type: String,
    nativeType: String,
    variant: String,
    size: String,
    loading: Boolean,
    disabled: Boolean,
    icon: [String, Object, Function],
    circle: Boolean,
    link: Boolean,
    text: Boolean,
    plain: Boolean,
  },
  setup(p, { attrs, slots }) {
    const formDisabled = inject<any>(disabledKey, ref(false));
    return () =>
      h(
        Primitive,
        {
          ...attrs,
          as: "button",
          type:
            p.nativeType ||
            (["button", "submit", "reset"].includes(p.type || "")
              ? p.type
              : "button"),
          disabled: p.disabled || p.loading || formDisabled.value,
          "aria-busy": p.loading || undefined,
          class: [
            "ui-button",
            `ui-button--${p.variant || (p.link || p.text ? "ghost" : p.plain ? "outline" : ["primary", "success", "danger", "warning"].includes(p.type || "") ? p.type : "default")}`,
            p.size && `ui-button--${p.size}`,
            { "ui-button--icon": p.circle },
            attrs.class,
          ],
        },
        () => [
          p.loading
            ? h(LoaderCircle, { class: "spin", size: 15 })
            : p.icon
              ? h(
                  typeof p.icon === "string"
                    ? icons[p.icon] || CircleHelp
                    : p.icon,
                  { size: 16 },
                )
              : null,
          slots.default?.(),
        ],
      );
  },
});
export const UiInput = defineComponent({
  inheritAttrs: false,
  props: {
    modelValue: [String, Number],
    type: { type: String, default: "text" },
    rows: [String, Number],
    showPassword: Boolean,
    disabled: Boolean,
    prefixIcon: String,
    size: String,
    clearable: Boolean,
  },
  emits: ["update:modelValue", "change", "input"],
  setup(p, { attrs, emit, expose }) {
    const input = ref<any>(),
      reveal = ref(false),
      field = inject<any>(fieldKey, null),
      disabled = inject<any>(disabledKey, ref(false));
    expose({
      focus: () => input.value?.$el?.focus(),
      blur: () => input.value?.$el?.blur(),
    });
    return () =>
      h("div", { class: ["ui-input-wrap", attrs.class], style: attrs.style }, [
        p.prefixIcon &&
          h(UiIcon, { name: p.prefixIcon, class: "input-prefix" }),
        h(Primitive, {
          ...attrs,
          class: ["ui-input", p.prefixIcon && "has-prefix"],
          style: undefined,
          ref: input,
          as: p.type === "textarea" ? "textarea" : "input",
          type:
            p.type === "textarea" ? undefined : reveal.value ? "text" : p.type,
          rows: p.rows,
          id: attrs.id || field?.id,
          "aria-label":
            attrs["aria-label"] || field?.label || attrs.placeholder,
          disabled: p.disabled || disabled.value,
          value: p.modelValue ?? "",
          onInput: (e: Event) => {
            const v = (e.target as HTMLInputElement).value;
            emit("update:modelValue", v);
            emit("input", v);
          },
          onChange: (e: Event) =>
            emit("change", (e.target as HTMLInputElement).value),
        }),
        p.showPassword &&
          h(
            UiButton,
            {
              class: "input-action",
              circle: true,
              variant: "ghost",
              "aria-label": reveal.value ? "隐藏密码" : "显示密码",
              onClick: () => (reveal.value = !reveal.value),
            },
            () => h(reveal.value ? EyeOff : Eye, { size: 16 }),
          ),
      ]);
  },
});
export const UiInputNumber = defineComponent({
  props: {
    modelValue: Number,
    min: Number,
    max: Number,
    step: Number,
    precision: Number,
    disabled: Boolean,
  },
  emits: ["update:modelValue", "change"],
  setup(p, { emit, attrs }) {
    const field = inject<any>(fieldKey, null),
      disabled = inject<any>(disabledKey, ref(false));
    return () =>
      h(
        NumberFieldRoot,
        {
          ...attrs,
          class: ["ui-number", attrs.class],
          modelValue: p.modelValue,
          min: p.min,
          max: p.max,
          step: p.step,
          disabled: p.disabled || disabled.value,
          formatOptions: {
            useGrouping: false,
            maximumFractionDigits: p.precision ?? 10,
          },
          "onUpdate:modelValue": (v: number | undefined) => {
            emit("update:modelValue", v);
            emit("change", v);
          },
        },
        () =>
          h(NumberFieldInput, {
            class: "ui-input",
            id: attrs.id || field?.id,
            "aria-label": attrs["aria-label"] || field?.label,
          }),
      );
  },
});
export const UiForm = defineComponent({
  props: {
    model: Object,
    disabled: Boolean,
    labelWidth: String,
    labelPosition: String,
  },
  setup(p, { slots, attrs }) {
    provide(
      disabledKey,
      computed(() => p.disabled),
    );
    return () =>
      h(
        Primitive,
        { ...attrs, as: "form", class: ["ui-form", attrs.class] },
        slots.default,
      );
  },
});
export const UiFormItem = defineComponent({
  props: { label: String, required: Boolean },
  setup(p, { slots, attrs }) {
    const id = `field-${useId()}`;
    provide(fieldKey, {
      id,
      get label() {
        return p.label;
      },
    });
    return () =>
      h("div", { ...attrs, class: ["ui-field", attrs.class] }, [
        (p.label || slots.label) &&
          h(Label, { for: id, class: "ui-label" }, () => [
            slots.label ? slots.label() : p.label,
            p.required && h("span", { class: "required" }, " *"),
          ]),
        slots.default?.(),
      ]);
  },
});
function flatten(nodes: any[]): VNode[] {
  return nodes.flatMap((n) =>
    !isVNode(n)
      ? []
      : n.type === Fragment
        ? flatten((n.children as any[]) || [])
        : [n],
  );
}
const selectKey = Symbol("select");
export const UiSelect = defineComponent({
  inheritAttrs: false,
  props: {
    modelValue: { type: null as unknown as PropType<any>, default: null },
    multiple: Boolean,
    placeholder: String,
    clearable: Boolean,
    disabled: Boolean,
    size: String,
    collapseTags: Boolean,
    collapseTagsTooltip: Boolean,
  },
  emits: ["update:modelValue", "change"],
  setup(p, { attrs, slots, emit }) {
    const open = ref(false),
      field = inject<any>(fieldKey, null),
      disabled = inject<any>(disabledKey, ref(false));
    provide(selectKey, {
      close: () => {
        if (!p.multiple) open.value = false;
      },
    });
    return () => {
      const options = flatten(slots.default?.() || []);
      const chosen = options.filter((n) =>
        p.multiple
          ? Array.isArray(p.modelValue) &&
            (p.modelValue as any[]).includes(n.props?.value)
          : n.props?.value === p.modelValue,
      );
      const label = chosen
        .map((n) => n.props?.label ?? n.props?.value)
        .join("、");
      const popup = h(
        PopoverRoot,
        { open: open.value, "onUpdate:open": (v: boolean) => (open.value = v) },
        () => [
          h(PopoverTrigger, { asChild: true }, () =>
            h(
              UiButton,
              {
                ...attrs,
                id: attrs.id || field?.id,
                disabled: p.disabled || disabled.value,
                class: "ui-select-trigger",
                style: undefined,
                "aria-label":
                  attrs["aria-label"] || field?.label || p.placeholder || label,
              },
              () => [
                h(
                  "span",
                  { class: !chosen.length ? "muted" : "" },
                  label || p.placeholder || "请选择",
                ),
                h(ChevronDown, { size: 14 }),
              ],
            ),
          ),
          h(PopoverPortal, {}, () =>
            h(
              PopoverContent,
              {
                class: "ui-popover ui-select-content",
                align: "start",
                sideOffset: 5,
                collisionPadding: 12,
              },
              () =>
                h(
                  ListboxRoot,
                  {
                    modelValue: p.modelValue,
                    multiple: p.multiple,
                    "aria-label":
                      attrs["aria-label"] ||
                      field?.label ||
                      p.placeholder ||
                      "选项",
                    "onUpdate:modelValue": (v: any) => {
                      emit("update:modelValue", v);
                      emit("change", v);
                      if (!p.multiple) open.value = false;
                    },
                  },
                  () =>
                    h(ListboxContent, {}, () => [
                      p.clearable &&
                        h(
                          ListboxItem,
                          { value: null, class: "ui-option" },
                          () => p.placeholder || "全部",
                        ),
                      ...options,
                    ]),
                ),
            ),
          ),
        ],
      );
      return h(
        "div",
        { class: ["ui-select", attrs.class], style: attrs.style },
        [popup],
      );
    };
  },
});
export const UiOption = defineComponent({
  props: {
    value: { type: null as unknown as PropType<any>, default: null },
    label: [String, Number],
    disabled: Boolean,
  },
  setup(p, { slots }) {
    return () =>
      h(
        ListboxItem,
        { value: p.value, disabled: p.disabled, class: "ui-option" },
        () => [
          h("span", {}, slots.default?.() || String(p.label ?? p.value)),
          h(ListboxItemIndicator, {}, () => h(Check, { size: 14 })),
        ],
      );
  },
});
export const UiCheckbox = defineComponent({
  props: { modelValue: Boolean, disabled: Boolean },
  emits: ["update:modelValue", "change"],
  setup(p, { attrs, slots, emit }) {
    const id = useId(),
      disabled = inject<any>(disabledKey, ref(false));
    return () =>
      h("div", { ...attrs, class: ["ui-check-label", attrs.class] }, [
        h(
          CheckboxRoot,
          {
            id,
            class: "ui-checkbox",
            modelValue: p.modelValue,
            disabled: p.disabled || disabled.value,
            "onUpdate:modelValue": (v: any) => {
              emit("update:modelValue", v === true);
              emit("change", v === true);
            },
          },
          () => h(CheckboxIndicator, {}, () => h(Check, { size: 12 })),
        ),
        h(Label, { for: id }, slots.default),
      ]);
  },
});
export const UiSwitch = defineComponent({
  props: { modelValue: Boolean, activeText: String, disabled: Boolean },
  emits: ["update:modelValue", "change"],
  setup(p, { attrs, emit }) {
    const field = inject<any>(fieldKey, null),
      disabled = inject<any>(disabledKey, ref(false));
    return () =>
      h("div", { class: "ui-switch-label" }, [
        h(
          SwitchRoot,
          {
            ...attrs,
            id: field?.id,
            "aria-label":
              attrs["aria-label"] || p.activeText || field?.label || "切换",
            class: "ui-switch",
            modelValue: p.modelValue,
            disabled: p.disabled || disabled.value,
            "onUpdate:modelValue": (v: any) => {
              emit("update:modelValue", v === true);
              emit("change", v === true);
            },
          },
          () => h(SwitchThumb, { class: "ui-switch-thumb" }),
        ),
        p.activeText && h("span", {}, p.activeText),
      ]);
  },
});
export const UiRadioGroup = defineComponent({
  props: { modelValue: [String, Number], disabled: Boolean, size: String },
  emits: ["update:modelValue", "change"],
  setup(p, { emit, attrs, slots }) {
    return () =>
      h(
        RadioGroupRoot,
        {
          ...attrs,
          class: ["ui-segmented", attrs.class],
          modelValue: p.modelValue,
          disabled: p.disabled,
          "onUpdate:modelValue": (v: any) => {
            emit("update:modelValue", v);
            emit("change", v);
          },
        },
        slots.default,
      );
  },
});
export const UiRadioButton = defineComponent({
  props: { value: [String, Number], disabled: Boolean },
  setup(p, { slots }) {
    return () =>
      h(
        RadioGroupItem,
        { value: p.value, disabled: p.disabled, class: "ui-segment" },
        slots.default,
      );
  },
});
export const UiDialog = defineComponent({
  inheritAttrs: false,
  props: {
    modelValue: Boolean,
    title: String,
    description: String,
    width: String,
    showClose: { type: Boolean, default: true },
    closeOnClickModal: { type: Boolean, default: true },
    closeOnPressEscape: { type: Boolean, default: true },
    top: String,
  },
  emits: ["update:modelValue", "close", "closed"],
  setup(p, { attrs, slots, emit }) {
    const update = (v: boolean) => {
      emit("update:modelValue", v);
      if (!v) {
        emit("close");
        emit("closed");
      }
    };
    return () =>
      h(DialogRoot, { open: p.modelValue, "onUpdate:open": update }, () =>
        h(DialogPortal, {}, () => [
          h(DialogOverlay, { class: "ui-dialog-overlay" }),
          h(
            DialogContent,
            {
              ...attrs,
              class: ["ui-dialog", attrs.class],
              style: [{ width: p.width || "560px" }, attrs.style],
              onPointerDownOutside: (e: Event) => {
                if (!p.closeOnClickModal) e.preventDefault();
              },
              onEscapeKeyDown: (e: Event) => {
                if (!p.closeOnPressEscape) e.preventDefault();
              },
            },
            () => [
              h("header", { class: "ui-dialog-header" }, [
                h(DialogTitle, { class: "ui-dialog-title" }, () => p.title),
                h(
                  DialogDescription,
                  { class: p.description ? "muted" : "sr-only" },
                  () => p.description || p.title,
                ),
                p.showClose &&
                  h(DialogClose, { asChild: true }, () =>
                    h(
                      UiButton,
                      {
                        circle: true,
                        variant: "ghost",
                        "aria-label": "关闭",
                        class: "dialog-close",
                      },
                      () => h(X, { size: 17 }),
                    ),
                  ),
              ]),
              h("div", { class: "ui-dialog-body" }, slots.default?.()),
              slots.footer &&
                h("footer", { class: "ui-dialog-footer" }, slots.footer()),
            ],
          ),
        ]),
      );
  },
});
export const UiTag = defineComponent({
  props: { type: String, size: String },
  setup(p, { attrs, slots }) {
    return () =>
      h(
        Primitive,
        {
          ...attrs,
          as: "span",
          class: ["ui-badge", `ui-badge--${p.type || "info"}`, attrs.class],
        },
        slots.default,
      );
  },
});
export const UiProgress = defineComponent({
  props: {
    percentage: Number,
    strokeWidth: Number,
    status: String,
    type: String,
    width: Number,
    textInside: Boolean,
    showText: { type: Boolean, default: true },
  },
  setup(p, { attrs }) {
    const value = () => Math.max(0, Math.min(100, Number(p.percentage) || 0));
    return () =>
      h(
        "div",
        {
          ...attrs,
          class: [
            "ui-progress",
            p.type === "circle" && "ui-progress-circle",
            attrs.class,
          ],
        },
        [
          h(
            ProgressRoot,
            {
              modelValue: value(),
              max: 100,
              class: "ui-progress-track",
              style: { height: `${p.strokeWidth || 5}px` },
              "aria-label": "完成进度",
            },
            () =>
              h(ProgressIndicator, {
                class: "ui-progress-indicator",
                style: { transform: `translateX(-${100 - value()}%)` },
              }),
          ),
          p.showText && h("span", {}, `${Math.round(value())}%`),
        ],
      );
  },
});
export const UiEmpty = defineComponent({
  props: { description: String, imageSize: [Number, String] },
  setup(p, { slots }) {
    return () =>
      h(Primitive, { class: "ui-empty" }, () => [
        h(Folder, { size: 32, strokeWidth: 1.3 }),
        h("p", {}, p.description || "暂无数据"),
        slots.default?.(),
      ]);
  },
});
export const UiAlert = defineComponent({
  props: { title: String, type: String, closable: Boolean, showIcon: Boolean },
  setup(p, { slots, attrs }) {
    return () =>
      h(
        Primitive,
        {
          ...attrs,
          role: p.type === "error" ? "alert" : "status",
          class: ["ui-alert", `ui-alert--${p.type || "info"}`, attrs.class],
        },
        () => [h("strong", {}, p.title), slots.default?.()],
      );
  },
});
export const UiDivider = defineComponent({
  setup(_, { slots }) {
    return () => h(Separator, { class: "ui-divider" }, slots.default);
  },
});
export const UiButtonGroup = defineComponent({
  setup(_, { slots }) {
    return () =>
      h(Primitive, { role: "group", class: "ui-button-group" }, slots.default);
  },
});
export const UiDropdown = defineComponent({
  emits: ["command"],
  setup(_, { slots, emit }) {
    provide("dropdown-command", (v: any) => emit("command", v));
    return () =>
      h(DropdownMenuRoot, {}, () => [
        h(DropdownMenuTrigger, { asChild: true }, slots.default),
        h(DropdownMenuPortal, {}, () =>
          h(
            DropdownMenuContent,
            { class: "ui-popover", sideOffset: 5, align: "end" },
            slots.dropdown,
          ),
        ),
      ]);
  },
});
export const UiDropdownMenu = defineComponent({
  setup(_, { slots }) {
    return () => h(Fragment, {}, slots.default?.());
  },
});
export const UiDropdownItem = defineComponent({
  props: { command: String, disabled: Boolean, divided: Boolean },
  setup(p, { slots, attrs }) {
    const command = inject<any>("dropdown-command");
    return () =>
      h(
        DropdownMenuItem,
        {
          ...attrs,
          disabled: p.disabled,
          class: "ui-option",
          onSelect: () => command(p.command),
        },
        slots.default,
      );
  },
});
export const UiTableColumn = defineComponent({
  props: {
    prop: String,
    label: String,
    width: [String, Number],
    minWidth: [String, Number],
    type: String,
    fixed: String,
    showOverflowTooltip: Boolean,
  },
  setup() {
    return () => null;
  },
});
export const UiTable = defineComponent({
  props: {
    data: { type: Array, default: () => [] },
    maxHeight: [String, Number],
    stripe: Boolean,
    size: String,
  },
  emits: ["row-click"],
  setup(p, { slots, attrs, emit }) {
    return () => {
      const columns = flatten(slots.default?.() || []).filter(
        (n) => n.type === UiTableColumn,
      );
      return h(
        "div",
        {
          ...attrs,
          class: ["ui-table-wrap", attrs.class],
          style: [
            attrs.style,
            { maxHeight: p.maxHeight ? `${p.maxHeight}px` : undefined },
          ],
        },
        h("table", { class: "ui-table" }, [
          h(
            "thead",
            {},
            h(
              "tr",
              {},
              columns.map((c) =>
                h(
                  "th",
                  {
                    style: {
                      minWidth: `${c.props?.minWidth || c.props?.width || 100}px`,
                      width: c.props?.width ? `${c.props.width}px` : undefined,
                    },
                  },
                  c.props?.label,
                ),
              ),
            ),
          ),
          h(
            "tbody",
            {},
            p.data.length
              ? p.data.map((row: any, index: number) =>
                  h(
                    "tr",
                    {
                      key: row.id || index,
                      onClick: () => emit("row-click", row),
                    },
                    columns.map((c) =>
                      h(
                        "td",
                        {},
                        typeof (c.children as any)?.default === "function"
                          ? (c.children as any).default({ row, $index: index })
                          : c.props?.type === "index"
                            ? index + 1
                            : (row[c.props?.prop] ?? "—"),
                      ),
                    ),
                  ),
                )
              : h(
                  "tr",
                  {},
                  h(
                    "td",
                    { colspan: columns.length },
                    h(UiEmpty, { description: "暂无数据" }),
                  ),
                ),
          ),
        ]),
      );
    };
  },
});
export const UiTabs = defineComponent({
  props: { modelValue: String },
  emits: ["update:modelValue"],
  setup(p, { slots, emit }) {
    return () => {
      const tabs = flatten(slots.default?.() || []);
      return h(
        TabsRoot,
        {
          modelValue: p.modelValue,
          defaultValue: String(tabs[0]?.props?.name || 0),
          "onUpdate:modelValue": (v: any) => emit("update:modelValue", v),
        },
        () => [
          h(TabsList, { class: "ui-tabs-list" }, () =>
            tabs.map((n, i) =>
              h(
                TabsTrigger,
                { value: String(n.props?.name || i), class: "ui-tab-trigger" },
                () => n.props?.label,
              ),
            ),
          ),
          ...tabs.map((n, i) =>
            h(
              TabsContent,
              { value: String(n.props?.name || i), class: "ui-tab-content" },
              (n.children as any)?.default,
            ),
          ),
        ],
      );
    };
  },
});
export const UiTabPane = defineComponent({
  props: { label: String, name: String },
  setup() {
    return () => null;
  },
});
export const UiPagination = defineComponent({
  props: {
    currentPage: { type: Number, default: 1 },
    total: { type: Number, default: 0 },
    pageSize: { type: Number, default: 20 },
    layout: String,
  },
  emits: ["update:currentPage", "current-change"],
  setup(p, { emit }) {
    const go = (n: number) => {
      emit("update:currentPage", n);
      emit("current-change", n);
    };
    return () => {
      const last = Math.max(1, Math.ceil(p.total / p.pageSize));
      return h(
        Primitive,
        { as: "nav", "aria-label": "分页", class: "ui-pagination" },
        () => [
          h("span", { class: "muted" }, `共 ${p.total} 项`),
          h(
            UiButton,
            {
              disabled: p.currentPage <= 1,
              "aria-label": "上一页",
              onClick: () => go(p.currentPage - 1),
            },
            () => h(ArrowLeft, { size: 14 }),
          ),
          h("span", {}, `${p.currentPage} / ${last}`),
          h(
            UiButton,
            {
              disabled: p.currentPage >= last,
              "aria-label": "下一页",
              onClick: () => go(p.currentPage + 1),
            },
            () => h(ArrowRight, { size: 14 }),
          ),
        ],
      );
    };
  },
});
export const UiDatePicker = defineComponent({
  props: {
    modelValue: Array,
    type: String,
    startPlaceholder: String,
    endPlaceholder: String,
    valueFormat: String,
  },
  emits: ["update:modelValue", "change"],
  setup(p, { emit }) {
    const change = (i: number, v: string) => {
      const next = [...(p.modelValue || ["", ""])];
      next[i] = v;
      emit("update:modelValue", next);
      if (next.every(Boolean)) emit("change", next);
    };
    return () =>
      h("div", { class: "ui-date-range" }, [
        h(UiInput, {
          type: "date",
          modelValue: String(p.modelValue?.[0] || ""),
          "aria-label": p.startPlaceholder || "开始日期",
          "onUpdate:modelValue": (v: string) => change(0, v),
        }),
        h("span", {}, "—"),
        h(UiInput, {
          type: "date",
          modelValue: String(p.modelValue?.[1] || ""),
          "aria-label": p.endPlaceholder || "结束日期",
          "onUpdate:modelValue": (v: string) => change(1, v),
        }),
      ]);
  },
});
export const UiUpload = defineComponent({
  props: {
    action: String,
    headers: Object,
    showFileList: { type: Boolean, default: true },
    autoUpload: { type: Boolean, default: true },
    accept: String,
    multiple: Boolean,
    onSuccess: Function,
    onError: Function,
    onChange: Function,
    onRemove: Function,
    directory: Boolean,
  },
  setup(p, { slots }) {
    const input = ref<HTMLInputElement>(),
      files = ref<any[]>([]);
    const choose = async (e: Event) => {
      const selected = Array.from(
        (e.target as HTMLInputElement).files || [],
      ).map((raw) => ({
        raw,
        name: raw.name,
        uid: `${Date.now()}-${raw.name}`,
      }));
      if (p.directory || !p.multiple) files.value = [];
      for (const file of selected) {
        files.value.push(file);
        p.onChange?.(file, files.value);
        if (p.autoUpload && p.action) {
          const body = new FormData();
          body.append("file", file.raw);
          try {
            const res = await fetch(p.action, {
              method: "POST",
              headers: p.headers as HeadersInit,
              body,
            });
            if (!res.ok) throw new Error("上传失败");
            p.onSuccess?.(await res.json(), file);
          } catch (e) {
            p.onError?.(e);
          }
        }
      }
      if (input.value) input.value.value = "";
    };
    return () =>
      h("div", { class: "ui-upload" }, [
        h("input", {
          ref: input,
          type: "file",
          class: "sr-only",
          tabindex: -1,
          accept: p.accept,
          multiple: p.multiple || p.directory,
          webkitdirectory: p.directory || undefined,
          onChange: choose,
          "aria-label": p.directory ? "选择目录" : "选择文件",
        }),
        h("div", { onClick: () => input.value?.click() }, slots.default?.()),
        slots.tip?.(),
        p.showFileList &&
          files.value.map((file) =>
            h("div", { class: "ui-file" }, [
              file.name,
              h(
                UiButton,
                {
                  size: "small",
                  variant: "ghost",
                  "aria-label": `移除 ${file.name}`,
                  onClick: () => {
                    files.value = files.value.filter((f) => f.uid !== file.uid);
                    p.onRemove?.(file, files.value);
                  },
                },
                () => "移除",
              ),
            ]),
          ),
      ]);
  },
});
// Structural primitives belong to the shared component system too.
export const UiCard = defineComponent({
  props: { as: { type: String, default: "section" } },
  setup(p, { attrs, slots }) {
    return () =>
      h(
        Primitive,
        { ...attrs, as: p.as, class: ["ui-card", attrs.class] },
        slots.default,
      );
  },
});
export const UiLink = defineComponent({
  props: { href: String },
  setup(p, { attrs, slots }) {
    return () =>
      h(
        Primitive,
        { ...attrs, as: "a", href: p.href, class: ["ui-link", attrs.class] },
        slots.default,
      );
  },
});
export const UiKbd = defineComponent({
  setup(_, { slots, attrs }) {
    return () =>
      h(Primitive, { ...attrs, as: "kbd", class: "ui-kbd" }, slots.default);
  },
});
export const UiSimpleTable = defineComponent({
  setup(_, { slots, attrs }) {
    return () =>
      h(
        Primitive,
        { ...attrs, as: "table", class: ["ui-table", attrs.class] },
        slots.default,
      );
  },
});
export const UiTableRow = defineComponent({
  setup(_, { slots, attrs }) {
    return () => h(Primitive, { ...attrs, as: "tr" }, slots.default);
  },
});
export const UiTableCell = defineComponent({
  setup(_, { slots, attrs }) {
    return () => h(Primitive, { ...attrs, as: "td" }, slots.default);
  },
});
export const UiCollapsible = defineComponent({
  props: { title: String, defaultOpen: Boolean },
  setup(p, { slots, attrs }) {
    return () =>
      h(
        CollapsibleRoot,
        {
          ...attrs,
          defaultOpen: p.defaultOpen,
          class: ["ui-collapsible", attrs.class],
        },
        () => [
          h("div", { class: "ui-collapsible-header" }, [
            h(CollapsibleTrigger, { class: "ui-collapsible-trigger" }, () => [
              h(ChevronDown, { size: 14 }),
              p.title,
            ]),
            slots.actions?.(),
          ]),
          h(
            CollapsibleContent,
            { class: "ui-collapsible-content" },
            slots.default,
          ),
        ],
      );
  },
});
export const uiComponents = {
  UiCollapsible,
  UiButton,
  UiInput,
  UiInputNumber,
  UiForm,
  UiFormItem,
  UiSelect,
  UiOption,
  UiCheckbox,
  UiSwitch,
  UiRadioGroup,
  UiRadioButton,
  UiDialog,
  UiIcon,
  UiTag,
  UiProgress,
  UiEmpty,
  UiAlert,
  UiDivider,
  UiButtonGroup,
  UiDropdown,
  UiDropdownMenu,
  UiDropdownItem,
  UiTable,
  UiTableColumn,
  UiTabs,
  UiTabPane,
  UiPagination,
  UiDatePicker,
  UiUpload,
  UiCard,
  UiLink,
  UiKbd,
  UiSimpleTable,
  UiTableRow,
  UiTableCell,
};
export function installUI(app: App) {
  for (const [name, component] of Object.entries(uiComponents))
    app.component(name, component);
  for (const [name, component] of Object.entries(icons))
    app.component(name, component);
  app.directive("loading", { mounted: setLoading, updated: setLoading });
}
function setLoading(el: HTMLElement, binding: any) {
  el.setAttribute("aria-busy", String(!!binding.value));
  el.toggleAttribute("data-loading", !!binding.value);
}
