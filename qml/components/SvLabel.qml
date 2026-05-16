// qml/components/SvLabel.qml
// ──────────────────────────
// Styled text label with semantic variants used throughout the UI.
//
// Properties
// ──────────
//   text     – label text
//   variant  – "heading" | "subheading" | "section" | "body" | "muted"
//   wrap     – whether to word-wrap (default false)

import QtQuick
import ".."   // Theme

Text {
    id: root

    property string variant: "body"
    property bool   wrap:    false

    wrapMode: root.wrap ? Text.Wrap : Text.NoWrap
    font.family: Theme.fontFamily

    color: {
        switch (root.variant) {
            case "heading":    return Theme.textPrimary
            case "subheading": return Theme.textSecondary
            case "section":    return Theme.textMuted
            case "muted":      return Theme.textMuted
            default:           return Theme.textPrimary
        }
    }

    font.pointSize: {
        switch (root.variant) {
            case "heading":    return Theme.fontSizeXL
            case "subheading": return Theme.fontSizeMD
            case "section":    return Theme.fontSizeXS
            case "muted":      return Theme.fontSizeSM
            default:           return Theme.fontSizeMD
        }
    }

    font.weight: {
        switch (root.variant) {
            case "heading":  return Font.Bold
            case "section":  return Font.DemiBold
            default:         return Font.Normal
        }
    }

    font.letterSpacing: root.variant === "section" ? 1.1 : 0

    Accessible.role: Accessible.StaticText
    Accessible.name: root.text
}
