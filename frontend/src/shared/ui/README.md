# RoboMark UI component library

The production UI uses the Reka UI accessible primitives with project-owned components, following the source-owned component pattern used by shadcn-vue. The design baseline is commit `4656e22`; tokens live in `../styles/tokens.css`. Icons use Lucide (`@lucide/vue`). Notifications use Vue Sonner and confirmations use Reka AlertDialog.

`index.ts` contains the shared controls, data table, pagination, upload/directory picker building blocks and structural components. `components.d.ts` exposes their types to Vue templates. Views compose these components; they must not introduce native form controls, clickable native elements, disclosure widgets, links or tables. Semantic HTML for document structure, images, SVG geometry and the annotation Canvas remains appropriate.

Run `pnpm check:ui` to enforce this boundary, or `pnpm check` for all frontend checks. Native HTML is an internal implementation detail of this library; Reka provides focus management, keyboard interaction, focus trapping and accessible states. Shared components must preserve form disabling, labels, focus rings, portal layering and both themes.

Use `message` for notifications and await `messageBox.confirm` for confirmation. Cancel rejects with `cancel`; Escape rejects with `close`, so a navigation guard can distinguish discarding edits from cancelling navigation.

Dataset queries use typed endpoints and keys in `../api/datasets.ts`, with cancellation and Query cache invalidation. Canvas session editing, history and revie w commands retain Pinia. Geometry and category shortcut helpers are independent TypeScript modules under `features/annotation/domain`.

`Carousel.vue` uses Embla Carousel and its autoplay plugin for the shared image carousel. It supports looping, dragging, arrow keys, previous/next buttons, indicators, pause on hover/focus, and reduced-motion preferences. The auth panel contains this carousel only.

Request failures must use `utils/api.js` (`api` for JSON/Blob requests, `apiFetch` for uploads and streams). Both report through the same `message.error` notification. Login/register 401 responses retain the form and show the server detail; authenticated 401 responses clear the session and navigate to login with a return address. Network failures and 5xx responses do not clear credentials. Cancellation and confirmation dismissal are not failures.

Local handlers that need to report additional errors should call `reportError(error, fallback)` instead of adding a second `message.error`: the same error object is reported once. Error bodies support FastAPI validation arrays, nested messages, and JSON download Blobs; non-JSON proxy errors get a readable status fallback. Batch imports additionally validate the SSE terminal event, so broken streams cannot appear complete. Toasts remain clickable above modal dialogs without dismissing the form.

Failure regression checks: `pnpm test`, and from the repository root, `playwright-cli -s=feedback-audit run-code --filename frontend/scripts/verify-feedback.js` with the local Vite server at `http://127.0.0.1:5173`. Browser fixtures intercept all business APIs and do not modify the database.

`DirectoryList.vue` uses Reka Listbox for the server directory chooser; `components/DirectoryPicker.vue` composes it with the shared dialog, controls and `shared/api/filesystem.ts`. Directory selection must browse the authenticated server API, not use a browser file input. See `docs/server-directory-picker.md` for scope configuration, component evaluation and isolated browser acceptance.
