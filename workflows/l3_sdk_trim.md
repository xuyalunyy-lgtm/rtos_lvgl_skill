# Workflow: L3 SDK 搭建 / Demo 改造 / 裁剪

**触发：** 新工程、SDK Demo 改造、删模块、sdkconfig/Makefile 裁剪、JL/BK 扫描。

<thinking>
1. 必须先问卷，禁止直接给删除清单
2. JL/BK 强制 Phase A 全景扫描
3. 裁剪每步编译冒烟后再写业务
</thinking>

## Step 1 — 产品需求问卷

读取并执行 [sdk_trim_prune.txt](../prompts/sdk_trim_prune.txt) **Step -1 问卷**。未确认项标注 `[假设]`。

## Step 2 — 平台专档

读取对应 [platforms/](../platforms/) 专档（JL 含 AC79/WL82/AC791N）。

## Step 3 — SDK 扫描与裁剪表

- JL/BK：**强制** Phase A 模块地图
- 输出需求驱动裁剪表（非固定删除清单）
- 每步验证：编译 / 冒烟 / `idf.py size` 或 map 对比

## Step 4 — 输出

按 [core_rules.md](../references/core_rules.md) L3 模板输出前几节：

```markdown
## 产品需求（问卷/假设）
## SDK 模块地图（JL/BK 扫描）
## 需求驱动裁剪表
## 架构核对 + 优先级 + 文件归属
```

**裁剪通过前不写业务代码。**
