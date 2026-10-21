// Run from repository root via Playwright CLI run-code --filename.
// All APIs are mocked. No business database or inference provider is accessed.
async (page) => {
  const results = [];

  // setup
  results.push({
    batch: "setup",
    result: await (async (page) => {
      const user = {
        id: 1,
        username: "AIM 管理员",
        email: "aim@example.com",
        is_admin: true,
        is_active: true,
      };
      const datasets = [
        {
          id: 1,
          name: "RoboMaster · 赛场机器人",
          description: "2026 赛季机器人目标检测，覆盖多视角与复杂光照场景。",
          image_path: "/data/robomaster/images",
          label_path: "/data/robomaster/labels",
          total_images: 18,
          labeled_images: 6,
          is_active: true,
        },
        {
          id: 2,
          name: "装甲板 · 多视角识别",
          description: "装甲板四点标注与姿态估计。",
          image_path: "/data/armor/images",
          label_path: "/data/armor/labels",
          total_images: 12,
          labeled_images: 12,
          is_active: true,
        },
        {
          id: 3,
          name: "几何图形 · 回归测试",
          description: "基础图形，验证标注与导出流程。",
          image_path: "/data/shapes",
          label_path: "",
          total_images: 0,
          labeled_images: 0,
          is_active: true,
        },
      ];
      let categories = [
        {
          id: 1,
          dataset_id: 1,
          name: "蓝方机器人",
          color: "#3a7df0",
          shortcut_key: "1,b",
          sort_order: 0,
        },
        {
          id: 2,
          dataset_id: 1,
          name: "红方机器人",
          color: "#ed646c",
          shortcut_key: "2",
          sort_order: 1,
        },
      ];
      let profiles = [
        {
          id: 1,
          owner_id: 1,
          name: "Qwen2.5-VL · 72B",
          endpoint: "http://localhost:8000/v1/chat/completions",
          model: "Qwen2.5-VL-72B",
          interface_type: "openai",
          is_shared: true,
          coordinate_system: "normalized",
          response_path: "choices[0].message.content",
          max_attempts: 3,
          timeout_seconds: 120,
        },
      ];
      const tasks = [
        {
          id: 24,
          dataset_id: 1,
          profile_id: 1,
          prompt: "标出赛场中的所有红方和蓝方机器人，框住完整机身。",
          annotation_type: "bbox",
          status: "completed_with_errors",
          is_sample: false,
          counts: { succeeded: 16, failed: 2 },
          approved: 6,
          rejected: 0,
          total_images: 18,
          processed_images: 18,
          with_results: 14,
          empty_results: 2,
          retryable_images: 2,
          categories_snapshot: categories,
          created_by: 1,
        },
      ];
      const image = (id) => ({
        id,
        dataset_id: 1,
        filename: `frame_${String(id).padStart(4, "0")}.jpg`,
        width: 1280,
        height: 720,
        annotation_revision: 0,
        status: id <= 6 ? "labeled" : "pending",
      });
      const candidate = {
        id: 101,
        category_id: 1,
        annotation_type: "bbox",
        x_center: 0.46,
        y_center: 0.54,
        width: 0.25,
        height: 0.35,
        confidence: 0.92,
        is_deleted: false,
      };
      const states = new Map();
      const state = (id) => {
        if (!states.has(id))
          states.set(id, {
            task_image: {
              execution_status: "succeeded",
              review_status: "unreviewed",
              revision: 0,
              original_count: 1,
              raw_response: '{"annotations":[{"label":"蓝方机器人"}]}',
            },
            image: image(id),
            candidates: id === 18 ? [] : [{ ...candidate, id: 100 + id }],
            annotations: [],
          });
        return states.get(id);
      };
      const daily = Array.from({ length: 7 }, (_, i) => ({
        date: `2026-10-${15 + i}`,
        images_labeled: [24, 51, 37, 82, 65, 95, 74][i],
        annotations_created: 80 + i * 30,
      }));
      const requests = [],
        unexpected = [],
        errors = [],
        warnings = [];
      page.on("pageerror", (e) => errors.push(e.message));
      page.on("console", (m) => {
        if (m.type() === "warning") warnings.push(m.text());
      });
      await page.addInitScript(() => {
        if (["/login", "/register"].includes(location.pathname)) {
          localStorage.removeItem("robomark-token");
          localStorage.removeItem("robomark-user");
          return;
        }
        localStorage.setItem("robomark-token", "local-test-token");
        localStorage.setItem(
          "robomark-user",
          JSON.stringify({
            id: 1,
            username: "AIM 管理员",
            is_admin: true,
            is_active: true,
          }),
        );
      });
      await page.unroute("**/api/**");
      await page.route("**/api/**", async (route) => {
        const req = route.request(),
          url = new URL(req.url()),
          path = url.pathname,
          method = req.method();
        if (!path.startsWith("/api/")) return route.continue();
        let data;
        const body =
          method === "GET"
            ? null
            : (() => {
                try {
                  return req.postDataJSON();
                } catch {
                  return req.postData();
                }
              })();
        requests.push({
          path,
          method,
          body,
          search: url.search,
          authorization: req.headers().authorization,
        });
        if (path === "/api/auth/me") data = user;
        else if (path === "/api/auth/login")
          data = { access_token: "local-test-token", user };
        else if (path === "/api/auth/register") data = user;
        else if (path === "/api/datasets") {
          if (method === "POST") {
            const d = {
              ...body,
              id: datasets.length + 1,
              total_images: 0,
              labeled_images: 0,
              is_active: true,
            };
            datasets.push(d);
            data = d;
          } else data = datasets;
        } else if (/^\/api\/datasets\/\d+$/.test(path)) {
          const d = datasets.find((d) => d.id === +path.split("/").pop());
          if (method === "PUT") Object.assign(d, body);
          data = d;
        } else if (/^\/api\/datasets\/\d+\/scan$/.test(path))
          data = { found_images: 18, imported_images: 0, skipped_images: 18 };
        else if (/^\/api\/dataset-configs\/\d+$/.test(path))
          data = {
            format_type: "yolo",
            source_width: 1920,
            source_height: 1080,
            auto_import_annotations: true,
          };
        else if (path === "/api/dataset-configs/") data = body;
        else if (/\/categories\/dataset\/\d+$/.test(path)) data = categories;
        else if (path === "/api/categories" && method === "POST") {
          data = { ...body, id: categories.length + 1 };
          categories.push(data);
        } else if (/^\/api\/categories\/\d+$/.test(path)) {
          const id = +path.split("/").pop();
          if (method === "PUT") {
            Object.assign(
              categories.find((c) => c.id === id),
              body,
            );
            data = categories.find((c) => c.id === id);
          } else {
            categories = categories.filter((c) => c.id !== id);
            data = { message: "删除成功" };
          }
        } else if (path === "/api/preannotation/profiles") {
          if (method === "POST") {
            data = { ...body, id: profiles.length + 1, owner_id: 1 };
            profiles.push(data);
          } else data = profiles;
        } else if (/^\/api\/preannotation\/profiles\/\d+$/.test(path)) {
          const id = +path.split("/").pop();
          if (method === "PUT")
            Object.assign(
              profiles.find((p) => p.id === id),
              body,
            );
          if (method === "DELETE")
            profiles = profiles.filter((p) => p.id !== id);
          data = profiles.find((p) => p.id === id) || {};
        } else if (/\/profiles\/(\d+\/)?test$/.test(path))
          data = {
            ok: true,
            http_status: 200,
            latency_ms: 162,
            message: "连接成功",
          };
        else if (/\/datasets\/\d+\/preannotation-tasks$/.test(path)) {
          if (method === "POST") {
            data = {
              ...tasks[0],
              id: 25,
              prompt: body.prompt,
              is_sample: !!body.sample_size,
            };
            tasks.unshift(data);
          } else data = { items: tasks, total: tasks.length };
        } else if (/\/preannotation\/tasks\/\d+$/.test(path))
          data = tasks.find((t) => t.id === +path.split("/").pop()) || tasks[0];
        else if (/\/datasets\/\d+\/preannotation-prompts$/.test(path)) {
          const q = url.searchParams.get("q") || "";
          const all = [
            {
              task_id: 24,
              dataset_name: datasets[0].name,
              username: user.username,
              prompt: tasks[0].prompt,
              is_sample: false,
              last_used_at: "2026-10-21T10:00:00",
              usage_count: 4,
            },
            {
              task_id: 23,
              dataset_name: datasets[0].name,
              username: user.username,
              prompt: "只识别装甲板，四点坐标按顺时针排列。",
              is_sample: true,
              last_used_at: "2026-10-20T10:00:00",
              usage_count: 1,
            },
          ].filter((p) => p.prompt.includes(q));
          data = { items: all, total: all.length };
        } else if (
          /\/preannotation\/tasks\/\d+\/images\/\d+\/trace$/.test(path)
        ) {
          const id = +path.split("/").at(-2);
          data = {
            image: image(id),
            task: tasks[0],
            task_image: state(id).task_image,
            input: {
              prompt: tasks[0].prompt,
              model: profiles[0].model,
              interface_type: "openai",
              categories,
            },
            total: 2,
            can_retry: false,
            attempts: [
              {
                id: 1,
                sequence_number: 1,
                status: "failed",
                elapsed_ms: 2000,
                error_code: "HTTP_500",
                trace: {
                  request: { data: { prompt: tasks[0].prompt } },
                  response: { data: { error: "服务暂时不可用" } },
                },
              },
              {
                id: 2,
                sequence_number: 2,
                status: "succeeded",
                elapsed_ms: 3610,
                trace: {
                  request: {
                    data: { model: "Qwen2.5-VL-72B", prompt: tasks[0].prompt },
                  },
                  response: { data: { annotations: [candidate] } },
                  parsed: { data: { annotations: [candidate] } },
                  normalized: { data: { annotations: [candidate] } },
                },
              },
            ],
          };
        } else if (/\/preannotation\/tasks\/\d+\/images\/\d+$/.test(path))
          data = state(+path.split("/").pop());
        else if (/\/(draft|review)$/.test(path)) {
          const id = +path.split("/").at(-2),
            item = state(id);
          if (path.endsWith("/draft")) {
            item.candidates = (body.annotations || item.candidates).map(
              (a, index) => ({ ...a, id: a.id || id * 1000 + index }),
            );
            item.task_image.review_status = "draft";
          } else {
            item.task_image.review_status =
              body.action === "reject" ? "rejected" : "approved";
            tasks[0].approved++;
          }
          item.task_image.revision++;
          data = item;
        } else if (/\/datasets\/\d+\/images$/.test(path)) {
          const id = +path.split("/")[3];
          let rows = Array.from(
            { length: datasets.find((d) => d.id === id)?.total_images || 0 },
            (_, i) => ({ ...image(i + 1), dataset_id: id }),
          );
          const task = url.searchParams.has("task_id");
          if (task)
            rows = rows.map((row) => ({
              ...row,
              ...state(row.id).task_image,
              candidates: state(row.id).candidates,
              inference_metrics: {
                input_tokens: 1426,
                output_tokens: 215,
                tps: 59.6,
              },
            }));
          const review = url.searchParams.get("review_status");
          if (review && review !== "all") {
            rows = rows.filter((row) =>
              review === "pending"
                ? ["unreviewed", "draft"].includes(row.review_status)
                : row.review_status === review,
            );
          }
          const total = rows.length;
          const after = +url.searchParams.get("after_id"),
            before = +url.searchParams.get("before_id");
          if (after) rows = rows.filter((row) => row.id > after);
          if (before) rows = rows.filter((row) => row.id < before).reverse();
          const size = +url.searchParams.get("page_size") || 20,
            start = ((+url.searchParams.get("page") || 1) - 1) * size;
          data = { items: rows.slice(start, start + size), total };
        } else if (path === "/api/images/next/1/batch")
          data = [image(7), image(8), image(9)];
        else if (path === "/api/images/next/1")
          data = { ...image(7), annotations: [] };
        else if (/^\/api\/images\/\d+$/.test(path))
          data = { ...image(+path.split("/").pop()), annotations: [] };
        else if (/^\/api\/images\/\d+\/save$/.test(path))
          data = { success: true, annotations: body.annotations || [] };
        else if (/\/images\/dataset\/\d+\/progress$/.test(path))
          data = {
            total: 18,
            labeled: 6,
            pending: 12,
            skipped: 0,
            progress: 33,
          };
        else if (/^\/api\/images\/\d+\/file$/.test(path))
          return route.fulfill({
            path: "docs/ui-redesign/assets/arena-3591.jpg",
            contentType: "image/jpeg",
          });
        else if (path === "/api/export/formats")
          data = [
            {
              id: "yolov8",
              name: "YOLOv8",
              description: "Ultralytics 标准格式",
            },
            { id: "yolo_darknet", name: "YOLO Darknet" },
            { id: "coco", name: "COCO JSON" },
          ];
        else if (path === "/api/export" && method === "POST")
          data = {
            format: body.format,
            total_images: 18,
            categories: 2,
            train_images: 14,
            val_images: 2,
            test_images: 2,
            total_annotations: 36,
            download_url: "/api/export/download/test-artifact",
          };
        else if (path === "/api/export/download/test-artifact")
          return route.fulfill({
            status: 200,
            contentType: "application/zip",
            body: Buffer.from("PK migration fixture"),
          });
        else if (path === "/api/admin/statistics/overview")
          data = {
            total_users: 4,
            total_datasets: 3,
            total_images: 30,
            labeled_images: 18,
            pending_images: 12,
            total_annotations: 86,
          };
        else if (path === "/api/admin/statistics/daily") data = daily;
        else if (path === "/api/admin/statistics/users")
          data = [
            {
              user_id: 1,
              username: "AIM 管理员",
              images_labeled: 74,
              annotations_created: 180,
            },
            {
              user_id: 2,
              username: "视觉组成员",
              images_labeled: 52,
              annotations_created: 142,
            },
          ];
        else if (path === "/api/admin/users")
          data =
            method === "POST"
              ? { id: 3, ...body }
              : [
                  user,
                  {
                    id: 2,
                    username: "视觉组成员",
                    email: "vision@example.com",
                    is_admin: false,
                    is_active: true,
                    created_at: "2026-10-20T10:00:00",
                  },
                ];
        else if (/^\/api\/admin\/users\/\d+(\/reset-password)?$/.test(path))
          data = { success: true };
        else {
          unexpected.push({ path, method });
          return route.fulfill({
            status: 404,
            json: { detail: "Unexpected test request " + path },
          });
        }
        return route.fulfill({ status: 200, json: data });
      });
      page.__migration = { requests, unexpected, errors, warnings };
      await page.setViewportSize({ width: 1600, height: 1100 });
      await page.goto("http://127.0.0.1:5173/admin/datasets");
      await page.getByRole("heading", { name: "数据集工作区" }).waitFor();
      await page.locator(".dataset-card").first().waitFor();
      await page.screenshot({
        path: "output/playwright/migration/datasets.png",
        fullPage: true,
      });
      return { ready: true };
    })(page),
  });

  // controls
  results.push({
    batch: "controls",
    result: await (async (page) => {
      const passed = [];
      const check = (condition, name) => {
        if (!condition) throw new Error(name);
        passed.push(name);
      };
      await page
        .getByRole("textbox", { name: "搜索数据集…" })
        .fill("不存在的数据集");
      await page.getByText("没有匹配的数据集", { exact: true }).waitFor();
      check((await page.locator(".dataset-card").count()) === 0, "搜索空状态");
      await page.getByRole("textbox", { name: "搜索数据集…" }).fill("");
      await page.getByRole("radio", { name: "列表视图" }).click();
      check(
        (await page.locator(".dataset-collection.list-view").count()) === 1,
        "列表视图",
      );
      await page.getByRole("radio", { name: "网格视图" }).click();
      await page
        .getByRole("link", { name: "打开数据集 RoboMaster · 赛场机器人" })
        .press("Enter");
      await page
        .getByRole("heading", { name: "RoboMaster · 赛场机器人", exact: true })
        .waitFor();
      await page.locator(".detail-image").first().waitFor();
      check(
        (await page.locator(".detail-image").count()) === 6,
        "图片默认只渲染6张",
      );
      await page.getByRole("button", { name: "每页图片数量" }).click();
      await page.getByRole("option", { name: "每页 12 张" }).click();
      await page.waitForFunction(
        () => document.querySelectorAll(".detail-image").length === 12,
      );
      check(true, "切换每页12张");
      await page.getByRole("button", { name: "下一页", exact: true }).click();
      await page.waitForFunction(
        () => document.querySelectorAll(".detail-image").length === 6,
      );
      check(true, "图片分页");
      await page.screenshot({
        path: "output/playwright/migration/dataset-detail.png",
        fullPage: true,
      });
      await page.goto("http://127.0.0.1:5173/datasets/1/preannotation?task=24");
      await page
        .getByRole("textbox", { name: "Prompt", exact: true })
        .waitFor();
      await page.waitForFunction(() =>
        document.querySelector("textarea")?.value.includes("红方"),
      );
      check(true, "恢复批次Prompt");
      check(
        (await page.locator(".image-card-wrap").count()) === 6,
        "预标注默认6张",
      );
      await page
        .getByRole("button", { name: "历史 Prompt", exact: true })
        .click();
      await page.getByRole("dialog", { name: "历史 Prompt" }).waitFor();
      await page
        .getByRole("textbox", { name: "搜索历史 Prompt" })
        .fill("装甲板");
      await page
        .getByRole("button", { name: "预览批次 #23 的 Prompt" })
        .waitFor();
      check(
        (await page
          .getByRole("button", { name: "预览批次 #24 的 Prompt" })
          .count()) === 0,
        "历史Prompt搜索",
      );
      await page.screenshot({
        path: "output/playwright/migration/prompt-history.png",
        fullPage: true,
      });
      await page
        .getByRole("button", { name: "填入 Prompt", exact: true })
        .click();
      await page.waitForFunction(() =>
        document.querySelector("textarea")?.value.startsWith("只识别装甲板"),
      );
      check(true, "明确填入历史Prompt");
      await page.getByRole("button", { name: "撤销填充" }).click();
      await page.waitForFunction(() =>
        document.querySelector("textarea")?.value.includes("红方"),
      );
      check(true, "撤销Prompt填充");
      await page
        .getByRole("button", { name: "推理详情", exact: true })
        .first()
        .click();
      await page
        .getByRole("dialog", { name: "推理详情", exact: true })
        .waitFor();
      await page.getByText("请求历史", { exact: true }).waitFor();
      check(
        new URL(page.url()).pathname === "/datasets/1/preannotation",
        "推理详情留在当前页",
      );
      await page.screenshot({
        path: "output/playwright/migration/trace-dialog.png",
        fullPage: true,
      });
      await page
        .getByRole("dialog", { name: "推理详情", exact: true })
        .getByRole("button", { name: "关闭", exact: true })
        .click();
      await page.screenshot({
        path: "output/playwright/migration/preannotation.png",
        fullPage: true,
      });
      return {
        passed,
        errors: page.__migration.errors,
        unexpected: page.__migration.unexpected,
        warnings: page.__migration.warnings,
      };
    })(page),
  });

  // admin
  results.push({
    batch: "admin",
    result: await (async (page) => {
      const passed = [];
      const check = (condition, name) => {
        if (!condition) throw new Error(name);
        passed.push(name);
      };
      const diagnostics = page.__migration;
      await page.goto("http://127.0.0.1:5173/admin/export");
      await page
        .getByText("提交有效配置后，在此查看导出结果", { exact: true })
        .waitFor();
      check(true, "导出初始空状态");
      await page.getByRole("button", { name: "选择数据集" }).click();
      await page.getByRole("option").first().click();
      await page.getByRole("spinbutton", { name: "训练集" }).fill("0.6");
      await page.getByRole("spinbutton", { name: "训练集" }).press("Tab");
      await page.getByRole("button", { name: "开始导出", exact: true }).click();
      await page.getByText("分割比例之和必须为1", { exact: true }).waitFor();
      check(
        !diagnostics.requests.some(
          (r) => r.path === "/api/export" && r.method === "POST",
        ),
        "无效导出比例不提交",
      );
      await page.getByRole("spinbutton", { name: "训练集" }).fill("0.8");
      await page.getByRole("spinbutton", { name: "训练集" }).press("Tab");
      await page.getByRole("button", { name: "开始导出", exact: true }).click();
      await page
        .getByRole("heading", { name: "导出完成", exact: true })
        .waitFor();
      const download = page.waitForEvent("download");
      await page.getByRole("button", { name: "下载 ZIP 文件" }).click();
      await download;
      check(
        diagnostics.requests.some(
          (r) =>
            r.path === "/api/export/download/test-artifact" &&
            r.authorization === "Bearer local-test-token",
        ),
        "导出下载保留认证",
      );
      check(
        !diagnostics.requests.some((r) => r.path.startsWith("/api/api/")),
        "导出无重复API前缀",
      );
      await page.screenshot({
        path: "output/playwright/migration/export-ready.png",
        fullPage: true,
      });
      await page.getByRole("textbox", { name: "输出名称" }).fill("new-export");
      await page
        .getByText("提交有效配置后，在此查看导出结果", { exact: true })
        .waitFor();
      check(
        (await page.getByRole("button", { name: "下载 ZIP 文件" }).count()) ===
          0,
        "导出配置变更清空旧预览",
      );
      await page.goto("http://127.0.0.1:5173/admin/categories/1");
      await page.getByRole("button", { name: "添加类别", exact: true }).click();
      const dialog = page.getByRole("dialog", {
        name: "添加类别",
        exact: true,
      });
      await dialog.getByRole("textbox", { name: "名称" }).fill("测试类别");
      await dialog
        .getByRole("button", { name: "添加快捷键", exact: true })
        .click();
      await dialog.getByRole("button", { name: "请按下快捷键…" }).press("3");
      await dialog
        .getByRole("button", { name: "添加快捷键", exact: true })
        .click();
      await dialog.getByRole("button", { name: "请按下快捷键…" }).press("c");
      check(
        (await dialog
          .getByRole("button", { name: "3 ×", exact: true })
          .count()) === 1 &&
          (await dialog
            .getByRole("button", { name: "c ×", exact: true })
            .count()) === 1,
        "捕获多个类别快捷键",
      );
      await dialog
        .getByRole("button", { name: "添加快捷键", exact: true })
        .click();
      await dialog.getByRole("button", { name: "请按下快捷键…" }).press("1");
      await page
        .getByText("快捷键已被 蓝方机器人 使用", { exact: true })
        .waitFor();
      check(true, "类别快捷键冲突校验");
      await page.screenshot({
        path: "output/playwright/migration/category-dialog.png",
        fullPage: true,
      });
      await dialog.getByRole("button", { name: "确定", exact: true }).click();
      await dialog.waitFor({ state: "hidden" });
      check(
        diagnostics.requests.some(
          (r) => r.path === "/api/categories" && r.body?.shortcut_key === "3,c",
        ),
        "类别快捷键真实保存",
      );
      await page.goto("http://127.0.0.1:5173/profiles");
      await page
        .getByRole("heading", { name: "Qwen2.5-VL · 72B", exact: true })
        .waitFor();
      await page.getByRole("button", { name: "编辑配置" }).click();
      await page.getByRole("dialog", { name: "编辑推理接口" }).waitFor();
      await page
        .getByRole("textbox", { name: "配置名称" })
        .fill("Qwen2.5-VL · 编辑测试");
      await page.getByRole("button", { name: "保存配置", exact: true }).click();
      await page
        .getByRole("heading", { name: "Qwen2.5-VL · 编辑测试", exact: true })
        .waitFor();
      check(
        diagnostics.requests.some(
          (r) =>
            r.path === "/api/preannotation/profiles/1" && r.method === "PUT",
        ),
        "推理接口编辑持久化",
      );
      await page.getByRole("button", { name: "测试连接", exact: true }).click();
      await page.getByText("连接成功", { exact: true }).waitFor();
      check(true, "接口连接结果");
      await page.goto("http://127.0.0.1:5173/admin/users");
      await page
        .getByRole("textbox", { name: "搜索成员姓名或邮箱" })
        .fill("视觉组");
      check((await page.getByRole("row").count()) === 2, "成员搜索");
      await page.getByRole("button", { name: "设为管理员", exact: true }).click();
      await page.getByRole("alertdialog").waitFor();
      await page
        .getByRole("alertdialog")
        .getByRole("button", { name: "取消", exact: true })
        .click();
      check(
        !diagnostics.requests.some(
          (r) => r.path === "/api/admin/users/2" && r.method === "PUT",
        ),
        "取消权限更改不提交",
      );
      await page.goto("http://127.0.0.1:5173/datasets/1/settings");
      await page
        .getByRole("textbox", { name: "数据集名称" })
        .fill("RoboMaster · 编辑测试");
      await page.getByRole("button", { name: "保存设置", exact: true }).click();
      await page.getByText("数据集设置已保存", { exact: true }).waitFor();
      check(
        diagnostics.requests.some(
          (r) => r.path === "/api/datasets/1" && r.method === "PUT",
        ) &&
          diagnostics.requests.some(
            (r) => r.path === "/api/dataset-configs/" && r.method === "POST",
          ),
        "数据集基础与格式设置真实保存",
      );
      return {
        passed,
        errors: diagnostics.errors,
        unexpected: diagnostics.unexpected,
        warnings: diagnostics.warnings,
      };
    })(page),
  });

  // editor
  results.push({
    batch: "editor",
    result: await (async (page) => {
      const passed = [];
      const check = (condition, name) => {
        if (!condition) throw new Error(name);
        passed.push(name);
      };
      const diagnostics = page.__migration;
      await page.goto(
        "http://127.0.0.1:5173/annotate/1?source=preannotation&task=24&image=1&review_status=all",
      );
      await page.locator(".canvas-container canvas").waitFor();
      await page.waitForFunction(
        () => document.querySelector(".canvas-container canvas")?.height > 0,
      );
      await page.getByRole("radio", { name: "矩形工具", exact: true }).click();
      const box = await page.locator(".canvas-container canvas").boundingBox();
      const draw = async () => {
        await page.mouse.move(
          box.x + box.width * 0.63,
          box.y + box.height * 0.45,
        );
        await page.mouse.down();
        await page.mouse.move(
          box.x + box.width * 0.75,
          box.y + box.height * 0.6,
          { steps: 5 },
        );
        await page.mouse.up();
      };
      const count = await page.locator(".annotation-item").count();
      await draw();
      const picker = page.getByRole("dialog", { name: "选择目标类别" });
      await picker.waitFor();
      check(true, "多类别默认画后选类");
      await page.screenshot({
        path: "output/playwright/migration/quick-category.png",
        fullPage: true,
      });
      await page.keyboard.press("Escape");
      await picker.waitFor({ state: "hidden" });
      check(
        (await page.locator(".annotation-item").count()) === count,
        "取消画后选类不新增对象",
      );
      await draw();
      await picker.waitFor();
      await picker.locator(".category-card").first().click();
      await page.waitForFunction(
        (n) => document.querySelectorAll(".annotation-item").length === n + 1,
        count,
      );
      check(true, "选择类别新增对象");
      await page.getByRole("button", { name: "撤销", exact: true }).click();
      check(
        (await page.locator(".annotation-item").count()) === count,
        "撤销绘制",
      );
      await page.getByRole("button", { name: "重做", exact: true }).click();
      check(
        (await page.locator(".annotation-item").count()) === count + 1,
        "重做绘制",
      );
      const reviewBefore = diagnostics.requests.filter((r) =>
        r.path.endsWith("/review"),
      ).length;
      await page
        .getByRole("button", { name: "保存草稿", exact: false })
        .click();
      await page
        .getByText("审核草稿已保存；尚未审核通过", { exact: true })
        .waitFor();
      check(
        diagnostics.requests.filter((r) => r.path.endsWith("/review"))
          .length === reviewBefore,
        "草稿保存不通过审核",
      );
      check(
        new URL(page.url()).searchParams.get("image") === "1",
        "草稿保存不切换图片",
      );
      await page.getByRole("button", { name: "放大", exact: true }).click();
      await page.getByRole("button", { name: "适应画布", exact: true }).click();
      check(true, "放大与适应画布");
      await page.getByRole("checkbox", { name: "候选框 · 虚线" }).uncheck();
      await page.getByRole("checkbox", { name: "候选框 · 虚线" }).check();
      check(true, "候选图层切换");
      await page
        .getByRole("button", { name: "完整推理记录", exact: true })
        .click();
      await page
        .getByRole("dialog", { name: "推理详情", exact: true })
        .getByText("请求历史", { exact: true })
        .waitFor();
      await page.keyboard.press("Escape");
      check(
        new URL(page.url()).pathname === "/annotate/1",
        "工作台推理详情不离页",
      );
      await page.screenshot({
        path: "output/playwright/migration/annotate.png",
        fullPage: true,
      });
      await page
        .getByRole("button", { name: "审核通过并下一张", exact: true })
        .click();
      await page.waitForURL(/image=2/);
      check(
        diagnostics.requests.some(
          (r) =>
            r.path === "/api/preannotation/tasks/24/images/1/review" &&
            r.body.action === "approve",
        ),
        "显式审核通过并切换",
      );
      check(
        diagnostics.requests.some(
          (r) =>
            r.path === "/api/datasets/1/images" &&
            new URLSearchParams(r.search).get("page_size") === "3",
        ),
        "预加载后续3张图片",
      );
      await page.goto("http://127.0.0.1:5173/annotate/1?source=manual&image=7");
      await page.locator(".canvas-container canvas").waitFor();
      await page
        .getByRole("radio", { name: "人工标注", exact: true })
        .waitFor();
      check(true, "人工标注共用工作台");
      await page.getByRole("button", { name: "快捷键", exact: true }).click();
      await page.getByRole("dialog", { name: "快捷键设置" }).waitFor();
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: "帮助", exact: true }).click();
      await page.getByRole("dialog", { name: "快捷键帮助" }).waitFor();
      await page.keyboard.press("Escape");
      check(true, "工作台快捷键设置与帮助弹窗");
      await page.screenshot({
        path: "output/playwright/migration/manual.png",
        fullPage: true,
      });
      return {
        passed,
        errors: diagnostics.errors,
        unexpected: diagnostics.unexpected,
        warnings: diagnostics.warnings,
      };
    })(page),
  });

  // errors
  results.push({
    batch: "errors",
    result: await (async (page) => {
      const passed = [];
      const check = (condition, name) => {
        if (!condition) throw new Error(name);
        passed.push(name);
      };
      const diagnostics = page.__migration;
      await page.setViewportSize({ width: 1600, height: 1100 });
      let fail = true;
      await page.route("**/api/datasets", async (route) => {
        if (fail) {
          fail = false;
          return route.fulfill({
            status: 500,
            json: { detail: "测试服务暂时不可用" },
          });
        }
        return route.fallback();
      });
      await page.goto("http://127.0.0.1:5173/");
      await page.getByText("数据集加载失败", { exact: true }).waitFor();
      await page.getByRole("button", { name: "重新加载", exact: true }).click();
      await page.locator(".dataset-card").first().waitFor();
      check(true, "API错误提示与重新加载");
      await page.unroute("**/api/datasets");
      await page.goto(
        "http://127.0.0.1:5173/datasets/1/preannotation?task=24&page=2&review_status=unreviewed",
      );
      await page
        .getByRole("textbox", { name: "Prompt", exact: true })
        .waitFor();
      await page.waitForFunction(
        () => !document.querySelector("[data-loading]"),
      );
      check(
        new URL(page.url()).searchParams.get("page") === "2" &&
          new URL(page.url()).searchParams.get("review_status") ===
            "unreviewed",
        "返回批次保留分页与筛选",
      );
      await page.goto(
        "http://127.0.0.1:5173/annotate/1?source=preannotation&task=24&image=3&review_status=all",
      );
      await page.locator(".canvas-container canvas").waitFor();
      const initial = await page.locator(".annotation-item").count();
      await page
        .getByRole("button", { name: "删除标注框", exact: true })
        .first()
        .click();
      check(
        (await page.locator(".annotation-item").count()) === initial - 1,
        "删除候选对象",
      );
      let conflict = true;
      const draft = "**/api/preannotation/tasks/24/images/3/draft";
      await page.route(draft, async (route) => {
        if (conflict) {
          conflict = false;
          return route.fulfill({
            status: 409,
            json: { detail: "修订冲突，请重新加载" },
          });
        }
        return route.fallback();
      });
      await page
        .getByRole("button", { name: "保存草稿", exact: false })
        .click();
      await page.getByText("修订冲突，请重新加载", { exact: true }).waitFor();
      check(
        (await page.locator(".annotation-item").count()) === initial - 1 &&
          new URL(page.url()).searchParams.get("image") === "3",
        "修订冲突保留本地修改与当前图片",
      );
      await page.unroute(draft);
      await page.getByRole("button", { name: "返回", exact: true }).click();
      await page.getByRole("alertdialog").waitFor();
      await page.keyboard.press("Escape");
      await page.getByRole("alertdialog").waitFor({ state: "hidden" });
      check(
        new URL(page.url()).pathname === "/annotate/1",
        "Escape取消离页并保留编辑",
      );
      await page.getByRole("button", { name: "撤销", exact: true }).click();
      await page.getByRole("button", { name: "快捷键", exact: true }).click();
      await page.getByRole("dialog", { name: "快捷键设置" }).waitFor();
      await page.keyboard.press("Delete");
      await page.keyboard.press("Escape");
      check(
        (await page.locator(".annotation-item").count()) === initial,
        "弹窗按键不删除画布对象",
      );
      await page.goto("http://127.0.0.1:5173/admin/datasets?create=1");
      const dialog = page.getByRole("dialog", {
        name: "创建数据集",
        exact: true,
      });
      await dialog.waitFor();
      await dialog
        .locator("input[type=file]")
        .first()
        .setInputFiles("docs/ui-redesign/assets");
      await dialog.getByText(/assets · 已读取/).waitFor();
      check(true, "目录选择读取名称与文件列表");
      await dialog.getByRole("button", { name: "取消", exact: true }).click();
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto("http://127.0.0.1:5173/admin/datasets");
      await page.getByRole("button", { name: "打开导航", exact: true }).click();
      await page.getByRole("button", { name: "推理接口", exact: true }).click();
      await page
        .getByRole("heading", { name: "推理接口", exact: true })
        .waitFor();
      check(true, "移动导航切换页面");
      return {
        passed,
        errors: diagnostics.errors,
        unexpected: diagnostics.unexpected,
        warnings: diagnostics.warnings,
      };
    })(page),
  });

  // additional
  results.push({
    batch: "additional",
    result: await (async (page) => {
      const passed = [];
      const check = (condition, name) => {
        if (!condition) throw new Error(name);
        passed.push(name);
      };
      const diagnostics = page.__migration;
      await page.setViewportSize({ width: 1600, height: 1100 });
      await page.goto("http://127.0.0.1:5173/annotate/1?source=manual&image=7");
      await page.locator(".canvas-container canvas").waitFor();
      const box = await page.locator(".canvas-container canvas").boundingBox();
      const at = async (x, y) =>
        page.mouse.click(box.x + box.width * x, box.y + box.height * y);
      await page.getByRole("radio", { name: "四点工具", exact: true }).click();
      for (const [x, y] of [
        [0.3, 0.4],
        [0.4, 0.4],
        [0.4, 0.5],
        [0.3, 0.5],
      ])
        await at(x, y);
      const picker = page.getByRole("dialog", { name: "选择目标类别" });
      await picker.waitFor();
      await picker.locator(".category-card").first().click();
      check(
        (await page.locator(".annotation-item").count()) === 1,
        "四点绘制接入原画布",
      );
      await page.getByRole("radio", { name: "八点工具", exact: true }).click();
      for (const [x, y] of [
        [0.5, 0.4],
        [0.65, 0.4],
        [0.65, 0.4],
        [0.65, 0.55],
        [0.65, 0.55],
        [0.5, 0.55],
        [0.5, 0.55],
        [0.5, 0.4],
      ])
        await at(x, y);
      await picker.waitFor();
      await picker.locator(".category-card").first().click();
      check(
        (await page.locator(".annotation-item").count()) === 2,
        "八点交线绘制接入原画布",
      );
      await page.getByRole("button", { name: "返回", exact: true }).click();
      await page
        .getByRole("alertdialog")
        .getByRole("button", { name: "放弃修改", exact: true })
        .click();
      await page.waitForURL("http://127.0.0.1:5173/");
      check(true, "放弃修改后离开工作台");
      await page.route("**/api/datasets/1", (route) =>
        route.fulfill({
          json: {
            id: 1,
            name: "抽样测试数据集",
            total_images: 128,
            labeled_images: 6,
            is_active: true,
          },
        }),
      );
      await page.goto("http://127.0.0.1:5173/datasets/1/preannotation?task=24");
      await page
        .getByRole("spinbutton", { name: "抽样数量", exact: true })
        .fill("35");
      await page
        .getByRole("spinbutton", { name: "抽样数量", exact: true })
        .press("Tab");
      await page.getByRole("button", { name: "抽样验证", exact: true }).click();
      await page
        .getByText("抽样任务已提交，可查看叠加效果", { exact: true })
        .waitFor();
      check(
        diagnostics.requests.some(
          (r) =>
            r.path === "/api/datasets/1/preannotation-tasks" &&
            r.method === "POST" &&
            r.body.sample_size === 35,
        ),
        "自定义35张抽样提交",
      );
      await page.unroute("**/api/datasets/1");
      await page.goto("http://127.0.0.1:5173/register");
      await page
        .getByRole("textbox", { name: "用户名", exact: true })
        .fill("migration-test");
      await page
        .getByRole("textbox", { name: "密码", exact: true })
        .fill("123456");
      await page
        .getByRole("textbox", { name: "确认密码", exact: true })
        .fill("654321");
      await page.getByRole("button", { name: "创建账号", exact: true }).click();
      await page.getByText("两次输入的密码不一致", { exact: true }).waitFor();
      check(
        !diagnostics.requests.some((r) => r.path === "/api/auth/register"),
        "注册密码不一致不提交",
      );
      await page
        .getByRole("textbox", { name: "确认密码", exact: true })
        .fill("123456");
      await page.getByRole("button", { name: "创建账号", exact: true }).click();
      await page.waitForURL("http://127.0.0.1:5173/login");
      check(
        diagnostics.requests.some((r) => r.path === "/api/auth/register"),
        "注册调用真实接口",
      );
      await page
        .getByRole("textbox", { name: "用户名", exact: true })
        .fill("migration-test");
      await page
        .getByRole("textbox", { name: "密码", exact: true })
        .fill("123456");
      await page.getByRole("button", { name: "显示密码", exact: true }).click();
      check(
        (await page
          .getByRole("textbox", { name: "密码", exact: true })
          .getAttribute("type")) === "text",
        "密码可见性切换",
      );
      await page
        .getByRole("textbox", { name: "密码", exact: true })
        .press("Enter");
      await page.waitForURL("http://127.0.0.1:5173/");
      check(
        diagnostics.requests.some((r) => r.path === "/api/auth/login"),
        "Enter提交登录",
      );
      await page.getByRole("button", { name: "搜索页面与功能 ⌘ K" }).click();
      await page
        .getByRole("textbox", { name: "搜索页面与功能" })
        .fill("推理接口");
      await page
        .getByRole("dialog", { name: "搜索工作空间" })
        .getByRole("button", { name: "推理接口", exact: true })
        .click();
      await page.waitForURL("http://127.0.0.1:5173/profiles");
      check(true, "工作空间搜索导航");
      await page.getByRole("button", { name: "退出登录", exact: true }).click();
      await page.waitForURL("http://127.0.0.1:5173/login");
      check(true, "退出登录清除会话");
      const annotator = {
        id: 2,
        username: "标注成员",
        is_admin: false,
        is_active: true,
      };
      await page.route("**/api/auth/login", (route) =>
        route.fulfill({
          json: { access_token: "annotator-test-token", user: annotator },
        }),
      );
      await page.route("**/api/auth/me", (route) =>
        route.fulfill({ json: annotator }),
      );
      await page
        .getByRole("textbox", { name: "用户名", exact: true })
        .fill("annotator");
      await page
        .getByRole("textbox", { name: "密码", exact: true })
        .fill("123456");
      await page
        .getByRole("button", { name: "登录工作空间", exact: true })
        .click();
      await page.waitForURL("http://127.0.0.1:5173/");
      check(
        (await page
          .getByRole("button", { name: "工作空间成员", exact: true })
          .count()) === 0,
        "标注员不显示管理入口",
      );
      const adminRequests = diagnostics.requests.filter((r) =>
        r.path.startsWith("/api/admin/"),
      ).length;
      await page.evaluate(() => {
        history.pushState({}, "", "/admin/users");
        window.dispatchEvent(new PopStateEvent("popstate"));
      });
      await page.waitForURL("http://127.0.0.1:5173/");
      check(
        diagnostics.requests.filter((r) => r.path.startsWith("/api/admin/"))
          .length === adminRequests,
        "标注员访问管理路由被拦截",
      );
      await page.unroute("**/api/auth/login");
      await page.unroute("**/api/auth/me");
      return {
        passed,
        errors: diagnostics.errors,
        unexpected: diagnostics.unexpected,
        warnings: diagnostics.warnings,
      };
    })(page),
  });

  // responsive
  results.push({
    batch: "responsive",
    result: await (async (page) => {
      const results = [];
      const diagnostics = page.__migration;
      await page.addInitScript(() => {
        if (["/login", "/register"].includes(location.pathname)) {
          localStorage.removeItem("robomark-token");
          localStorage.removeItem("robomark-user");
        }
      });
      const routes = [
        ["home", "/"],
        ["dashboard", "/admin"],
        ["datasets", "/admin/datasets"],
        ["dataset-detail", "/datasets/1"],
        ["preannotation", "/datasets/1/preannotation?task=24"],
        [
          "annotate",
          "/annotate/1?source=preannotation&task=24&image=2&review_status=all",
        ],
        ["manual", "/annotate/1?source=manual&image=7"],
        ["categories", "/admin/categories/1"],
        ["members", "/admin/users"],
        ["export", "/admin/export"],
        ["profiles", "/profiles"],
        ["settings", "/datasets/1/settings"],
        ["tutorial", "/tutorial"],
        ["login", "/login"],
        ["register", "/register"],
      ];
      for (const [width, height] of [
        [1600, 1100],
        [768, 1024],
        [390, 844],
      ]) {
        await page.setViewportSize({ width, height });
        for (const [name, path] of routes) {
          await page.goto("http://127.0.0.1:5173" + path);
          await page.locator("h1:visible,h2:visible").first().waitFor();
          await page.waitForFunction(
            () => !document.querySelector("[data-loading]"),
          );
          await page.evaluate(async () => {
            for (const image of document.images) image.loading = "eager";
            await Promise.all(
              [...document.images].map((image) =>
                image.decode().catch(() => {}),
              ),
            );
          });
          const result = await page.evaluate(() => ({
            width: innerWidth,
            scroll: document.documentElement.scrollWidth,
            broken: [...document.images]
              .filter((image) => image.complete && !image.naturalWidth)
              .map((image) => image.src),
            body: document.body.innerText.length,
          }));
          results.push({ name, width, ...result });
          if (
            result.scroll > width + 1 ||
            result.broken.length ||
            result.body < 80
          )
            throw new Error(JSON.stringify(results.at(-1)));
          await page.screenshot({
            path: `output/playwright/migration/${name}-${width}.png`,
            fullPage: true,
          });
        }
      }
      return {
        checks: results.length,
        results,
        errors: diagnostics.errors,
        unexpected: diagnostics.unexpected,
        warnings: diagnostics.warnings,
      };
    })(page),
  });
  const diagnostics = page.__migration;
  if (
    diagnostics.errors.length ||
    diagnostics.unexpected.length ||
    diagnostics.warnings.length
  )
    throw new Error(JSON.stringify(diagnostics));
  return {
    results,
    requests: diagnostics.requests.length,
    errors: diagnostics.errors,
    unexpected: diagnostics.unexpected,
    warnings: diagnostics.warnings,
  };
}
