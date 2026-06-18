## Step 3 — 代码生成与落地（Lite）

**默认：** [core_rules.md](../references/core_rules.md) **自主实施模式** — 按 scene prompt 手写骨架，直接写入用户工程。

**Lite 限制：** 无 `examples/`、`tools/`、`mvp_codegen`、`run_review`；按 [lite_manual_checklist.md](../references/lite_manual_checklist.md) 完成人工审查。

## Step 4 — 编译闭环（必做）

按 `platforms/xxx.md` 执行编译；失败则修错重编，直至 **0 error**。

## Step 5 — 人工校验（Lite）

执行 [lite_manual_checklist.md](../references/lite_manual_checklist.md)，并按已加载 prompt 手工核对 C1/C2/C3/C4 等约束。
