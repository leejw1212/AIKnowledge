#!/usr/bin/env python3
"""새 모델이 B300 서버에 들어가는지, 동시 사용자를 몇 명 받을 수 있는지 대략 계산한다.

사용 예:
  # Hugging Face 모델의 config.json을 내려받아 넣는 방법
  python3 tools/fit_check.py --config config.json --params-b 70 --weight-dtype fp8 --context 32768

  # config.json 없이 구조 값을 직접 넣는 방법 (Llama 3.1 70B 예시)
  python3 tools/fit_check.py --params-b 70 --layers 80 --kv-heads 8 --head-dim 128 --weight-dtype fp8

결과는 이론값이다. 실제로는 활성화 메모리, CUDA 그래프, 엔진 오버헤드 때문에 더 적게 들어간다.
"""
import argparse
import json

DTYPE_BYTES = {"fp32": 4, "bf16": 2, "fp16": 2, "fp8": 1, "int8": 1, "fp4": 0.5, "int4": 0.5}

# B300.md 기준값
GPU_USABLE_GB = 270
GPU_HBM_TBPS = 8.0


def kv_bytes_per_token(cfg, kv_dtype_bytes):
    layers = cfg["layers"]
    if cfg.get("kv_lora_rank"):
        # MLA (DeepSeek 계열): 레이어마다 압축된 잠재 벡터 하나만 저장한다
        per_layer = cfg["kv_lora_rank"] + cfg.get("qk_rope_head_dim", 0)
        return layers * per_layer * kv_dtype_bytes
    # 일반 어텐션: 레이어마다 K와 V 두 개
    return 2 * layers * cfg["kv_heads"] * cfg["head_dim"] * kv_dtype_bytes


def load_config(path):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    raw = raw.get("text_config", raw)
    heads = raw["num_attention_heads"]
    return {
        "layers": raw["num_hidden_layers"],
        "kv_heads": raw.get("num_key_value_heads", heads),
        "head_dim": raw.get("head_dim") or raw["hidden_size"] // heads,
        "kv_lora_rank": raw.get("kv_lora_rank"),
        "qk_rope_head_dim": raw.get("qk_rope_head_dim"),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", help="Hugging Face config.json 경로")
    p.add_argument("--params-b", type=float, required=True, help="총 파라미터 수 (단위: 10억)")
    p.add_argument("--active-params-b", type=float, help="MoE의 토큰당 활성 파라미터 수 (단위: 10억)")
    p.add_argument("--layers", type=int)
    p.add_argument("--kv-heads", type=int)
    p.add_argument("--head-dim", type=int)
    p.add_argument("--weight-dtype", default="fp8", choices=DTYPE_BYTES)
    p.add_argument("--kv-dtype", default="fp8", choices=DTYPE_BYTES)
    p.add_argument("--context", type=int, default=32768, help="사용자 한 명의 최대 토큰 수 (입력+출력)")
    p.add_argument("--gpus", type=int, default=8)
    p.add_argument("--gpu-mem-gb", type=float, default=GPU_USABLE_GB)
    p.add_argument("--reserve", type=float, default=0.10, help="엔진 오버헤드용 여유 비율")
    a = p.parse_args()

    if a.config:
        cfg = load_config(a.config)
    elif a.layers and a.kv_heads and a.head_dim:
        cfg = {"layers": a.layers, "kv_heads": a.kv_heads, "head_dim": a.head_dim}
    else:
        p.error("--config 또는 --layers/--kv-heads/--head-dim 을 넣어 주세요")

    w_bytes = DTYPE_BYTES[a.weight_dtype]
    weights_gb = a.params_b * w_bytes
    total_gb = a.gpus * a.gpu_mem_gb
    usable_gb = total_gb * (1 - a.reserve)
    kv_token = kv_bytes_per_token(cfg, DTYPE_BYTES[a.kv_dtype])
    kv_user_gb = kv_token * a.context / 1e9
    kv_room_gb = usable_gb - weights_gb

    print(f"GPU {a.gpus}장, 사용 가능 메모리 {total_gb:,.0f} GB (여유 {a.reserve:.0%} 제외 {usable_gb:,.0f} GB)")
    print(f"가중치 ({a.weight_dtype}): {weights_gb:,.1f} GB")
    print(f"KV 캐시 ({a.kv_dtype}): 토큰당 {kv_token / 1024:,.1f} KB, 사용자 1명({a.context:,} 토큰) {kv_user_gb:,.2f} GB")
    if kv_room_gb <= 0:
        print(f"결과: 들어가지 않음. 가중치만으로 {-kv_room_gb:,.0f} GB 초과. 더 낮은 정밀도나 GPU 추가가 필요합니다.")
        return
    users = int(kv_room_gb // kv_user_gb) if kv_user_gb else 0
    print(f"KV 캐시에 쓸 수 있는 메모리: {kv_room_gb:,.0f} GB")
    print(f"결과: 들어감. 최대 컨텍스트를 꽉 채운 사용자 기준 동시 약 {users:,}명")

    # 토큰 하나를 만들 때마다 활성 가중치를 HBM에서 한 번 읽는다고 보는 상한
    active_gb = (a.active_params_b or a.params_b) * w_bytes
    bw_gbps = GPU_HBM_TBPS * 1000 * a.gpus
    print(f"사용자 1명 기준 토큰 생성 속도 상한: 약 {bw_gbps / active_gb:,.0f} 토큰/초 "
          f"(활성 가중치 {active_gb:,.1f} GB ÷ HBM {bw_gbps / 1000:,.0f} TB/s, 이상적인 텐서 병렬 가정)")


if __name__ == "__main__":
    main()
