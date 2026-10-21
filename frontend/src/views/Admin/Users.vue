<script setup>
import { ref, onMounted, computed } from "vue";
import { message, messageBox } from "../../shared/ui/feedback";
import { ChevronDown as ArrowDown } from "@lucide/vue";
import api from "../../utils/api";

const users = ref([]),
  search = ref(""),
  loadError = ref(false);
const filteredUsers = computed(() =>
  users.value.filter((user) =>
    `${user.username} ${user.email || ""}`
      .toLowerCase()
      .includes(search.value.toLowerCase()),
  ),
);
const loading = ref(true);
const resetDialogVisible = ref(false);
const createDialogVisible = ref(false);
const selectedUser = ref(null);
const newPassword = ref("");
const newUser = ref({
  username: "",
  password: "",
  email: "",
  is_admin: false,
});

onMounted(() => {
  loadUsers();
});

async function loadUsers() {
  loading.value = true;
  loadError.value = false;
  try {
    const response = await api.get("/admin/users");
    users.value = response.data;
  } catch {
    loadError.value = true;
  } finally {
    loading.value = false;
  }
}

async function toggleUserStatus(user) {
  try {
    await api.put(`/admin/users/${user.id}`, {
      is_active: !user.is_active,
    });
    message.success(user.is_active ? "已禁用" : "已启用");
    loadUsers();
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

async function toggleAdminStatus(user) {
  try {
    await messageBox.confirm(
      user.is_admin
        ? `确定要取消 "${user.username}" 的管理员权限吗？`
        : `确定要将 "${user.username}" 设为管理员吗？`,
      "确认",
      { type: "warning" },
    );

    await api.put(`/admin/users/${user.id}`, {
      is_admin: !user.is_admin,
    });
    message.success("操作成功");
    loadUsers();
  } catch (error) {
    if (error !== "cancel") {
      // 错误已在拦截器中处理
    }
  }
}

function showResetDialog(user) {
  selectedUser.value = user;
  newPassword.value = "";
  resetDialogVisible.value = true;
}

async function handleResetPassword() {
  if (!newPassword.value || newPassword.value.length < 6) {
    message.warning("密码长度不能少于6位");
    return;
  }

  try {
    await api.post(`/admin/users/${selectedUser.value.id}/reset-password`, {
      new_password: newPassword.value,
    });
    message.success("密码重置成功");
    resetDialogVisible.value = false;
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

async function handleDeleteUser(user) {
  try {
    await messageBox.confirm(
      `确定要删除用户 "${user.username}" 吗？此操作不可恢复。`,
      "警告",
      { type: "warning" },
    );

    await api.delete(`/admin/users/${user.id}`);
    message.success("删除成功");
    loadUsers();
  } catch (error) {
    if (error !== "cancel") {
      // 错误已在拦截器中处理
    }
  }
}

function formatDate(dateStr) {
  if (!dateStr) return "-";
  return new Date(dateStr).toLocaleString("zh-CN");
}

function handleCommand(command, user) {
  if (command === "toggleAdmin") {
    toggleAdminStatus(user);
  } else if (command === "delete") {
    handleDeleteUser(user);
  }
}

function showCreateDialog() {
  newUser.value = {
    username: "",
    password: "",
    email: "",
    is_admin: false,
  };
  createDialogVisible.value = true;
}

async function handleCreateUser() {
  if (!newUser.value.username) {
    message.warning("请输入用户名");
    return;
  }
  if (!newUser.value.password || newUser.value.password.length < 6) {
    message.warning("密码长度不能少于6位");
    return;
  }

  try {
    await api.post("/admin/users", newUser.value);
    message.success("用户创建成功");
    createDialogVisible.value = false;
    loadUsers();
  } catch (error) {
    // 错误已在拦截器中处理
  }
}
</script>

<template>
  <div class="users-page">
    <div class="page-header">
      <div>
        <h2>工作空间成员</h2>
        <p>为团队成员配置账号、访问权限与角色。</p>
      </div>
      <ui-button type="primary" @click="showCreateDialog">添加用户</ui-button>
    </div>

    <div class="members-search">
      <ui-input
        v-model="search"
        prefix-icon="Search"
        placeholder="搜索成员姓名或邮箱"
      /><span class="muted">{{ filteredUsers.length }} 位成员</span>
    </div>
    <ui-alert v-if="loadError" type="error" title="成员加载失败"
      ><ui-button @click="loadUsers">重新加载</ui-button></ui-alert
    >
    <ui-table
      :data="filteredUsers"
      v-loading="loading"
      stripe
      style="width: 100%"
    >
      <ui-table-column prop="id" label="ID" width="80" />
      <ui-table-column prop="username" label="用户名" min-width="120" />
      <ui-table-column
        prop="email"
        label="邮箱"
        min-width="180"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ row.email || "-" }}
        </template>
      </ui-table-column>
      <ui-table-column label="角色" width="90">
        <template #default="{ row }">
          <ui-tag :type="row.is_admin ? 'danger' : 'info'" size="small">
            {{ row.is_admin ? "管理员" : "普通用户" }}
          </ui-tag>
        </template>
      </ui-table-column>
      <ui-table-column label="状态" width="100">
        <template #default="{ row }">
          <ui-tag :type="row.is_active ? 'success' : 'warning'" size="small">
            {{ row.is_active ? "正常" : "已禁用" }}
          </ui-tag>
        </template>
      </ui-table-column>
      <ui-table-column prop="images_labeled" label="标注图片数" width="120" />
      <ui-table-column label="注册时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </ui-table-column>
      <ui-table-column label="操作" min-width="240">
        <template #default="{ row }">
          <div class="action-buttons">
            <ui-button
              size="small"
              :type="row.is_active ? 'warning' : 'success'"
              @click="toggleUserStatus(row)"
            >
              {{ row.is_active ? "禁用" : "启用" }}
            </ui-button>
            <ui-button size="small" @click="showResetDialog(row)"
              >重置密码</ui-button
            >
            <ui-dropdown
              trigger="click"
              @command="(cmd) => handleCommand(cmd, row)"
            >
              <ui-button size="small">
                更多<ui-icon class="el-icon--right"><arrow-down /></ui-icon>
              </ui-button>
              <template #dropdown>
                <ui-dropdown-menu>
                  <ui-dropdown-item command="toggleAdmin">
                    {{ row.is_admin ? "取消管理员" : "设为管理员" }}
                  </ui-dropdown-item>
                  <ui-dropdown-item
                    command="delete"
                    divided
                    style="color: #f56c6c"
                  >
                    删除用户
                  </ui-dropdown-item>
                </ui-dropdown-menu>
              </template>
            </ui-dropdown>
          </div>
        </template>
      </ui-table-column>
    </ui-table>

    <!-- 添加用户对话框 -->
    <ui-dialog v-model="createDialogVisible" title="添加用户" width="450px">
      <ui-form :model="newUser" label-width="80px">
        <ui-form-item label="用户名" required>
          <ui-input v-model="newUser.username" placeholder="请输入用户名" />
        </ui-form-item>
        <ui-form-item label="密码" required>
          <ui-input
            v-model="newUser.password"
            type="password"
            placeholder="请输入密码（至少6位）"
            show-password
          />
        </ui-form-item>
        <ui-form-item label="邮箱">
          <ui-input v-model="newUser.email" placeholder="留空则自动生成" />
          <div class="form-tip">留空将自动生成为：用户名@robomark.local</div>
        </ui-form-item>
        <ui-form-item label="管理员">
          <ui-switch v-model="newUser.is_admin" />
        </ui-form-item>
      </ui-form>
      <template #footer>
        <ui-button @click="createDialogVisible = false">取消</ui-button>
        <ui-button type="primary" @click="handleCreateUser">创建</ui-button>
      </template>
    </ui-dialog>

    <!-- 重置密码对话框 -->
    <ui-dialog v-model="resetDialogVisible" title="重置密码" width="400px">
      <ui-form>
        <ui-form-item label="用户">
          <span>{{ selectedUser?.username }}</span>
        </ui-form-item>
        <ui-form-item label="新密码">
          <ui-input
            v-model="newPassword"
            type="password"
            placeholder="请输入新密码（至少6位）"
            show-password
          />
        </ui-form-item>
      </ui-form>
      <template #footer>
        <ui-button @click="resetDialogVisible = false">取消</ui-button>
        <ui-button type="primary" @click="handleResetPassword">确定</ui-button>
      </template>
    </ui-dialog>
  </div>
</template>

<style scoped>
.users-page {
  min-width: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0;
}

.action-buttons {
  display: flex;
  gap: 8px;
  align-items: center;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.members-search {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 22px;
  font-size: 11px;
}
.members-search > .ui-input-wrap {
  max-width: 300px;
}
</style>
