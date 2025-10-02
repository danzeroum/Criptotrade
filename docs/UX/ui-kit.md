# 🎨 BuildToValue v6 UI Kit

## Design System Base
```css
:root {
  /* Cores (WCAG AA compliant) */
  --primary: #0D6EFD;
  --secondary: #6C757D;
  --success: #16A34A;
  --warning: #D97706;
  --danger: #DC2626;
  --info: #0891B2;

  /* Typography */
  --font-family: 'Inter', system-ui, sans-serif;
  --font-size-base: 16px;
  --line-height: 1.5;

  /* Spacing (8px grid) */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;

  /* Breakpoints */
  --mobile: 640px;
  --tablet: 768px;
  --desktop: 1024px;
  --wide: 1280px;
}
```

## Componentes Essenciais
| Componente | Variantes | Estados |
|------------|-----------|---------|
| Button | primary, secondary, danger | default, hover, active, disabled |
| Input | text, email, password, number | default, focus, error, disabled |
| Card | default, elevated | - |
| Modal | info, confirm, form | open, closed |
| Toast | success, error, warning, info | visible, hidden |
| Table | default, striped | sortable, paginated |

## Checklist de Acessibilidade
- Contraste mínimo 4.5:1 (texto normal)
- Contraste mínimo 3:1 (texto grande)
- Foco visível em todos os elementos interativos
- Labels associados a todos os inputs
- Hierarquia semântica de headings (h1→h6)
- Alt text em todas as imagens
- ARIA labels onde necessário
- Navegação por teclado completa
- Skip links para conteúdo principal
- Mensagens de erro claras e associadas
