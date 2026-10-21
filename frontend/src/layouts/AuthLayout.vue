<script setup>
import UiCarousel from "../shared/ui/Carousel.vue";
import { cards } from "../assets/aim-cards";
import BrandLogo from "../components/BrandLogo.vue";
defineProps({ register: Boolean });
</script>
<template>
  <main class="auth-layout">
    <section class="auth-visual" aria-label="AIM 纪念卡牌展示">
      <UiCarousel :slides="cards" label="AIM 五周年纪念卡牌" />
    </section>
    <section class="auth-form-area">
      <p class="auth-switch">
        {{ register ? "已有账号？" : "还没有账号？" }}
        <ui-link :href="register ? '/login' : '/register'"
          >{{ register ? "登录" : "创建账号" }} →</ui-link
        >
      </p>
      <div class="auth-form-content">
        <div class="auth-mini-brand"><BrandLogo /></div>
        <h2>{{ register ? "加入工作空间" : "欢迎回来。" }}</h2>
        <p>
          {{
            register
              ? "创建账号，开始你的第一份标注。"
              : "登录以继续你的标注与审核工作。"
          }}
        </p>
        <slot />
      </div>
      <footer>RoboMark · 为专注的标注而设计。</footer>
    </section>
  </main>
</template>
<style scoped>
.auth-layout {
  display: grid;
  grid-template-columns: 47% 53%;
  min-height: calc(100dvh - 55px);
}
.auth-visual {
  min-width: 0;
  min-height: calc(100dvh - 55px);
  background: #060708;
  overflow: hidden;
}
.auth-form-area {
  padding: 36px 48px;
  display: flex;
  flex-direction: column;
  background: white;
}
.auth-switch {
  font-size: 11px;
  color: var(--muted);
  text-align: right;
}
.auth-switch .ui-link {
  color: var(--primary);
  font-weight: 600;
}
.auth-form-content {
  width: 100%;
  max-width: 350px;
  margin: auto;
  padding: 45px 0;
}
.auth-mini-brand {
  margin-bottom: 28px;
}
.auth-form-content h2 {
  font-size: 29px;
  margin-bottom: 10px;
}
.auth-form-content > p {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 30px;
}
.auth-form-area > footer {
  font-size: 9px;
  color: #b1b6c1;
  text-align: center;
}
@media (max-width: 950px) {
  .auth-form-area {
    padding: 30px;
  }
}
@media (max-width: 650px) {
  .auth-layout {
    grid-template-columns: 1fr;
  }
  .auth-visual {
    display: none;
  }
  .auth-form-area {
    padding: 25px;
    min-height: calc(100dvh - 80px);
  }
  .auth-form-content {
    padding: 45px 0;
  }
  .auth-form-content h2 {
    font-size: 28px;
  }
}
</style>
