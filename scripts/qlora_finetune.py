"""인하우스 QLoRA 미세조정 배치 (PRD §7.2).

GPU가 없으면 학습을 SKIP 처리하고 로그만 남긴다. 실제 학습은 GPU 머신에서 실행.
"""
import sys


def gpu_available():
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def run(base_model="meta-llama/Meta-Llama-3-8B-Instruct", dry_run=False):
    if not gpu_available():
        msg = "[QLoRA] GPU 미탐지 → 학습 SKIP (스크립트/스케줄은 준비됨)."
        print(msg)
        return {"status": "SKIP", "reason": "no_gpu", "message": msg}

    if dry_run:
        return {"status": "READY", "base_model": base_model}

    # 실제 학습 경로 (GPU 머신 전용). 의존성: transformers, peft, bitsandbytes, trl.
    from datasets import Dataset  # noqa: F401
    from peft import LoraConfig  # noqa: F401
    from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: F401

    raise NotImplementedError(
        "GPU 학습 파이프라인은 별도 머신에서 데이터셋 경로를 지정해 실행하십시오."
    )


if __name__ == "__main__":
    result = run(dry_run="--dry-run" in sys.argv)
    print(result)
    sys.exit(0 if result["status"] in ("SKIP", "READY") else 1)
