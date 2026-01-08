# 🤖 AI Robot Estimation & Decision System (판단부)

## 📝 Project Overview
이 프로젝트는 자율주행 로봇의 **판단부(Estimation Unit)** 소프트웨어입니다.
**인식부(Vision/Camera)**에서 수집한 시각 데이터를 바탕으로, 로봇이 현재 상황을 분석하고 다음 행동을 결정하는 핵심 로직을 담당합니다.

Google의 최신 **Gemini 3 API**를 활용하여 복잡한 비정형 환경에서도 유연한 판단을 내릴 수 있도록 설계되었습니다.

## 🎯 Key Features
* **Situation Analysis:** 카메라 이미지/센서 데이터를 분석하여 객체 및 장애물 식별
* **Decision Making:** 식별된 정보를 바탕으로 로봇의 제어 명령(이동, 정지, 조작 등) 생성
* **LLM Integration:** Google Gemini 3 Pro/Flash 모델을 활용한 고수준 추론

## 🛠 Tech Stack
* **Language:** Python 3.x
* **Environment:** Ubuntu (Linux)
* **AI Model:** Google Gemini API (Gemini-3-pro / Gemini-3-flash)
* **Version Control:** Git / GitHub

## 📂 Directory Structure
```text
estimation/
├── src/               # 소스 코드 (판단 로직)
├── data/              # 테스트용 데이터 또는 로그
├── .gitignore         # Git 제외 파일 목록
└── README.md          # 프로젝트 설명


## 🚀 How to Run

### 1. Clone Repository

```bash
git clone [https://github.com/KimJinA-7793/estimation.git](https://github.com/KimJinA-7793/estimation.git)
cd estimation

```

### 2. Environment Setup

API 키 보안을 위해 환경 변수 설정이 필요합니다.

```bash
# 프로젝트 루트에 .env 파일 생성 및 API 키 입력
GEMINI_API_KEY=your_api_key_here

```

### 3. Execution

```bash
python main.py  # (실행 파일명에 맞게 변경 필요)

```

## 👨‍💻 Author

* **Name:** JinA Kim
* **Role:** Project Manager & Robot Software Engineer
* **Contact:** (이메일 주소 기재)

---

```

### 💡 수정 팁 (PM의 디테일)
1.  **`main.py` 부분:** 실제 실행시키는 파이썬 파일 이름이 `app.py`나 `run.py`라면 그 이름으로 바꿔주세요.
2.  **이메일:** 맨 아래 `Contact`에 아까 설정한 이메일 주소를 적어두면 더 프로페셔널해 보입니다.
