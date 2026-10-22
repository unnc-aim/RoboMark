import { createApp } from "vue";
import { createPinia } from "pinia";
import { VueQueryPlugin } from "@tanstack/vue-query";
import { queryClient } from "./shared/api/query";
import { installUI } from "./shared/ui";
import App from "./App.vue";
import router from "./router";
import { useUserStore } from "./stores/user";
import "./shared/styles/tokens.css";
import "vue-sonner/style.css";
import "./style.css";
const app = createApp(App);
app.use(createPinia());
app.use(VueQueryPlugin, { queryClient });
window.addEventListener("robomark:session-expired", () => {
  useUserStore().logout();
  const route = router.currentRoute.value;
  if (!route.meta.guest) {
    const redirect = route.fullPath === "/login" ? "/" : route.fullPath;
    void router.replace({ name: "Login", query: { redirect } });
  }
});
app.use(router);
installUI(app);
app.mount("#app");
