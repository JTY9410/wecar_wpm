# LLM 자동 장애 전환 설계

**Date:** 2026-08-03  
**Status:** Approved (user chose option 1)

## Goal

활성 AI가 답변하지 못하면 키가 등록된 다른 AI로 자동 전환해 시스템 운영이 끊기지 않게 한다.

## Behavior

1. LLM 호출은 활성 provider부터 시도한다.
2. `LLMError` 시 키가 설정된 나머지 provider를 `gemini → openai → claude` 순으로 시도한다.
3. 대체 성공 시 해당 provider를 `set_active`로 승격한다.
4. 전부 실패 시 기존 graceful 오류를 반환한다.
5. 응답에 `provider`, 필요 시 `failover_from`을 포함한다.

## Scope

- `llm_hub.generate_with_failover` + forecast/summary/report 경로
- Admin UI에 자동 전환 안내 문구
- Out of scope: i18n Gemini 하드코딩 경로
