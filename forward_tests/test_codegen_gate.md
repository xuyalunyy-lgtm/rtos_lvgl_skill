# 测试：Codegen Gate 约束驱动生成

## 输入
- 项目：tools/fixtures/mini_esp32
- 工具：project_scaffold.py + codegen_gate.py
- 期望触发：生成 → manifest → gate → 通过/失败

## 验收条件
- [ ] project_scaffold.py --name test --platform esp32 生成 generation_manifest.json
- [ ] generation_manifest.json 包含 schema_version、generator、platform、generated_files、constraints
- [ ] codegen_gate.py --self-test 5 项全绿
- [ ] codegen_gate.py --dir <生成目录> --manifest <manifest> --strict 对合法代码通过
- [ ] codegen_gate.py 对含裸 portMAX_DELAY 的代码拒绝
- [ ] codegen_gate.py 对缺文件的 manifest 拒绝
- [ ] codegen_gate.py 对缺必填字段的 manifest 拒绝
- [ ] codegen_gate.py 对约束未覆盖（strict 模式）拒绝
- [ ] 无 Python traceback

## 自动化命令
```bash
python tools/codegen_gate.py --self-test
python tools/project_scaffold.py --name gate_test --platform esp32 --outdir /tmp/gate_test
python tools/codegen_gate.py --dir /tmp/gate_test/gate_test --manifest /tmp/gate_test/gate_test/generation_manifest.json --platform esp32 --strict
```
