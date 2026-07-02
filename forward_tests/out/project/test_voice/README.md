# test_voice

基础功能 MVP 项目。

## 构建

```bash
# esp32 构建命令
# TODO: 根据平台填写
```

## 约束覆盖

- C8: 启动顺序（Queue 先于回调）
- C12: 错误处理（返回值检查）
- C14: 日志规范（LOG_* + TAG）
- C29: 模块契约
- C33: 生命周期对称

## 目录结构

```
test_voice/
├── CMakeLists.txt
├── constraint_manifest.json
├── main/
│   ├── CMakeLists.txt
│   ├── main.c
│   ├── app_mvp.h
│   └── task_topology.h
└── README.md
```
