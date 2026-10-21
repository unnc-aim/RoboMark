# RoboMark UI component library

The production UI uses the Reka UI accessible primitives with project-owned components, following the source-owned component pattern used by shadcn-vue. The design baseline is commit `4656e22`; tokens live in `../styles/tokens.css`. Icons use Lucide (`@lucide/vue`). Notifications use Vue Sonner and confirmations use Reka AlertDialog.

`index.ts` contains the shared controls, data table, pagination, upload/directory picker building blocks and structural components. `components.d.ts` exposes their types to Vue templates. Views compose these components; they must not introduce native form controls, clickable native elements, disclosure widgets, links or tables. Semantic HTML for document structure, images, SVG geometry and the annotation Canvas remains appropriate.

Run `pnpm check:ui` to enforce this boundary, or `pnpm check` for all frontend checks. Native HTML is an internal implementation detail of this library; Reka provides focus management, keyboard interaction, focus trapping and accessible states. Shared components must preserve form disabling, labels, focus rings, portal layering and both themes.

Use `message` for notifications and await `messageBox.confirm` for confirmation. Cancel rejects with `cancel`; Escape rejects with `close`, so a navigation guard can distinguish discarding edits from cancelling navigation.

Dataset queries use typed endpoints and keys in `../api/datasets.ts`, with cancellation and Query cache invalidation. Canvas session editing, history and revie w commands retain Pinia. Geometry and category shortcut helpers are independent TypeScript modules under `features/annotation/domain`.

`Carousel.vue` uses Embla Carousel and its autoplay plugin for the shared image carousel. It supports looping, dragging, arrow keys, previous/next buttons, indicators, pause on hover/focus, and reduced-motion preferences. The auth panel contains this carousel only.
