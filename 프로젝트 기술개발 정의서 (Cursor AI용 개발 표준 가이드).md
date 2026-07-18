프로젝트 기술개발 정의서 (Cursor AI용 개발 표준 가이드)
이 문서는 AI 코딩 에이전트(Cursor)가 프로젝트의 기술 스택, 핵심 개발 원칙, 하이브리드 앱 최적화 요구사항, 그리고 코드 품질 표준을 일관되게 이해하고 준수할 수 있도록 정의한 최상위 헌법(Rules of Engagement)입니다.
프로젝트 최상위 디렉토리에 .cursorrules 또는 cursor.md 파일로 저장하여 AI가 상시 참조하도록 설정하십시오.
 
1. 기술 스택 및 버전 사양 (Tech Stack)
•	Backend: Python 3.11 / Flask (웹 프레임워크)
•	Database: SQLite (SQLAlchemy ORM + Flask-Migrate를 통한 마이그레이션 및 버전 관리 필수)
•	Frontend: HTML5 / CSS3 / JavaScript (Vanilla ES6+), Bootstrap 5 (UI 프레임워크)
•	Containerization: Docker (Multi-stage 빌드 구성 및 Docker Compose 환경 구축)
•	UI/UX: 최신 웹 트렌드를 반영한 반응형 웹 디자인 (모바일 퍼스트, Glassmorphism, 다크모드 대응)
 
2. 핵심 개발 원칙 (Core Principles)
A. SSOT (Single Source of Truth, 단일 진실 공급원) 원칙
•	모든 비즈니스 로직, 데이터 모델, 그리고 시스템 설정은 단 한 곳에서만 정의되고 관리되어야 합니다. (코드 중복 엄격히 금지)
•	프로젝트 전반에서 활용되는 주요 설정값과 API 키는 루트 디렉토리의 .env 파일에 정의합니다.
•	애플리케이션 내의 공통 설정은 config.py 파일(SSOT Config)에 집중 관리하며, 프로젝트 내부에서는 이 구성을 참조하여 상시 작동하도록 구현합니다.
B. 데이터베이스 마이그레이션 자동화
•	요구사항 변경으로 인해 DB 스키마를 수정할 때, SQL 문을 직접 작성하여 수동 변경하지 않습니다.
•	SQLAlchemy 모델(models.py)을 먼저 수정하고, Flask-Migrate(Alembic)를 활용하여 마이그레이션 스크립트를 자동 생성(flask db migrate)한 뒤 반영(flask db upgrade)하는 방식을 철저히 고수합니다.
C. UI/UX Flow와 소스코드의 일치성 보장
•	코드와 실제 화면 흐름에 상이한 점이 없도록, 프론트엔드 HTML/템플릿 페이지를 작성할 때 반드시 각 페이지 상단에 기본 처리 과정(Flow) 및 데이터 송수신 과정을 주석으로 명시해야 합니다.
D. 3-Step Iteration (자가 검토 및 반복 테스트)
•	코드 생성 및 수정 시, 하위 작업 에이전트(Sub-Agents)와 테스트 모듈을 적극적으로 활용합니다.
•	코드가 완벽하게 기능하도록 검토, 수정, 테스트 과정을 최소 3회 이상 반복한 뒤 최종 적용합니다.
 
3. 하이브리드 앱 최적화 및 사용자 경험(UX) 극대화 요건
A. 모바일 & PC 바탕화면 아이콘 설치 (PWA 도입)
웹 브라우저의 보안 정책상 사용자 동의 없는 '강제/자동 아이콘 설치'는 기술적으로 불가능합니다. 따라서 최신 표준인 PWA (Progressive Web App)를 사용하여 브라우저에서 자연스러운 앱 설치를 유도합니다.
•	PWA 매니페스트 구축: manifest.json을 정의하여 앱 이름, 시작 URL, 아이콘, display: "standalone" 옵션 등을 올바르게 지정합니다.
•	서비스 워커 구현: service-worker.js를 등록하여 핵심 애셋을 오프라인 캐싱하고, 설치 이벤트(beforeinstallprompt)를 가로채어 커스텀 설치 안내 UI를 제공합니다.
•	자동 유도 UI/UX: 사용자가 처음 접속하거나 특정 화면에 머무를 때 바탕화면에 단축 아이콘(앱)을 추가할 수 있도록 직관적인 안내 팝업 및 가이드를 노출합니다.
B. 인앱 브라우저(카카오톡, 네이버, 인스타그램 등) 탈출 시스템 (Deep Linking)
인앱 브라우저 내부에서는 PWA 설치 기능이나 특정 하이브리드 기능이 원활하게 지원되지 않거나 차단됩니다. 이를 방지하기 위해 웹 애플리케이션 진입 시 인앱 브라우저 여부를 감지하고 외부 브라우저로 전환시켜야 합니다.
•	User-Agent 감지: 접속 기기의 User-Agent 분석을 통해 카카오톡(KAKAOTALK), 네이버(NAVER), 인스타그램(Instagram) 등 외부 인앱 앱 내 브라우저인지 판별합니다.
•	외부 브라우저 강제 전환 스크립트 적용:
o	Android: intent:// 스키마 링크를 통해 Chrome 등 시스템 브라우저를 강제로 호출하도록 유도합니다.
o	iOS (Safari): 모바일 Safari 브라우저로 열 수 있도록 탈출 안내 화면과 함께 복사 링크 및 외부 실행 경로(iOS 딥링크/인텐트 스키마 패턴)를 동적으로 제공합니다.
•	웹 앱 로그인 및 설치 동작 프로세스가 정상 브라우저 환경에서 유연하게 이어질 수 있도록 사용자 친화적 UI를 마련합니다.
 
