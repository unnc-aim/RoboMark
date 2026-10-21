import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { guest: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
    meta: { guest: true }
  },
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/Home.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/annotate/:datasetId',
    name: 'Annotation',
    component: () => import('../views/Annotation.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/datasets/:datasetId/preannotation',
    component: () => import('../views/Admin/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Preannotation',
        component: () => import('../views/Preannotation.vue'),
        meta: { title: '预标注与审核', activeMenu: '/admin/datasets' }
      },
      {
        path: ':taskId/images/:imageId/trace',
        name: 'PreannotationTrace',
        component: () => import('../views/PreannotationTrace.vue'),
        meta: { title: '图像推理记录', activeMenu: '/admin/datasets' }
      },
      {
        path: ':taskId/images/:imageId',
        name: 'PreannotationReview',
        redirect: to => ({ name:'Annotation', params:{datasetId:to.params.datasetId}, query:{...to.query,source:'preannotation',task:to.params.taskId,image:to.params.imageId,review_status:to.query.review_status || 'all'} }),
        meta: { title: '预标注审核', activeMenu: '/admin/datasets' }
      }
    ]
  },
  {
    path: '/datasets/:datasetId',
    component: () => import('../views/Admin/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'DatasetDetail', component: () => import('../views/DatasetDetail.vue'), meta: { title: '数据集详情' } },
      { path: 'settings', name: 'DatasetSettings', component: () => import('../views/DatasetSettings.vue'), meta: { title: '数据集设置', requiresAdmin: true } }
    ]
  },
  {
    path: '/profiles', component: () => import('../views/Admin/Layout.vue'), meta: { requiresAuth: true },
    children: [{ path: '', name: 'Profiles', component: () => import('../views/Profiles.vue'), meta: { title: '推理接口' } }]
  },
  {
    path: '/tutorial',
    name: 'Tutorial',
    component: () => import('../views/Tutorial.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('../views/Admin/Layout.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
    children: [
      {
        path: '',
        name: 'AdminDashboard',
        component: () => import('../views/Admin/Dashboard.vue')
      },
      {
        path: 'datasets',
        name: 'AdminDatasets',
        component: () => import('../views/Admin/Datasets.vue')
      },
      {
        path: 'categories/:datasetId',
        name: 'AdminCategories',
        component: () => import('../views/Admin/Categories.vue')
      },
      {
        path: 'users',
        name: 'AdminUsers',
        component: () => import('../views/Admin/Users.vue')
      },
      {
        path: 'export',
        name: 'AdminExport',
        component: () => import('../views/Admin/Export.vue')
      },
      {
        path: ':pathMatch(.*)*',
        redirect: '/admin'
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to, from, saved) { return saved || (to.path !== from.path ? { top: 0 } : undefined) },
  routes
})

// 路由守卫
router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()

  // 等待用户信息初始化完成
  if (!userStore.initialized && userStore.token) {
    try {
      await userStore.fetchUser()
    } catch {
      // 忽略错误，fetchUser 内部会处理
    }
  }

  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (to.meta.requiresAdmin && !userStore.isAdmin) {
    next({ name: 'Home' })
  } else if (to.meta.guest && userStore.isLoggedIn) {
    next({ name: 'Home' })
  } else {
    next()
  }
})

export default router
