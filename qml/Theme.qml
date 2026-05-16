// qml/Theme.qml
// ─────────────
// Global design-token singleton — premium cybersecurity dark theme.
// Inspired by Linear, Arc Browser, Proton Pass, and modern SOC dashboards.
//
// UPDATED: Added sidebar-specific tokens and refined nav active-state colours.

pragma Singleton
import QtQuick

QtObject {
    // ── Backgrounds ──────────────────────────
    readonly property color bgBase:     "#0f1117"
    readonly property color bgSurface:  "#161b26"
    readonly property color bgSurface2: "#1c2333"
    readonly property color bgSurface3: "#232b3e"
    readonly property color bgBorder:   "#2a3348"
    readonly property color bgOverlay:  "#000000bb"
    readonly property color bgGlass:    "#161b26cc"

    // ── Accent ───────────────────────────────
    readonly property color accent:      "#7c5bf5"
    readonly property color accentHover: "#9078f7"
    readonly property color accentPress: "#6346d9"
    readonly property color accentMuted: "#7c5bf526"
    readonly property color accentGlow:  "#7c5bf540"

    // ── Secondary accent (cyber-blue) ────────
    readonly property color accent2:    "#6366f1"
    readonly property color cyan:       "#5BC0FF"
    readonly property color cyanHover:  "#79CCFF"
    readonly property color cyanPress:  "#379FE0"
    readonly property color cyanBg:     "#5BC0FF1A"   // ~10 % opacity
    readonly property color cyanBorder: "#5BC0FF59"   // ~35 % opacity
    readonly property color cyanGlow:   "#5BC0FF38"   // ~22 % opacity

    // ── Text ─────────────────────────────────
    readonly property color textPrimary:   "#e2e8f0"
    readonly property color textSecondary: "#94a3b8"
    readonly property color textMuted:     "#475569"
    readonly property color textInverse:   "#0f1117"

    // ── Semantic colours ─────────────────────
    readonly property color success:       "#5BC0FF"
    readonly property color successHover:  "#79CCFF"
    readonly property color successPress:  "#379FE0"
    readonly property color successBg:     "#5BC0FF1A"
    readonly property color successBorder: "#5BC0FF59"

    readonly property color danger:       "#f87171"
    readonly property color dangerBg:     "#f8717115"
    readonly property color dangerBorder: "#f8717130"
    readonly property color warning:      "#fbbf24"
    readonly property color warningBg:    "#fbbf2415"
    readonly property color warningBorder:"#fbbf2430"

    // ── Strength scale ────────────────────────
    readonly property color strengthVeryWeak:   "#ef4444"
    readonly property color strengthWeak:       "#f97316"
    readonly property color strengthMedium:     "#eab308"
    readonly property color strengthStrong:     "#379FE0"
    readonly property color strengthVeryStrong: "#5BC0FF"

    // ════════════════════════════════════════
    // Sidebar-specific design tokens
    // ════════════════════════════════════════

    // Panel surface — one step darker than bgSurface so the sidebar
    // recedes slightly behind the main content area.
    readonly property color sidebarBg: "#12161f"

    // Section label colour — dimmer than textMuted for subtlety
    readonly property color sidebarSectionLabel: "#364152"

    // Navigation item states
    // Active — soft cyan tint, no harsh highlight
    readonly property color navActiveBg:    "#5BC0FF14"   // ~8 % cyan
    readonly property color navActiveText:  "#7dd3fc"     // sky-300, softer than full cyan
    readonly property color navGlow:        "#5BC0FF28"   // outer ring glow on active item
    // Hover — barely-there lift
    readonly property color navHoverBg:     "#1c2333"     // == bgSurface2
    // Default resting text
    readonly property color navText:        "#7b8fa8"     // between textMuted and textSecondary

    // ── Typography ───────────────────────────
    readonly property string fontFamily: "Segoe UI, Inter, SF Pro Display, -apple-system, sans-serif"
    readonly property int    fontSizeXS: 10
    readonly property int    fontSizeSM: 11
    readonly property int    fontSizeMD: 13
    readonly property int    fontSizeLG: 15
    readonly property int    fontSizeXL: 18
    readonly property int    fontSizeH2: 22
    readonly property int    fontSizeH1: 28

    // ── Radius / spacing ─────────────────────
    readonly property int radiusXS: 4
    readonly property int radiusSM: 6
    readonly property int radiusMD: 8
    readonly property int radiusLG: 12
    readonly property int radiusXL: 16

    readonly property int spacingXS:  4
    readonly property int spacingSM:  8
    readonly property int spacingMD:  16
    readonly property int spacingLG:  24
    readonly property int spacingXL:  32
    readonly property int spacingXXL: 40

    // ── Sidebar ───────────────────────────────
    readonly property int sidebarWidth: 240

    // ── Animation ────────────────────────────
    readonly property int animFast:   100
    readonly property int animNormal: 200
    readonly property int animSlow:   350
}
