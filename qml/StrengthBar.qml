// qml/StrengthBar.qml
// ───────────────────
// Visual password strength indicator.
// FIX: Removed Layout.preferredWidth binding on tips Text that caused
//      "QML RowLayout: Detected recursive rearrange" at runtime.
//      Now uses elide + Layout.fillWidth on the tips label instead.

import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    spacing: 6

    property int    score:  0
    property string level:  ""
    property color  colour: "transparent"
    property var    tips:   []

    function setStrength(s, l, c, t) {
        root.score  = s
        root.level  = l
        root.colour = c
        root.tips   = t || []
    }

    function clear() {
        root.score  = 0
        root.level  = ""
        root.colour = "transparent"
        root.tips   = []
    }

    // ── Segment bar ───────────────────────────
    RowLayout {
        Layout.fillWidth: true
        spacing: 4

        Repeater {
            model: 5
            Rectangle {
                Layout.fillWidth: true
                height: 4
                radius: 2
                color: {
                    if (root.score === 0) return Theme.bgSurface3
                    var segs = 1
                    if (root.score >= 25) segs = 2
                    if (root.score >= 50) segs = 3
                    if (root.score >= 75) segs = 4
                    if (root.score >= 90) segs = 5
                    return index < segs ? root.colour : Theme.bgSurface3
                }
                Behavior on color { ColorAnimation { duration: Theme.animNormal; easing.type: Easing.OutCubic } }
            }
        }
    }

    // ── Level label + first tip ───────────────
    // Uses a single RowLayout with fixed-size level label and fillWidth tip.
    // No width binding on either child — avoids the circular rearrange.
    RowLayout {
        Layout.fillWidth: true
        visible: root.level !== ""
        spacing: 8

        Text {
            text:  root.level
            color: root.colour
            font.family:      Theme.fontFamily
            font.pointSize:   Theme.fontSizeXS
            font.weight:      Font.DemiBold
            font.letterSpacing: 0.5
            font.capitalization: Font.AllUppercase
        }

        Item { Layout.fillWidth: true }

        Text {
            visible:        root.tips && root.tips.length > 0
            text:           (root.tips && root.tips.length > 0) ? root.tips[0] : ""
            color:          Theme.textMuted
            font.family:    Theme.fontFamily
            font.pointSize: Theme.fontSizeXS
            elide:          Text.ElideRight
            Layout.maximumWidth: 200
        }
    }
}
