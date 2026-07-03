# L2 自修复工作流

> 检测 → 诊断 → 修复 → 验证全自动闭环

## 适用场景

用户要求「自动修复」「自动修 bug」「一键修复」时使用本 workflow。

## 前置条件

- 项目有 .c 源文件
- 已安装 FreeRTOS Skill（`tools/` 目录可用）
- 用户明确同意自动修改代码

## Step 1: 扫描违规

运行所有 checker，收集违规列表：

```bash
python tools/run_review.py --dir <project_dir> --json > violations.json
```

统计违规总数和分布：

```bash
python tools/constraint_inference.py --changed-files <violated_files> --json > inference.json
```

## Step 2: 分级处理

根据违规严重度分级：

| 级别 | 处理方式 | 说明 |
|------|----------|------|
| P0 | 必须修复 | 死机/泄漏/阻塞风险 |
| P1 | 建议修复 | 量产问题 |
| P2 | 可选修复 | 可维护性 |

## Step 3: 自动修复（高置信度）

对以下违规类型，自动应用修复：

### 3.1 cJSON 泄漏 (C3)

```bash
python tools/auto_fix_engine.py <file> --checker cjson_leak
```

修复模式：添加 `goto cleanup` + `cJSON_Delete`

### 3.2 返回值未检查 (C12)

```bash
python tools/auto_fix_engine.py <file> --checker return_check
```

修复模式：添加 `if (ret != pdPASS)` 检查

### 3.3 生命周期不对称 (C33)

```bash
python tools/auto_fix_engine.py <file> --checker lifecycle
```

修复模式：添加对应的 deinit 函数

### 3.4 OTA 安全 (C22)

```bash
python tools/auto_fix_engine.py <file> --checker ota
```

修复模式：添加签名验证 + mark_valid

## Step 4: 人工确认（中置信度）

对以下违规类型，仅提供建议，需人工确认：

| 违规类型 | 建议方式 |
|----------|----------|
| C8 启动顺序 | 输出 reorder 建议 |
| C15 优先级 | 输出 mutex 替换建议 |
| C32 可观测性 | 输出字段添加建议 |
| C39 配置矩阵 | 输出归类建议 |

## Step 5: 验证修复

修复后自动重跑 checker 验证：

```bash
python tools/run_review.py --dir <project_dir> --self-test
python tools/run_review.py --dir <project_dir> --validate-examples
```

## Step 6: 输出报告

生成修复报告：

```markdown
## 自修复报告

### 修复统计
- 扫描文件数: N
- 发现违规数: M
- 自动修复数: X
- 人工确认数: Y
- 修复后违规数: Z

### 修复详情
| 文件 | 违规 | 修复方式 | 状态 |
|------|------|----------|------|
| ... | ... | ... | fixed/skipped |

### 剩余人工项
- [ ] ...
```

## 回滚机制

修复前自动 git stash：

```bash
git stash push -m "auto-repair-<timestamp>"
```

修复失败时回滚：

```bash
git stash pop
```

## 约束引用

- C3: cJSON 防泄漏
- C8: 启动顺序
- C12: 错误处理
- C15: 任务优先级
- C22: OTA 安全
- C32: 可观测性
- C33: 生命周期对称
- C39: 配置矩阵
