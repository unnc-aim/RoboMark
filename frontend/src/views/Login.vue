<script setup>
import { ref } from "vue";
import AuthLayout from "../layouts/AuthLayout.vue";
import { useRouter, useRoute } from "vue-router";
import { useUserStore } from "../stores/user";
import { message } from "../shared/ui/feedback";
import { getErrorMessage } from "../utils/apiErrors";

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();

const form = ref({
  username: "",
  password: "",
});
const loading = ref(false);
const errorMessage = ref("");

async function handleLogin() {
  if (loading.value) return;
  errorMessage.value = "";
  if (!form.value.username || !form.value.password) {
    message.warning("请填写用户名和密码");
    return;
  }

  loading.value = true;
  try {
    await userStore.login(form.value.username, form.value.password);
    message.success("登录成功");
    const target = route.query.redirect;
    const redirect = typeof target === "string" && target.startsWith("/") && !target.startsWith("//") ? target : "/";
    router.push(redirect);
  } catch (error) {
    errorMessage.value = await getErrorMessage(error);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <AuthLayout
    ><ui-alert v-if="errorMessage" type="error" :title="errorMessage" role="alert" />
    <ui-form @submit.prevent="handleLogin"
      ><ui-form-item label="用户名"
        ><ui-input
          v-model="form.username"
          placeholder="输入用户名"
          autocomplete="username"
          required /></ui-form-item
      ><ui-form-item label="密码"
        ><ui-input
          v-model="form.password"
          type="password"
          placeholder="输入密码"
          autocomplete="current-password"
          show-password
          required /></ui-form-item
      ><ui-button
        native-type="submit"
        type="primary"
        :loading="loading"
        class="auth-submit"
        >登录工作空间 <ui-icon name="ArrowRight" /></ui-button></ui-form
  ></AuthLayout>
</template>
<style scoped>
.auth-submit {
  width: 100%;
  justify-content: space-between;
  margin-top: 5px;
  min-height: 42px;
}
.auth-note {
  font-size: 10px;
  color: var(--muted);
  margin: 0 0 var(--space-4);
}
</style>
