<script setup lang="ts">
import { Toaster } from "vue-sonner";
import { useRoute } from "vue-router";
const route = useRoute();
import {
  AlertDialogRoot,
  AlertDialogPortal,
  AlertDialogOverlay,
  AlertDialogContent,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
} from "reka-ui";
import { UiButton } from "./index";
import { confirmation, settleConfirmation } from "./feedback";
</script>
<template>
  <Toaster
    position="top-center"
    :theme="route.name === 'Annotation' ? 'dark' : 'light'"
    rich-colors
    close-button
  />
  <AlertDialogRoot :open="!!confirmation">
    <AlertDialogPortal
      ><AlertDialogOverlay class="ui-dialog-overlay" /><AlertDialogContent
        class="ui-dialog"
        style="width: 460px"
        @escape-key-down="settleConfirmation(false, 'close')"
      >
        <div class="ui-dialog-header">
          <AlertDialogTitle class="ui-dialog-title">{{
            confirmation?.title
          }}</AlertDialogTitle>
        </div>
        <AlertDialogDescription class="ui-dialog-body">{{
          confirmation?.text
        }}</AlertDialogDescription>
        <div class="ui-dialog-footer">
          <AlertDialogCancel as-child
            ><UiButton @click="settleConfirmation(false)">{{
              confirmation?.options.cancelButtonText || "取消"
            }}</UiButton></AlertDialogCancel
          ><AlertDialogAction as-child
            ><UiButton type="primary" @click="settleConfirmation(true)">{{
              confirmation?.options.confirmButtonText || "确定"
            }}</UiButton></AlertDialogAction
          >
        </div>
      </AlertDialogContent></AlertDialogPortal
    >
  </AlertDialogRoot>
</template>

<style>
/* Modal dialogs lock body pointer events; notifications must remain interactive. */
[data-sonner-toast]:not([data-visible="false"]) {
  pointer-events: auto;
}
</style>
