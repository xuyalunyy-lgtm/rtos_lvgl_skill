# 测试：生成模块

## 输入
- 模块列表：audio_player, display_mgr
- 期望触发：module_contract_gen.py --modules

## 验收条件
- [ ] module_contract_gen.py 正常退出
- [ ] 生成 audio_player_contract.h
- [ ] 生成 audio_player_fsm.c
- [ ] 生成 display_mgr_contract.h
- [ ] 生成 display_mgr_fsm.c
- [ ] 生成 modules_init.c
- [ ] modules_init.c 包含 audio_player_init 和 display_mgr_init
- [ ] 无 Python traceback

## 自动化命令
```bash
python tools/module_contract_gen.py --modules audio_player display_mgr --outdir forward_tests/out_modules
```
