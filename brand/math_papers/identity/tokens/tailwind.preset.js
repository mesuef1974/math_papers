// preset لـTailwind من هوية math_papers: الأدوار تقرأ متغيرات tokens.css (فاتح وداكن)، والتدرجات قيم ثابتة.
module.exports = {
  "theme": {
    "extend": {
      "colors": {
        "brand": {
          "50": "#FFF1F4",
          "100": "#FFDEE5",
          "200": "#FFC1D0",
          "300": "#EDA2B5",
          "400": "#D58298",
          "500": "#BC637D",
          "600": "#A24562",
          "700": "#842447",
          "800": "#6F1137",
          "900": "#510024",
          "950": "#340015"
        },
        "accent": {
          "50": "#FFF4E1",
          "100": "#FFE4B7",
          "200": "#FFCB6D",
          "300": "#E3AB3C",
          "400": "#C99424",
          "500": "#A97A04",
          "600": "#886100",
          "700": "#6C4C00",
          "800": "#513800",
          "900": "#372500",
          "950": "#221600"
        },
        "neutral": {
          "50": "#F1F5FC",
          "100": "#E3E8F0",
          "200": "#CFD5DD",
          "300": "#B5BBC4",
          "400": "#989FA8",
          "500": "#7D848E",
          "600": "#5F6670",
          "700": "#4C535C",
          "800": "#383E46",
          "900": "#242930",
          "950": "#14191F"
        },
        "success": {
          "50": "#DEFFE8",
          "100": "#C3F6D4",
          "200": "#ABE4BE",
          "300": "#8CCCA2",
          "400": "#6AB184",
          "500": "#489667",
          "600": "#21794A",
          "700": "#026337",
          "800": "#004A28",
          "900": "#003219",
          "950": "#001F0D"
        },
        "warning": {
          "50": "#FFF3E7",
          "100": "#FFE2C7",
          "200": "#FFC893",
          "300": "#EAAC6E",
          "400": "#D08E49",
          "500": "#A86400",
          "600": "#955800",
          "700": "#774500",
          "800": "#593300",
          "900": "#3D2100",
          "950": "#271300"
        },
        "error": {
          "50": "#FFF2EF",
          "100": "#FFE0DA",
          "200": "#FFC4BA",
          "300": "#FF9C8C",
          "400": "#F07362",
          "500": "#D75041",
          "600": "#B42318",
          "700": "#9D0602",
          "800": "#780200",
          "900": "#540100",
          "950": "#360000"
        },
        "info": {
          "50": "#EEF6FF",
          "100": "#D7EAFF",
          "200": "#B4D8FF",
          "300": "#91BFF0",
          "400": "#6FA3D8",
          "500": "#4F87C0",
          "600": "#2F6CA6",
          "700": "#1F5F99",
          "800": "#003F6F",
          "900": "#002A4E",
          "950": "#001932"
        },
        "math_papers": {
          "bg": "var(--math_papers-bg)",
          "surface": "var(--math_papers-surface)",
          "raised": "var(--math_papers-raised)",
          "border": "var(--math_papers-border)",
          "border-strong": "var(--math_papers-border-strong)",
          "text": "var(--math_papers-text)",
          "text-muted": "var(--math_papers-text-muted)",
          "brand": "var(--math_papers-brand)",
          "brand-strong": "var(--math_papers-brand-strong)",
          "brand-soft": "var(--math_papers-brand-soft)",
          "on-brand": "var(--math_papers-on-brand)",
          "accent": "var(--math_papers-accent)",
          "accent-soft": "var(--math_papers-accent-soft)",
          "focus": "var(--math_papers-focus)",
          "success": "var(--math_papers-success)",
          "success-soft": "var(--math_papers-success-soft)",
          "warning": "var(--math_papers-warning)",
          "warning-soft": "var(--math_papers-warning-soft)",
          "error": "var(--math_papers-error)",
          "error-soft": "var(--math_papers-error-soft)",
          "info": "var(--math_papers-info)",
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
