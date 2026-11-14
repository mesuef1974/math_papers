// preset لـTailwind من هوية math_papers: الأدوار تقرأ متغيرات tokens.css (فاتح وداكن)، والتدرجات قيم ثابتة.
module.exports = {
  "theme": {
    "extend": {
      "colors": {
        "brand": {
          "50": "#FFF1F1",
          "100": "#FFDFDF",
          "200": "#FFC2C3",
          "300": "#F4A1A3",
          "400": "#DC8084",
          "500": "#C36167",
          "600": "#A8424B",
          "700": "#8E2433",
          "800": "#740A21",
          "900": "#530013",
          "950": "#360009"
        },
        "accent": {
          "50": "#FFF3E6",
          "100": "#FFE2C5",
          "200": "#FFC98E",
          "300": "#F0AA58",
          "400": "#DB943C",
          "500": "#B3731B",
          "600": "#935A00",
          "700": "#754700",
          "800": "#583400",
          "900": "#3C2200",
          "950": "#261400"
        },
        "neutral": {
          "50": "#FBF4EE",
          "100": "#EEE6E0",
          "200": "#DBD3CB",
          "300": "#C2B9B1",
          "400": "#A69C94",
          "500": "#8B8178",
          "600": "#6F655C",
          "700": "#5A5148",
          "800": "#443B34",
          "900": "#2F2721",
          "950": "#1D1711"
        },
        "success": {
          "50": "#E3FEE0",
          "100": "#D5F2D1",
          "200": "#BFDFBA",
          "300": "#A2C69E",
          "400": "#83AB7E",
          "500": "#669061",
          "600": "#3F6B3A",
          "700": "#345F2F",
          "800": "#20481C",
          "900": "#0D3209",
          "950": "#012000"
        },
        "warning": {
          "50": "#FFF3E7",
          "100": "#FFE2C6",
          "200": "#F5CCA3",
          "300": "#DEB183",
          "400": "#C59360",
          "500": "#AB773E",
          "600": "#8A5510",
          "700": "#764600",
          "800": "#593300",
          "900": "#3D2200",
          "950": "#261300"
        },
        "error": {
          "50": "#FFF2EF",
          "100": "#FFE0D9",
          "200": "#FFC4B8",
          "300": "#FF9C89",
          "400": "#EC7761",
          "500": "#D25640",
          "600": "#B5341F",
          "700": "#981B04",
          "800": "#740F00",
          "900": "#510700",
          "950": "#340300"
        },
        "info": {
          "50": "#ECF7FF",
          "100": "#D2ECFF",
          "200": "#BAD9F0",
          "300": "#9CC0DA",
          "400": "#7CA4C0",
          "500": "#5E89A7",
          "600": "#416E8D",
          "700": "#2F5E7D",
          "800": "#14415D",
          "900": "#002C45",
          "950": "#001B2C"
        },
        "math_papers": {
          "bg": "var(--math_papers-bg)",
          "surface": "var(--math_papers-surface)",
          "raised": "var(--math_papers-raised)",
          "border": "var(--math_papers-border)",
          "text": "var(--math_papers-text)",
          "text-muted": "var(--math_papers-text-muted)",
          "brand": "var(--math_papers-brand)",
          "brand-strong": "var(--math_papers-brand-strong)",
          "on-brand": "var(--math_papers-on-brand)",
          "accent": "var(--math_papers-accent)",
          "border-strong": "var(--math_papers-border-strong)",
          "focus": "var(--math_papers-focus)",
          "brand-soft": "var(--math_papers-brand-soft)",
          "accent-text": "var(--math_papers-accent-text)",
          "accent-soft": "var(--math_papers-accent-soft)",
          "success": "var(--math_papers-success)",
          "warning": "var(--math_papers-warning)",
          "error": "var(--math_papers-error)",
          "info": "var(--math_papers-info)",
          "success-soft": "var(--math_papers-success-soft)",
          "warning-soft": "var(--math_papers-warning-soft)",
          "error-soft": "var(--math_papers-error-soft)",
          "info-soft": "var(--math_papers-info-soft)"
        }
      },
      "fontFamily": {
        "heading": [
          "Cairo",
          "Tahoma",
          "sans-serif"
        ],
        "body": [
          "Cairo",
          "Tahoma",
          "sans-serif"
        ]
      },
      "fontSize": {
        "caption": [
          "0.75rem",
          {
            "lineHeight": "1.7"
          }
        ],
        "small": [
          "0.8rem",
          {
            "lineHeight": "1.7"
          }
        ],
        "body": [
          "1.0rem",
          {
            "lineHeight": "1.7"
          }
        ],
        "lead": [
          "1.25rem",
          {
            "lineHeight": "1.7"
          }
        ],
        "h4": [
          "1.5625rem",
          {
            "lineHeight": "1.3"
          }
        ],
        "h3": [
          "1.95rem",
          {
            "lineHeight": "1.3"
          }
        ],
        "h2": [
          "2.4438rem",
          {
            "lineHeight": "1.3"
          }
        ],
        "h1": [
          "3.05rem",
          {
            "lineHeight": "1.3"
          }
        ],
        "display": [
          "3.8125rem",
          {
            "lineHeight": "1.3"
          }
        ]
      }
    }
  }
};
