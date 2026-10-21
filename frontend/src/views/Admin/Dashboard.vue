<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useQuery } from "@tanstack/vue-query";
import api from "../../utils/api";
import { useDatasets } from "../../shared/api/datasets";
const router = useRouter(),
  datasets = useDatasets();
const overview = useQuery({
  queryKey: ["statistics", "overview"],
  queryFn: async () => (await api.get("/admin/statistics/overview")).data,
});
const daily = useQuery({
  queryKey: ["statistics", "daily", 7],
  queryFn: async () =>
    (await api.get("/admin/statistics/daily", { params: { days: 7 } })).data,
});
const users = useQuery({
  queryKey: ["statistics", "users"],
  queryFn: async () => (await api.get("/admin/statistics/users")).data,
});
const metrics = computed(() => [
  ["图片总量", overview.data.value?.total_images, "Picture"],
  ["已标注图片", overview.data.value?.labeled_images, "Select"],
  ["目标标注框", overview.data.value?.total_annotations, "Aim"],
  ["工作空间成员", overview.data.value?.total_users, "Users"],
]);
const largest = computed(() =>
  Math.max(1, ...(daily.data.value || []).map((d) => d.images_labeled)),
);
</script>
<template>
  <header class="page-heading">
    <div>
      <h1>管理概览</h1>
      <p>团队的数据、标注进展与近期工作，尽在一处。</p>
    </div>
    <ui-button
      type="primary"
      icon="Plus"
      @click="router.push('/admin/datasets?create=1')"
      >新建数据集</ui-button
    >
  </header>
  <ui-alert v-if="overview.isError.value" type="error" title="概览加载失败"
    ><ui-button @click="overview.refetch()">重新加载</ui-button></ui-alert
  >
  <div v-loading="overview.isPending.value" class="dashboard-metrics">
    <ui-card v-for="[title, value, icon] in metrics" :key="title" class="metric"
      ><span>{{ title }}<ui-icon :name="icon" /></span
      ><strong>{{ value?.toLocaleString() ?? "—" }}</strong
      ><small>工作空间实时数据</small></ui-card
    >
  </div>
  <div class="dashboard-columns">
    <div class="stack">
      <ui-card class="panel-padding"
        ><div class="section-heading">
          <div>
            <h2>标注趋势</h2>
            <p>最近 7 天的图片标注量</p>
          </div>
        </div>
        <div v-loading="daily.isPending.value" class="dashboard-chart">
          <div
            v-for="day in daily.data.value"
            :key="day.date"
            class="chart-day"
          >
            <strong>{{ day.images_labeled }}</strong>
            <div
              :style="{
                height: `${Math.max(2, (day.images_labeled / largest) * 150)}px`,
              }"
            />
            <small>{{ day.date.slice(5) }}</small>
          </div>
          <ui-empty
            v-if="!daily.isPending.value && !daily.data.value?.length"
            description="近期还没有标注记录"
          />
        </div>
        <ui-alert v-if="daily.isError.value" type="error" title="趋势加载失败"
          ><ui-button @click="daily.refetch()">重试</ui-button></ui-alert
        ></ui-card
      ><ui-card class="panel-padding"
        ><div class="section-heading">
          <h2>数据集进度</h2>
          <ui-button variant="ghost" @click="router.push('/admin/datasets')"
            >全部数据集 <ui-icon name="ArrowRight"
          /></ui-button>
        </div>
        <div
          v-for="dataset in datasets.data.value?.slice(0, 5)"
          :key="dataset.id"
          class="dashboard-dataset"
        >
          <ui-button
            variant="ghost"
            icon="Folder"
            @click="router.push(`/datasets/${dataset.id}`)"
            >{{ dataset.name }}</ui-button
          ><span>{{ dataset.labeled_images }} / {{ dataset.total_images }}</span
          ><ui-progress
            :percentage="
              dataset.total_images
                ? (dataset.labeled_images / dataset.total_images) * 100
                : 0
            "
          />
        </div>
        <ui-empty
          v-if="datasets.data.value && !datasets.data.value.length"
          description="暂无数据集"
      /></ui-card>
    </div>
    <ui-card class="panel-padding dashboard-activity"
      ><div class="section-heading">
        <div>
          <h2>近期工作</h2>
          <p>根据团队实际标注统计</p>
        </div>
        <ui-icon name="Activity" />
      </div>
      <div
        v-for="day in [...(daily.data.value || [])]
          .reverse()
          .filter((d) => d.images_labeled > 0)"
        :key="day.date"
        class="activity-item"
      >
        <span class="activity-dot" />
        <div>
          <strong>完成 {{ day.images_labeled }} 张图片标注</strong>
          <p>新增 {{ day.annotations_created }} 个目标标注框</p>
          <small>{{ day.date }}</small>
        </div>
      </div>
      <ui-empty
        v-if="
          !daily.isPending.value &&
          !daily.data.value?.some((d) => d.images_labeled > 0)
        "
        description="近期还没有标注活动" /><ui-divider />
      <h3>成员贡献</h3>
      <div
        v-for="(member, index) in users.data.value?.slice(0, 5)"
        :key="member.user_id || member.username"
        class="contributor"
      >
        <span>{{ index + 1 }}</span
        ><strong>{{ member.username }}</strong
        ><small>{{ member.images_labeled }} 张</small>
      </div>
      <ui-empty v-if="users.isError.value" description="成员统计暂时不可用"
    /></ui-card>
  </div>
