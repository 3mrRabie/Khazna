// qml/components/SvButton.qml
// ─────────────────────────────
// Styled push button that follows the khazna dark palette.

import QtQuick
import QtQuick.Controls.Basic
import ".."    // Theme singleton

Button {
    id: root

    property string variant:   "default"   // "primary" | "danger" | "default"
    property string iconLabel: ""
    // Do NOT bind text at the Button level – callers set it externally.
    // iconLabel is composed in contentItem.text to avoid a circular binding.

    implicitHeight: 40
    implicitWidth:  Math.max(contentItem.implicitWidth + 36, 110)

    Accessible.role: Accessible.Button
    Accessible.name: root.text
    Accessible.onPressAction: root.clicked()

    // ── Background ────────────────────────────
    background: Rectangle {
        radius: Theme.radiusMD
        color: {
            if (!root.enabled)        return Theme.bgSurface3
            if (root.pressed)         return pressedColor()
            if (root.hovered)         return hoveredColor()
            return baseColor()
        }
        border.color: {
            if (!root.enabled)  return Theme.bgBorder
            if (root.hovered)   return root.variant === "danger" ? Theme.danger : Theme.cyan
            return borderColor()
        }
        border.width: 1
        Behavior on color        { ColorAnimation { duration: Theme.animFast } }
        Behavior on border.color { ColorAnimation { duration: Theme.animFast } }
        
        // Subtle scale on press
        scale: root.pressed ? 0.98 : 1.0
        Behavior on scale { NumberAnimation { duration: Theme.animFast } }
    }

    // ── Label ─────────────────────────────────
    contentItem: Text {
        text:  (root.iconLabel ? root.iconLabel + "  " : "") + root.text
        font.family:    Theme.fontFamily
        font.pointSize: Theme.fontSizeSM
        font.weight:    root.variant === "primary" ? Font.DemiBold : Font.Medium
        color: {
            if (!root.enabled)            return Theme.textMuted
            if (root.variant === "primary") return Theme.textInverse
            if (root.variant === "danger")  return root.hovered ? Theme.bgBase : Theme.danger
            return Theme.textPrimary
        }
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment:   Text.AlignVCenter
        Behavior on color { ColorAnimation { duration: Theme.animFast } }
    }

    // ── Focus ring ────────────────────────────
    Rectangle {
        anchors.fill:   parent
        anchors.margins: -3
        radius:          Theme.radiusMD + 3
        color:           "transparent"
        border.color:    root.visualFocus ? Theme.cyan : "transparent"
        border.width:    2
    }

    // ── Colour helpers ────────────────────────
    function baseColor() {
        if (variant === "primary") return Theme.accent
        if (variant === "danger")  return "transparent"
        return Theme.bgSurface2
    }
    function hoveredColor() {
        if (variant === "primary") return Theme.accentHover
        if (variant === "danger")  return Theme.danger
        return Theme.bgSurface3
    }
    function pressedColor() {
        if (variant === "primary") return Theme.accentPress
        if (variant === "danger")  return Qt.darker(Theme.danger, 1.2)
        return Theme.bgSurface
    }
    function borderColor() {
        if (variant === "primary") return Theme.accent
        if (variant === "danger")  return Theme.dangerBorder
        return Theme.bgBorder
    }
}
