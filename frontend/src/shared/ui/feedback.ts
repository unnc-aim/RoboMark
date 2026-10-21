import { shallowRef } from "vue";
import { toast } from "vue-sonner";
export const message = {
  success: toast.success,
  error: toast.error,
  warning: toast.warning,
  info: toast.info,
};
export const confirmation = shallowRef<any>(null);
// Queue promises so concurrent navigation and save guards never overwrite one another.
let queue = Promise.resolve();
export const messageBox = {
  confirm(text: string, title = "请确认", options: any = {}) {
    const result = queue.then(
      () =>
        new Promise((resolve, reject) => {
          confirmation.value = { text, title, options, resolve, reject };
        }),
    );
    queue = result.then(
      () => undefined,
      () => undefined,
    );
    return result;
  },
};
export function settleConfirmation(accepted: boolean, reason = "cancel") {
  const current = confirmation.value;
  confirmation.value = null;
  if (accepted) current?.resolve("confirm");
  else current?.reject(reason);
}
