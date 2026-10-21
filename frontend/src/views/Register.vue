<script setup>
import { ref } from "vue";
import AuthLayout from "../layouts/AuthLayout.vue";
import { useRouter } from "vue-router";
import { useUserStore } from "../stores/user";
import { message } from "../shared/ui/feedback";

const router = useRouter();
const userStore = useUserStore();

const form = ref({
  username: "",
  password: "",
  confirmPassword: "",
  email: "",
});
const loading = ref(false);

async function handleRegister() {
  if (!form.value.username || !form.value.password) {
    message.warning("请填写用户名和密码");
    return;
  }

  if (form.value.password !== form.value.confirmPassword) {
    message.warning("两次输入的密码不一致");
    return;
  }

  if (form.value.password.length < 6) {
    message.warning("密码长度不能少于6位");
    return;
  }

  loading.value = true;
  try {
    await userStore.register(
      form.value.username,
      form.value.password,
      form.value.email,
    );
    message.success("注册成功，请登录");
    router.push("/login");
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <AuthLayout register
    ><ui-form @submit.prevent="handleRegister"
      ><ui-form-item label="用户名"
        ><ui-input
          v-model="form.username"
          placeholder="输入用户名"
          autocomplete="username"
          required
          minlength="3" /></ui-form-item
      ><ui-form-item label="邮箱（可选）"
        ><ui-input
          v-model="form.email"
          type="email"
          placeholder="you@example.com"
          autocomplete="email" /></ui-form-item
      ><ui-form-item label="密码"
        ><ui-input
          v-model="form.password"
          type="password"
          placeholder="至少 6 位字符"
          autocomplete="new-password"
          show-password
          required
          minlength="6" /></ui-form-item
      ><ui-form-item label="确认密码"
        ><ui-input
          v-model="form.confirmPassword"
          type="password"
          placeholder="再次输入密码"
          autocomplete="new-password"
          required
          minlength="6"
      /></ui-form-item>
      <p class="auth-note">注册后由管理员分配数据集权限。</p>
      <ui-button
        native-type="submit"
        type="primary"
        :loading="loading"
        class="auth-submit"
        >创建账号 <ui-icon name="ArrowRight" /></ui-button></ui-form
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
