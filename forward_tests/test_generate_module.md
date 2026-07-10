# Test: Generate Module

## Input
- Module list: audio_player, display_mgr
- Expected trigger: module_contract_gen.py --modules

## Acceptance Criteria
- [ ] module_contract_gen.py exits normally
- [ ] Generates audio_player_contract.h
- [ ] Generates audio_player_fsm.c
- [ ] Generates display_mgr_contract.h
- [ ] Generates display_mgr_fsm.c
- [ ] Generates modules_init.c
- [ ] modules_init.c contains audio_player_init and display_mgr_init
- [ ] No Python traceback

## Automation Command
```bash
python tools/module_contract_gen.py --modules audio_player display_mgr --outdir forward_tests/out_modules
```
