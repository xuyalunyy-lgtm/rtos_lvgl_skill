# Workflow: L3 SDK 搭建 / Demo 改造 / 裁剪

**触发：** 新工程 / SDK Demo 改造 / 删模块 / sdkconfig/Makefile 裁剪 / JL/BK 扫描 / SDK trimming

```yaml
# Workflow Input Schema
inputs:
  required:
    - name: platform
      type: enum[esp32, stm32, jl, bk]
      description: 目标平台
    - name: product_description
      type: string
      description: 产品功能描述（用于判断哪些模块需要保留）
  optional:
    - name: sdk_path
      type: string
      description: SDK 路径（JL/BK 强制需要）
    - name: existing_config
      type: string
      description: 现有 sdkconfig/Makefile 路径

# Workflow Output Schema
outputs:
  format: markdown
  sections:
    - 产品需求问卷结果
    - 保留/裁剪驱动列表
    - 裁剪步骤（逐步编译冒烟）
    - 裁剪后编译验证结果
  verification: 裁剪后编译通过 + 核心功能不受影响
```

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
- 内存缩池顺序 → [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt)（C7.2、C7.6）

## Step 4 — 输出

按 [core_rules.md](../references/core_rules.md) L3 模板输出前几节：

```markdown
## 产品需求（问卷/假设）
## SDK 模块地图（JL/BK 扫描）
## 需求驱动裁剪表
## 架构核对 + 优先级 + 文件归属
```

**裁剪通过前不写业务代码。**

---
验收标准：[acceptance_criteria.md](../references/acceptance_criteria.md#sdk-trimmingl3_sdk_trim)
