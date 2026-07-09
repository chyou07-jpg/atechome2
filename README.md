# atec 기업 홈페이지

HTML, CSS, JavaScript만으로 구성된 정적 기업 홈페이지입니다.

## 파일 구조

```
├── index.html      # 메인 페이지
├── css/style.css   # 스타일
├── js/main.js      # 인터랙션 (메뉴, 스크롤 애니메이션, 폼)
└── public/         # 로고, 파비콘 등 정적 파일
    ├── favicon.svg
    └── logo.png    # 로고 (직접 추가)
```

## 실행 방법

**Node.js 없이** 바로 열 수 있습니다.

1. `index.html`을 브라우저에서 더블클릭하거나
2. VS Code / Cursor의 **Live Server** 확장으로 실행

로고는 `src/assets/` 폴더에 넣으면 헤더·푸터에 자동 표시됩니다.

## 페이지 구성

| 섹션 | 설명 |
|------|------|
| Hero | 메인 비주얼 및 CTA |
| Clients | 파트너 기업 |
| About | 회사 소개 |
| Services | 6가지 서비스 |
| Stats | 숫자 카운트업 애니메이션 |
| Testimonials | 고객 후기 |
| Contact | 문의 폼 |
| Footer | 연락처 및 링크 |

## 커스터마이징

- `index.html` — 텍스트, 섹션 구조
- `css/style.css` — `:root` 변수로 브랜드 색상 변경
- `public/logo.png` — 로고 이미지
