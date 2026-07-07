# FreeRTOS Runtime Guide

## Scope
This doc is the canonical platform/runtime reference for FreeRTOS-based projects in this skill.

## Core Notes
- Default scheduler and task model follow FreeRTOS vanilla API.
- Validate interrupt/service interactions with `FromISR` variants.
- Treat heap behavior and stack usage as explicit constraints in reviews.
- For cross-reference with MCU-specific quirks, load corresponding platform docs.

## Priority
- Keep UI/audio/network task priorities deterministic.
- Pin critical tasks if the BSP requires multi-core affinity.
