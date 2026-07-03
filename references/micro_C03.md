# C03 cJSON 生命周期微分片

> ~800 tokens。完整规则见 `constraint_review.md`。

## 典型症状

- 堆持续下降，cJSON_Parse 后无 cJSON_Delete
- goto cleanup 路径遗漏 cJSON_Delete
- 循环中 cJSON_Parse 未在每次迭代释放

## 危险模式

```c
// ❌ 泄漏：early return 未释放
cJSON *root = cJSON_Parse(json);
if (root == NULL) return -1;
cJSON *item = cJSON_GetObjectItem(root, "key");
if (item == NULL) return -1;  // 泄漏！
cJSON_Delete(root);
```

## 修复模板

```c
// ✅ goto cleanup 模式
cJSON *root = NULL;
root = cJSON_Parse(json);
if (root == NULL) goto cleanup;
// ... 使用 root ...
ret = 0;
cleanup:
    if (root) cJSON_Delete(root);
    return ret;
```

## 相关 Checker / Example

- `cjson_leak_checker.py` — 自动检测
- `examples/bad_cjson_leak.c` — 反例
- `examples/good_cjson_parse.c` — 正例

## 升级到完整 Shard

需要 cJSON_Create* 泄漏、嵌套对象释放、strdup 失败路径时 → 加载 `constraint_review.md`