</template>
<style scoped>
.dashboard-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}
.metric {
  padding: var(--space-5);
}
.metric > span {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: var(--muted);
}
.metric > span > svg {
  color: #9da8bc;
  width: 17px;
}
.metric > strong {
  display: block;
  font-size: 31px;
  letter-spacing: -1px;
  font-weight: 600;
  margin: var(--space-4) 0 var(--space-3);
}
.metric > small {
  font-size: 9px;
  color: var(--muted);
}
.dashboard-columns {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(270px, 1fr);
  gap: var(--space-5);
}
.dashboard-activity {
  min-height: 100%;
}
.dashboard-chart {
  height: 235px;
  display: flex;
  gap: var(--space-4);
  align-items: flex-end;
  justify-content: space-around;
  padding: var(--space-5) 0;
}
.chart-day {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
}
.chart-day > div {
  width: 70%;
  background: #e3e9fd;
  border-radius: 4px 4px 0 0;
  max-width: 50px;
}
.chart-day:last-child > div {
  background: var(--primary);
}
.chart-day strong {
  font-size: 10px;
  font-weight: 500;
  color: var(--muted);
}
.chart-day small {
  font-size: 9px;
  color: var(--muted);
}
.dashboard-dataset {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 90px 140px;
  align-items: center;
  gap: var(--space-4);
  border-bottom: 1px solid var(--border);
  padding: var(--space-4) 0;
}
.dashboard-dataset > .ui-button {
  padding: 0;
  justify-content: flex-start;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 11px;
}
.dashboard-dataset > span {
  font-size: 10px;
  color: var(--muted);
}
.activity-item {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-5) 0;
  border-bottom: 1px solid var(--border);
}
.activity-dot {
  margin-top: 4px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary);
  flex-shrink: 0;
}
.activity-item strong {
  font-size: 11px;
  font-weight: 550;
}
.activity-item p {
  font-size: 10px;
  color: var(--muted);
  margin: 7px 0 var(--space-3);
}
.activity-item small {
  font-size: 9px;
  color: #9da5b3;
}
.contributor {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) 0;
  font-size: 11px;
}
.contributor > span {
  font-size: 9px;
  color: var(--muted);
  width: 15px;
}
.contributor > strong {
  font-weight: 500;
}
.contributor > small {
  margin-left: auto;
  color: var(--muted);
  font-size: 10px;
}
@media (max-width: 1100px) {
  .dashboard-metrics {
    grid-template-columns: repeat(2, 1fr);
  }
  .dashboard-columns {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 600px) {
  .dashboard-metrics {
    gap: var(--space-3);
  }
  .metric {
    padding: var(--space-4);
  }
  .metric > strong {
    font-size: 25px;
  }
  .dashboard-dataset {
    grid-template-columns: minmax(0, 1fr) 65px;
  }
  .dashboard-dataset > .ui-progress {
    grid-column: 1/-1;
  }
  .dashboard-chart {
    gap: 6px;
  }
}
</style>