4. 권장 디렉토리 구조 (Standard Directory Structure)
project-root/
│
├── .cursorrules          # 본 기술개발정의서 파일 (Cursor 상시 인지용)
├── .env                  # 환경 변수 정의 파일 (SSOT)
├── config.py             # 전역 설정 파일 (SSOT Config)
├── app.py                # Flask 애플리케이션 진입 포인트
├── Dockerfile            # 도커 빌드 구성 파일
├── docker-compose.yml    # 서비스 오케스트레이션 정의 파일
│
├── apps/                 # 모듈식 비즈니스 로직 폴더 (Blueprint 구조)
│   ├── __init__.py       # 앱 초기화 및 확장 모듈 등록
│   ├── models.py         # 데이터베이스 모델 정의 (SQLAlchemy)
│   └── routes.py         # 컨트롤러 및 라우트 핸들러
│
├── migrations/           # Flask-Migrate 자동 생성 스키마 마이그레이션 파일들
│
├── static/               # 정적 파일 보관 디렉토리
│   ├── js/
│   │   ├── app.js        # 일반 스크립트 및 인앱 브라우저 감지 로직
│   │   └── sw-register.js# 서비스 워커 등록 스크립트
│   ├── css/
│   │   └── style.css     # Glassmorphism, 반응형 전용 스타일시트
│   ├── manifest.json     # PWA 구성 메타데이터
│   └── service-worker.js # 백그라운드 작업 및 오프라인 제어
│
└── templates/            # HTML 템플릿
    ├── base.html         # 공통 레이아웃 (PWA 등록 및 인앱 탈출 스크립트 내장)
    ├── login.html        # 예: 로그인 페이지 (상단 주석에 UI Flow 기재 필수)
    └── index.html        # 메인 페이지 (상단 주석에 UI Flow 기재 필수)


 
5. 에이전트(Cursor) 가동 시 준수 프로세스 및 명령어 (Prompts for Agent)
🚨 [AI Agent Directive - MANDATORY]
코드를 생성, 수정 또는 확장할 때는 항상 이 .cursorrules의 명세를 최우선 순위로 간주하고 아래의 체크리스트를 실행하십시오.
1.	SSOT 검증: 수정하려는 로직이 시스템의 다른 부분에 중복으로 존재하지 않는지 확인하십시오. 설정이 추가될 경우 개별 파일이 아닌 config.py나 .env에 먼저 추가해야 합니다.
2.	DB 변경 감지: 모델 파일(models.py)에 변경 사항이 생기면 즉시 수동 SQL 변경을 멈추고 flask db migrate 명령어를 사용하여 스키마 이전 내역을 작성하도록 유도하십시오.
3.	프론트엔드 표준 주석: 새로 생성하거나 수정하는 모든 HTML 템플릿 파일 맨 위에 <!-- [UI Flow: 처리 과정 설명 및 데이터 흐름] --> 주석이 누락되지 않도록 강제하십시오.
4.	하이브리드 대응 점검: 모바일 환경에서의 가독성(반응형 CSS, Bootstrap 5 클래스 활용), PWA 호환성, 그리고 인앱 브라우저 차단 우회 스크립트가 온전히 작동하는지 최종 작성 코드에서 한 단계 더 검토하십시오.
5.	자가 루프 검토: 코드를 사용자에게 최종 제안하기 전, 스스로 로직 흐름을 시뮬레이션하고 발생 가능한 예외 상황을 고려하여 최소 3회 이상 검토 및 자가 수정 루프를 거쳤는지 확인하십시오.

로그인