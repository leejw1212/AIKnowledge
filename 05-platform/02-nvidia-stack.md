# NVIDIA 소프트웨어 스택

> 상위 가지: [05. OS·드라이버·클러스터 운영](./README.md)
> 이전: [Linux 기초](./01-linux-basics.md) · 다음: [컨테이너](./03-containers.md)

**키워드:** GPU 드라이버, CUDA, NCCL, Fabric Manager, nvidia-smi

## 왜 필요해졌나

_이 주제가 아래 층의 어떤 한계나 문제 때문에 생겨났는지 공부하면서 적어 보세요._

## 공부할 질문

- [ ] 드라이버, CUDA, NCCL은 각각 어떤 층에 있고 버전 호환은 어떻게 맞추는가?
- [ ] NVSwitch가 있는 서버에서 Fabric Manager는 왜 필요한가?
- [ ] nvidia-smi로 무엇을 확인할 수 있는가?

## 한 줄 요약


## 핵심 개념


## B300 서버와의 연결

GPU 드라이버, CUDA, NCCL 외에 NVLink 스위치를 관리하는 Fabric Manager 계열 소프트웨어가 필요합니다. DGX는 NVIDIA가 검증한 DGX OS(Ubuntu 기반)로 이 구성을 한 번에 제공하고, OEM 서버는 직접 버전을 맞춰 설치해야 합니다.

_근거: [B300 사양 정리](../B300.md)_

## 참고 자료


## 메모

